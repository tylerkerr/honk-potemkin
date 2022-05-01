import json
import discord
import time
import sys
import os
import asyncio
import secrets
import requests
import traceback
import re
from math import ceil

try:
    assert os.path.exists('config.json')

    with open('config.json', 'r') as cfg:
        config = json.load(cfg)

    potemkin_webhook = config['potemkin_webhook']
    bot_discord_token = config['bot_discord_token']
    potemkin_channel_id = int(config['potemkin_channel_id'])
    default_avatar = config['default_avatar']
    administrator_uid = config['administrator_uid']                 # who to PM when things start to break
    chat_interval_multiplier = config['chat_interval_multiplier']   # lower speeds up chat interval, higher slows it down
    convo_interval_minutes = config['convo_interval_minutes']       # range in minutes to wait to start a new conversation
    censored_strings = config['censored_strings']
    do_not_mention = config['do_not_mention'].values()

except:
    print("[!] couldn't load config.json! exiting")
    sys.exit(1)

with open('usercache.json', 'r', encoding="utf-8") as f:
    user_cache = json.load(f)


def get_chat_author(chatline: str):
    name = re.match("^[^:]{3,}: ", chatline)[0]
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
    seconds = ceil(seconds)
    print(f"[-] chat sleep for {seconds} seconds before {msg_length} chars. {convo_pool_size} lines left in pool")
    await asyncio.sleep(seconds)


async def convo_interval_sleep():
    # sleep for a few minutes
    minutes = secrets.randbelow(convo_interval_minutes[1] - convo_interval_minutes[0] + 1) + convo_interval_minutes[0]
    print(f"[-] convo sleep for {minutes} minutes")
    await asyncio.sleep(minutes * 60)


async def check_user_exists(uid: int, discord_client):
    if not uid:
        return False
    try:
        userdata = await discord_client.fetch_user(uid)
        if userdata:
            return True
        return False
    except:
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
        print("[!] HTTP error follows:")
        print(err)
        print("[!] failed message:", username + ': ' + msg)


async def message_admin(discord_client, msg: str):
    admin_user = await discord_client.fetch_user(administrator_uid)
    await admin_user.send(msg)


def is_message_sensitive(msg: str):
    for string in censored_strings:
        if string.lower() in msg.lower():
            return True
    return False


def get_bare_emoji(msg: str):
    emoji = re.findall(r'\W(:\w+:)\W', msg)
    if emoji:
        return emoji
    return False


def get_role_mentions(msg: str):
    roles = re.findall(r'<@&\d{5,}>', msg)
    if roles:
        return roles
    return False


def get_user_mentions(msg: str):
    mentions = re.findall(r'<@!?\d{5,}>', msg)
    if mentions:
        return mentions
    return False 


def get_role_id(mention: str):
    role_id = re.search(r'\d+', mention)[0]
    return int(role_id)


def get_mention_id(mention: str):
    mention_id = re.search(r'\d+', mention)[0]
    return int(mention_id)


def get_emojicode(emoji: str, discord_client):
    if emoji in discord_client.emoji_lookup:
        return discord_client.emoji_lookup[emoji]
    try:
        emojicode = discord.utils.get(discord_client.guilds[0].emojis, name=emoji)
        if emojicode:
            discord_client.emoji_lookup[emoji] = str(emojicode)
            return str(emojicode)
        return False
    except:
        return False


def get_rolename(role: int, discord_client):
    if role in discord_client.role_lookup:
        return discord_client.role_lookup[role]
    role_id = get_role_id(role)
    try:
        rolename = discord.utils.get(discord_client.guilds[0].roles, id=role_id)
        if rolename:
            fancy = '**@' + str(rolename) + '**'
            discord_client.emoji_lookup[role] = fancy
            return fancy
        return False
    except:
        return False


def emoji_massage(msg: str, discord_client):
    bare_emoji = get_bare_emoji(msg)
    if not bare_emoji:
        return msg
    translated = {}
    for bare in bare_emoji:
        check = get_emojicode(bare[1:-1], discord_client)
        if check:
            translated[bare] = check
        else:
            translated[bare] = bare
    massaged = msg
    for emoji in translated:
        massaged = re.sub(emoji, translated[emoji], massaged)
    return massaged


def role_massage(msg: str, discord_client):
    roles = get_role_mentions(msg)
    if not roles:
        return msg
    translated = {}
    for role in roles:
        check = get_rolename(role, discord_client)
        if check:
            translated[role] = check
        else:
            translated[role] = '**@Diplomat**'
    massaged = msg
    for role in translated:
        massaged = re.sub(role, translated[role], massaged)
    return massaged


async def mention_massage(msg: str, discord_client):
    mentions = get_user_mentions(msg)
    if not mentions:
        return msg
    translated = {}
    for mention in mentions:
        mid = get_mention_id(mention)
        if not mid in do_not_mention:
            translated[mention] = mention
            continue
        user_check = await check_user_exists(mid, discord_client)
        if user_check:
            name_check = await lookup_nickname(mid, discord_client)
            if name_check:
                translated[mention] = '**__@' + name_check + '__**'
            else:
                translated[mention] = '**__@Elroy Jetson__**'
        else:
            translated[mention] = '**__@Elroy Jetson__**'
    massaged = msg
    for mention in translated:
        massaged = re.sub(mention, translated[mention], massaged)
    return massaged


def main():
    user_style_cache = {}
    intents = discord.Intents.default()
    intents.members = True
    client = discord.Client(intents=intents)
    convo_pool = []
    max_author_repeat = 6
    client.server_nicks = {}
    client.emoji_lookup = {}
    client.role_lookup = {}

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
                    emoji_massaged = emoji_massage(message, client)
                    role_massaged = role_massage(emoji_massaged, client)
                    mention_massaged = await mention_massage(role_massaged, client)
                    send_chat(mention_massaged, username, avatar)
                    if len(convo_pool) == 0:
                        await convo_interval_sleep()
            except Exception as e:
                print(f'[!] failed to send chat:')
                print(next_msg)
                print(e, ''.join(traceback.format_tb(e.__traceback__)))
        
    @client.event
    async def on_message(message):
        if message.channel.id == potemkin_channel_id and not message.author.bot:
            try:
                uid = message.author.id
                username = await lookup_nickname(uid, client)
                avatar = await lookup_avatar(uid, client)
                if is_message_sensitive(message.content):
                    await message.delete()
                    await message.channel.send(f"<@{message.author.id}>! OPSEC CENSORED! USE U4 LOCAL CHAT FOR SENSITIVE INTEL")
                else:
                    send_chat(message.content, username, avatar)
                    await message.delete()
            except:
                print("[!] failed to censor '" + message.author.display_name + ': ' + message.content + "'")

    client.run(bot_discord_token)


if __name__ == '__main__':
    main()