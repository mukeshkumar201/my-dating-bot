"""
💘 Dating Group Telegram Bot
Flask + Telegram Webhook — Render Free
"""

import os
import logging
import random
from flask import Flask, request
from dotenv import load_dotenv
from groq import Groq
import telegram
from telegram import Update
import asyncio

load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY       = os.getenv("GROQ_API_KEY")
WEBHOOK_URL        = os.getenv("WEBHOOK_URL")
PORT               = int(os.getenv("PORT", 10000))

groq_client = Groq(api_key=GROQ_API_KEY)
bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)
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


def get_groq_reply(user_id, user_name, user_message):
    if user_id not in conversation_histories:
        conversation_histories[user_id] = []
    history = conversation_histories[user_id]
    history.append({"role": "user", "content": f"{user_name}: {user_message}"})
    if len(history) > MAX_HISTORY:
        conversation_histories[user_id] = history[-MAX_HISTORY:]
    try:
        response = groq_client.chat.completions.create(
            model="llama3-8b-8192",
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


async def process_update(update_data):
    update = Update.de_json(update_data, bot)
    message = update.message
    if not message:
        return

    chat_id   = message.chat.id
    text      = (message.text or "").strip()
    user      = message.from_user
    user_name = user.first_name or user.username or "Yaar"
    user_id   = user.id
    msg_id    = message.message_id

    if user.is_bot:
        return

    # New member welcome
    if message.new_chat_members:
        for member in message.new_chat_members:
            if not member.is_bot:
                name = member.first_name or "Stranger"
                greeting = random.choice(FLIRTY_GREETINGS)
                await bot.send_message(chat_id, f"Oho! *{name}* aa gaye! 🎉\n{greeting}\n\nApna introduction do na... 😍", parse_mode="Markdown")
        return

    if not text:
        return

    # Commands
    if text.startswith("/start"):
        await bot.send_message(chat_id, f"Heyy {user_name}! 💘 Main Anika hoon!\n\nTumse milke achha laga... bahut achha 😏\nBolo kya haal hai? 🥺", reply_to_message_id=msg_id)
        return
    if text.startswith("/help"):
        await bot.send_message(chat_id, "💘 Commands:\n\n/start — Mujhse milna 😏\n/flirt — Flirty line\n/icebreaker — Fun sawaal\n/compliment — Special\n/reset — Fresh start\n\nYa seedha bolo! 🔥")
        return
    if text.startswith("/flirt"):
        reply = get_groq_reply(user_id, user_name, f"Ek bold flirty line bolo. Mera naam {user_name} hai.")
        await bot.send_message(chat_id, reply, reply_to_message_id=msg_id)
        return
    if text.startswith("/icebreaker"):
        await bot.send_message(chat_id, random.choice(ICEBREAKERS))
        return
    if text.startswith("/compliment"):
        reply = get_groq_reply(user_id, user_name, f"Ek passionate compliment do. Mera naam {user_name} hai.")
        await bot.send_message(chat_id, reply, reply_to_message_id=msg_id)
        return
    if text.startswith("/reset"):
        conversation_histories.pop(user_id, None)
        await bot.send_message(chat_id, "Fresh start! ✨ Ab batao kya soch rahe ho? 😏", reply_to_message_id=msg_id)
        return

    # Har message pe reply
    await bot.send_chat_action(chat_id, "typing")
    reply = get_groq_reply(user_id, user_name, text)
    await bot.send_message(chat_id, reply, reply_to_message_id=msg_id)


@app.route("/webhook", methods=["POST"])
def webhook():
    update_data = request.get_json()
    asyncio.run(process_update(update_data))
    return "ok", 200


@app.route("/", methods=["GET"])
def index():
    return "Anika bot alive! 💘", 200


def set_webhook():
    asyncio.run(bot.set_webhook(url=f"{WEBHOOK_URL}/webhook"))
    logger.info(f"Webhook set: {WEBHOOK_URL}/webhook")


if __name__ == "__main__":
    set_webhook()
    logger.info("💘 Anika Bot Flask server chal rahi hai...")
    app.run(host="0.0.0.0", port=PORT)
