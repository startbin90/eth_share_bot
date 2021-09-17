import discord
import requests
import json
import os
from discord.ext import tasks
from datetime import datetime
import platform
from replit import db

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
eth_symbol = "<:eth:888234376427614228>"


class worker_dict:
    def __init__(self, d=dict()):
        self.d = d
        self.loaded_from_json = False
        self.workers_in_pool = {} # {"name": is_online}
        self.allowed_to_talk = True

    def get_total_shares(self):
        return sum([value["shares"] for _, value in self.d.items()])

    def get_stored_worker_names(self):
        return list(self.d.keys())

    def get_worker_shares(self, worker):
        if worker in self.d:
            return self.d[worker]["shares"]

    def get_worker_latest_time(self, name):
        if name in self.d:
            return self.d[name]["latest_time"]

    def get_worker_history(self, name):
        if name in self.d and "history" in self.d[name]:
            return self.d[name]["history"]

    def pop_worker_history_entry(self, name, ts):
        if name in self.d and "history" in self.d[name]:
            ret = self.d[name]["history"].pop(ts, None)
            return True if ret != None else False
        else:
            return False

    def set_worker_history_entry(self, name, ts, shares):
        if name in self.d and "history" in self.d[name]:
            self.d[name]["history"][ts] = shares
        else:
            return None

    def set(self, name, shares=0, ts=start_ts):
        self.d[name] = {"shares": shares, "latest_time": ts, "history": {}}

    def add_share_update_ts(self, name, new_shares, ts=None):
        if name in self.d:
            self.d[name]["shares"] += new_shares
            if ts:
                self.d[name]["latest_time"] = ts

    def set_workers_in_pool(self, d):
        self.workers_in_pool = d

    def get_worker_names_in_pool(self):
        return list(self.workers_in_pool.keys())
    
    def get_online_workers_in_pool(self):
        return [ name for name, is_online in self.workers_in_pool.items() if is_online ]

    def is_worker_in_pool(self, name):
        return name in self.workers_in_pool
    
    def is_worker_online(self, name):
        return self.is_worker_in_pool(name) and self.workers_in_pool[name]

    def load_from_json(self):
        try:
            with open("local_log.json", "r") as f:
                s = f.read()
                self.d = json.loads(s)
                self.loaded_from_json = True

                # if eth_wallet not in db:
                #     db[eth_wallet] = {"share_book": self.d, "share_log": []}
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
        lst = [ (name, value["shares"], value["latest_time"], self.is_worker_online(name), self.is_worker_in_pool(name))for name, value in self.d.items()]
        lst.sort(key=lambda x: (-x[3], -x[1]))
        msg = ""
        for name, shares, latest_time, is_online, is_in_pool in lst:
            if is_online:
                msg += ":green_circle:  " 
            elif is_in_pool:
                msg += ":red_circle:  "
            else:
                msg += ":no_entry:  "
            msg += name + " has "
            msg += str(shares)
            msg += " shares. Last report time: "
            msg += str(latest_time) + "\n\n"
        msg += "NOTE: :green_circle:  online  "
        msg += ":red_circle:  offline  "
        msg += ":no_entry:  worker removed from SparkPool for 24h inactivity"
        return msg


workers = worker_dict()
client = discord.Client()

def http_request(url, payload={}):
    r = requests.get(url, params=payload)
    if r.status_code != 200:
        print("Error: HTTP request failed!")
        return None
    return json.loads(r.text)

# return data section if on success
def sparkpool_http_request(url, payload):
    res = http_request(url, payload)
    if res["code"] != 200:
        print("Error: SparkPool HTTP request failed!")
        return None
    return res["data"]

def fetch_in_pool_workers():
    payload = {'currency': 'ETH', 'miner': eth_wallet}
    data = sparkpool_http_request(pool_api_addr + "/v1/worker/list", payload)
    return { worker["worker"]: worker["online"] for worker in data } if data is not None else None


