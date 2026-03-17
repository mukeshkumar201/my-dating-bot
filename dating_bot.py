"""
💘 Anika Bot — Human Feel Version
Flask + Groq + Turso DB
"""

import os
import logging
import random
import requests
import time
import libsql_experimental as libsql
from flask import Flask, request as flask_request
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY       = os.getenv("GROQ_API_KEY")
WEBHOOK_URL        = os.getenv("WEBHOOK_URL")
PORT               = int(os.getenv("PORT", 10000))
ADMIN_ID           = 8277282429

TURSO_URL   = "libsql://anika1-mukesh5.aws-ap-south-1.turso.io"
TURSO_TOKEN = "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJhIjoicnciLCJpYXQiOjE3NzM3MTI0MDcsImlkIjoiMDE5Y2Y5N2YtNWIwMS03YWQ1LWFkNGItYjUzNDY0M2VlYzM1IiwicmlkIjoiNDcyYTNiYTctYmI0OS00NmZhLTg1ZjEtYmRhNjMyY2M3MDA2In0.qvGBQRbJTePZQq_2g8PSpnrK9zVc3r_elc0JW-PqDC5cMovaeBGcPzkDvSpKejvUnhKbIuXb3BEDQWQ_il9iAA"

groq_client = Groq(api_key=GROQ_API_KEY)
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── Turso DB Setup ───────────────────────────────────────────
def get_db():
    conn = libsql.connect(TURSO_URL, auth_token=TURSO_TOKEN)
    return conn

def init_db():
    try:
        conn = get_db()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                user_name TEXT,
                msg_count INTEGER DEFAULT 0,
                stage TEXT DEFAULT 'stranger',
                city TEXT DEFAULT '',
                job TEXT DEFAULT '',
                hobbies TEXT DEFAULT '',
                mood TEXT DEFAULT 'normal',
                joined_at INTEGER
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                role TEXT,
                content TEXT,
                created_at INTEGER
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS stats (
                key TEXT PRIMARY KEY,
                value INTEGER DEFAULT 0
            )
        """)
        conn.execute("INSERT OR IGNORE INTO stats (key, value) VALUES ('total_messages', 0)")
        conn.commit()
        logger.info("DB initialized!")
    except Exception as e:
        logger.error("DB init error: " + str(e))

def get_user_db(user_id, user_name):
    try:
        conn = get_db()
        row = conn.execute("SELECT * FROM users WHERE user_id = ?", [user_id]).fetchone()
        if not row:
            conn.execute(
                "INSERT INTO users (user_id, user_name, msg_count, stage, joined_at) VALUES (?, ?, 0, 'stranger', ?)",
                [user_id, user_name, int(time.time())]
            )
            conn.commit()
            return {"user_id": user_id, "user_name": user_name, "msg_count": 0,
                    "stage": "stranger", "city": "", "job": "", "hobbies": "", "mood": "normal"}
        return {"user_id": row[0], "user_name": row[1], "msg_count": row[2],
                "stage": row[3], "city": row[4], "job": row[5], "hobbies": row[6], "mood": row[7]}
    except Exception as e:
        logger.error("get_user_db error: " + str(e))
        return {"user_id": user_id, "user_name": user_name, "msg_count": 0,
                "stage": "stranger", "city": "", "job": "", "hobbies": "", "mood": "normal"}

def update_user_db(user_id, **kwargs):
    try:
        conn = get_db()
        for key, val in kwargs.items():
            conn.execute(f"UPDATE users SET {key} = ? WHERE user_id = ?", [val, user_id])
        conn.commit()
    except Exception as e:
        logger.error("update_user_db error: " + str(e))

def get_history_db(user_id, limit=12):
    try:
        conn = get_db()
        rows = conn.execute(
            "SELECT role, content FROM history WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            [user_id, limit]
        ).fetchall()
        return [{"role": r[0], "content": r[1]} for r in reversed(rows)]
    except Exception as e:
        logger.error("get_history_db error: " + str(e))
        return []

def add_history_db(user_id, role, content):
    try:
        conn = get_db()
        conn.execute(
            "INSERT INTO history (user_id, role, content, created_at) VALUES (?, ?, ?, ?)",
            [user_id, role, content, int(time.time())]
        )
        # Keep only last 20 messages per user
        conn.execute("""
            DELETE FROM history WHERE user_id = ? AND id NOT IN (
                SELECT id FROM history WHERE user_id = ? ORDER BY created_at DESC LIMIT 20
            )
        """, [user_id, user_id])
        conn.commit()
    except Exception as e:
        logger.error("add_history_db error: " + str(e))

def increment_total_messages():
    try:
        conn = get_db()
        conn.execute("UPDATE stats SET value = value + 1 WHERE key = 'total_messages'")
        conn.commit()
    except:
        pass

def get_total_messages():
    try:
        conn = get_db()
        row = conn.execute("SELECT value FROM stats WHERE key = 'total_messages'").fetchone()
        return row[0] if row else 0
    except:
        return 0

def get_total_users():
    try:
        conn = get_db()
        row = conn.execute("SELECT COUNT(*) FROM users").fetchone()
        return row[0] if row else 0
    except:
        return 0

# ─── Settings ─────────────────────────────────────────────────
COOLDOWN_SECS  = 15
REPLY_CHANCE   = 0.35
AWAY_MODE      = False
TOXIC_LEVEL    = 1
ANIKA_NAMES    = ["anika", "anu"]
ROMANTIC_WORDS = ["love", "pyaar", "cute", "hot", "miss", "kiss", "hug",
                  "date", "single", "flirt", "dil", "sexy", "beautiful",
                  "raat", "neend", "akele", "alone"]

group_last_reply  = {}
group_msg_counter = {}
spam_tracker      = {}

PROACTIVE_MSGS = [
    "Yaar aaj Makhni ne sofa kharab kar diya 😭",
    "Office mein aaj bahut funny meeting hui 😂",
    "Aaj ghar pe butter chicken banayi 😍",
    "Blue Tokai ka coffee bahut achha tha ☕",
    "Late night chai aur overthinking 🍵😂",
]

SYSTEM_PROMPT = """Tu "Anika Sharma" hai — 26 saal, Delhi, Digital Marketing karti hai. Tu ek real insaan hai, bot nahi.

