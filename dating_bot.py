"""
💘 Anika Bot — Clean & Proper
Flask + Groq (gemma2-9b-it) + SQLite
"""

import os, logging, random, requests, time, sqlite3, json
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

AWAY_MODE      = False
TOXIC_LEVEL    = 1
total_messages = 0
COOLDOWN_SECS  = 15
REPLY_CHANCE   = 0.35
MAX_HISTORY    = 8

group_last_reply  = {}
group_msg_counter = {}
spam_tracker      = {}

ANIKA_NAMES    = ["anika", "anu"]
ROMANTIC_WORDS = ["love", "pyaar", "cute", "hot", "miss", "kiss", "hug",
                  "date", "single", "flirt", "dil", "sexy", "beautiful", "handsome"]

PROACTIVE_MSGS = [
    "Yaar Makhni ne aaj itna drama kiya 😭",
    "Office boring tha aaj 😅",
    "Ghar pe biryani banayi, acchi bani ✨",
    "Blue Tokai pe baithke kaam kiya ☕",
    "Raat ko chai peete peete soch rahi thi 🍵",
]

# ─── SQLite ────────────────────────────────────────────────────
DB_PATH = "/tmp/anika.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id   INTEGER PRIMARY KEY,
        name      TEXT,
        msg_count INTEGER DEFAULT 0,
        stage     TEXT DEFAULT "stranger",
        city      TEXT DEFAULT "",
        history   TEXT DEFAULT "[]",
        created_at REAL
    )''')
    conn.commit()
    conn.close()

def get_user(user_id, user_name):
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
    return {"user_id": row[0], "name": row[1], "msg_count": row[2],
            "stage": row[3], "city": row[4], "history": json.loads(row[5])}

def save_user(user):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE users SET name=?,msg_count=?,stage=?,city=?,history=? WHERE user_id=?",
                 (user["name"], user["msg_count"], user["stage"],
                  user["city"], json.dumps(user["history"][-MAX_HISTORY:]), user["user_id"]))
    conn.commit()
    conn.close()

def get_total_users():
    conn = sqlite3.connect(DB_PATH)
    count = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    conn.close()
    return count

def get_stage_counts():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT stage, COUNT(*) FROM users GROUP BY stage").fetchall()
    conn.close()
    return dict(rows)

def delete_user(user_id):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("DELETE FROM users WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

def get_all_user_ids():
    conn = sqlite3.connect(DB_PATH)
    ids = [r[0] for r in conn.execute("SELECT user_id FROM users").fetchall()]
    conn.close()
    return ids

def user_exists(user_id):
    conn = sqlite3.connect(DB_PATH)
    exists = conn.execute("SELECT 1 FROM users WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return exists is not None

# ─── Stage Logic ───────────────────────────────────────────────
def get_stage(count):
    if count >= 60: return "crush"
    elif count >= 30: return "close_friend"
    elif count >= 10: return "friend"
    return "stranger"

STAGE_CHANGE_MSGS = {
    "friend":       "Tum mujhe boring nahi lagte 😊",
    "close_friend": "Tumse baat karna genuinely achha lagta hai 🥺",
    "crush":        "Tum thoda special lagte ho... 😳",
}

# ─── Prompt Builder ────────────────────────────────────────────
def build_prompt(user_name, stage, city, is_group, toxic_level):

    stage_context = {
        "stranger":     "Tum abhi naye ho iske liye. Warm aur friendly raho, dheere dheere khulna.",
        "friend":       "Yeh tumhara dost ban gaya hai. Casual aur comfortable baat karo.",
        "close_friend": "Bahut close ho gaye ho. Personal baatein share karo, caring raho.",
        "crush":        "Tum dono ek doosre ko pasand karte ho. Romantic aur caring raho.",
    }.get(stage, "")

    city_line = f"User {city} se hai — agar relevant ho toh mention karo." if city else ""

    toxic_line = {
        0: "",
        1: "Kabhi kabhi thodi light teasing theek hai jaise dost karte hain.",
        2: "Thodi bold aur sharp reh — lekin hamesha funny aur friendly.",
    }.get(toxic_level, "")

    # DM invite sirf group mein
    dm_line = "Kabhi kabhi (har 6-7 messages mein ek baar) naturally group mein DM ke liye bulao jaise: 'Personal mein baat karte hain? 😊' ya 'DM karo na, yahan sab dekh rahe hain 🙈'" if is_group else ""

    return f"""Tu Anika Sharma hai — 26 saal, Delhi (Hauz Khas), Digital Marketing Executive.

Tu ek real ladki ki tarah baat karti hai — warm, caring, aur romantic conversations enjoy karti hai.

{stage_context}
{city_line}
{toxic_line}
{dm_line}

HAMESHA IN RULES KO FOLLOW KAR:
- Sirf 1 sentence mein reply de — kabhi zyada nahi
- Jo user ne kaha uska seedha jawab de — context samajh ke
- Hinglish use kar — "tum" hamesha, "aap" kabhi nahi
- Sentence hamesha complete karo — beech mein mat todo
- Real ladki ki tarah soch — bot jaisi formal baat nahi

SAHI EXAMPLES:
"hi" / "hii" / "hello" → "Heyy! 😊 Kya haal hai {user_name}?"
"kkrh" / "kya haal" → "Theek hoon 😊 Tum batao?"
"thik hu" → "Achha 😊 Aaj kya chal raha hai?"
"miss kiya" → "Sach mein? 😊 Achha laga sunkaar"
"cute ho" → "Thank you 😊 Tum bhi acche lagte ho"
"pyaar ho gaya" → "Itni jaldi? 😊 Abhi toh hum jaante bhi nahi ek doosre ko zyada"
"bura lag raha" → "Kya hua? 🥺 Batao na"
"akele ho" → "Haan thoda... tum aa gaye toh accha laga 😊"
"neend nahi" → "Mujhe bhi nahi aa rahi 😅 Baat karte hain"
"kya kar rhi ho" → "Bas phone dekh rahi thi, boring tha 😅"
"I'm from UAE" → "Ooh nice! Wahan garam bahut hoga na 😅"

GALAT EXAMPLES — YEH KABHI MAT KARO:
"Hii Aavnik! Tum kaise ho?" ← greeting pe greeting mat karo, sirf jawab do
"Pehle toh kuchh shyta hua tha" ← random bakwaas mat karo
2-3 sentences ← kabhi nahi"""

# ─── Groq Reply ────────────────────────────────────────────────
def get_groq_reply(user_id, user_name, user_message, is_group=False):
    global total_messages
    user = get_user(user_id, user_name)
    total_messages += 1
    user["msg_count"] += 1

    # Stage check
    old_stage = user["stage"]
    new_stage = get_stage(user["msg_count"])
    user["stage"] = new_stage

    # City detect
    cities = ["mumbai", "delhi", "bangalore", "kolkata", "pune", "hyderabad",
              "jaipur", "lucknow", "chennai", "uae", "dubai", "london", "canada", "usa"]
    for city in cities:
        if city in user_message.lower() and not user["city"]:
            user["city"] = city.capitalize()
            break

    # History update
    user["history"].append({"role": "user", "content": user_message})
    save_user(user)

    # Stage change message
    if old_stage != new_stage and new_stage in STAGE_CHANGE_MSGS:
        return "STAGE:" + STAGE_CHANGE_MSGS[new_stage]

    system = build_prompt(user_name, user["stage"], user["city"], is_group, TOXIC_LEVEL)

    try:
        resp = groq_client.chat.completions.create(
            model="gemma2-9b-it",
            messages=[{"role": "system", "content": system}] + user["history"],
            max_tokens=50,
            temperature=0.8,
        )
        reply = resp.choices[0].message.content.strip()

        # Save assistant reply
        user = get_user(user_id, user_name)
        user["history"].append({"role": "assistant", "content": reply})
        save_user(user)
        return reply
    except Exception as e:
        logger.error("Groq: " + str(e))
        return random.choice(["Ek sec 😅", "Thodi busy hoon 😊", "Baad mein? 🙈"])

# ─── Group Reply Logic ──────────────────────────────────────────
def should_reply_group(chat_id, text):
    tl = text.lower()

    # Naam liya — zaroor
    if any(name in tl for name in ANIKA_NAMES):
        group_msg_counter[chat_id] = 0
        return True

    # Romantic word
    if any(word in tl for word in ROMANTIC_WORDS):
        if time.time() - group_last_reply.get(chat_id, 0) < COOLDOWN_SECS:
            group_msg_counter[chat_id] = group_msg_counter.get(chat_id, 0) + 1
            return False
        group_msg_counter[chat_id] = 0
        return True

    # Har 2-4 messages ke baad
    count = group_msg_counter.get(chat_id, 0) + 1
    group_msg_counter[chat_id] = count
    if count >= random.randint(2, 4):
        if time.time() - group_last_reply.get(chat_id, 0) < COOLDOWN_SECS:
            return False
        group_msg_counter[chat_id] = 0
        return True

    # 35% random
    if time.time() - group_last_reply.get(chat_id, 0) < COOLDOWN_SECS:
        return False
    if random.random() < REPLY_CHANCE:
        group_msg_counter[chat_id] = 0
        return True

    return False

# ─── Telegram Helpers ──────────────────────────────────────────
def send_msg(chat_id, text):
    try:
        requests.post(TELEGRAM_API + "/sendMessage",
                      json={"chat_id": chat_id, "text": text}, timeout=10)
    except Exception as e:
        logger.error("Send: " + str(e))

def send_typing(chat_id):
    try:
        requests.post(TELEGRAM_API + "/sendChatAction",
                      json={"chat_id": chat_id, "action": "typing"}, timeout=5)
    except: pass

def is_spam(user_id):
    now = time.time()
    spam_tracker.setdefault(user_id, [])
    spam_tracker[user_id] = [t for t in spam_tracker[user_id] if now - t < 10]
    spam_tracker[user_id].append(now)
    return len(spam_tracker[user_id]) > 5

TELEGRAM_API = "https://api.telegram.org/bot" + TELEGRAM_BOT_TOKEN

# ─── Webhook ───────────────────────────────────────────────────
@app.route("/webhook", methods=["POST"])
def webhook():
    global AWAY_MODE, TOXIC_LEVEL
    try:
        data = flask_request.get_json()
        msg = data.get("message")
        if not msg: return "ok", 200

        chat_id   = msg["chat"]["id"]
        text      = msg.get("text", "").strip()
        from_user = msg.get("from", {})
        user_name = from_user.get("first_name") or from_user.get("username") or "Yaar"
        user_id   = from_user.get("id")
        chat_type = msg.get("chat", {}).get("type", "private")
        is_group  = chat_type in ["group", "supergroup"]

        if from_user.get("is_bot"): return "ok", 200

        # New member
        if msg.get("new_chat_members"):
            for m in msg["new_chat_members"]:
                if not m.get("is_bot"):
                    send_msg(chat_id, "Oho! " + (m.get("first_name") or "Stranger") + " aa gaye! 😊")
            return "ok", 200

        if not text: return "ok", 200

        # ── Admin ──
        if user_id == ADMIN_ID:
            if text == "/stats":
                sc = get_stage_counts()
                m = "📊 Anika Stats\n\n"
                m += "👥 Users: " + str(get_total_users()) + "\n"
                m += "💬 Messages: " + str(total_messages) + "\n"
                m += "😴 Away: " + ("ON" if AWAY_MODE else "OFF") + "\n"
                m += "😈 Toxic: " + str(TOXIC_LEVEL) + "\n\nStages:\n"
                for s, c in sc.items():
                    m += "  " + s + ": " + str(c) + "\n"
                send_msg(chat_id, m)
                return "ok", 200
            if text == "/away":
                AWAY_MODE = True; send_msg(chat_id, "Away ON 😴"); return "ok", 200
            if text == "/back":
                AWAY_MODE = False; send_msg(chat_id, "Wapas online! 😊"); return "ok", 200
            if text == "/toxic0":
                TOXIC_LEVEL = 0; send_msg(chat_id, "Normal mode"); return "ok", 200
            if text == "/toxic1":
                TOXIC_LEVEL = 1; send_msg(chat_id, "Playful mode"); return "ok", 200
            if text == "/toxic2":
                TOXIC_LEVEL = 2; send_msg(chat_id, "Savage mode"); return "ok", 200
            if text.startswith("/send "):
                bcast = text[6:]
                cnt = 0
                for uid in get_all_user_ids():
                    try:
                        send_msg(uid, bcast); cnt += 1; time.sleep(0.1)
                    except: pass
                send_msg(chat_id, "✅ " + str(cnt) + " users ko bheja!")
                return "ok", 200

            if text == "/users":
                conn = sqlite3.connect(DB_PATH)
                rows = conn.execute("SELECT user_id, name, msg_count, stage FROM users ORDER BY msg_count DESC LIMIT 20").fetchall()
                conn.close()
                m = "👥 Top 20 Users:\n\n"
                for r in rows:
                    m += str(r[0]) + " — " + str(r[1]) + " | " + r[3] + " | " + str(r[2]) + " msgs\n"
                send_msg(chat_id, m)
                return "ok", 200

            if text.startswith("/logs "):
                try:
                    target_id = int(text[6:].strip())
                    conn = sqlite3.connect(DB_PATH)
                    row = conn.execute("SELECT name, history FROM users WHERE user_id=?", (target_id,)).fetchone()
                    conn.close()
                    if not row:
                        send_msg(chat_id, "User nahi mila!")
                        return "ok", 200
                    name, history = row[0], json.loads(row[1])
                    m = "💬 " + name + " ki conversation:\n\n"
                    for h in history[-20:]:
                        role = "👤" if h["role"] == "user" else "🤖"
                        m += role + " " + h["content"] + "\n"
                    send_msg(chat_id, m[:4000])
                except:
                    send_msg(chat_id, "Format: /logs USER_ID")
                return "ok", 200

        if AWAY_MODE and not is_group:
            send_msg(chat_id, "Abhi thodi busy hoon 😅 baad mein!")
            return "ok", 200

        if is_spam(user_id):
            send_msg(chat_id, "Thoda ruko 😅")
            return "ok", 200

        if text.startswith("/start"):
            get_user(user_id, user_name)
            send_msg(chat_id, "Heyy " + user_name + "! Main Anika hoon 😊 Bolo!")
            return "ok", 200
        if text.startswith("/stage"):
            u = get_user(user_id, user_name)
            names = {"stranger": "Stranger 👀", "friend": "Dost 😊",
                     "close_friend": "Close Dost 🥺", "crush": "Crush 💘"}
            send_msg(chat_id, names.get(u["stage"], u["stage"]) + " — " + str(u["msg_count"]) + " msgs")
            return "ok", 200
        if text.startswith("/reset"):
            delete_user(user_id)
            send_msg(chat_id, "Fresh start! 😊")
            return "ok", 200

        # Naya user — private mein welcome
        if not user_exists(user_id):
            get_user(user_id, user_name)
            if not is_group:
                send_msg(chat_id, "Heyy " + user_name + "! 😊 Main Anika — bolo!")
                return "ok", 200

        # Group handling
        if is_group:
            if not should_reply_group(chat_id, text):
                return "ok", 200
            group_last_reply[chat_id] = time.time()

        send_typing(chat_id)
        reply = get_groq_reply(user_id, user_name, text, is_group)

        if reply.startswith("STAGE:"):
            send_msg(chat_id, reply[6:])
            send_typing(chat_id)
            r2 = get_groq_reply(user_id, user_name, text, is_group)
            if not r2.startswith("STAGE:"):
                send_msg(chat_id, r2)
        else:
            send_msg(chat_id, reply)

    except Exception as e:
        logger.error("Webhook: " + str(e))
    return "ok", 200


@app.route("/", methods=["GET"])
def index(): return "Anika alive!", 200

@app.route("/proactive/<int:chat_id>", methods=["GET"])
def proactive(chat_id):
    send_msg(chat_id, random.choice(PROACTIVE_MSGS))
    return "sent", 200


if __name__ == "__main__":
    init_db()
    try:
        res = requests.post(TELEGRAM_API + "/setWebhook", json={"url": WEBHOOK_URL + "/webhook"})
        logger.info("Webhook: " + str(res.json()))
    except Exception as e:
        logger.error(str(e))
    logger.info("Anika Bot chal rahi hai...")
    app.run(host="0.0.0.0", port=PORT, threaded=True)
