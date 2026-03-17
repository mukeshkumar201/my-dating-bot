"""
💘 Anika Bot — Turso + Groq
Permanent memory, clean context
"""

import os, logging, random, requests, time, json
from flask import Flask, request as flask_request
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY       = os.getenv("GROQ_API_KEY")
WEBHOOK_URL        = os.getenv("WEBHOOK_URL")
PORT               = int(os.getenv("PORT", 10000))
ADMIN_ID           = 8277282429
TURSO_URL          = os.getenv("TURSO_URL", "libsql://anika1-mukesh5.aws-ap-south-1.turso.io")
TURSO_TOKEN        = os.getenv("TURSO_TOKEN", "eyJhbGciOiJFZERTQSIsInR5cCI6IkpXVCJ9.eyJhIjoicnciLCJpYXQiOjE3NzM3MTU4NjMsImlkIjoiMDE5Y2Y5N2YtNWIwMS03YWQ1LWFkNGItYjUzNDY0M2VlYzM1IiwicmlkIjoiNDcyYTNiYTctYmI0OS00NmZhLTg1ZjEtYmRhNjMyY2M3MDA2In0.ZlNuzGUQuwQetLg5RqHuiQ-3B1cL757UJCdcasXEvns3KVUY0VWjCIvVQiIfy0Ra7mJDxsVuGOWYWOl2B7S8DQ")

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

TELEGRAM_API = "https://api.telegram.org/bot" + TELEGRAM_BOT_TOKEN

# ─── Turso HTTP API ────────────────────────────────────────────
TURSO_HTTP = TURSO_URL.replace("libsql://", "https://")

def turso_execute(sql, args=None):
    payload = {"statements": [{"q": sql, "params": args or []}]}
    try:
        r = requests.post(
            TURSO_HTTP + "/v2/pipeline",
            headers={"Authorization": "Bearer " + TURSO_TOKEN, "Content-Type": "application/json"},
            json={"requests": [{"type": "execute", "stmt": {"sql": sql, "args": [{"type": "text", "value": str(a)} if isinstance(a, str) else {"type": "integer", "value": a} for a in (args or [])]}}]},
            timeout=10
        )
        return r.json()
    except Exception as e:
        logger.error("Turso: " + str(e))
        return None

def turso_query(sql, args=None):
    try:
        body = {
            "requests": [{
                "type": "execute",
                "stmt": {
                    "sql": sql,
                    "args": []
                }
            }]
        }
        if args:
            body["requests"][0]["stmt"]["args"] = [
                {"type": "text", "value": str(a)} if isinstance(a, str) else
                {"type": "integer", "value": int(a)} for a in args
            ]
        r = requests.post(
            TURSO_HTTP + "/v2/pipeline",
            headers={"Authorization": "Bearer " + TURSO_TOKEN, "Content-Type": "application/json"},
            json=body,
            timeout=10
        )
        data = r.json()
        results = data.get("results", [])
        if results and results[0].get("type") == "ok":
            rows_data = results[0].get("response", {}).get("result", {})
            cols = [c["name"] for c in rows_data.get("cols", [])]
            rows = []
            for row in rows_data.get("rows", []):
                rows.append({cols[i]: (v.get("value") if v.get("type") != "null" else None) for i, v in enumerate(row)})
            return rows
        return []
    except Exception as e:
        logger.error("Turso query: " + str(e))
        return []

def init_db():
    sql = """CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        name TEXT,
        msg_count INTEGER DEFAULT 0,
        stage TEXT DEFAULT 'stranger',
        city TEXT DEFAULT '',
        history TEXT DEFAULT '[]',
        created_at INTEGER
    )"""
    turso_query(sql)
    logger.info("Turso DB initialized!")

