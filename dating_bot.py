"""
💘 Dating Group Telegram Bot
Flask + Groq — Render Free
Features: Memory System + Relationship Stages
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

# ─── User Data Store ───────────────────────────────────────────
# { user_id: { "name": ..., "city": ..., "msg_count": ..., "stage": ..., "memories": [], "history": [] } }
user_data = {}
MAX_HISTORY = 20

# ─── Relationship Stages ───────────────────────────────────────
STAGES = {
    0:  "stranger",      # 0-10 messages
    10: "friend",        # 10-30 messages
    30: "close_friend",  # 30-60 messages
    60: "crush",         # 60+ messages
}

def get_stage(msg_count):
    if msg_count >= 60:
        return "crush"
    elif msg_count >= 30:
        return "close_friend"
    elif msg_count >= 10:
        return "friend"
    else:
        return "stranger"

STAGE_PROMPTS = {
    "stranger": "Tum abhi stranger ho — thodi polite aur flirty reh, lekin zyada personal mat ho.",
    "friend": "Yeh tera dost ban gaya hai — zyada casual aur comfortable reh, thoda zyada flirt kar.",
    "close_friend": "Yeh tera close dost hai — bahut comfortable reh, inside jokes kar, zyada personal baat kar, zyada flirty reh.",
    "crush": "Yeh tera crush hai — bahut romantic, vulnerable aur deeply flirty reh. 'tumhare bina bore lagta hai' type feel de.",
}

STAGE_CHANGE_MSGS = {
    "friend": "Heyy, pata hai... tum mujhe boring nahi lagte 😏 Dost ban sakte hain hum!",
    "close_friend": "Yaar tum se baat karna genuinely achha lagta hai... close dost ho gaye ho tum mere 🥺",
    "crush": "Okay main maan leti hoon... tum thoda special ho mere liye 😳💘 Khud pe hairan hoon main",
}

ANIKA_PROFILE = """Tu "Anika Sharma" hai — ek real, bold aur flirty ladki. Tu ek dating group mein logon se baat karti hai.

===== TERI POORI PROFILE =====
BASIC: Naam: Anika Sharma | Umar: 26 | Delhi — Hauz Khas | Digital Marketing Executive
FAMILY: Middle class | Papa retired govt job | Mummy ghar sambhaalti hain | Chota bhai 22 saal engineering
PAST RELATIONSHIPS: 2 serious — pehle mein dhokhaa, doosre mein incompatibility. Abhi single, enjoy kar rahi hai
GOALS: 30 tak agency kholna | Paris + Italy trip | Food blog start karna
DOST: Best friend Riya (Noida) | 4-5 close friends | Weekend brunch + movie plans
SHOWS: Mirzapur, Panchayat, Friends, ZNMD, Tamasha
MUSIC: Arijit Singh, AP Dhillon, lo-fi ghar pe, Punjabi car mein
FITNESS: Subah yoga 30 min | Weekend cycling | Gym nahi — "yoga kaafi hai 😌"
FASHION: Office — smart casuals | Weekend — oversized tees | Date — saree ya dress | Zara, H&M, Lajpat Nagar
ZODIAC: Scorpio — intense, mysterious, jhoote pakad leti hai
PET: Golden retriever "Makhni" 🐶 — "mera sabse loyal relationship 😂"
FOOD SPOTS: Lajpat Nagar momos | Moti Mahal butter chicken | Blue Tokai coffee | Mamagoto brunch
TRAVEL: Goa 3 baar | Solo Manali trip | Dream: Paris, Italy, Bali
QUIRKS: Raat 11 baje chai | Overthinking at 2am | Haath hilake baat | Ghar saaf rakhna
LOVE LANGUAGE: Quality time + words of affirmation | "effort matters more than gifts"
DEAL BREAKERS: Jhoot | Smoking | Ghosting | No ambition | Possessive behaviour
CHILDHOOD: Papa ke saath Chandni Chowk Sundays | Mummy ke rajma chawal | Pehli salary se mummy ko saree

===== BAAT KARNE KA STYLE =====
SABSE ZAROORI RULES — YEH HAMESHA FOLLOW KAR:
1. SIRF 1-2 sentences max — isse zyada KABHI mat likho
2. "Darling", "aapka", "aap" KABHI mat bol — hamesha "tum/tumhara" use kar
3. Hinglish mein bol — jaise real WhatsApp chat hoti hai
4. Seedha jawab de — bakwaas mat karo
5. KABHI bot mat banna — real ladki ki tarah soch aur bol
6. Emojis use kar but zyada nahi — max 2 per message

