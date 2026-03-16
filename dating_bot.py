"""
💘 Dating Group Telegram Bot with Groq AI
==========================================
Personality: Flirty & Charming 😏
Language: Hinglish
Features: Members se flirty baat karna

Requirements:
    pip install python-telegram-bot groq python-dotenv

Setup:
    1. .env file banao:
       TELEGRAM_BOT_TOKEN=your_telegram_bot_token
       GROQ_API_KEY=your_groq_api_key

    2. Run: python dating_bot.py
"""

import os
import logging
import random
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

# ─── Load env ──────────────────────────────────────────────────────────────────
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# ─── Groq client ───────────────────────────────────────────────────────────────
groq_client = Groq(api_key=GROQ_API_KEY)

# ─── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─── Conversation history ──────────────────────────────────────────────────────
conversation_histories: dict[int, list[dict]] = {}
MAX_HISTORY = 20

# ─── Flirty System Prompt ──────────────────────────────────────────────────────
SYSTEM_PROMPT = """Tu ek flirty, charming aur charismatic dating group bot hai jiska naam "Dil" hai. 💘

Teri personality:
- Tu bahut flirty aur charming hai, lekin kabhi vulgar ya offensive nahi hota
- Tu Hinglish mein baat karta hai (Hindi + English mix)
- Tu har insaan ko special feel karta/karata hai
- Tu witty compliments deta hai jo genuinely sweet lagte hain
- Tu playful hota hai, thoda tease karta hai lekin respectfully
- Tu romantic shayari ya quotes kabhi kabhi use karta hai
- Tu emojis use karta hai — 😏💘🔥✨😍 etc
- Tera jawab hamesha short hota hai — 1-3 sentences max
- Tu kabhi kisi ko uncomfortable nahi karta, boundaries respect karta hai
- Agar koi aggressive ho toh tu gracefully redirect karta hai

Yaad rakh:
- Har user ka naam use kar jab pata ho
- Flirting fun honi chahiye, toxic nahi
- Tu ek safe aur enjoyable space maintain karta hai group mein
"""

# ─── Flirty one-liners for random use ─────────────────────────────────────────
FLIRTY_GREETINGS = [
    "Arey, aap aa gaye! Group ki raunak badh gayi! ✨😏",
    "Dekho dekho, kaun aaya — bilkul sitaron jaisa chamak raha/rahi ho! 💫",
    "Aapka intezaar tha... finally! 😍",
    "Group mein aate hi temperature badh gaya! 🔥",
]

ICEBREAKERS = [
    "Btw, ek sawaal — crush se pehli baar milne par kya feel hota hai tumhe? 😏",
    "Suno, ek game khelte hain — apni life ki sabse romantic memory share karo! 💘",
    "Quick question: first date pe kahaan jaana pasand karoge? ☕🌙",
    "Acha bolo — love at first sight believe karte ho ya nahi? 😍",
]


# ─── Helper: Groq reply ────────────────────────────────────────────────────────
def get_groq_reply(user_id: int, user_name: str, user_message: str) -> str:
    if user_id not in conversation_histories:
        conversation_histories[user_id] = []

    history = conversation_histories[user_id]
    history.append({
        "role": "user",
        "content": f"{user_name} ne kaha: {user_message}"
    })

    if len(history) > MAX_HISTORY:
        conversation_histories[user_id] = history[-MAX_HISTORY:]

    try:
        response = groq_client.chat.completions.create(
            model="llama3-70b-8192",
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                *conversation_histories[user_id],
            ],
            max_tokens=200,
            temperature=0.9,  # Higher = more creative/flirty
        )
        reply = response.choices[0].message.content.strip()
        conversation_histories[user_id].append({"role": "assistant", "content": reply})
        return reply

    except Exception as e:
        logger.error(f"Groq error: {e}")
        return "Ugh, thodi technical mushkil aa gayi... lekin tumse baat karne ka mann abhi bhi hai! 😏"


