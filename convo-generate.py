from aitextgen import aitextgen
from io import StringIO
from re import match
from contextlib import redirect_stdout
from bot import get_chat_author
from hashlib import sha1
import time
import os, os.path

convo_max = 65534

def is_valid_chat(chatline: str):
    return bool(match(r"^[^:]{3,}: .{1,}", chatline))

def has_url(chatline: str):
    if 'http://' in chatline or 'https://' in chatline:
        return True
    return False

def has_repeat_author(chatline: str):
    author = get_chat_author(chatline) + ':'
    if chatline.count(author) > 1:
        return True
    return False

def generate_chats():
    print("generating batch...")    
    start = time.perf_counter()
    ai = aitextgen(model_folder="trained_model", to_gpu=True)
    f = StringIO()
    with redirect_stdout(f):
        ai.generate(n=10,
                max_length=2048,
                temperature=0.8,
                repetition_penalty=1.2,
                top_p=0.9)
    out = f.getvalue()
    end = time.perf_counter()
    elapse = end - start
    print(f'done. took {elapse}s')
    return out

def process_chats(chunks: list):
    convos = []
    for chunk in chunks:
        convo = []
        occurrences = {}
        lines = chunk.splitlines()
        for line in lines:
            if len(line) == 0:
                continue
            if has_url(line):
                print("[!] deleting line with URL:")
                print(line)
                continue
            if not is_valid_chat(line):
                # print("[!] deleting nonconforming line:")
                # print(line)
                continue
            if has_repeat_author(line):
                print("[!] deleting repeated author:")
                print(line)
                continue
            if line in occurrences:
                occurrences[line] += 1
            else:
                occurrences[line] = 1
            if occurrences[line] > 3:
                print("[!] deleting repeated chat:")
                print(line)
                continue
            convo.append(line)
        if len(convo) > 1:
            convos.append('\n'.join(convo))
    return convos

divider = '=========='

def main():
    convo_count = len(os.listdir('./convos'))

    while convo_count < convo_max:
        print(f"only {convo_count} convos")
        chatblock = generate_chats()
        chunks = chatblock.split(divider)
        convos = process_chats(chunks)
        for convo in convos:
            digest = sha1(convo.encode('utf-8')).hexdigest()
            filename = 'convos/' + digest + '.txt'
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(convo)
            print('saved', digest)
        convo_count = len(os.listdir('convos'))

    print(f"we have {convo_count} convos now. exiting")

if __name__ == '__main__':
    main()