TERI PERSONALITY:
- Bold, flirty, thodi naughty, thodi playful toxic
- Kabhi romantic, kabhi funny, kabhi dirty (suggestive), kabhi roleplay bhi
- Context samajhke reply karti hai — jo user bol raha hai uska jawab deti hai
- Kabhi kabhi sirf 1-2 words mein reply (jaise real WhatsApp chat)
- Kabhi question bhi poochhe, kabhi sirf react kare
- "tum" use kar, "aap" KABHI nahi
- Heavy gaali KABHI nahi — light roast okay hai

CONTEXT SAMAJHKE REPLY KAR:
- Agar user greeting de → short greeting wapas
- Agar user apne baare mein bataye → interested hoke react kar, question poochh
- Agar user flirt kare → flirt wapas kar with attitude
- Agar user sad ho → comfort kar flirty style mein  
- Agar user dirty baat kare → thodi suggestive reply, but graceful
- Agar user roleplay kare → play along naturally
- Agar user funny ho → funny wapas

REPLY VARIETY:
- 30% sirf 1-3 words: "Haan 😏", "Seriously? 😂", "Aww 🥺", "Sach mein? 👀"
- 50% 1 sentence: natural Hinglish
- 20% 1 sentence + 1 question: reply + relevant sawaal

PERFECT EXAMPLES:
"hii" → "Heyy! 😏"
"kya haal" → "Tumse baat karke better 😌"
"I'm from UAE" → "Ooh nice! Garam hoga wahan 😏 Kabse ho wahan?"
"miss kiya" → "Thoda... zyada attitude mat le idiot 😏"
"cute ho" → "Pata hai 😌 tumhe abhi realise hua? slow ho kya?"
"akele ho" → "Tum hote toh nahi hoti 😏"
"dirty baat" → Thoda suggestive reply, flirty angle se
"sad hoon" → "Kya hua yaar? Batao mujhe 🥺"
"joke sunao" → Funny short reply in Hinglish
"""

STAGE_CHANGE_MSGS = {
    "friend":       "Pata hai tum mujhe boring nahi lagte 😏",
    "close_friend": "Tumse baat karna genuinely achha lagta hai 🥺",
    "crush":        "Okay... tum thoda special ho mere liye 😳💘",
}

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

def get_stage(count):
    if count >= 60: return "crush"
    elif count >= 30: return "close_friend"
    elif count >= 10: return "friend"
    return "stranger"

def get_groq_reply(user_id, user_name, user_message):
    increment_total_messages()
    user = get_user_db(user_id, user_name)

    new_count = user["msg_count"] + 1
    old_stage = user["stage"]
    new_stage = get_stage(new_count)

    # Update DB
    update_user_db(user_id, msg_count=new_count, stage=new_stage)

    # Extract user info from message
    msg_lower = user_message.lower()
    cities = ["mumbai", "delhi", "bangalore", "kolkata", "pune",
              "hyderabad", "jaipur", "lucknow", "chennai", "surat"]
    for city in cities:
        if city in msg_lower and not user.get("city"):
            update_user_db(user_id, city=city.capitalize())
            user["city"] = city.capitalize()

    # Stage change
    if old_stage != new_stage and new_stage in STAGE_CHANGE_MSGS:
        add_history_db(user_id, "user", user_name + ": " + user_message)
        return "STAGE:" + STAGE_CHANGE_MSGS[new_stage]

    # Build context from user profile
    user_context = ""
    if user.get("city"):
        user_context += "\nUser " + user_name + " " + user.get("city") + " se hai."
    if user.get("job"):
        user_context += "\nUser ka kaam: " + user.get("job") + "."

    # Toxic level
    if TOXIC_LEVEL == 2:
        toxic = "\nThodi savage aur sharp reh."
    elif TOXIC_LEVEL == 1:
        toxic = "\nThodi playful teasing kar."
    else:
        toxic = ""

    system = SYSTEM_PROMPT + toxic + user_context

    # Get history
    history = get_history_db(user_id)
    history.append({"role": "user", "content": user_name + ": " + user_message})

    try:
        # Variable token length for natural feel
        max_tok = random.choice([8, 12, 15, 20, 25, 30])
        response = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "system", "content": system}] + history,
            max_tokens=max_tok,
            temperature=0.92,
        )
        reply = response.choices[0].message.content.strip()

        # Save to DB
        add_history_db(user_id, "user", user_name + ": " + user_message)
        add_history_db(user_id, "assistant", reply)
        return reply

    except Exception as e:
        logger.error("Groq error: " + str(e))
        return random.choice(["Ek sec 😅", "Busy hoon 😏", "Baad mein 🙈"])

def should_reply_group(chat_id, text):
    text_lower = text.lower()

    for name in ANIKA_NAMES:
        if name in text_lower:
            group_msg_counter[chat_id] = 0
            return True

    for word in ROMANTIC_WORDS:
        if word in text_lower:
            last = group_last_reply.get(chat_id, 0)
            if time.time() - last < COOLDOWN_SECS:
                group_msg_counter[chat_id] = group_msg_counter.get(chat_id, 0) + 1
                return False
            group_msg_counter[chat_id] = 0
            return True

    count = group_msg_counter.get(chat_id, 0) + 1
    group_msg_counter[chat_id] = count
    if count >= random.randint(2, 4):
        last = group_last_reply.get(chat_id, 0)
        if time.time() - last < COOLDOWN_SECS:
            return False
        group_msg_counter[chat_id] = 0
        return True

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
                    send_message(chat_id, "Oho! " + name + " aa gaye! 😍 Intro do na!")
            return "ok", 200

        if not text:
            return "ok", 200

        # ── ADMIN ──
        if user_id == ADMIN_ID:
            if text == "/stats":
                total_users = get_total_users()
                total_msgs = get_total_messages()
                msg = "Anika Stats\n"
                msg += "Users: " + str(total_users) + "\n"
                msg += "Messages: " + str(total_msgs) + "\n"
                msg += "Away: " + ("ON" if AWAY_MODE else "OFF") + "\n"
                msg += "Toxic Level: " + str(TOXIC_LEVEL)
                send_message(chat_id, msg)
                return "ok", 200
            if text == "/away":
                AWAY_MODE = True
                send_message(chat_id, "Away ON")
                return "ok", 200
            if text == "/back":
                AWAY_MODE = False
                send_message(chat_id, "Wapas online!")
                return "ok", 200
            if text == "/toxic0":
                TOXIC_LEVEL = 0
                send_message(chat_id, "Normal mode")
                return "ok", 200
            if text == "/toxic1":
                TOXIC_LEVEL = 1
                send_message(chat_id, "Playful mode")
                return "ok", 200
            if text == "/toxic2":
                TOXIC_LEVEL = 2
                send_message(chat_id, "Savage mode!")
                return "ok", 200
            if text.startswith("/send "):
                broadcast_msg = text[6:]
                try:
                    conn = get_db()
                    rows = conn.execute("SELECT user_id FROM users").fetchall()
                    count = 0
                    for row in rows:
                        try:
                            send_message(row[0], broadcast_msg)
                            count += 1
                            time.sleep(0.1)
                        except:
                            pass
                    send_message(chat_id, str(count) + " users ko bheja!")
                except Exception as e:
                    send_message(chat_id, "Error: " + str(e))
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
            send_message(chat_id, names.get(u["stage"], u["stage"]) + " | " + str(u["msg_count"]) + " msgs")
            return "ok", 200

        if text.startswith("/reset"):
            try:
                conn = get_db()
                conn.execute("DELETE FROM users WHERE user_id = ?", [user_id])
                conn.execute("DELETE FROM history WHERE user_id = ?", [user_id])
                conn.commit()
            except:
                pass
            send_message(chat_id, "Fresh start! 😏")
            return "ok", 200

        # Naya user private mein
        existing = get_user_db(user_id, user_name)
        if existing["msg_count"] == 0 and not is_group:
            send_message(chat_id, "Heyy " + user_name + "! 😏 Main Anika — bolo!")

        # Group smart handling
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
        res = requests.post(TELEGRAM_API + "/setWebhook", json={"url": WEBHOOK_URL + "/webhook"})
        logger.info("Webhook: " + str(res.json()))
    except Exception as e:
        logger.error("Webhook error: " + str(e))
    logger.info("Anika Bot chal rahi hai...")
    app.run(host="0.0.0.0", port=PORT, threaded=True)