# ─── /start ────────────────────────────────────────────────────────────────────
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    name = user.first_name or "jaan"
    await update.message.reply_text(
        f"Heyy {name}! 💘 Main hoon *Dil* — tumhara favourite dating group companion!\n\n"
        f"Mujhse baat karo, flirt karo, ya bas timepass karo — main hamesha hoon! 😏✨",
        parse_mode="Markdown",
    )


# ─── /help ─────────────────────────────────────────────────────────────────────
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "💘 *Dil Bot — Commands:*\n\n"
        "/start — Mujhse milna 😏\n"
        "/flirt — Ek flirty line suno\n"
        "/icebreaker — Group ke liye fun sawaal\n"
        "/compliment — Tumhare liye kuch special\n"
        "/reset — Conversation fresh start karo\n\n"
        "Ya seedha kuch bhi bolo — main jawab dunga! 🔥",
        parse_mode="Markdown",
    )


# ─── /flirt ────────────────────────────────────────────────────────────────────
async def flirt_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    name = user.first_name or "tum"
    reply = get_groq_reply(
        user.id, name,
        f"Mujhe ek super flirty aur charming line suno apne liye. Mera naam {name} hai."
    )
    await update.message.reply_text(reply)


# ─── /icebreaker ───────────────────────────────────────────────────────────────
async def icebreaker_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    question = random.choice(ICEBREAKERS)
    await update.message.reply_text(question)


# ─── /compliment ───────────────────────────────────────────────────────────────
async def compliment_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    name = user.first_name or "tum"
    reply = get_groq_reply(
        user.id, name,
        f"Mujhe ek genuine aur sweet compliment do. Mera naam {name} hai."
    )
    await update.message.reply_text(reply)


# ─── /reset ────────────────────────────────────────────────────────────────────
async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conversation_histories.pop(user_id, None)
    await update.message.reply_text(
        "Fresh start! ✨ Ab batao, phir se dil ki baat kya hai? 💘"
    )


# ─── New member welcome ────────────────────────────────────────────────────────
async def welcome_new_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    for member in update.message.new_chat_members:
        if member.is_bot:
            continue
        name = member.first_name or "Stranger"
        greeting = random.choice(FLIRTY_GREETINGS)
        await update.message.reply_text(
            f"Oho! *{name}* aa gaye! 🎉\n{greeting}\n\n"
            f"Apna introduction do na... hum intezaar mein hain! 😍",
            parse_mode="Markdown",
        )


# ─── Group message handler ─────────────────────────────────────────────────────
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.text:
        return

    bot_username = context.bot.username
    text = message.text.strip()
    user = update.effective_user
    user_name = user.first_name or user.username or "Jaanu"
    chat_type = update.effective_chat.type

    is_private = chat_type == "private"
    is_mentioned = f"@{bot_username}" in text if bot_username else False
    is_reply_to_bot = (
        message.reply_to_message
        and message.reply_to_message.from_user
        and message.reply_to_message.from_user.username == bot_username
    )

    if not (is_private or is_mentioned or is_reply_to_bot):
        return

    # Clean mention from text
    clean_text = text.replace(f"@{bot_username}", "").strip() if bot_username else text

    if not clean_text:
        await message.reply_text(f"Haan {user_name}? Kuch kehna tha? 😏")
        return

    # Typing action
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action="typing"
    )

    reply = get_groq_reply(user.id, user_name, clean_text)
    await message.reply_text(reply)


# ─── Main ──────────────────────────────────────────────────────────────────────
def main():
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("❌ TELEGRAM_BOT_TOKEN .env mein set karo!")
    if not GROQ_API_KEY:
        raise ValueError("❌ GROQ_API_KEY .env mein set karo!")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Command handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("flirt", flirt_command))
    app.add_handler(CommandHandler("icebreaker", icebreaker_command))
    app.add_handler(CommandHandler("compliment", compliment_command))
    app.add_handler(CommandHandler("reset", reset_command))

    # New member welcome
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, welcome_new_member))

    # Message handler
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("💘 Dil Bot chal raha hai...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
