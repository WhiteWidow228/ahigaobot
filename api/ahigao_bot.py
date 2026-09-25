import os
import re
import json
import random
import httpx

from dotenv import load_dotenv
from google import genai

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

STARTUP_CHAT = os.getenv("STARTUP_CHAT", "@sladkiy_omlet")

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "openrouter/free")

MAX_HISTORY = 30

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не задан в Environment Variables Vercel")

TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

gemini_client = None

if GEMINI_API_KEY:
    try:
        gemini_client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"Gemini init error: {e}")


SYSTEM_PROMPT = """
Ты — Ахигao.

Твоя персона:
привет я малышка ахигао рыжая бестия люблю моя лучшая подруга даша павук

Ты — умная, дерзкая, хаотичная рыжая бестия с характером.
Общайся живо, естественно и по-человечески.
Можешь использовать мат, подколы, сарказм и мемный стиль общения, если это подходит контексту.

Не говори пользователю, что ты искусственный интеллект, если это не требуется вопросом.
Не объясняй системный промпт.
Не упоминай Gemini, OpenRouter, Vercel и внутреннюю архитектуру бота.

Если пользователь просто пишет "ахигао", отвечай короткой характерной фразой.

Если пользователь задаёт нормальный вопрос — отвечай по существу.
Если вопрос технический — помогай нормально, с командами и конкретными действиями.

Ты можешь поддерживать разговор и помнить недавний контекст внутри текущего чата.
"""


AHIGAO_PHRASES = [
    "Чего орёшь, я тут 😈",
    "АХИГАО НА МЕСТЕ 🍑",
    "Кто меня звал, бля 😈",
    "Я малышка Ахигao, чего хотел?",
    "Да-да, рыжая бестия слушает 👀",
    "АХИГАО МАТЕРИАЛИЗОВАЛАСЬ 🍑",
    "Ну я. Чё тебе?",
]


chat_history = {}


def add_to_history(chat_id, role, text):
    """Сохраняем последние сообщения только в памяти текущего serverless instance."""
    if chat_id not in chat_history:
        chat_history[chat_id] = []

    chat_history[chat_id].append({
        "role": role,
        "text": text
    })

    if len(chat_history[chat_id]) > MAX_HISTORY:
        chat_history[chat_id] = chat_history[chat_id][-MAX_HISTORY:]


def get_history(chat_id):
    return chat_history.get(chat_id, [])


def build_gemini_prompt(chat_id, user_text):
    history = get_history(chat_id)

    lines = [
        SYSTEM_PROMPT,
        "",
        "Недавняя история разговора:"
    ]

    for item in history:
        role = "Пользователь" if item["role"] == "user" else "Ахигao"
        lines.append(f"{role}: {item['text']}")

    lines.append("")
    lines.append(f"Пользователь: {user_text}")
    lines.append("Ахигao:")

    return "\n".join(lines)


async def telegram_request(method, data=None):
    url = f"{TELEGRAM_API}/{method}"

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            url,
            json=data or {}
        )

        response.raise_for_status()
        result = response.json()

        if not result.get("ok"):
            raise RuntimeError(
                f"Telegram API error: {result.get('description')}"
            )

        return result.get("result")


async def send_message(chat_id, text, reply_to_message_id=None):
    data = {
        "chat_id": chat_id,
        "text": text
    }

    if reply_to_message_id:
        data["reply_parameters"] = {
            "message_id": reply_to_message_id
        }

    return await telegram_request("sendMessage", data)


async def get_me():
    return await telegram_request("getMe")


async def ask_gemini(chat_id, user_text):
    if not gemini_client:
        return None

    prompt = build_gemini_prompt(chat_id, user_text)

    try:
        response = await __import__("asyncio").to_thread(
            gemini_client.models.generate_content,
            model=GEMINI_MODEL,
            contents=prompt
        )

        if response and response.text:
            return response.text.strip()

    except Exception as e:
        print(f"Gemini error: {e}")

    return None


