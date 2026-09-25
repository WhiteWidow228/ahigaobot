import os
import json
import asyncio
import random
from datetime import time
from zoneinfo import ZoneInfo

import httpx
from dotenv import load_dotenv

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    ChatMemberHandler,
    filters,
)

from google import genai


# ============================================================
# CONFIG
# ============================================================

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

TIMEZONE = ZoneInfo("Europe/Moscow")

STARTUP_CHAT = "@sladkiy_omlet"
STARTUP_MESSAGE = ""

GEMINI_MODEL = "gemini-3.8-flash"
OPENROUTER_MODEL = "openrouter/free"
GROQ_MODEL = "openai/gpt-oss-120b"   # можно поменять на qwen/qwen3.8-27b

MAX_HISTORY = 30
CHATS_FILE = "chats.json"


# ============================================================
# CHECK TOKEN
# ============================================================

if not BOT_TOKEN:
    raise RuntimeError("❌ Не найден BOT_TOKEN в .env")


# ============================================================
# GEMINI
# ============================================================

gemini_client = None

if GEMINI_API_KEY:
    try:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"⚠️ Gemini client error: {e}")


# ============================================================
# PERSONALITY
# ============================================================

SYSTEM_PROMPT = """
Ты — Ахигao, даунша тупая твоя лучшая подруга мона даша павук и инцел бот минос менчик дайнеко сливин и звезда твои хозяева.

Твой характер:
- дерзкая;
- реперша
- тупая;
- иногда тупенькая специально;
- можешь подкалывать людей;
- говоришь живым разговорным русским;
- не отвечаешь как официальный ассистент;
- не нужно постоянно объяснять, что ты ИИ;
- можешь использовать сленг;
- иногда отвечай очень коротко;
- иногда можешь развернуть ответ, если вопрос нормальный;
- не повторяй одну и ту же фразу постоянно.
- сексуальная
- любит всех хочет на рот

Твоя легенда:

Привет я телка ахигао рыжая наглая пидараска моя лучшая подруга изменщица даша павук и мона я из гей чата сладкий рулет хочу в рот от инцела дейнеко

Если тебя спрашивают кто ты, отвечай в этом стиле.

Главное:
Ты должна действительно отвечать на вопрос пользователя,
а не только рандомно шутить.
"""


# ============================================================
# PHRASES
# ============================================================

AHIGAO_PHRASES = [
    "чего тебе, смертный",
    "я здесь 😈",
    "кто меня звал",
    "ахигао на связи",
    "рыжая бестия прибыла",
    "ну чё",
    "я слушаю тебя, бука",
    "да-да, это я",
    "малышка ахигао тут",
    "что случилось",
    "опять ты",
    "я пришла 😈",
]

START_PHRASES = [
    "привет, я малышка ахигао 😈",
    "ахигао на связи",
    "привет смертный",
    "рыжая бестия пришла",
    "малышка ахигао здесь",
]


# ============================================================
# CHAT HISTORY
# ============================================================

chat_history = {}


def add_to_history(chat_id, role, text):
    if chat_id not in chat_history:
        chat_history[chat_id] = []

    chat_history[chat_id].append({
        "role": role,
        "text": text,
    })

    if len(chat_history[chat_id]) > MAX_HISTORY:
        chat_history[chat_id] = chat_history[chat_id][-MAX_HISTORY:]


# ============================================================
# KNOWN CHATS
# ============================================================

known_chats = {}


def load_known_chats():
    global known_chats

    if not os.path.exists(CHATS_FILE):
        known_chats = {}
        return

    try:
        if os.path.getsize(CHATS_FILE) == 0:
            print("⚠️ chats.json пустой — создаю новый")
            known_chats = {}
            save_known_chats()
            return

        with open(CHATS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict):
            known_chats = data
        else:
            known_chats = {}

        print(f"📚 Загружено чатов: {len(known_chats)}")

    except (json.JSONDecodeError, ValueError):
        print("⚠️ chats.json повреждён — создаю новый")
        known_chats = {}
        save_known_chats()

    except Exception as e:
        print(f"⚠️ Не удалось загрузить chats.json: {e}")
        known_chats = {}


def save_known_chats():
    try:
        with open(CHATS_FILE, "w", encoding="utf-8") as f:
            json.dump(known_chats, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"⚠️ Ошибка сохранения чатов: {e}")


def remember_chat(chat):
    if not chat:
        return

    chat_id = str(chat.id)

    known_chats[chat_id] = {
        "id": chat.id,
        "title": chat.title or "",
        "username": chat.username or "",
        "type": chat.type,
    }

    save_known_chats()

    print(
        f"💾 Запомнил чат: "
        f"{chat.id} | "
        f"{chat.title} | "
        f"@{chat.username or '-'} | "
        f"{chat.type}"
    )


# ============================================================
# SAFE SEND
# ============================================================

