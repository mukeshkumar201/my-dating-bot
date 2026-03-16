"""
💘 Dating Group Telegram Bot with Groq AI
==========================================
Webhook mode + Keep-Alive Server
Render Free Web Service ke liye
"""

import os
import logging
import random
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from dotenv import load_dotenv
from groq import Groq
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY       = os.getenv("GROQ_API_KEY")
WEBHOOK_URL        = os.getenv("WEBHOOK_URL")
PORT               = int(os.getenv("PORT", 10000))

groq_client = Groq(api_key=GROQ_API_KEY)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

conversation_histories: dict[int, list[dict]] = {}
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
- Bold flirting — lekin graceful rehna
"""

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


# ─── Keep-Alive HTTP Server ────────────────────────────────────
class KeepAliveHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Anika bot alive!")
    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()
    def log_message(self, format, *args):
        pass

def run_keep_alive():
    server = HTTPServer(("0.0.0.0", PORT), KeepAliveHandler)
    logger.info(f"Keep-alive server port {PORT} pe chal raha hai")
    server.serve_forever()


# ─── Groq reply ───────────────────────────────────────────────
def get_groq_reply(user_id: int, user_name: str, user_message: str) -> str:
    if user_id not in conversation_histories:
        conversation_histories[user_id] = []

    history = conversation_histories[user_id]
    history.append({"role": "user", "content": f"{user_name}: {user_message}"})

    if len(history) > MAX_HISTORY:
        conversation_histories[user_id] = history[-MAX_HISTORY:]

    try:
        response = groq_client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                *conversation_histories[user_id],
            ],
            max_tokens=150,
            temperature=0.95,
        )
        reply = response.choices[0].message.content.strip()
        conversation_histories[user_id].append({"role": "assistant", "content": reply})
        return reply
    except Exception as e:
        logger.error(f"Groq error: {e}")
        return "Yaar thodi net problem hai... lekin tumse baat karne ka mann hai 😘"


# ─── Commands ──────────────────────────────────────────────────
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.effective_user.first_name or "tum"
    await update.message.reply_text(
        f"Heyy {name}! 💘 Main Anika hoon!\n\nTumse milke achha laga... bahut achha 😏\nBolo kya haal hai? 🥺"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💘 Commands:\n\n"
        "/start — Mujhse milna 😏\n"
        "/flirt — Flirty line suno\n"
        "/icebreaker — Fun sawaal\n"
        "/compliment — Tumhare liye kuch special\n"
        "/reset — Fresh start\n\n"
        "Ya seedha kuch bhi bolo — main hamesha hoon! 🔥"
    )

async def flirt_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    name = user.first_name or "tum"
    reply = get_groq_reply(user.id, name, f"Ek bahut bold aur flirty line bolo. Mera naam {name} hai.")
    await update.message.reply_text(reply)

async def icebreaker_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(random.choice(ICEBREAKERS))

async def compliment_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    name = user.first_name or "tum"
    reply = get_groq_reply(user.id, name, f"Ek bahut passionate aur bold compliment do. Mera naam {name} hai.")
    await update.message.reply_text(reply)

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conversation_histories.pop(update.effective_user.id, None)
    await update.message.reply_text("Fresh start! ✨ Ab batao... kya soch rahe ho mere baare mein? 😏")

async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        if member.is_bot:
            continue
        name = member.first_name or "Stranger"
        await update.message.reply_text(
            f"Oho! *{name}* aa gaye! 🎉\n{random.choice(FLIRTY_GREETINGS)}\n\nApna introduction do na... 😍",
            parse_mode="Markdown",
        )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.text:
        return
    user = update.effective_user
    if user.is_bot:
        return
    user_name = user.first_name or user.username or "Yaar"
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")
    reply = get_groq_reply(user.id, user_name, message.text.strip())
    await message.reply_text(reply)


# ─── Main ──────────────────────────────────────────────────────
def main():
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN set karo!")
    if not GROQ_API_KEY:
        raise ValueError("GROQ_API_KEY set karo!")
    if not WEBHOOK_URL:
        raise ValueError("WEBHOOK_URL set karo!")

    # Keep-alive alag thread mein
    t = threading.Thread(target=run_keep_alive)
    t.daemon = True
    t.start()

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("flirt", flirt_command))
    app.add_handler(CommandHandler("icebreaker", icebreaker_command))
    app.add_handler(CommandHandler("compliment", compliment_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_member))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("💘 Anika Bot chal rahi hai...")
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        webhook_url=f"{WEBHOOK_URL}/webhook",
    )


if __name__ == "__main__":
    main()
