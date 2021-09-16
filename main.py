import discord
import requests
import json
import os
from discord.ext import tasks
from datetime import datetime
import platform

# Json format
# {
#   name:
#     { "shares": 0,
#       "latest_time": start_ts,
#     },
# }


def str_to_ts(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S.%fZ")


def ts_to_str(ts):
    return ts.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


MACOS = 'Darwin'
LINUX = 'Linux'
WIN = 'Windows'
onLocal = False
if platform.system() == MACOS:
    onLOcal = True

log_channel = 885966677689401386
test_channel = 639512541701079073
test_spark_wallet = "sp_ethereum"
log_spark_wallet = "sp_startbin"
sparkpool_api_addr = "https://www.sparkpool.com"
# test_nano_wallet = "0x7c3d72a477f3d36a34c68990a9e62a48c0331710"
# nanopool_api_addr = "https://api.nanopool.org/v1/eth/workers/"


start_ts = ts_to_str(datetime(2021, 9, 1))
channel_id = log_channel
eth_wallet = log_spark_wallet
pool_api_addr = sparkpool_api_addr



class worker_dict:
    def __init__(self, d=dict()):
        self.d = d
        self.loaded_from_json = False
        self.online_workers = []
        self.allowed_to_talk = True

    def get_total_shares(self):
        return sum([value["shares"] for _, value in self.d.items()])

    def get_workers(self):
        return list(self.d.keys())

    def get_shares(self, name):
        if name in self.d:
            return self.d[name]["shares"]

    def get_latest_time(self, name):
        if name in self.d:
            return self.d[name]["latest_time"]

    def get_history(self, name):
        if name in self.d and "history" in self.d[name]:
            return self.d[name]["history"]
        else:
            return None

    def pop_entry_from_history(self, name, ts):
        if name in self.d and "history" in self.d[name]:
            ret = self.d[name]["history"].pop(ts, None)
            return True if ret != None else False
        else:
            return False

    def set_entry_to_history(self, name, ts, shares):
        if name in self.d and "history" in self.d[name]:
            self.d[name]["history"][ts] = shares
        else:
            return None

    def set(self, name, shares=0, ts=start_ts):
        self.d[name] = {"shares": shares, "latest_time": ts, "history": {}}

    def update_share_and_ts(self, name, new_shares, ts=None):
        if name in self.d:
            self.d[name]["shares"] += new_shares
            if ts:
                self.d[name]["latest_time"] = ts

    def set_online_workers(self, lst):
        self.online_workers = lst

    def get_online_workers(self):
        return self.online_workers

    def load_from_json(self):
        try:
            with open("local_log.json", "r") as f:
                s = f.read()
                self.d = json.loads(s)
                self.loaded_from_json = True
        except:
            self.d = {}
            self.loaded_from_json = False

    def dump_to_file(self):
        try:
            with open("local_log.json", "w") as f:
                json.dump(self.d, f)
                f.flush()
        except Exception as e:
            print(e)
            print("dump failed")

    def __str__(self):
        msg = ""
        for key, value in self.d.items():
            if key in self.online_workers:
                msg += ":green_circle:  "
            else:
                msg += ":red_circle:  "
            msg += key + " has "
            msg += str(value["shares"])
            msg += " shares. Last report time: "
            msg += str(value["latest_time"]) + "\n\n"
        msg += "NOTE: :green_circle:  The worker is registered on SparkPool  "
        msg += ":red_circle:  The worker is removed from SparkPool for 24h inactivity"
        return msg


workers = worker_dict()
client = discord.Client()

def fetch_workers():
    payload = {'currency': 'ETH', 'miner': eth_wallet}
    r = requests.get(pool_api_addr + "/v1/worker/list", params=payload)
    if r.status_code != 200:
        return
    res = json.loads(r.text)
    if res["code"] != 200:
        return
    return [worker["worker"] for worker in res["data"]]


@client.event
async def on_ready():
    print('We have logged in as {0.user}'.format(client))

    workers.load_from_json()
    online_workers = fetch_workers()
    workers.set_online_workers(online_workers)

    msg = "\n:white_check_mark: Bot is online. "
    if workers.loaded_from_json:
        msg += "I recovered these workers from logfile:\n\n"
        msg += str(workers) + "\n\n"
    else:
        msg += "I didn't found anything from logfile\n\n"
    msg += "Available commands:\n"
    msg += "$list     List all workers stat\n"
    msg += "$v        Verbose, update share increment to the channel\n"
    msg += "$shutup   Disable share update\n"
    msg += "$status   Display current setting status\n"
    msg += "$profit   Calculate profit based on shares\n"
    await client.get_channel(channel_id).send(msg)

    fetch_data.start()


@client.event
async def on_message(message):
    if message.content.startswith("$list"):
        msg = str(workers)
        await client.get_channel(channel_id).send(msg)
    if message.content.startswith("$v"):
        workers.allowed_to_talk = True
        await client.get_channel(channel_id).send("Verbose mode ON")
    if message.content.startswith("$shutup"):
        workers.allowed_to_talk = False
        await client.get_channel(channel_id).send(
            "Verbose mode OFF, now I shutup :slight_smile: ")
    if message.content.startswith("$status"):
        if workers.allowed_to_talk:
            msg = "Verbose: :green_circle: \n"
        else:
            msg = "Verbose: :red_circle: \n"
        await client.get_channel(channel_id).send(msg)
    if message.content.startswith("$profit"):
        payload = {'currency': 'ETH', 'miner': eth_wallet}
        r = requests.get(pool_api_addr + "/v1/bill/stats", params=payload)
        if r.status_code != 200:
            return
        res = json.loads(r.text)
        if res["code"] != 200:
            return
        balance = res["data"]["balance"]
        print(res["data"])
        r = requests.get(pool_api_addr + "/v1/currency/stats", params=payload)
        if r.status_code != 200:
            return
        res = json.loads(r.text)
        if res["code"] != 200:
            return
        eth_in_usd = res["data"]["usd"]
        print(res["data"])
        total = workers.get_total_shares()
        worker_names = workers.get_workers()
        msg = "Current Balance is {}, ETH price in USD {}\n".format(balance, eth_in_usd)
        for worker_name in worker_names:
            worker_share = workers.get_shares(worker_name)
            share_ratio = worker_share / total
            eth_profit = balance * share_ratio
            usd_profit = eth_in_usd * eth_profit
            msg += "{} has {}/{}({}) shares, equivalent to {} ETH or {} USD.\n".format(worker_name, worker_share, total, share_ratio, eth_profit, usd_profit)
        await client.get_channel(channel_id).send(msg)


@tasks.loop(seconds=5)
async def fetch_data():
    ## check and notify online/offline status
    online_workers = fetch_workers()
    old = set(workers.get_online_workers())
    new = set(online_workers)
    upline = list(new - old)
    downline = list(old - new)
    msg = ""
    # if upline:
    #     for name in upline:
    #         msg += ":green_circle:  " + name + " is mining now\n\n"
    if downline:
        for name in downline:
            msg += ":red_circle:  " + name + " is removed from SparkPool now\n\n"
    if msg:
        await client.get_channel(channel_id).send(msg)
    workers.set_online_workers(online_workers)


    # has change(new/delete/modify) in local_log.json
    has_file_change = False
    # flush_to_discord = True
    discord_msg = ""
    res_log_msg = ""
    for name in workers.get_online_workers():
        discord_msg_worker = ""
        res_log_msg_worker = ""
        ## init new worker if found
        if name not in workers.get_workers():
            workers.set(name)
            has_file_change = True
            # flush_to_discord = True
            msg = "{} joined mining for the first time, welcome!\n".format(name)
            discord_msg_worker += msg
            res_log_msg_worker += msg
        # else:
            # msg = "Updates for {}:\n".format(name)
            # discord_msg_worker += msg
            # res_log_msg_worker += msg

        ## get current worker share history
        payload = {'currency': 'ETH', 'miner': eth_wallet, 'worker': name}
        r = requests.get(pool_api_addr + "/v1/worker/sharesHistory", params=payload)
        if r.status_code != 200:
            return
        res = json.loads(r.text)
        if res["code"] != 200:
            return


        # validate all history entry/ remove outdated ones
        history = workers.get_history(name)
        ts_lst = list(history.keys())
        res_history = {entry["time"]: entry["validShares"] for entry in res["data"]}
        adjustment_log = []
        adjustment_delta = 0
        for ts in ts_lst:
            ## check and remove outdated entries
            if ts not in res_history:
                has_file_change = True
                if not workers.pop_entry_from_history(name, ts):
                    print("Error: old entry removal failed")
            else:
            ## check and modify existing entries
                new_share = res_history[ts]
                share_in_record = history[ts]
                if new_share != share_in_record:
                    has_file_change = True
                    # flush_to_discord = True
                    adjustment_log.append((ts, share_in_record, new_share))
                    adjustment_delta += new_share - share_in_record
                    workers.set_entry_to_history(name, ts, new_share)

        if adjustment_log: # has_file_change is true namely
            msg = ""
            for ts, old_share, new_share in adjustment_log:
                sign = ""
                if new_share - old_share >= 0:
                    sign = "+"
                msg += "        {} shares @ {} adjusted to {}({}{})\n".format(old_share, ts, new_share, sign, new_share - old_share)
            
            sign = ""
            if adjustment_delta >= 0:
                sign = "+"
            worker_shares = workers.get_shares(name)
            msg += "        total adjustment: {}({}{}) -> {}\n".format(worker_shares, sign, adjustment_delta, worker_shares + adjustment_delta)
            discord_msg_worker += "        adjustment detected:\n" + msg
            res_log_msg_worker += "        adjustment detected\n" + msg
            workers.update_share_and_ts(name, adjustment_delta)
            
            # if workers.allowed_to_talk:
            #     await client.get_channel(channel_id).send(msg)
            # print(msg)
            # res_log_msg += msg + "\n"


        test_share_sum = 0
        shares_delta = 0
        latest_time = workers.get_latest_time(name)
        msg = ""
        for entry in res["data"]:
            ts = entry["time"]
            share = entry["validShares"]
            test_share_sum += share
            if str_to_ts(ts) > str_to_ts(workers.get_latest_time(name)):
                has_file_change = True
                workers.set_entry_to_history(name, ts, share)
                shares_delta += share
                latest_time = ts if str_to_ts(ts) > str_to_ts(latest_time) else latest_time
                msg += "        {} + {} @ {}\n".format(name, share, ts)
        if msg: # new entry/share detected
            res_log_msg_worker += "        new share update:\n" + msg
            msg = "{}'s share: {}( + {}) -> {}\n".format(name, str(workers.get_shares(name)), shares_delta, str(workers.get_shares(name) + shares_delta))
            res_log_msg_worker += msg
            if shares_delta: # if has change, add to discord message
                discord_msg_worker += msg
        # print("test share sum {} for {}; ".format(test_share_sum, name), end="", flush=True)
        
        # update anyway
        workers.update_share_and_ts(name, shares_delta, latest_time)

        if res_log_msg_worker:
            res_log_msg += "Updates for {}:\n".format(name) + res_log_msg_worker
        if discord_msg_worker:
            discord_msg += discord_msg_worker

    if has_file_change:
        workers.dump_to_file()
    if discord_msg and workers.allowed_to_talk:
        await client.get_channel(channel_id).send(discord_msg)
    if res_log_msg:
        print(res_log_msg)
        with open("res_log", "a") as res_log:
            res_log.write(res_log_msg)
            res_log.flush()
        

TOKEN = ""
if not onLocal:
    from keep_alive import keep_alive
    keep_alive()
    TOKEN += os.getenv("TOKEN")
else:
    with open("../discord_bot_token", "r") as f:
        TOKEN += f.read()
client.run(TOKEN)