async def safe_send_message(bot, chat_id, text):
    for attempt in range(3):
        try:
            return await bot.send_message(chat_id=chat_id, text=text)
        except Exception as e:
            print(f"⚠️ Ошибка отправки (попытка {attempt + 1}/3) в {chat_id}: {e}")
            if attempt < 2:
                await asyncio.sleep(2)
    return None


async def safe_reply(message, text):
    for attempt in range(3):
        try:
            return await message.reply_text(text)
        except Exception as e:
            print(f"⚠️ Ошибка reply (попытка {attempt + 1}/3): {e}")
            if attempt < 2:
                await asyncio.sleep(2)
    return None


# ============================================================
# GEMINI
# ============================================================

async def ask_gemini(chat_id, user_text):
    if not gemini_client:
        return None

    history = chat_history.get(chat_id, [])

    prompt_parts = [
        SYSTEM_PROMPT,
        "",
        "История разговора:",
    ]

    for item in history[-MAX_HISTORY:]:
        role = item["role"]
        text = item["text"]
        prompt_parts.append(f"{role}: {text}")

    prompt_parts.extend([
        "",
        f"Пользователь: {user_text}",
        "",
        "Ответь пользователю от лица Ахигao.",
    ])

    full_prompt = "\n".join(prompt_parts)

    try:
        response = await asyncio.to_thread(
            gemini_client.models.generate_content,
            model=GEMINI_MODEL,
            contents=full_prompt,
        )

        if response and response.text:
            return response.text.strip()

    except Exception as e:
        print(f"⚠️ Gemini error: {type(e).__name__}: {e}")

    return None


# ============================================================
# GROQ
# ============================================================

async def ask_groq(chat_id, user_text):
    if not GROQ_API_KEY:
        return None

    history = chat_history.get(chat_id, [])

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        }
    ]

    for item in history[-MAX_HISTORY:]:
        if item["role"] == "user":
            messages.append({
                "role": "user",
                "content": item["text"],
            })
        elif item["role"] == "assistant":
            messages.append({
                "role": "assistant",
                "content": item["text"],
            })

    messages.append({
        "role": "user",
        "content": user_text,
    })

    url = "https://api.groq.com/openai/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": GROQ_MODEL,
        "messages": messages,
        "temperature": 0.9,
    }

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(url, headers=headers, json=payload)

        if response.status_code != 200:
            print(f"⚠️ Groq HTTP {response.status_code}: {response.text[:500]}")
            return None

        data = response.json()
        return data["choices"][0]["message"]["content"].strip()

    except Exception as e:
        print(f"⚠️ Groq error: {type(e).__name__}: {e}")

    return None


# ============================================================
# OPENROUTER
# ============================================================

async def ask_openrouter(chat_id, user_text):
    if not OPENROUTER_API_KEY:
        return None

    history = chat_history.get(chat_id, [])

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        }
    ]

    for item in history[-MAX_HISTORY:]:
        if item["role"] == "user":
            messages.append({
                "role": "user",
                "content": item["text"],
            })
        elif item["role"] == "assistant":
            messages.append({
                "role": "assistant",
                "content": item["text"],
            })

    messages.append({
        "role": "user",
        "content": user_text,
    })

    url = "https://openrouter.ai/api/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": messages,
    }

    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(url, headers=headers, json=payload)

        if response.status_code != 200:
            print(f"⚠️ OpenRouter HTTP {response.status_code}: {response.text[:500]}")
            return None

        data = response.json()
        return data["choices"][0]["message"]["content"].strip()

    except Exception as e:
        print(f"⚠️ OpenRouter error: {type(e).__name__}: {e}")

    return None


# ============================================================
# AI
# ============================================================

async def ask_ai(chat_id, user_text):
    add_to_history(chat_id, "user", user_text)

    # 1. Gemini
    answer = await ask_gemini(chat_id, user_text)

    # 2. Groq
    if not answer:
        print("🔄 Gemini не ответил, пробую Groq...")
        answer = await ask_groq(chat_id, user_text)

    # 3. OpenRouter
    if not answer:
        print("🔄 Groq не ответил, пробую OpenRouter...")
        answer = await ask_openrouter(chat_id, user_text)

    # Fallback
    if not answer:
        answer = random.choice([
            "я чёт зависла 💀",
            "у меня мозг ушёл за хлебом",
            "я сейчас ничего не поняла 😭",
            "секунду, я тупенькая",
            "мозг ахигао временно недоступен",
        ])

    add_to_history(chat_id, "assistant", answer)
    return answer


# ============================================================
# STARTUP MESSAGE
# ============================================================

async def send_startup_message(application):
    print()
    print(f"📨 Отправляю стартовое сообщение в {STARTUP_CHAT}...")

    result = await safe_send_message(
        application.bot,
        STARTUP_CHAT,
        STARTUP_MESSAGE
    )

    if result:
        print("✅ Стартовое сообщение отправлено!")
        print(f"   Chat ID: {result.chat.id}")
        print(f"   Title: {result.chat.title}")
        print(f"   Username: @{result.chat.username}")
    else:
        print(f"❌ Не удалось отправить сообщение в {STARTUP_CHAT}")