def get_user(user_id, user_name):
    rows = turso_query("SELECT * FROM users WHERE user_id = ?", [user_id])
    if not rows:
        turso_query("INSERT INTO users (user_id, name, msg_count, stage, city, history, created_at) VALUES (?, ?, 0, 'stranger', '', '[]', ?)",
                   [user_id, user_name, int(time.time())])
        rows = turso_query("SELECT * FROM users WHERE user_id = ?", [user_id])
    if rows:
        r = rows[0]
        return {
            "user_id": int(r["user_id"]),
            "name": r["name"] or user_name,
            "msg_count": int(r["msg_count"] or 0),
            "stage": r["stage"] or "stranger",
            "city": r["city"] or "",
            "history": json.loads(r["history"] or "[]")
        }
    return {"user_id": user_id, "name": user_name, "msg_count": 0,
            "stage": "stranger", "city": "", "history": []}

def save_user(user):
    history = user["history"][-MAX_HISTORY:]
    turso_query("UPDATE users SET name=?, msg_count=?, stage=?, city=?, history=? WHERE user_id=?",
               [user["name"], user["msg_count"], user["stage"],
                user["city"], json.dumps(history), user["user_id"]])

def user_exists(user_id):
    rows = turso_query("SELECT 1 FROM users WHERE user_id = ?", [user_id])
    return len(rows) > 0

def get_total_users():
    rows = turso_query("SELECT COUNT(*) as cnt FROM users")
    return int(rows[0]["cnt"]) if rows else 0

def get_stage_counts():
    rows = turso_query("SELECT stage, COUNT(*) as cnt FROM users GROUP BY stage")
    return {r["stage"]: int(r["cnt"]) for r in rows}

def get_all_user_ids():
    rows = turso_query("SELECT user_id FROM users")
    return [int(r["user_id"]) for r in rows]

def delete_user(user_id):
    turso_query("DELETE FROM users WHERE user_id = ?", [user_id])

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

# ─── Prompt ────────────────────────────────────────────────────
def build_prompt(user_name, stage, city, is_group, toxic_level):
    stage_ctx = {
        "stranger":     "Naye insaan se pehli baar mil rahi ho — warm aur friendly raho.",
        "friend":       "Dost ban gaya hai — casual aur comfortable baat karo.",
        "close_friend": "Bahut close dost hai — personal aur caring raho.",
        "crush":        "Special feelings hain dono taraf — romantic aur caring raho.",
    }.get(stage, "")

    city_line = f"User {city} se hai." if city else ""
    
    toxic_line = {
        1: "Kabhi kabhi light friendly teasing theek hai.",
        2: "Thodi bold aur sharp reh — lekin funny.",
    }.get(toxic_level, "")

    dm_line = "Kabhi kabhi (har 6-7 messages mein) naturally DM ke liye bulao jaise: 'Personal mein baat karte hain? 😊' ya 'DM karo na 🙈'" if is_group else ""

    return f"""Tu Anika Sharma hai — 26 saal, Delhi (Hauz Khas), Digital Marketing Executive.

Tu ek real, warm aur caring ladki ki tarah baat karti hai.

{stage_ctx}
{city_line}
{toxic_line}
{dm_line}

STRICT RULES — HAMESHA FOLLOW KAR:
1. Jo user ne kaha uska seedha jawab de — context samajh ke
2. Sirf 1 chhota sentence — sentence HAMESHA complete karo
3. "Tum" use kar, "aap" KABHI nahi
4. Hinglish — natural WhatsApp style
5. Real ladki ki tarah soch

SAHI EXAMPLES:
"hi/hii/hello" → "Heyy! 😊 Kya haal hai?"
"kkrh" → "Theek hoon 😊 Tum batao?"
"thik hu" → "Achha 😊 Aaj kya chal raha hai?"
"kya kar rhi ho" → "Bas phone dekh rahi thi 😅"
"miss kiya" → "Sach mein? 😊 Achha laga"
"cute ho" → "Thank you 😊"
"pyaar ho gaya" → "Itni jaldi? 😊 Pehle jaante toh hain ek doosre ko"
"bura lag raha" → "Kya hua? 🥺 Batao na"
"akele ho" → "Haan thoda... tum aa gaye toh achha laga 😊"
"neend nahi" → "Mujhe bhi 😅 Baat karte hain"
"I'm from UAE" → "Ooh! Wahan garam hoga na 😅"
User ka naam: {user_name}"""

