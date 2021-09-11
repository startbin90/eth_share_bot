import discord
import requests
import json
import os
from discord.ext import tasks
from keep_alive import keep_alive
from datetime import datetime

log_channel = 885966677689401386
test_channel = 639512541701079073
test_nano_wallet = "0x7c3d72a477f3d36a34c68990a9e62a48c0331710"
test_spark_wallet = "sp_ethereum"
nanopool_api_addr = "https://api.nanopool.org/v1/eth/workers/"
sparkpool_api_addr = "https://www.sparkpool.com/v1/worker/"
start_ts = datetime(2021, 9, 1)
channel_id = test_channel
eth_wallet = test_spark_wallet
pool_api_addr = sparkpool_api_addr

# { name: 
#   {"shares": 0, "latest_time": start_ts},
# }
worker_dict = {}
client = discord.Client() 

def str_to_ts(s):
  return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S.%fZ")

@client.event
async def on_ready():
  print('We have logged in as {0.user}'.format(client))
  fetch_data.start()

@client.event
async def on_message(message):
  if message.content.startswith("$list"):
    msg = ""
    for key, value in worker_dict.items():
      msg += key + " has " 
      msg += str(value["shares"])
      msg += " shares.\n"
    await client.get_channel(channel_id).send(msg)

@tasks.loop(seconds=5)
async def fetch_data():
    print(worker_dict)
    payload1 = {'currency': 'ETH', 'miner': eth_wallet}
    r1 = requests.get(pool_api_addr + "list", params=payload1)
    if r1.status_code != 200:
      return
    res1 = json.loads(r1.text)
    if res1["code"] != 200:
      return
    for worker in res1["data"]:
      
      name = worker["worker"]
      
      if name not in worker_dict:
        await client.get_channel(channel_id).send("welcome new worker: " + name)
        worker_dict[name] = {"shares": 0, "latest_time": start_ts}
      
      payload2 = {'currency': 'ETH', 'miner': eth_wallet, 'worker': name}
      r2 = requests.get(pool_api_addr + "sharesHistory", params=payload2)
      if r2.status_code != 200:
        return
      res2 = json.loads(r2.text)
      if res2["code"] != 200:
        return
      # 2021-09-10T04:40:00.000Z
      res2["data"].sort(key=lambda x: str_to_ts(x["time"]))
      shares_delta = 0
      for entry in res2["data"]:
        if str_to_ts(entry["time"]) > worker_dict[name]["latest_time"]:
          shares_delta += entry["validShares"]
          worker_dict[name]["latest_time"] = str_to_ts(entry["time"])
      if shares_delta:
        await client.get_channel(channel_id).send(name + "'s share: " + str(worker_dict[name]["shares"]) + " -> " + str(worker_dict[name]["shares"] + shares_delta))
        worker_dict[name]["shares"] += shares_delta
          
# keep_alive()     
client.run(os.getenv("TOKEN"))
