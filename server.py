from pymongo import MongoClient # pymongo is a dependency of motor and will be installed automatically
from flask import Flask
from threading import Thread
from config import Config
from flask import request

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
    # Add the task to the database
    tasks.insert_one({
        "_type": "upvote",
        "website": "top.gg",
        "user": request.json["user"]
    })
    return request.json

def run():
    app.run(host="0.0.0.0", port=Config.PORT)

def run_server_thread():
    if Config.PRODUCTION == True:
        t = Thread(target=run)
        t.start()