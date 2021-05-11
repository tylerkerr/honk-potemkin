import json
import discord
import time
import sys
import os
import secrets
from re import match
from math import ceil
from aiohttp import ClientSession

try:
    assert os.path.exists('config.json')

    with open('config.json', 'r') as cfg:
        config = json.load(cfg)

    potemkin_webhook = config['potemkin_webhook']
    bot_discord_token = config['bot_discord_token']
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


def chat_interval_sleep(msg_length: int, convo_pool_size: int):
    # sleep for a few seconds depending on message length
    seconds = ceil(max(1, msg_length / 3) * chat_interval_multiplier)
    seconds += secrets.choice([0, 0, 0, 0, 0, 2, 3, 5, 7, 11])
    print(f"[-] chat sleep for {seconds} seconds before {msg_length} chars. {convo_pool_size} lines left in pool")
    time.sleep(seconds)


def convo_interval_sleep():
    # sleep for a few minutes
    minutes = secrets.randbelow(convo_interval_minutes[1]) + convo_interval_minutes[0]
    print(f"[-] convo sleep for {minutes} minutes")
    # time.sleep(minutes * 60)
    # ^^^ SWITCH TO MINUTES FOR PRODUCTION ^^^
    time.sleep(minutes)


async def check_user_exists(uid: int, discord_client):
    userdata = await discord_client.fetch_user(uid)
    if userdata:
        return True
    return False


async def lookup_avatar(uid: int, discord_client):
    userdata = await discord_client.fetch_user(uid)
    return userdata.avatar_url


async def lookup_nickname(uid: int, discord_client, server_nicks: dict):
    userdata = await discord_client.fetch_user(uid)
    if int(uid) in server_nicks:
        if server_nicks[int(uid)]:
            return server_nicks[int(uid)]
    return userdata.display_name


async def send_chat(msg, username, avatar_url):
    async with ClientSession() as session:
        webhook = discord.Webhook.from_url(potemkin_webhook, adapter=discord.AsyncWebhookAdapter(session))
        await webhook.send(content=msg, username=username, avatar_url=avatar_url)


async def message_admin(discord_client, msg: str):
    admin_user = await discord_client.fetch_user(administrator_uid)
    await admin_user.send(msg)


def main():
    user_style_cache = {}
    intents = discord.Intents.default()
    intents.members = True
    client = discord.Client(intents=intents)
    convo_pool = []

    @client.event
    async def on_ready():
        first_run = True
        print(f'[+] {client.user.name} has connected to the discord API')
        for guild in client.guilds:
            print(f'[+] joined {guild.name} [{guild.id}]')

        member_list = client.guilds[0].members      # this might need neatening up someday
        server_nicks = {}
        for member in member_list:
            server_nicks[member.id] = member.nick

        while True:
            if len(convo_pool) == 0:
                print(f"[-] convo pool empty, refreshing")
                new_convo = get_convo()
                convo_reserve = check_convo_reserve()
                print(f"[-] {convo_reserve} convos remaining")
                if convo_reserve < 1024 and convo_reserve % 50 == 0:
                    await message_admin(client, f"Warning: only {convo_reserve} convos remaining")
                if not new_convo:
                    await message_admin(client, "YOU HAVE RUN OUT OF CONVO MATERIAL!")
                    print('[!] no convos remaining on disk! exiting')
                    sys.exit(1)
                convo_pool.extend(new_convo)
                if not first_run:
                    convo_interval_sleep()
                else:
                    first_run = False

            next_msg = prep_chat(convo_pool.pop(0))
            message = next_msg['message']
            uid = next_msg['uid']
            if uid in user_style_cache:
                username = user_style_cache[uid]['nickname']
                avatar = user_style_cache[uid]['avatar_url']
            else:
                user_check = await check_user_exists(uid, client)
                if user_check:
                    user_style_cache[uid] = {}
                    fetch_nick = await lookup_nickname(uid, client, server_nicks)
                    fetch_avatar = await lookup_avatar(uid, client)
                    if fetch_nick and fetch_avatar:
                        user_style_cache[uid]['nickname'] = fetch_nick
                        user_style_cache[uid]['avatar_url'] = fetch_avatar
                        username = fetch_nick
                        avatar = fetch_avatar
                else:
                    username = next_msg['author']
                    avatar = default_avatar
            try:
                chat_interval_sleep(len(message), len(convo_pool))
                await send_chat(message, username, avatar)
            except:
                print(f'[!] failed to send chat:')
                print(next_msg)
        
    client.run(bot_discord_token)

        

if __name__ == '__main__':
    main()