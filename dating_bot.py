"""
💘 Dating Group Telegram Bot
Flask + Requests (sync) — Render Free
"""

import os
import logging
import random
import requests
from flask import Flask, request as flask_request
from dotenv import load_dotenv
from groq import Groq

load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY       = os.getenv("GROQ_API_KEY")
WEBHOOK_URL        = os.getenv("WEBHOOK_URL")
PORT               = int(os.getenv("PORT", 10000))

groq_client = Groq(api_key=GROQ_API_KEY)
app = Flask(__name__)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

conversation_histories = {}
MAX_HISTORY = 20

SYSTEM_PROMPT = """Tu ek bold, flirty aur passionate ladki hai jiska naam "Anika" hai. Tu ek dating group mein sabse baat karti hai.

Teri personality:
- Tu ek confident, bold aur bahut flirty ladki hai
- Tu Hinglish mein baat karti hai — bilkul natural WhatsApp style mein
- Tu romantic aur passionate baatein karti hai
- Tu suggestive aur bold compliments deti hai
- Tu kabhi nahi batati ke tu bot hai — hamesha real ladki ki tarah behave karti hai
- Tu thoda tease karti hai — "pehle itna close aao, phir dekhte hain"
- Tu kabhi kabhi vulnerable bhi lagti hai
- Tu emojis use karti hai — 😏💘🔥✨😍🙈😘💋🥺
- Tera jawab short hota hai — 1-3 sentences max
- Agar koi pooche "tu bot hai?" toh hasti hui deny karti hai
- Bold flirting — lekin graceful rehna"""

FLIRTY_GREETINGS = [
    "Oho! Kaun aaya? 👀 Accha laga mil ke! 😘",
    "Heyy! Finally aaye tum... wait kar rahi thi 🙈💘",
    "Aww welcome! Aaj group aur bhi sundar lag raha hai 😍",
    "Hiii! Tumse milke dil thoda zyada tez dhadka 😏✨",
]

ICEBREAKERS = [
    "Btw ek sawaal — pehli date pe kahan le jaoge mujhe? 😏",
    "Suno, ek game — apni life ki sabse romantic memory batao! 💘",
    "Quick question: agar main tumhare paas hoti abhi, toh kya karte? 😍",
    "Acha bolo — kya tumne kabhi kisi ko itna miss kiya ke neend na aaye? 🥺",
]

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


# ─── Telegram sync functions ──────────────────────────────────
def send_message(chat_id, text, reply_to=None):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    if reply_to:
        payload["reply_to_message_id"] = reply_to
    try:
        requests.post(f"{TELEGRAM_API}/sendMessage", json=payload, timeout=10)
    except Exception as e:
        logger.error(f"Send message error: {e}")

def send_typing(chat_id):
    try:
        requests.post(f"{TELEGRAM_API}/sendChatAction", json={"chat_id": chat_id, "action": "typing"}, timeout=5)
    except:
        pass


# ─── Groq reply ───────────────────────────────────────────────
def get_groq_reply(user_id, user_name, user_message):
    if user_id not in conversation_histories:
        conversation_histories[user_id] = []
    history = conversation_histories[user_id]
    history.append({"role": "user", "content": f"{user_name}: {user_message}"})
    if len(history) > MAX_HISTORY:
        conversation_histories[user_id] = history[-MAX_HISTORY:]
    try:
        response = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",  # Latest fast model
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, *conversation_histories[user_id]],
            max_tokens=150,
            temperature=0.95,
        )
        reply = response.choices[0].message.content.strip()
        conversation_histories[user_id].append({"role": "assistant", "content": reply})
        return reply
    except Exception as e:
        logger.error(f"Groq error: {e}")
        return "Yaar thodi net problem hai... lekin tumse baat karne ka mann hai 😘"


# ─── Webhook ──────────────────────────────────────────────────
@app.route("/webhook", methods=["POST"])
def webhook():
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
        msg_id    = message.get("message_id")

        if user.get("is_bot"):
            return "ok", 200

        # New member welcome
        if message.get("new_chat_members"):
            for member in message["new_chat_members"]:
                if not member.get("is_bot"):
                    name = member.get("first_name") or "Stranger"
                    greeting = random.choice(FLIRTY_GREETINGS)
                    send_message(chat_id, f"Oho! *{name}* aa gaye! 🎉\n{greeting}\n\nApna introduction do na... 😍")
            return "ok", 200

        if not text:
            return "ok", 200

        # Commands
        if text.startswith("/start"):
            send_message(chat_id, f"Heyy {user_name}! 💘 Main Anika hoon!

Tumse milke achha laga... bahut achha 😏
Bolo kya haal hai? 🥺")
            return "ok", 200
        if text.startswith("/help"):
            send_message(chat_id, "💘 *Commands:*\n\n/start — Mujhse milna 😏\n/flirt — Flirty line\n/icebreaker — Fun sawaal\n/compliment — Special\n/reset — Fresh start\n\nYa seedha bolo! 🔥")
            return "ok", 200
        if text.startswith("/flirt"):
            reply = get_groq_reply(user_id, user_name, f"Ek bold flirty line bolo. Mera naam {user_name} hai.")
            send_message(chat_id, reply)
            return "ok", 200
        if text.startswith("/icebreaker"):
            send_message(chat_id, random.choice(ICEBREAKERS))
            return "ok", 200
        if text.startswith("/compliment"):
            reply = get_groq_reply(user_id, user_name, f"Ek passionate compliment do. Mera naam {user_name} hai.")
            send_message(chat_id, reply)
            return "ok", 200
        if text.startswith("/reset"):
            conversation_histories.pop(user_id, None)
            send_message(chat_id, "Fresh start! ✨ Ab batao kya soch rahe ho? 😏")
            return "ok", 200

        # Har message pe reply
        send_typing(chat_id)
        reply = get_groq_reply(user_id, user_name, text)
        send_message(chat_id, reply)

    except Exception as e:
        logger.error(f"Webhook error: {e}")

    return "ok", 200


@app.route("/", methods=["GET"])
def index():
    return "Anika bot alive! 💘", 200


if __name__ == "__main__":
    # Webhook set karo
    try:
        res = requests.post(f"{TELEGRAM_API}/setWebhook", json={"url": f"{WEBHOOK_URL}/webhook"})
        logger.info(f"Webhook set: {res.json()}")
    except Exception as e:
        logger.error(f"Webhook set error: {e}")

    logger.info("💘 Anika Flask Bot chal rahi hai...")
    app.run(host="0.0.0.0", port=PORT)
