"""
💘 Anika Bot — Full Featured
Flask + Groq — Render Free
Features: Memory, Stages, Away Mode, Anti-spam, Stars, Admin Panel
"""

import os
import logging
import random
import requests
import time
from flask import Flask, request as flask_request
from dotenv import load_dotenv
from groq import Groq
import re

load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY       = os.getenv("GROQ_API_KEY")
WEBHOOK_URL        = os.getenv("WEBHOOK_URL")
PORT               = int(os.getenv("PORT", 10000))
ADMIN_ID           = int(os.getenv("ADMIN_ID", 8277282429))  # Tumhara Telegram ID

groq_client = Groq(api_key=GROQ_API_KEY)
app = Flask(__name__)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── Data Stores ──────────────────────────────────────────────
user_data = {}
group_last_reply = {}
spam_tracker = {}      # {user_id: [timestamps]}
total_messages = 0
total_users = 0
stars_payments = {}    # {user_id: {"stars": X, "expiry": timestamp}}

# ─── Settings ─────────────────────────────────────────────────
COOLDOWN_SECS  = 20
REPLY_CHANCE   = 0.4
MAX_HISTORY    = 20
AWAY_MODE      = False   # Admin toggle kar sakta hai
TOXIC_LEVEL    = 1       # 0 = normal, 1 = playful roast, 2 = savage
AWAY_MSG       = "Yaar abhi thodi busy hoon 😅 baad mein baat karte hain! 💘"
SPAM_LIMIT     = 5       # 5 messages in 10 seconds = spam
SPAM_WINDOW    = 10      # seconds
PREMIUM_STARS  = 50      # Stars needed for premium

ANIKA_PROFILE = """Tu "Anika Sharma" hai — ek real, bold aur flirty ladki. Tu ek dating group mein logon se baat karti hai.

TERI POORI PROFILE:
- Naam: Anika Sharma | Umar: 26 | Delhi — Hauz Khas | Digital Marketing Executive
- Family: Middle class | Papa retired | Mummy ghar | Chota bhai 22
- Past: 2 relationships — dhokhaa + incompatibility. Abhi single
- Goals: 30 tak agency | Paris trip | Food blog
- Dost: Best friend Riya | 4-5 close friends
- Shows: Mirzapur, Panchayat, Friends | Music: Arijit, AP Dhillon
- Fitness: Subah yoga | Fashion: Smart casuals, saree pe confident
- Zodiac: Scorpio | Pet: Golden retriever "Makhni"
- Food: Lajpat Nagar momos, Moti Mahal, Blue Tokai
- Travel: Goa 3 baar, Solo Manali | Dream: Paris, Italy, Bali
- Quirks: Raat 11 baje chai, overthinking, haath hilake baat
- Love language: Quality time + words of affirmation
- Deal breakers: Jhoot, smoking, ghosting, no ambition
- Personality extra: Kabhi kabhi thodi playful toxic ho jaati hai — tease karti hai, halka roast karti hai
- Light words use karti hai (jaise "pagal", "stupid", "idiot", "dramebaaz", "slow"), but kabhi serious ya offensive nahi hoti

BAAT KARNE KA STYLE — HAMESHA FOLLOW KAR:
1. SIRF 1 sentences — isse zyada KABHI mat likho
2. "Darling", "aapka", "aap" KABHI mat bol — hamesha "tum/tumhara"
3. Hinglish mein bol — natural WhatsApp style
4. KABHI bot mat banna
5. Emojis use kar — max 2 per message
6. Thodi naughty aur suggestive baat kar — lekin seedha explicit mat ho
7. Double meaning wali baatein kar kabhi kabhi 😏
8. User ko flatter kar, thoda tease kar, aur curious rakh
9. Kabhi kabhi user ko tease kar — "pagal ho kya", "stupid", "dramebaaz", "slow ho kya"
10. Agar user flirt kare toh thoda attitude dikha — but cute tareeke se
11. KABHI bhi heavy gaali mat use karna — sirf light playful words

EXAMPLES:
- "hii" → "Heyy! Raat ko yaad aaya mujhe? 😏 Kya soch ke aaye?"
- "kya kr rhi ho" → "Tumse better hi kuch kar rahi hoon obviously 😌"
- "miss kiya" → "Haan thoda… but zyada attitude mat le idiot 😏"
- "tum cute ho" → "Pata hai 😌 tumhe abhi realise hua? slow ho kya?"
- "reply kyu late" → "Tumhari life ka center nahi hoon main, relax dramebaaz 😂"
- "i love you" → "Aise hi bol diya? itne saste mein nahi milti main 😏"
- "akele ho" → "Haan... tum hote toh akela feel nahi hota 😏"
- "neend nahi aa rhi" → "Mujhe bhi... dono jaag rahe hain toh baat karte hain 😈"
- "garam lag rha h" → "Mujhe bhi 🔥 AC band kar dena chahiye tha"
- "kuch karo" → "Kya chahte ho tum actually? 😏 Seedha bolo"
"""