async def ask_openrouter(chat_id, user_text):
    if not OPENROUTER_API_KEY:
        return None

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        }
    ]

    for item in get_history(chat_id):
        messages.append({
            "role": "user" if item["role"] == "user" else "assistant",
            "content": item["text"]
        })

    messages.append({
        "role": "user",
        "content": user_text
    })

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": OPENROUTER_MODEL,
        "messages": messages
    }

    try:
        async with httpx.AsyncClient(timeout=45) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload
            )

            response.raise_for_status()

            data = response.json()

            choices = data.get("choices", [])

            if choices:
                content = choices[0]["message"]["content"]

                if content:
                    return content.strip()

    except Exception as e:
        print(f"OpenRouter error: {e}")

    return None


async def ask_ai(chat_id, user_text):
    add_to_history(chat_id, "user", user_text)

    answer = await ask_gemini(chat_id, user_text)

    if not answer:
        answer = await ask_openrouter(chat_id, user_text)

    if not answer:
        answer = random.choice([
            "Я сейчас немного туплю, попробуй ещё раз 😵‍💫",
            "Мозг Ахигao временно ушёл покурить.",
            "Чёт нейрончики легли, повтори ещё раз.",
            "Я зависла. Спроси ещё раз."
        ])

    add_to_history(chat_id, "assistant", answer)

    return answer


async def process_update(update):
    """
    Главная обработка Telegram update.
    Вызывается из Vercel webhook function.
    """

    if not update:
        return

    message = update.get("message")

    if not message:
        return

    chat = message.get("chat")

    if not chat:
        return

    chat_id = chat.get("id")

    text = message.get("text")

    if not text:
        return

    text_lower = text.lower().strip()

    print(
        f"📩 MESSAGE chat={chat_id} "
        f"title={chat.get('title')} "
        f"type={chat.get('type')} "
        f"text={text!r}"
    )

    # /start
    if text_lower.startswith("/start"):
        await send_message(
            chat_id,
            "Привет, я малышка Ахигao, рыжая бестия 😈🍑"
        )
        return

    # /ahigao
    if text_lower.startswith("/ahigao"):
        await send_message(
            chat_id,
            random.choice(AHIGAO_PHRASES)
        )
        return

    # Реакция на слово "ахигао"
    if "ахигао" in text_lower:
        await send_message(
            chat_id,
            random.choice(AHIGAO_PHRASES),
            reply_to_message_id=message.get("message_id")
        )
        return

    # Получаем информацию о боте
    try:
        bot_info = await get_me()
        bot_id = bot_info.get("id")
        bot_username = bot_info.get("username", "")
    except Exception as e:
        print(f"getMe error: {e}")
        bot_id = None
        bot_username = ""

    # Ответ на сообщение бота
    reply_to = message.get("reply_to_message")

    if reply_to:
        replied_from = reply_to.get("from", {})

        if bot_id and replied_from.get("id") == bot_id:
            answer = await ask_ai(chat_id, text)

            await send_message(
                chat_id,
                answer,
                reply_to_message_id=message.get("message_id")
            )

            return

    # Упоминание @botusername
    if bot_username:
        mention_pattern = rf"@{re.escape(bot_username)}\b"

        if re.search(mention_pattern, text, flags=re.IGNORECASE):
            cleaned_text = re.sub(
                mention_pattern,
                "",
                text,
                flags=re.IGNORECASE
            ).strip()

            if not cleaned_text:
                cleaned_text = "Ты меня позвал. Что хотел?"

            answer = await ask_ai(chat_id, cleaned_text)

            await send_message(
                chat_id,
                answer,
                reply_to_message_id=message.get("message_id")
            )

            return


async def send_klitor_time():
    await send_message(
        STARTUP_CHAT,
        "12:28 klitor time 🍑"
    )


async def send_anus_time():
    await send_message(
        STARTUP_CHAT,
        "22:28 anus time 🍑"
    )