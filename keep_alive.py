from flask import Flask;import threading,os
app=Flask(__name__)
@app.route("/")
def home(): return "I'm alive!"
def run(): app.run(host="0.0.0.0",port=int(os.environ.get("PORT",8080)))
def keep_alive(): threading.Thread(target=run).start()