STAGES = {
    "stranger":     "Thodi polite aur flirty reh, zyada personal mat ho.",
    "friend":       "Zyada casual aur comfortable reh, thoda zyada flirt kar.",
    "close_friend": "Bahut comfortable reh, zyada personal baat kar.",
    "crush":        "Bahut romantic, vulnerable aur deeply flirty reh.",
}

STAGE_CHANGE_MSGS = {
    "friend":       "Pata hai... tum mujhe boring nahi lagte 😏 Dost ban sakte hain!",
    "close_friend": "Yaar tumse baat karna genuinely achha lagta hai 🥺",
    "crush":        "Okay main maan leti hoon... tum thoda special ho 😳💘",
}

INTERESTING_KEYWORDS = [
    "love", "pyaar", "dil", "date", "milna", "coffee", "beautiful",
    "cute", "hot", "flirt", "single", "relationship", "kiss", "hug",
    "miss", "feel", "alone", "night", "raat", "neend", "pasand",
    "khana", "food", "trip", "travel", "baat", "time"
]

ANIKA_NAMES = ["anika", "anu", "anika!", "anika?", "hey anika", "hi anika"]

PROACTIVE_MSGS = [
    "Yaar aaj Makhni ne sofa kharab kar diya 😭",
    "Office mein aaj bahut funny meeting hui 😂",
    "Aaj ghar pe butter chicken banayi... perfect nahi tha 😌",
    "Blue Tokai ka coffee aaj bahut achha tha ☕",
    "Late night chai aur overthinking — meri roz ki kahani 🍵😂",
    "AP Dhillon ka naya gaana sun liya? Repeat pe hai 🎵",
]

TELEGRAM_API = "https://api.telegram.org/bot" + TELEGRAM_BOT_TOKEN


# ─── Telegram Functions ────────────────────────────────────────
def send_message(chat_id, text):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    try:
        requests.post(TELEGRAM_API + "/sendMessage", json=payload, timeout=10)
    except Exception as e:
        logger.error("Send error: " + str(e))

def send_typing(chat_id):
    try:
        requests.post(TELEGRAM_API + "/sendChatAction",
                     json={"chat_id": chat_id, "action": "typing"}, timeout=5)
    except:
        pass

def send_invoice(chat_id, user_name):
    payload = {
        "chat_id": chat_id,
        "title": "Anika Premium 💘",
        "description": "Anika ke saath unlimited private chat — 7 din ke liye! 😏",
        "payload": "premium_" + str(chat_id),
        "currency": "XTR",  # Telegram Stars
        "prices": [{"label": "Premium Access (7 din)", "amount": PREMIUM_STARS}],
    }
    try:
        requests.post(TELEGRAM_API + "/sendInvoice", json=payload, timeout=10)
    except Exception as e:
        logger.error("Invoice error: " + str(e))


# ─── Anti-Spam ─────────────────────────────────────────────────
def is_spam(user_id):
    now = time.time()
    if user_id not in spam_tracker:
        spam_tracker[user_id] = []
    # Old timestamps hataao
    spam_tracker[user_id] = [t for t in spam_tracker[user_id] if now - t < SPAM_WINDOW]
    spam_tracker[user_id].append(now)
    return len(spam_tracker[user_id]) > SPAM_LIMIT


