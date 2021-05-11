README.MD

0) figure out all the dependencies
1) scrape the discord channels you want with DHT (https://dht.chylex.com/, or dht.js in this repo)
2) set `dht_input` in `parsing.py` to use your DHT scrape and run it to generate `parsed_discord.txt` and `usercache.json`
3) fine-tune the model by running `finetune.py` while checking results with `test-generate.py`
4) mine some convos with `convo-generate.py`
5) configure variables/tokens in `bot.py` and connect it to discord