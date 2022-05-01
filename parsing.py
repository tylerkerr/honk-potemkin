import json

''' dump taken 2021-05-08:
general
newbie
salt
grindhouse
minecraft
blowshitup
serious
warroom
pocketdefense
wingmates
shootblues
'''

dht_input = 'goose-2022-04-19.txt'

with open(dht_input, 'r', encoding="utf-8") as f:
    dump = json.load(f)

discord_users = dump['meta']['users']

uids = {}
unums = {}
usernames = {}
count = 0
for uid in discord_users:
    name = discord_users[uid]['name']
    if 'tag' in discord_users[uid]:
        tag = discord_users[uid]['tag'] 
    else:
        tag = None
    
    uids[uid] = {'name': name, 'tag': tag, 'unum': count}
    unums[count] = {'name': name, 'tag': tag, 'uid': uid}
    usernames[name] = {'uid': uid, 'tag': tag}
    count += 1

discord_channels = dump['meta']['channels']

channel_ids = {}
for cid in discord_channels:
    channel_ids[cid] = discord_channels[cid]['name']

textout = ''
message_dump = dump['data']
for channel in message_dump:
    msgs = message_dump[channel]
    prev_msg = None
    for msg in msgs:
        name = unums[msgs[msg]['u']]['name']
        if 'm' in msgs[msg]:
            message = msgs[msg]['m']
        else:
            pass
        if message == prev_msg:
            continue
        else:
            prev_msg = message
        textout += name + ': ' + message + '\n'

with open('parsed_discord.txt', 'w', encoding="utf-8") as outfile:
    outfile.write(textout)

with open('usercache.json', 'w', encoding='utf-8') as userdump:
    json.dump(usernames, userdump)