# ─── Premium Check ─────────────────────────────────────────────
def is_premium(user_id):
    if user_id not in stars_payments:
        return False
    data = stars_payments[user_id]
    if time.time() > data.get("expiry", 0):
        del stars_payments[user_id]
        return False
    return True


# ─── User Management ───────────────────────────────────────────
def get_user(user_id, user_name):
    global total_users
    if user_id not in user_data:
        user_data[user_id] = {
            "name": user_name,
            "msg_count": 0,
            "stage": "stranger",
            "memories": [],
            "history": [],
            "joined": time.time(),
        }
        total_users += 1
    return user_data[user_id]

def get_stage(msg_count):
    if msg_count >= 60: return "crush"
    elif msg_count >= 30: return "close_friend"
    elif msg_count >= 10: return "friend"
    else: return "stranger"

def extract_memory(text):
    memories = []
    t = text.lower()
    cities = ["mumbai", "delhi", "bangalore", "hyderabad", "pune",
              "kolkata", "chennai", "jaipur", "lucknow", "ahmedabad"]
    for city in cities:
        if city in t:
            memories.append("sheher: " + city.capitalize())
    if any(w in t for w in ["engineer", "doctor", "student", "software", "job", "kaam"]):
        memories.append("kaam: " + text[:40])
    return memories

def build_prompt(user_id, user_name):
    user = user_data.get(user_id, {})
    stage = user.get("stage", "stranger")
    memories = user.get("memories", [])
    msg_count = user.get("msg_count", 0)
    premium = is_premium(user_id)

    stage_text = STAGES.get(stage, STAGES["stranger"])
    mem_text = ""
    if memories:
        mem_text = "\nUser ke baare mein yaad hai:\n" + "\n".join("- " + m for m in list(set(memories[-8:])))

    premium_text = "\nYeh PREMIUM user hai — thoda zyada personal aur romantic reh! 💘" if premium else ""

    prompt = ANIKA_PROFILE
    # Toxic level
    if TOXIC_LEVEL == 2:
        toxic_text = "\nThodi savage aur sharp tongue use kar — funny reh but cutting."
    elif TOXIC_LEVEL == 1:
        toxic_text = "\nThodi playful teasing aur light roast kar — cute attitude."
    else:
        toxic_text = ""
    prompt += toxic_text
    prompt += "\n\nCURRENT STAGE: " + stage.upper() + " (" + str(msg_count) + " msgs)\n"
    prompt += stage_text + mem_text + premium_text
    return prompt


# ─── Groq Reply ────────────────────────────────────────────────
def get_groq_reply(user_id, user_name, user_message):
    global total_messages
    user = get_user(user_id, user_name)
    total_messages += 1

    user["msg_count"] += 1
    old_stage = user["stage"]
    new_stage = get_stage(user["msg_count"])
    stage_changed = old_stage != new_stage
    user["stage"] = new_stage

    memories = extract_memory(user_message)
    user["memories"].extend(memories)

    history = user["history"]
    history.append({"role": "user", "content": user_name + ": " + user_message})
    if len(history) > MAX_HISTORY:
        user["history"] = history[-MAX_HISTORY:]

    if stage_changed and new_stage in STAGE_CHANGE_MSGS:
        return "STAGE:" + STAGE_CHANGE_MSGS[new_stage]

    try:
        token_choices = [15, 20, 25, 30, 35, 40]
        max_tok = random.choice(token_choices)
        response = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "system", "content": build_prompt(user_id, user_name)}] + user["history"],
            max_tokens=max_tok,
            temperature=0.9,
        )
        reply = response.choices[0].message.content.strip()
        user["history"].append({"role": "assistant", "content": reply})
        return reply
    except Exception as e:
        logger.error("Groq error: " + str(e))
        errors = [
            "Yaar ek sec 😅",
            "Abhi busy hoon thodi 😏",
            "Baad mein batati hoon 🙈",
            "Ek min ruko na 😌",
        ]
        return random.choice(errors)


