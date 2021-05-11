import json
import discord
import time
import sys
import os
import asyncio
import secrets
import requests
import traceback
from re import match
from math import ceil

try:
    assert os.path.exists('config.json')

    with open('config.json', 'r') as cfg:
        config = json.load(cfg)

    potemkin_webhook = config['potemkin_webhook']
    bot_discord_token = config['bot_discord_token']
    puppetry_channel_id = int(config['puppetry_channel_id'])
    default_avatar = config['default_avatar']
    administrator_uid = config['administrator_uid']                 # who to PM when things start to break
    chat_interval_multiplier = config['chat_interval_multiplier']   # lower speeds up chat interval, higher slows it down
    convo_interval_minutes = config['convo_interval_minutes']       # range in minutes to wait to start a new conversation

except:
    print("[!] couldn't load config.json! exiting")
    sys.exit(1)

with open('usercache.json', 'r', encoding="utf-8") as f:
    user_cache = json.load(f)

def get_chat_author(chatline: str):
    name = match("^[^:]{3,}: ", chatline)[0]
    return name[:-2]


def get_uid(author: str):
    if author in user_cache:
        return user_cache[author]['uid']
    else:
        return None


def strip_chat_author(chatline: str):
    author = get_chat_author(chatline)
    message = chatline[len(author)+2:]
    return message


def prep_chat(chat: str):
    # plain chat string into useful dict
    author = get_chat_author(chat)
    message = strip_chat_author(chat)
    uid = get_uid(author)
    return {'author': author, 'uid': uid, 'message': message}


def check_convo_reserve():
    # how many convo files exist
    return len(os.listdir('./convos/'))


def get_convo():
    all_convos = os.listdir('./convos/')
    if check_convo_reserve() == 0:
        return False
    next_file = './convos/' + all_convos[0]
    print(f"[-] getting new convo {next_file}")
    with open(next_file, 'r', encoding='utf-8') as f:
        next_convo = f.read().splitlines()
    os.remove(next_file)
    print(f"[-] deleted {next_file}")
    return next_convo


async def chat_interval_sleep(msg_length: int, convo_pool_size: int):
    # sleep for a few seconds depending on message length
    seconds = ceil(max(1, msg_length / 3))
    seconds += secrets.choice([0, 0, 0, 0, 0, 2, 3, 5, 7, 11])
    seconds *= chat_interval_multiplier
    print(f"[-] chat sleep for {seconds} seconds before {msg_length} chars. {convo_pool_size} lines left in pool")
    await asyncio.sleep(seconds)


async def convo_interval_sleep():
    # sleep for a few minutes
    minutes = secrets.randbelow(convo_interval_minutes[1]) + convo_interval_minutes[0]
    print(f"[-] convo sleep for {minutes} minutes")
    await asyncio.sleep(minutes * 60)


async def check_user_exists(uid: int, discord_client):
    if not uid:
        return False
    userdata = await discord_client.fetch_user(uid)
    if userdata:
        return True
    return False


async def lookup_avatar(uid: int, discord_client):
    userdata = await discord_client.fetch_user(uid)
    return userdata.avatar_url


async def lookup_nickname(uid: int, discord_client):
    userdata = await discord_client.fetch_user(uid)
    if int(uid) in discord_client.server_nicks:
        if discord_client.server_nicks[int(uid)]:
            return discord_client.server_nicks[int(uid)]
    return userdata.display_name


def send_chat(msg, username, avatar_url):
    data = {"content" : msg,
            "username" : username,
            "avatar_url": f'{avatar_url}'}
    response = requests.post(potemkin_webhook, json = data)
    try:
        response.raise_for_status()
    except requests.exceptions.HTTPError as err:
        print(err)


async def message_admin(discord_client, msg: str):
    admin_user = await discord_client.fetch_user(administrator_uid)
    await admin_user.send(msg)


def main():
    user_style_cache = {}
    intents = discord.Intents.default()
    intents.members = True
    client = discord.Client(intents=intents)
    convo_pool = []
    max_author_repeat = 6
    client.server_nicks = {}

    @client.event
    async def on_ready():
        prev_author = None
        author_repeat_count = 0
        print(f'[+] {client.user.name} has connected to the discord API')
        for guild in client.guilds:
            print(f'[+] joined {guild.name} [{guild.id}]')

        member_list = client.guilds[0].members      # this might need neatening up someday
        for member in member_list:
            client.server_nicks[member.id] = member.nick

        while True:
            if len(convo_pool) == 0:
                print(f"[-] convo pool empty, refreshing")
                new_convo = get_convo()
                author_repeat_count = 0
                convo_reserve = check_convo_reserve()
                print(f"[-] {convo_reserve} convos remaining")
                if convo_reserve < 1024 and convo_reserve % 50 == 0:
                    await message_admin(client, f"Warning: only {convo_reserve} convos remaining")
                if not new_convo:
                    await message_admin(client, "YOU HAVE RUN OUT OF CONVO MATERIAL!")
                    print('[!] no convos remaining on disk! exiting')
                    sys.exit(1)
                convo_pool.extend(new_convo)

            next_msg = prep_chat(convo_pool.pop(0))
            message = next_msg['message']
            uid = next_msg['uid']
            if uid == prev_author:
                author_repeat_count += 1
            else:
                author_repeat_count = 0
            if not uid:
                username = next_msg['author']
                avatar = default_avatar
            if uid in user_style_cache:
                username = user_style_cache[uid]['nickname']
                avatar = user_style_cache[uid]['avatar_url']
            else:
                user_check = await check_user_exists(uid, client)
                if user_check:
                    fetch_nick = await lookup_nickname(uid, client)
                    fetch_avatar = await lookup_avatar(uid, client)
                    if fetch_nick and fetch_avatar:
                        user_style_cache[uid] = {}
                        user_style_cache[uid]['nickname'] = fetch_nick
                        user_style_cache[uid]['avatar_url'] = fetch_avatar
                        username = fetch_nick
                        avatar = fetch_avatar
                else:
                    username = next_msg['author']
                    avatar = default_avatar
            try:
                if author_repeat_count >= max_author_repeat:
                    print(f"[!] skipping rampage:", username + ':', message)
                else:
                    await chat_interval_sleep(len(message), len(convo_pool))
                    prev_author = uid
                    send_chat(message, username, avatar)
                    if len(convo_pool) == 0:
                        await convo_interval_sleep()
            except Exception as e:
                print(f'[!] failed to send chat:')
                print(next_msg)
                print(e, ''.join(traceback.format_tb(e.__traceback__)))
        
    @client.event
    async def on_message(message):
        if message.channel.id == puppetry_channel_id:    
            try:
                uid = message.author.id
                username = await lookup_nickname(uid, client)
                avatar = await lookup_avatar(uid, client)
                send_chat(message.content, username, avatar)
            except:
                print("[!] failed to puppet '" + message.author + ': ' + message.content + "'")

    client.run(bot_discord_token)


if __name__ == '__main__':
    main()