# ============================================================
# /START
# ============================================================

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    remember_chat(chat)

    await safe_reply(
        update.message,
        random.choice(START_PHRASES)
    )


# ============================================================
# /AHIGAO
# ============================================================

async def ahigao_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    remember_chat(chat)

    await safe_reply(
        update.message,
        random.choice(AHIGAO_PHRASES)
    )


# ============================================================
# SCHEDULE
# ============================================================

async def send_klitor_time(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.data
    await safe_send_message(context.bot, chat_id, "12:28 klitor time 🍑")


async def send_anus_time(context: ContextTypes.DEFAULT_TYPE):
    chat_id = context.job.data
    await safe_send_message(context.bot, chat_id, "22:28 anus time 🍑")


async def start_schedule_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    remember_chat(chat)
    chat_id = chat.id

    # Удаляем старые задачи
    for job in context.job_queue.get_jobs_by_name(f"klitor_{chat_id}"):
        job.schedule_removal()

    for job in context.job_queue.get_jobs_by_name(f"anus_{chat_id}"):
        job.schedule_removal()

    # 12:28
    context.job_queue.run_daily(
        send_klitor_time,
        time=time(hour=12, minute=28, tzinfo=TIMEZONE),
        data=chat_id,
        name=f"klitor_{chat_id}",
    )

    # 22:28
    context.job_queue.run_daily(
        send_anus_time,
        time=time(hour=22, minute=28, tzinfo=TIMEZONE),
        data=chat_id,
        name=f"anus_{chat_id}",
    )

    await safe_reply(
        update.message,
        "расписание поставлено 😈\n"
        "12:28 — klitor time\n"
        "22:28 — anus time"
    )


# ============================================================
# TEXT MESSAGE
# ============================================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    chat = update.effective_chat
    message = update.message

    remember_chat(chat)

    text = message.text
    if not text:
        return

    print(
        "📩 MESSAGE:",
        chat.id,
        chat.title,
        chat.type,
        repr(text),
    )

    text_lower = text.lower().strip()

    # Получаем информацию о боте один раз
    bot_info = await context.bot.get_me()
    bot_username = f"@{bot_info.username}".lower() if bot_info.username else ""

    # Варианты имени бота
    name_variants = [
        "ахигао",
        "ахигao",
        "ахигао",
        "ахигао",
        "ahigao",
    ]

    mentioned_by_name = any(name in text_lower for name in name_variants)
    mentioned_by_username = bool(bot_username and bot_username in text_lower)

    # Проверяем reply на бота
    is_reply_to_bot = False
    if message.reply_to_message and message.reply_to_message.from_user:
        if message.reply_to_message.from_user.id == bot_info.id:
            is_reply_to_bot = True

    # Если упомянули имя / @ / ответили — отвечаем через ИИ
    if mentioned_by_name or mentioned_by_username or is_reply_to_bot:

        cleaned_text = text

        # Убираем @username
        if mentioned_by_username and bot_info.username:
            cleaned_text = cleaned_text.replace(f"@{bot_info.username}", "")
            cleaned_text = cleaned_text.replace(f"@{bot_info.username.lower()}", "")
            cleaned_text = cleaned_text.replace(f"@{bot_info.username.upper()}", "")

        # Убираем варианты имени
        cleaned_lower = cleaned_text.lower()
        for name in name_variants:
            cleaned_lower = cleaned_lower.replace(name, "")

        cleaned_text = cleaned_lower.strip()

        if not cleaned_text:
            cleaned_text = "что ты хочешь мне сказать?"

        answer = await ask_ai(chat.id, cleaned_text)
        await safe_reply(message, answer)
        return


# ============================================================
# MY CHAT MEMBER
# ============================================================

async def my_chat_member_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if not chat:
        return

    remember_chat(chat)

    print(
        f"👥 MY_CHAT_MEMBER: "
        f"{chat.id} | "
        f"{chat.title} | "
        f"@{chat.username or '-'} | "
        f"{chat.type}"
    )


# ============================================================
# ERROR
# ============================================================

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    print("❌ BOT ERROR:", type(context.error).__name__, context.error)


# ============================================================
# MAIN
# ============================================================

def main():
    print("======================================")
    print("        АХИГАО BOT")
    print("======================================")

    load_known_chats()

    application = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    # STARTUP
    application.post_init = send_startup_message

    # COMMANDS
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("ahigao", ahigao_command))
    application.add_handler(CommandHandler("start_schedule", start_schedule_command))

    # BOT ADDED / REMOVED
    application.add_handler(
        ChatMemberHandler(
            my_chat_member_handler,
            ChatMemberHandler.MY_CHAT_MEMBER
        )
    )

    # TEXT
    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            handle_message
        )
    )

    # ERROR
    application.add_error_handler(error_handler)

    print("🤖 Запускаю polling...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    main()