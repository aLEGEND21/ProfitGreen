from flask import Flask
from threading import Thread
from config import Config

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running..."

def run():
    app.run(host="0.0.0.0")

def run_server_thread():
    if Config.PRODUCTION == True:
        t = Thread(target=run)
        t.start()