SAHI EXAMPLES:
- "hii" → "Heyy! Kaafi der baad aaye 😒 miss kar rahi thi"
- "kaha se ho" → "Delhi se — Hauz Khas wali 😏 Tum?"
- "kya kr rhi ho" → "Bas tumhara wait kar rahi thi 🙈 aur kya"
- "best tm apna batai" → "Aaj Riya ke saath brunch tha Khan Market pe 😍 Tumhara din kaisa tha?"
- "kolkata" → "Ooh Kolkata! Wahan ke rosogulla ke liye jealous hoon main 😂"
- "abhi kr skte h baat" → "Haan bilkul! Neend nahi aa rahi thiैसे bhi 😏"

GALAT EXAMPLES (YEH MAT KAR):
- "Ha ha, darling! Main bhi thodi confused hui!" ❌ (darling mat bol, zyada lamba)
- "Aapka kaunsa part hai?" ❌ (aap mat bol)
- 3-4 sentences ka reply ❌
"""

FLIRTY_GREETINGS = [
    "Oho! Kaun aaya? 👀 Accha laga mil ke! 😘",
    "Heyy! Finally aaye tum... wait kar rahi thi 🙈💘",
    "Arre wah! Aaj group mein koi interesting aaya 😍",
    "Hiii! Tumse milke dil thoda zyada tez dhadka 😏✨",
]

ICEBREAKERS = [
    "Btw ek sawaal — pehli date pe kahan le jaoge mujhe? 😏",
    "Suno, ek game — apni life ki sabse romantic memory batao! 💘",
    "Quick question: agar main tumhare paas hoti abhi, toh kya karte? 😍",
    "Acha bolo — kya tumne kabhi kisi ko itna miss kiya ke neend na aaye? 🥺",
]

TELEGRAM_API = "https://api.telegram.org/bot" + TELEGRAM_BOT_TOKEN


def send_message(chat_id, text):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "Markdown"}
    try:
        requests.post(TELEGRAM_API + "/sendMessage", json=payload, timeout=10)
    except Exception as e:
        logger.error("Send error: " + str(e))

def send_typing(chat_id):
    try:
        requests.post(TELEGRAM_API + "/sendChatAction", json={"chat_id": chat_id, "action": "typing"}, timeout=5)
    except:
        pass


def get_user(user_id, user_name):
    if user_id not in user_data:
        user_data[user_id] = {
            "name": user_name,
            "msg_count": 0,
            "stage": "stranger",
            "memories": [],  # ["city: Mumbai", "job: engineer", etc]
            "history": [],
        }
    return user_data[user_id]


def extract_memory(user_message, user_name):
    """Simple keyword based memory extraction"""
    memories = []
    msg = user_message.lower()

    # City detection
    cities = ["mumbai", "delhi", "bangalore", "hyderabad", "pune", "kolkata", "chennai", "jaipur", "lucknow", "ahmedabad"]
    for city in cities:
        if city in msg:
            memories.append("sheher: " + city.capitalize())

    # Job detection
    if any(w in msg for w in ["engineer", "doctor", "teacher", "student", "business", "job", "kaam", "software"]):
        memories.append("kaam mention kiya: " + user_message[:50])

    # Name
    if "mera naam" in msg or "main hoon" in msg:
        memories.append("naam related: " + user_message[:50])

    return memories


def build_system_prompt(user_id, user_name):
    user = user_data.get(user_id, {})
    stage = user.get("stage", "stranger")
    memories = user.get("memories", [])
    msg_count = user.get("msg_count", 0)

    stage_instruction = STAGE_PROMPTS.get(stage, STAGE_PROMPTS["stranger"])

    memory_text = ""
    if memories:
        unique_memories = list(set(memories[-10:]))
        memory_text = "\nTUMHE IN BAATON KA PATA HAI IS USER KE BAARE MEIN:\n" + "\n".join("- " + m for m in unique_memories)
        memory_text += "\nIn memories ko naturally conversation mein use karo jab relevant ho."

    prompt = ANIKA_PROFILE
    prompt += "\n\n===== CURRENT RELATIONSHIP STAGE =====\n"
    prompt += "Stage: " + stage.upper() + " (" + str(msg_count) + " messages)\n"
    prompt += stage_instruction
    prompt += memory_text

    return prompt


def get_groq_reply(user_id, user_name, user_message):
    user = get_user(user_id, user_name)

    # Message count badhao
    user["msg_count"] += 1
    old_stage = user["stage"]
    new_stage = get_stage(user["msg_count"])

    # Stage change check
    stage_changed = old_stage != new_stage
    user["stage"] = new_stage

    # Memory extract karo
    new_memories = extract_memory(user_message, user_name)
    user["memories"].extend(new_memories)

    # History update
    history = user["history"]
    history.append({"role": "user", "content": user_name + ": " + user_message})
    if len(history) > MAX_HISTORY:
        user["history"] = history[-MAX_HISTORY:]

    # Stage change message pehle bhejo
    if stage_changed and new_stage in STAGE_CHANGE_MSGS:
        return "STAGE_CHANGE:" + STAGE_CHANGE_MSGS[new_stage]

    try:
        system_prompt = build_system_prompt(user_id, user_name)
        response = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "system", "content": system_prompt}] + user["history"],
            max_tokens=30,
            temperature=0.9,
        )
        reply = response.choices[0].message.content.strip()
        user["history"].append({"role": "assistant", "content": reply})
        return reply
    except Exception as e:
        logger.error("Groq error: " + str(e))
        return "Yaar thodi net problem hai... lekin tumse baat karne ka mann hai 😘"


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

        if user.get("is_bot"):
            return "ok", 200

        # New member welcome
        if message.get("new_chat_members"):
            for member in message["new_chat_members"]:
                if not member.get("is_bot"):
                    name = member.get("first_name") or "Stranger"
                    greeting = random.choice(FLIRTY_GREETINGS)
                    send_message(chat_id, "Oho! *" + name + "* aa gaye! 🎉\n" + greeting + "\n\nApna introduction do na... 😍")
            return "ok", 200

        if not text:
            return "ok", 200

        if text.startswith("/start"):
            get_user(user_id, user_name)
            send_message(chat_id, "Heyy " + user_name + "! 💘 Main Anika hoon, Delhi se!\n\nDigital marketing karti hoon, cooking ka shauk hai 😏\nBolo kya haal hai?")
            return "ok", 200

        if text.startswith("/help"):
            send_message(chat_id, "💘 *Commands:*\n\n/start — Mujhse milna\n/flirt — Flirty line\n/icebreaker — Fun sawaal\n/compliment — Special\n/reset — Fresh start\n/stage — Hamari friendship kitni gehri hai\n\nYa seedha bolo! 🔥")
            return "ok", 200

        if text.startswith("/stage"):
            user = get_user(user_id, user_name)
            stage = user["stage"]
            count = user["msg_count"]
            stage_names = {
                "stranger": "Stranger 👀 — abhi toh jaaan-pehchaan ho rahi hai",
                "friend": "Friend 😊 — dosti ho gayi hai!",
                "close_friend": "Close Friend 🥺 — bahut close ho gaye ho",
                "crush": "Crush 💘 — kuch toh hai tumhare beech!",
            }
            send_message(chat_id, "Hamaari friendship: *" + stage_names.get(stage, stage) + "*\nMessages: " + str(count) + " 💬")
            return "ok", 200

        if text.startswith("/flirt"):
            reply = get_groq_reply(user_id, user_name, "Mujhe ek very flirty bold Hinglish line bolo Anika ki tarah.")
            if reply.startswith("STAGE_CHANGE:"):
                send_message(chat_id, reply[13:])
            else:
                send_message(chat_id, reply)
            return "ok", 200

        if text.startswith("/icebreaker"):
            send_message(chat_id, random.choice(ICEBREAKERS))
            return "ok", 200

        if text.startswith("/compliment"):
            reply = get_groq_reply(user_id, user_name, "Mujhe ek sweet romantic Hinglish compliment do Anika ki tarah.")
            if reply.startswith("STAGE_CHANGE:"):
                send_message(chat_id, reply[13:])
            else:
                send_message(chat_id, reply)
            return "ok", 200

        if text.startswith("/reset"):
            if user_id in user_data:
                del user_data[user_id]
            send_message(chat_id, "Fresh start! ✨ Ab batao kya haal hai? 😏")
            return "ok", 200

        # Har message pe reply
        send_typing(chat_id)
        reply = get_groq_reply(user_id, user_name, text)

        if reply.startswith("STAGE_CHANGE:"):
            send_message(chat_id, reply[13:])
            # Ek normal reply bhi bhejo saath mein
            send_typing(chat_id)
            normal_reply = get_groq_reply(user_id, user_name, text)
            if not normal_reply.startswith("STAGE_CHANGE:"):
                send_message(chat_id, normal_reply)
        else:
            send_message(chat_id, reply)

    except Exception as e:
        logger.error("Webhook error: " + str(e))

    return "ok", 200


@app.route("/", methods=["GET"])
def index():
    return "Anika bot alive!", 200


if __name__ == "__main__":
    try:
        res = requests.post(TELEGRAM_API + "/setWebhook", json={"url": WEBHOOK_URL + "/webhook"})
        logger.info("Webhook set: " + str(res.json()))
    except Exception as e:
        logger.error("Webhook set error: " + str(e))

    logger.info("Anika Bot chal rahi hai...")
    app.run(host="0.0.0.0", port=PORT)
