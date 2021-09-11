import discord
import requests
import json
import os
from discord.ext import tasks
from keep_alive import keep_alive

test_channel_id_general = 639512541701079073
channel_id = test_channel_id_general
nanopool_api_addr = "https://api.nanopool.org/v1/eth/workers/"
eth_wallet = "0x7c3d72a477f3d36a34c68990a9e62a48c0331710"
pool_api_addr = nanopool_api_addr

url = pool_api_addr + eth_wallet
worker_dict = {}
client = discord.Client() 

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
      msg += str(sum(value))
      msg += " shares.\n"
    await client.get_channel(channel_id).send(msg)

@tasks.loop(seconds=5)
async def fetch_data():
    r = requests.get(url)
    if r.status_code != 200:
      return
    res = json.loads(r.text)
    if not res["status"]:
      return
    for worker in res["data"]:
      name = worker["id"]
      rating = worker["rating"]
      if name not in worker_dict:
        await client.get_channel(channel_id).send("welcome new worker: " + name + " with " + str(rating) + " shares.")
        worker_dict[name] = [rating]
      else:
        if worker_dict[name][-1] < rating:
          await client.get_channel(channel_id).send(name + "'s share: " + str(worker_dict[name][-1]) + " -> " + str(rating))
          worker_dict[name][-1] = rating
        elif worker_dict[name][-1] > rating:
          await client.get_channel(channel_id).send("worker " + name + " detects share drop! " + str(worker_dict[name][-1]) + " -> " + str(rating))
          worker_dict[name].append(rating)
          
keep_alive()     
client.run(os.getenv("TOKEN"))