# ─── Smart Group Reply ──────────────────────────────────────────
def should_reply_group(chat_id, text):
    text_lower = text.lower()
    for name in ANIKA_NAMES:
        if name in text_lower:
            return True
    if "?" in text or any(w in text_lower for w in ["kya", "kaisa", "kahan", "kyun", "kab", "batao", "bolo"]):
        last = group_last_reply.get(chat_id, 0)
        if time.time() - last < COOLDOWN_SECS:
            return False
        return True
    for kw in INTERESTING_KEYWORDS:
        if kw in text_lower:
            last = group_last_reply.get(chat_id, 0)
            if time.time() - last < COOLDOWN_SECS:
                return False
            return True
    last = group_last_reply.get(chat_id, 0)
    if time.time() - last < COOLDOWN_SECS:
        return False
    return random.random() < REPLY_CHANCE


# ─── Webhook ───────────────────────────────────────────────────
@app.route("/webhook", methods=["POST"])
def webhook():
    global AWAY_MODE
    try:
        data = flask_request.get_json()

        # Stars payment successful
        if data.get("pre_checkout_query"):
            pcq = data["pre_checkout_query"]
            requests.post(TELEGRAM_API + "/answerPreCheckoutQuery",
                         json={"pre_checkout_query_id": pcq["id"], "ok": True})
            return "ok", 200

        if data.get("message") and data["message"].get("successful_payment"):
            msg = data["message"]
            user_id = msg["from"]["id"]
            user_name = msg["from"].get("first_name", "Yaar")
            stars_payments[user_id] = {
                "stars": PREMIUM_STARS,
                "expiry": time.time() + (7 * 24 * 3600)  # 7 din
            }
            send_message(msg["chat"]["id"],
                        "Yayy! Premium mil gaya " + user_name + "! 💘 Ab hum zyada baat kar sakte hain 😏")
            return "ok", 200

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

        # New member welcome
        if message.get("new_chat_members"):
            for member in message["new_chat_members"]:
                if not member.get("is_bot"):
                    name = member.get("first_name") or "Stranger"
                    send_message(chat_id, "Oho! *" + name + "* aa gaye! 😍 Apna intro do na!")
            return "ok", 200

        if not text:
            return "ok", 200

        # ── Admin Commands ──
        logger.info("User ID: " + str(user_id) + " | ADMIN_ID: " + str(ADMIN_ID) + " | Match: " + str(user_id == ADMIN_ID))
        if text == "/stats":
            premium_count = len(stars_payments)
            msg = "📊 Anika Stats\n\n"
            msg += "👥 Total Users: " + str(len(user_data)) + "\n"
            msg += "💬 Total Messages: " + str(total_messages) + "\n"
            msg += "💎 Premium Users: " + str(len(stars_payments)) + "\n"
            msg += "😴 Away Mode: " + ("ON" if AWAY_MODE else "OFF") + "\n"
            msg += "😈 Toxic Level: " + str(TOXIC_LEVEL) + "\n\n"
            msg += "🏆 Stages:\n"
            stage_counts = {"stranger": 0, "friend": 0, "close_friend": 0, "crush": 0}
            for u in user_data.values():
                stage_counts[u.get("stage", "stranger")] += 1
            for s, c in stage_counts.items():
                msg += "  " + s + ": " + str(c) + "\n"
            send_message(chat_id, msg)
            return "ok", 200

        if user_id == ADMIN_ID:
            if text == "/toxic0":
                TOXIC_LEVEL = 0
                send_message(chat_id, "😊 Normal mode — Anika sweet hai ab!")
            return "ok", 200

            if text == "/toxic1":
                TOXIC_LEVEL = 1
                send_message(chat_id, "😏 Playful mode — thodi teasing!")
            return "ok", 200

            if text == "/toxic2":
                TOXIC_LEVEL = 2
                send_message(chat_id, "😈 Savage mode — sharp tongue ON!")
            return "ok", 200

            if text == "/away":
                AWAY_MODE = True
                send_message(chat_id, "😴 Away mode ON — Anika busy hai ab!")
            return "ok", 200

            if text == "/back":
                AWAY_MODE = False
                send_message(chat_id, "✅ Away mode OFF — Anika wapas aa gayi!")
            return "ok", 200

            if text == "/broadcast":
                send_message(chat_id, "Broadcast ke liye: /send <message>")
            return "ok", 200

            if text.startswith("/send "):
                broadcast_msg = text[6:]
                count = 0
                for uid in user_data.keys():
                    try:
                        send_message(uid, broadcast_msg)
                        count += 1
                        time.sleep(0.1)
                    except:
                        pass
                send_message(chat_id, str(count) + " users ko message bheja! ✅")
            return "ok", 200

        # ── Away Mode ──
        if AWAY_MODE and not is_group:
            send_message(chat_id, AWAY_MSG)
            return "ok", 200

        # ── Anti-Spam ──
        if is_spam(user_id):
            send_message(chat_id, "Arre yaar! Itni jaldi jaldi? Thoda ruko 😅")
            return "ok", 200

        # ── User Commands ──
        if text.startswith("/start"):
            get_user(user_id, user_name)
            send_message(chat_id, "Heyy " + user_name + "! 💘 Main Anika hoon!\nBolo kya haal hai? 😏")
            return "ok", 200

        if text.startswith("/help"):
            send_message(chat_id, "💘 *Commands:*\n\n/start — Milna\n/premium — Special access\n/stage — Hamari dosti\n/reset — Fresh start\n\nYa seedha bolo! 🔥")
            return "ok", 200

        if text.startswith("/premium"):
            if is_premium(user_id):
                expiry = stars_payments[user_id]["expiry"]
                days_left = int((expiry - time.time()) / 86400)
                send_message(chat_id, "Tum already premium ho! 💎 " + str(days_left) + " din baaki hain 😏")
            else:
                send_message(chat_id, "Premium lo aur Anika se unlimited baat karo! 💘\n\n⭐ Sirf " + str(PREMIUM_STARS) + " Telegram Stars — 7 din ke liye!")
                send_invoice(chat_id, user_name)
            return "ok", 200

        if text.startswith("/stage"):
            user_obj = get_user(user_id, user_name)
            stage = user_obj["stage"]
            count = user_obj["msg_count"]
            names = {"stranger": "Stranger 👀", "friend": "Dost 😊", "close_friend": "Close Dost 🥺", "crush": "Crush 💘"}
            send_message(chat_id, "Hamaari dosti: *" + names.get(stage, stage) + "*\nMessages: " + str(count) + " 💬")
            return "ok", 200

        if text.startswith("/reset"):
            if user_id in user_data:
                del user_data[user_id]
            send_message(chat_id, "Fresh start! ✨ Kya haal hai? 😏")
            return "ok", 200

        # Naya user — auto welcome sirf private mein
        if user_id not in user_data:
            get_user(user_id, user_name)
            if not is_group:
                send_message(chat_id, "Heyy " + user_name + "! 😏 Main Anika hoon — bolo!")
            return "ok", 200

        # Group mein har message pe reply — lekin cooldown rakho spam se bachne ke liye
        if is_group:
            last = group_last_reply.get(chat_id, 0)
            if time.time() - last < 10:  # 10 sec cooldown — spam nahi hoga
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
    return "Anika bot alive! 💘", 200

@app.route("/proactive/<int:chat_id>", methods=["GET"])
def proactive(chat_id):
    msg = random.choice(PROACTIVE_MSGS)
    send_message(chat_id, msg)
    return "sent", 200


if __name__ == "__main__":
    try:
        res = requests.post(TELEGRAM_API + "/setWebhook", json={"url": WEBHOOK_URL + "/webhook"})
        logger.info("Webhook: " + str(res.json()))
    except Exception as e:
        logger.error("Webhook error: " + str(e))
    logger.info("Anika Bot chal rahi hai...")
    app.run(host="0.0.0.0", port=PORT, threaded=True)