@client.event
async def on_ready():
    print('We have logged in as {0.user}'.format(client))

    workers.load_from_json()
    in_pool_workers = fetch_in_pool_workers()
    workers.set_workers_in_pool(in_pool_workers)

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
        data = sparkpool_http_request(pool_api_addr + "/v1/bill/stats", {'currency': 'ETH', 'miner': eth_wallet})
        if data is None:
            return
        balance = data["balance"]
        
        res = http_request("https://api.coingecko.com/api/v3/simple/price", {'ids':'ethereum', 'vs_currencies':'usd,cad,sgd,cny'})
        if res is None:
            return 
        print(res)
        eth_usd = res["ethereum"]["usd"]
        eth_cad = res["ethereum"]["cad"]
        eth_sgd = res["ethereum"]["sgd"]
        eth_cny = res["ethereum"]["cny"]

        res = http_request("http://ethgas.watch/api/gas")
        if res is None:
            return
        gwei = res["normal"]["gwei"]
        gwei_usd = res["normal"]["usd"]

        total = workers.get_total_shares()
        worker_name_shares = [(worker_name, workers.get_worker_shares(worker_name)) for worker_name in workers.get_stored_worker_names()]
        worker_name_shares.sort(key=lambda x: (-x[1]))

        msg = eth_symbol + ": {}  :fuelpump:: {} gwei ≈ {} USD\n".format(balance, gwei, gwei_usd)
        msg += "Price: :flag_us:: {} :flag_ca:: {} :flag_sg:: {} :flag_cn:: {}\n".format(eth_usd, eth_cad, eth_sgd, eth_cny)
        embed = discord.Embed(title="Profit", description= msg)

        for worker_name, worker_shares in worker_name_shares:
            share_ratio = worker_shares / total
            eth_profit = balance * share_ratio
            usd_profit = eth_usd * eth_profit
            cad_profit = eth_cad * eth_profit
            sgd_profit = eth_sgd * eth_profit
            cny_profit = eth_cny * eth_profit
            value = "{}/{}({:.2f}) shares\n".format(worker_shares, total, share_ratio) + eth_symbol + ": {:.5f} :flag_us:: {:.2f} :flag_ca:: {:.2f} :flag_sg:: {:.2f} :flag_cn:: {:.2f}\n".format(eth_profit, usd_profit, cad_profit, sgd_profit, cny_profit)
            embed.add_field(name=worker_name, inline=False, value=value)
        embed.add_field(name="\u200B", value="Source: [ETH Gas.watch](http://ethgas.watch) [CoinGecko](https://www.coingecko.com/)")
        await client.get_channel(channel_id).send(embed=embed)


@tasks.loop(seconds=5)
async def fetch_data():
    ## check and notify online/offline status
    workers_in_pool = fetch_in_pool_workers()
    if workers_in_pool is None:
        print("Error: HTTP request failed!")
        return
    previous_online = set(workers.get_online_workers_in_pool())
    latest_online = set([ name for name, is_online in workers_in_pool.items() if is_online ])
    upline = list(latest_online - previous_online)
    downline = list(previous_online - latest_online)
    msg = ""
    if upline:
        for name in upline:
            msg += ":green_circle:  " + name + " starts mining :)\n\n"
    if downline:
        for name in downline:
            msg += ":red_circle:  " + name + " stops mining :(\n\n"
    if msg:
        await client.get_channel(channel_id).send(msg)
    workers.set_workers_in_pool(workers_in_pool)


    # has change(new/delete/modify) in local_log.json
    has_file_change = False
    # flush_to_discord = True
    discord_msg = ""
    res_log_msg = ""
    for name in workers.get_worker_names_in_pool():
        discord_msg_worker = ""
        res_log_msg_worker = ""
        ## init new worker if found
        if name not in workers.get_stored_worker_names():
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
        data = sparkpool_http_request(pool_api_addr + "/v1/worker/sharesHistory", payload)
        if data is None:
            return 
        # validate all history entry/ remove outdated ones
        history = workers.get_worker_history(name)
        ts_lst = list(history.keys())
        res_history = {entry["time"]: entry["validShares"] for entry in data}
        adjustment_log = []
        adjustment_delta = 0
        for ts in ts_lst:
            ## check and remove outdated entries
            if ts not in res_history:
                has_file_change = True
                if not workers.pop_worker_history_entry(name, ts):
                    print("Error: last_online entry removal failed")
            else:
            ## check and modify existing entries
                new_share = res_history[ts]
                share_in_record = history[ts]
                if new_share != share_in_record:
                    has_file_change = True
                    # flush_to_discord = True
                    adjustment_log.append((ts, share_in_record, new_share))
                    adjustment_delta += new_share - share_in_record
                    workers.set_worker_history_entry(name, ts, new_share)

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
            worker_shares = workers.get_worker_shares(name)
            msg += "        total adjustment: {}({}{}) -> {}\n".format(worker_shares, sign, adjustment_delta, worker_shares + adjustment_delta)
            discord_msg_worker += "        adjustment detected:\n" + msg
            res_log_msg_worker += "        adjustment detected\n" + msg
            workers.add_share_update_ts(name, adjustment_delta)
            
            # if workers.allowed_to_talk:
            #     await client.get_channel(channel_id).send(msg)
            # print(msg)
            # res_log_msg += msg + "\n"


        test_share_sum = 0
        shares_delta = 0
        latest_time = workers.get_worker_latest_time(name)
        msg = ""
        for entry in data:
            ts = entry["time"]
            share = entry["validShares"]
            test_share_sum += share
            if str_to_ts(ts) > str_to_ts(workers.get_worker_latest_time(name)):
                has_file_change = True
                workers.set_worker_history_entry(name, ts, share)
                shares_delta += share
                latest_time = ts if str_to_ts(ts) > str_to_ts(latest_time) else latest_time
                msg += "        {} + {} @ {}\n".format(name, share, ts)
        if msg: # new entry/share detected
            res_log_msg_worker += "        new share update:\n" + msg
            msg = "{}'s share: {}( + {}) -> {}\n".format(name, str(workers.get_worker_shares(name)), shares_delta, str(workers.get_worker_shares(name) + shares_delta))
            res_log_msg_worker += msg
            if shares_delta: # if has change, add to discord message
                discord_msg_worker += msg
        # print("test share sum {} for {}; ".format(test_share_sum, name), end="", flush=True)
        
        # update anyway
        workers.add_share_update_ts(name, shares_delta, latest_time)

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