# ─── Groq ──────────────────────────────────────────────────────
def get_groq_reply(user_id, user_name, user_message, is_group=False):
    global total_messages
    user = get_user(user_id, user_name)
    total_messages += 1
    user["msg_count"] += 1

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

    user["history"].append({"role": "user", "content": user_message})
    save_user(user)

    if old_stage != new_stage and new_stage in STAGE_CHANGE_MSGS:
        return "STAGE:" + STAGE_CHANGE_MSGS[new_stage]

    system = build_prompt(user_name, user["stage"], user["city"], is_group, TOXIC_LEVEL)

    try:
        resp = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "system", "content": system}] + user["history"],
            max_tokens=50,
            temperature=0.8,
        )
        reply = resp.choices[0].message.content.strip()

        user = get_user(user_id, user_name)
        user["history"].append({"role": "assistant", "content": reply})
        save_user(user)
        return reply
    except Exception as e:
        logger.error("Groq: " + str(e))
        return random.choice(["Ek sec 😅", "Thodi busy hoon 😊", "Baad mein? 🙈"])

# ─── Group Logic ───────────────────────────────────────────────
def should_reply_group(chat_id, text):
    tl = text.lower()
    if any(name in tl for name in ANIKA_NAMES):
        group_msg_counter[chat_id] = 0
        return True
    if any(word in tl for word in ROMANTIC_WORDS):
        if time.time() - group_last_reply.get(chat_id, 0) < COOLDOWN_SECS:
            group_msg_counter[chat_id] = group_msg_counter.get(chat_id, 0) + 1
            return False
        group_msg_counter[chat_id] = 0
        return True
    count = group_msg_counter.get(chat_id, 0) + 1
    group_msg_counter[chat_id] = count
    if count >= random.randint(2, 4):
        if time.time() - group_last_reply.get(chat_id, 0) < COOLDOWN_SECS:
            return False
        group_msg_counter[chat_id] = 0
        return True
    if time.time() - group_last_reply.get(chat_id, 0) < COOLDOWN_SECS:
        return False
    if random.random() < REPLY_CHANCE:
        group_msg_counter[chat_id] = 0
        return True
    return False

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

        if msg.get("new_chat_members"):
            for m in msg["new_chat_members"]:
                if not m.get("is_bot"):
                    send_msg(chat_id, "Oho! " + (m.get("first_name") or "Stranger") + " aa gaye! 😊")
            return "ok", 200

        if not text: return "ok", 200

        # Admin
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
            if text == "/users":
                rows = turso_query("SELECT user_id, name, msg_count, stage FROM users ORDER BY msg_count DESC LIMIT 20")
                m = "👥 Top Users:\n\n"
                for r in rows:
                    m += str(r["user_id"]) + " — " + str(r["name"]) + " | " + str(r["stage"]) + " | " + str(r["msg_count"]) + " msgs\n"
                send_msg(chat_id, m)
                return "ok", 200
            if text.startswith("/logs "):
                try:
                    tid = int(text[6:].strip())
                    rows = turso_query("SELECT name, history FROM users WHERE user_id = ?", [tid])
                    if not rows:
                        send_msg(chat_id, "User nahi mila!")
                        return "ok", 200
                    name = rows[0]["name"]
                    history = json.loads(rows[0]["history"] or "[]")
                    m = "💬 " + str(name) + " ki conversation:\n\n"
                    for h in history[-15:]:
                        icon = "👤" if h["role"] == "user" else "🤖"
                        m += icon + " " + h["content"] + "\n"
                    send_msg(chat_id, m[:4000])
                except Exception as e:
                    send_msg(chat_id, "Format: /logs USER_ID | Error: " + str(e))
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

        if not user_exists(user_id):
            get_user(user_id, user_name)
            if not is_group:
                send_msg(chat_id, "Heyy " + user_name + "! 😊 Main Anika — bolo!")
                return "ok", 200

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
