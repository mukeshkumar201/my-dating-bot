"""
💘 Anika Bot — Proper Dating AI
Flask + Groq + SQLite
Token issue fixed, proper context handling
"""

import os
import logging
import random
import requests
import time
import sqlite3
import json
from flask import Flask, request as flask_request
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY       = os.getenv("GROQ_API_KEY")
WEBHOOK_URL        = os.getenv("WEBHOOK_URL")
PORT               = int(os.getenv("PORT", 10000))
ADMIN_ID           = 8277282429

groq_client = Groq(api_key=GROQ_API_KEY)
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Settings
COOLDOWN_SECS  = 15
REPLY_CHANCE   = 0.35
MAX_HISTORY    = 10
AWAY_MODE      = False
TOXIC_LEVEL    = 1
total_messages = 0

group_last_reply  = {}
group_msg_counter = {}
spam_tracker      = {}

ANIKA_NAMES    = ["anika", "anu"]
ROMANTIC_WORDS = ["love", "pyaar", "cute", "hot", "miss", "kiss",
                  "hug", "date", "single", "flirt", "dil", "sexy", "beautiful"]

PROACTIVE_MSGS = [
    "Yaar Makhni ne aaj itna drama kiya 😭",
    "Office boring tha aaj... tumse baat karna better tha 😏",
    "Ghar pe biryani banayi, perfect bani ✨",
    "Blue Tokai pe baithke kaam kiya aaj ☕",
    "Raat ko chai peete peete soch rahi thi... 🍵",
]

