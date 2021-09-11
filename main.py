import discord
import requests
import json
import os
from discord.ext import tasks
from keep_alive import keep_alive
from datetime import datetime

def str_to_ts(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S.%fZ")

def ts_to_str(ts):
    return ts.strftime("%Y-%m-%dT%H:%M:%S.%fZ")

log_channel = 885966677689401386
test_channel = 639512541701079073
test_nano_wallet = "0x7c3d72a477f3d36a34c68990a9e62a48c0331710"
test_spark_wallet = "sp_ethereum"
nanopool_api_addr = "https://api.nanopool.org/v1/eth/workers/"
sparkpool_api_addr = "https://www.sparkpool.com/v1/worker/"
start_ts = ts_to_str(datetime(2021, 9, 1))
channel_id = test_channel
eth_wallet = test_spark_wallet
pool_api_addr = sparkpool_api_addr


class worker_dict:
    def __init__(self, d=dict()):
        self.d = d

    def get(self):
        return self.d

    def get_shares(self, name):
        if name in self.d:
            return self.d[name]["shares"]

    def get_latest_time(self, name):
        if name in self.d:
            return self.d[name]["latest_time"]

    def set(self, name, shares=0, ts=start_ts):
        # {
        #   name:
        #     { "shares": 0,
        #       "latest_time": start_ts,
        #     },
        # }
        self.d[name] = {"shares": shares, "latest_time": ts}
        self.dump_to_file()

    def update(self, name, new_shares, ts):
        if name in self.d:
            self.d[name]["shares"] += new_shares
            self.d[name]["latest_time"] = ts
            self.dump_to_file()

    def load_from_json(self):
        try:
            with open("local_log.json", "r") as f:
                s = f.read()
                self.d = json.loads(s)
        except:
            self.d = {}

    def dump_to_file(self):
        try:
            with open("local_log.json", "w") as f:
                json.dump(self.d, f)
        except Exception as e: 
            print(e)
            print("dump failed")

    def __str__(self):
        return str(self.d)


workers = worker_dict()
workers.load_from_json()
client = discord.Client()

@client.event
async def on_ready():
    print('We have logged in as {0.user}'.format(client))
    fetch_data.start()


@client.event
async def on_message(message):
    if message.content.startswith("$list"):
        msg = ""
        for key, value in workers.get().items():
            msg += key + " has "
            msg += str(value["shares"])
            msg += " shares.\n"
        await client.get_channel(channel_id).send(msg)


@tasks.loop(seconds=5)
async def fetch_data():
    print(workers.get())
    payload1 = {'currency': 'ETH', 'miner': eth_wallet}
    r1 = requests.get(pool_api_addr + "list", params=payload1)
    if r1.status_code != 200:
        return
    res1 = json.loads(r1.text)
    if res1["code"] != 200:
        return
    for worker in res1["data"]:

        name = worker["worker"]

        if name not in workers.get():
            await client.get_channel(channel_id).send("welcome new worker: " +
                                                      name)
            workers.set(name)

        payload2 = {'currency': 'ETH', 'miner': eth_wallet, 'worker': name}
        r2 = requests.get(pool_api_addr + "sharesHistory", params=payload2)
        if r2.status_code != 200:
            return
        res2 = json.loads(r2.text)
        if res2["code"] != 200:
            return
        # 2021-09-10T04:40:00.000Z
        # res2["data"].sort(key=lambda x: str_to_ts(x["time"]))
        shares_delta = 0
        latest_time = start_ts
        has_change = False
        for entry in res2["data"]:
            # print(str_to_ts(entry["time"]))
            # print(workers.get_latest_time(name))
            if str_to_ts(entry["time"]) > str_to_ts(workers.get_latest_time(name)):
                has_change = True
                shares_delta += entry["validShares"]
                latest_time = entry["time"] if str_to_ts(entry["time"]) > str_to_ts(latest_time) else latest_time
        if has_change:
            if shares_delta:
                await client.get_channel(channel_id).send(
                    name + "'s share: " + str(workers.get_shares(name)) +
                    " -> " + str(workers.get_shares(name) + shares_delta))
            workers.update(name, shares_delta, latest_time)


keep_alive()
client.run(os.getenv("TOKEN"))
