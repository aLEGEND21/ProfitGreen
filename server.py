from pymongo import MongoClient # pymongo is a dependency of motor and will be installed automatically
from flask import Flask
from threading import Thread
from config import Config
from time import time
from flask import request

# Declare the var to hold all the users to remind them of their next vote
REMIND_USERS = [
    #416730155332009984, # aLEGEND#8740
    388874485303869441, # Brian McLogan#7569
    726516937676423188, # IamtheBest#7537
    411315998646468608, # m0m1n#2300
    516066882256764950  # TheGroke#1123
]

# Initalize the app
app = Flask(__name__)

# Connect to the database
client = MongoClient(Config.DB_CONNECTION_STRING)
db = client.get_database("ProfitGreen")
tasks = db.get_collection("Tasks")

@app.route("/")
def home():
    return "Bot is running..."

@app.route("/topgg_webhook", methods=["POST"])
def topgg_webhook():
    """
    Example Output:
    {'user': '416730155332009984', 'type': 'test', 'query': '', 'bot': '958046938245234778'}
    Docs:
    https://docs.top.gg/resources/webhooks/
    """
    # Add the upvote task to the database
    tasks.insert_one({
        "_type": "upvote",
        "website": "top.gg",
        "user": request.json["user"]
    })
    # Add a task to remind the user to the database
    if request.json["user"] in REMIND_USERS:
        tasks.insert_one({
            "_type": "upvote_reminder",
            "user": request.json["user"],
            "remind_timestamp": round(time()) + 60 * 60 * 12 # 12 hours from now
        })
    return request.json

def run():
    app.run(host="0.0.0.0", port=Config.PORT)

def run_server_thread():
    if Config.PRODUCTION == True:
        t = Thread(target=run)
        t.start()