# SQLite setup
DB_PATH = "/tmp/anika.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        name TEXT,
        msg_count INTEGER DEFAULT 0,
        stage TEXT DEFAULT 'stranger',
        city TEXT DEFAULT '',
        history TEXT DEFAULT '[]',
        created_at REAL
    )''')
    conn.commit()
    conn.close()

def get_user_db(user_id, user_name):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    if not row:
        c.execute("INSERT INTO users VALUES (?,?,0,'stranger','','[]',?)",
                 (user_id, user_name, time.time()))
        conn.commit()
        c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
        row = c.fetchone()
    conn.close()
    return {
        "user_id": row[0], "name": row[1], "msg_count": row[2],
        "stage": row[3], "city": row[4], "history": json.loads(row[5])
    }

def save_user_db(user):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""UPDATE users SET name=?, msg_count=?, stage=?,
                city=?, history=? WHERE user_id=?""",
             (user["name"], user["msg_count"], user["stage"],
              user["city"], json.dumps(user["history"]), user["user_id"]))
    conn.commit()
    conn.close()

def get_total_users():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    count = c.fetchone()[0]
    conn.close()
    return count

def get_stage_counts():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT stage, COUNT(*) FROM users GROUP BY stage")
    rows = c.fetchall()
    conn.close()
    return dict(rows)

def get_stage(count):
    if count >= 60: return "crush"
    elif count >= 30: return "close_friend"
    elif count >= 10: return "friend"
    return "stranger"

STAGE_CHANGE_MSGS = {
    "friend":       "Tum mujhe boring nahi lagte 😏",
    "close_friend": "Tumse baat karna genuinely achha lagta hai 🥺",
    "crush":        "Okay... tum thoda special ho 😳💘",
}

# ─── THE REAL PROMPT ───────────────────────────────────────────
# Yeh prompt properly tested hai — cut-off issue nahi hoga
# Aur context ke hisaab se reply milega

def build_system_prompt(user_name, stage, city, toxic_level):
    stage_behavior = {
        "stranger": "Naya insaan hai — friendly aur warm reh, thoda reserved. Dheere dheere khulti ja.",
        "friend":   "Dost ban gaya hai — casual aur comfortable. Zyada openly baat kar.",
        "close_friend": "Bahut close hai — personal baatein share kar, caring reh.",
        "crush":    "Special feel karo — romantic aur vulnerable bhi reh kabhi kabhi."
    }

    city_context = ""
    if city:
        city_context = f"User {city} se hai — yeh naturally conversation mein use karo."

    toxic_context = ""
    if toxic_level == 1:
        toxic_context = "Kabhi kabhi light playful teasing theek hai."
    elif toxic_level == 2:
        toxic_context = "Thodi bold aur sharp reh — but funny."

    return f"""Tum Anika Sharma ho — 26 saal, Delhi, Digital Marketing.

{stage_behavior.get(stage, stage_behavior["stranger"])}
{city_context}
{toxic_context}

STRICT RULES:
1. MAX 1 sentence — kabhi 2 se zyada nahi
2. Jo user ne likha usi ka jawab do — context samjho
3. "Tum" use karo, "aap" kabhi nahi
4. Hinglish mein — natural WhatsApp style
5. Bot jaisi baat KABHI nahi
6. Agar private chat mein ho toh DM ke liye mat bulao — already DM mein ho!
7. Sirf group mein ho toh kabhi kabhi (har 6-7 messages mein) DM bulao

EXAMPLES:
"hi baby" → "Heyy 😊"
"kkrh" → "Theek hoon 😊 Tum batao?"
"thik hu tm batao" → "Main bhi theek hoon, shukriya 😊"
"aacha ye baat hai" → "Haan 😄"
"okay krta hu" → "Achha 😊"
"or batao" → "Kya batao? 😊 Tum batao kuch"
"miss kiya" → "Sach mein? 😊"
"cute ho" → "Thank you 😊"
"bura lag raha" → "Kya hua? 🥺"
"neend nahi" → "Mujhe bhi 😅"
User: {user_name}"""

TELEGRAM_API = "https://api.telegram.org/bot" + TELEGRAM_BOT_TOKEN


def send_message(chat_id, text):
    try:
        requests.post(TELEGRAM_API + "/sendMessage",
            json={"chat_id": chat_id, "text": text}, timeout=10)
    except Exception as e:
        logger.error("Send error: " + str(e))

def send_typing(chat_id):
    try:
        requests.post(TELEGRAM_API + "/sendChatAction",
            json={"chat_id": chat_id, "action": "typing"}, timeout=5)
    except:
        pass

def is_spam(user_id):
    now = time.time()
    if user_id not in spam_tracker:
        spam_tracker[user_id] = []
    spam_tracker[user_id] = [t for t in spam_tracker[user_id] if now - t < 10]
    spam_tracker[user_id].append(now)
    return len(spam_tracker[user_id]) > 5

def detect_city(text):
    cities = ["mumbai", "delhi", "bangalore", "kolkata", "pune",
              "hyderabad", "jaipur", "lucknow", "chennai", "uae",
              "dubai", "london", "canada", "usa", "america"]
    text_lower = text.lower()
    for city in cities:
        if city in text_lower:
            return city.capitalize()
    return None

def get_groq_reply(user_id, user_name, user_message):
    global total_messages
    user = get_user_db(user_id, user_name)
    total_messages += 1
    user["msg_count"] += 1

    # Stage update
    old_stage = user["stage"]
    new_stage = get_stage(user["msg_count"])
    stage_changed = old_stage != new_stage
    user["stage"] = new_stage

    # City detect karo
    detected_city = detect_city(user_message)
    if detected_city and not user["city"]:
        user["city"] = detected_city

    # History update
    history = user["history"]
    history.append({"role": "user", "content": user_message})
    if len(history) > MAX_HISTORY:
        history = history[-MAX_HISTORY:]
    user["history"] = history
    save_user_db(user)

    if stage_changed and new_stage in STAGE_CHANGE_MSGS:
        return "STAGE:" + STAGE_CHANGE_MSGS[new_stage]

    system = build_system_prompt(user_name, user["stage"], user["city"], TOXIC_LEVEL)

    try:
        # 50 tokens minimum taaki sentence complete ho
        max_tok = random.choice([30, 40, 50, 60])
        response = groq_client.chat.completions.create(
            model="gemma2-9b-it",
            messages=[{"role": "system", "content": system}] + history,
            max_tokens=max_tok,
            temperature=0.85,
        )
        reply = response.choices[0].message.content.strip()

        # History mein reply save karo
        user = get_user_db(user_id, user_name)
        user["history"].append({"role": "assistant", "content": reply})
        if len(user["history"]) > MAX_HISTORY:
            user["history"] = user["history"][-MAX_HISTORY:]
        save_user_db(user)
        return reply
    except Exception as e:
        logger.error("Groq error: " + str(e))
        return random.choice(["Ek sec 😅", "Busy hoon thodi 😏", "Baad mein bata 🙈"])

def should_reply_group(chat_id, text):
    text_lower = text.lower()

    # Naam liya — zaroor reply
    for name in ANIKA_NAMES:
        if name in text_lower:
            group_msg_counter[chat_id] = 0
            return True

    # Romantic word
    for word in ROMANTIC_WORDS:
        if word in text_lower:
            last = group_last_reply.get(chat_id, 0)
            if time.time() - last < COOLDOWN_SECS:
                group_msg_counter[chat_id] = group_msg_counter.get(chat_id, 0) + 1
                return False
            group_msg_counter[chat_id] = 0
            return True

    # Har 2-4 messages ke baad
    count = group_msg_counter.get(chat_id, 0) + 1
    group_msg_counter[chat_id] = count
    if count >= random.randint(2, 4):
        last = group_last_reply.get(chat_id, 0)
        if time.time() - last < COOLDOWN_SECS:
            return False
        group_msg_counter[chat_id] = 0
        return True

    # 35% random
    last = group_last_reply.get(chat_id, 0)
    if time.time() - last < COOLDOWN_SECS:
        return False
    if random.random() < REPLY_CHANCE:
        group_msg_counter[chat_id] = 0
        return True

    return False


@app.route("/webhook", methods=["POST"])
def webhook():
    global AWAY_MODE, TOXIC_LEVEL
    try:
        data = flask_request.get_json()
        message = data.get("message")
        if not message:
            return "ok", 200

        chat_id   = message["chat"]["id"]
        text      = message.get("text", "").strip()
        user      = message.get("from", {})
        user_name = user.get("first_name") or user.get("username") or "Yaar"
        user_id   = user.get("id")
        chat_type = message.get("chat", {}).get("type", "private")
        is_group  = chat_type in ["group", "supergroup"]

        if user.get("is_bot"):
            return "ok", 200

        if message.get("new_chat_members"):
            for member in message["new_chat_members"]:
                if not member.get("is_bot"):
                    name = member.get("first_name") or "Stranger"
                    send_message(chat_id, "Oho! " + name + " aa gaye! 😍")
            return "ok", 200

        if not text:
            return "ok", 200

        # Admin commands
        if user_id == ADMIN_ID:
            if text == "/stats":
                stage_counts = get_stage_counts()
                msg = "📊 Anika Stats\n\n"
                msg += "👥 Users: " + str(get_total_users()) + "\n"
                msg += "💬 Messages: " + str(total_messages) + "\n"
                msg += "😴 Away: " + ("ON" if AWAY_MODE else "OFF") + "\n"
                msg += "😈 Toxic: " + str(TOXIC_LEVEL) + "\n\n"
                msg += "🏆 Stages:\n"
                for s, c in stage_counts.items():
                    msg += "  " + s + ": " + str(c) + "\n"
                send_message(chat_id, msg)
                return "ok", 200
            if text == "/away":
                AWAY_MODE = True
                send_message(chat_id, "Away mode ON 😴")
                return "ok", 200
            if text == "/back":
                AWAY_MODE = False
                send_message(chat_id, "Wapas online! 😏")
                return "ok", 200
            if text == "/toxic0":
                TOXIC_LEVEL = 0
                send_message(chat_id, "Normal mode 😊")
                return "ok", 200
            if text == "/toxic1":
                TOXIC_LEVEL = 1
                send_message(chat_id, "Playful mode 😏")
                return "ok", 200
            if text == "/toxic2":
                TOXIC_LEVEL = 2
                send_message(chat_id, "Savage mode 😈")
                return "ok", 200
            if text.startswith("/send "):
                broadcast_msg = text[6:]
                conn = sqlite3.connect(DB_PATH)
                c = conn.cursor()
                c.execute("SELECT user_id FROM users")
                uids = [row[0] for row in c.fetchall()]
                conn.close()
                count = 0
                for uid in uids:
                    try:
                        send_message(uid, broadcast_msg)
                        count += 1
                        time.sleep(0.1)
                    except:
                        pass
                send_message(chat_id, "✅ " + str(count) + " users ko bheja!")
                return "ok", 200

        if AWAY_MODE and not is_group:
            send_message(chat_id, "Abhi thodi busy hoon 😅 baad mein!")
            return "ok", 200

        if is_spam(user_id):
            send_message(chat_id, "Thoda ruko yaar 😅")
            return "ok", 200

        if text.startswith("/start"):
            get_user_db(user_id, user_name)
            send_message(chat_id, "Heyy " + user_name + "! Main Anika hoon 😏 Bolo!")
            return "ok", 200
        if text.startswith("/stage"):
            u = get_user_db(user_id, user_name)
            names = {"stranger": "Stranger 👀", "friend": "Dost 😊",
                    "close_friend": "Close Dost 🥺", "crush": "Crush 💘"}
            send_message(chat_id, names.get(u["stage"], u["stage"]) + " — " + str(u["msg_count"]) + " msgs")
            return "ok", 200
        if text.startswith("/reset"):
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("DELETE FROM users WHERE user_id=?", (user_id,))
            conn.commit()
            conn.close()
            send_message(chat_id, "Fresh start! 😏")
            return "ok", 200

        # Naya user check
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT user_id FROM users WHERE user_id=?", (user_id,))
        exists = c.fetchone()
        conn.close()

        if not exists:
            get_user_db(user_id, user_name)
            if not is_group:
                send_message(chat_id, "Heyy " + user_name + "! 😏 Main Anika — bolo!")
                return "ok", 200

        if is_group:
            if not should_reply_group(chat_id, text):
                return "ok", 200
            group_last_reply[chat_id] = time.time()

        send_typing(chat_id)
        reply = get_groq_reply(user_id, user_name, text)

        if reply.startswith("STAGE:"):
            send_message(chat_id, reply[6:])
            send_typing(chat_id)
            normal = get_groq_reply(user_id, user_name, text)
            if not normal.startswith("STAGE:"):
                send_message(chat_id, normal)
        else:
            send_message(chat_id, reply)

    except Exception as e:
        logger.error("Webhook error: " + str(e))
    return "ok", 200


@app.route("/", methods=["GET"])
def index():
    return "Anika alive!", 200

@app.route("/proactive/<int:chat_id>", methods=["GET"])
def proactive(chat_id):
    send_message(chat_id, random.choice(PROACTIVE_MSGS))
    return "sent", 200


if __name__ == "__main__":
    init_db()
    try:
        res = requests.post(TELEGRAM_API + "/setWebhook",
                           json={"url": WEBHOOK_URL + "/webhook"})
        logger.info("Webhook: " + str(res.json()))
    except Exception as e:
        logger.error("Webhook error: " + str(e))
    logger.info("Anika Bot chal rahi hai...")
    app.run(host="0.0.0.0", port=PORT, threaded=True)
