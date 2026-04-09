"""
Telegram bot: daily weather-poem broadcaster with inline buttons.
"""

import asyncio
import json
import logging
import os
from pathlib import Path

import pytz
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from gigachat import GigaChat
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

# ─────────────────────────────────────────────────────────────────────────────
#  Logging  (must be set up before anything that calls logger)
# ─────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
#  Config — prefer environment variables; fall back to the literals below
# ─────────────────────────────────────────────────────────────────────────────

BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
GIGACHAT_AUTH_KEY: str = os.getenv("GIGACHAT_AUTH_KEY", "")
WEATHER_API_KEY: str = os.getenv("WEATHER_API_KEY", "")

CITY = "498817"
UNITS = "metric"

TIMEZONE = "Europe/Moscow"
SCHEDULE_HOUR = 19
SCHEDULE_MINUTE = 17

FIXED_BUTTON_LABEL = "📌 Пара строк о погоде"
FIXED_BUTTON_MESSAGE = "🎉 Как вдохновлю"
AI_BUTTON_LABEL = "✨ Думаю-с"

AI_PROMPT = (
    "Напиши 4 случайных существительных и 2 прилагательных. "
    "Выведи только слова и используй какое-нибудь релевантное эмодзи рядом со словом"
)

SUBSCRIBERS_FILE = Path("subscribers.json")

# ─────────────────────────────────────────────────────────────────────────────
#  GigaChat client
# ─────────────────────────────────────────────────────────────────────────────

giga = GigaChat(credentials=GIGACHAT_AUTH_KEY)


# ─────────────────────────────────────────────────────────────────────────────
#  Weather client
# ─────────────────────────────────────────────────────────────────────────────


def get_weather(city: str, api_key: str, units: str = "metric") -> dict:
    """Fetch current weather data from OpenWeatherMap API."""
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "id": city,
        "appid": api_key,
        "units": units,
    }

    response = requests.get(url, params=params)
    response.raise_for_status()  # Raises HTTPError for 4xx/5xx responses
    return response.json()


def display_weather(data: dict, units: str = "metric") -> None:
    """Print a formatted weather summary."""
    temp_unit = "°C" if units == "metric" else ("°F" if units == "imperial" else "K")
    speed_unit = "m/s" if units != "imperial" else "mph"

    # city = data["name"]
    # country = data["sys"]["country"]
    description = data["weather"][0]["description"].capitalize()
    # temp = data["main"]["temp"]
    feels_like = data["main"]["feels_like"]
    # humidity = data["main"]["humidity"]
    wind_speed = data["wind"]["speed"]
    # visibility = data.get("visibility", "N/A")

    # print(f"\n{'=' * 40}")
    # print(f"  Weather in {city}, {country}")
    # print(f"{'=' * 40}")
    # print(f"  Condition  : {description}")
    # print(f"  Temperature: {temp}{temp_unit} (feels like {feels_like}{temp_unit})")
    # print(f"  Humidity   : {humidity}%")
    # print(f"  Wind Speed : {wind_speed} {speed_unit}")
    # print(f"  Visibility : {visibility} m" if visibility != "N/A" else "  Visibility : N/A")
    # print(f"{'=' * 40}\n")
    weather_report = f'Condition {description}, temperature {feels_like}{temp_unit}, wind {wind_speed} {speed_unit}'
    return weather_report

def get_city_id():
    s_city = "Saint Petersburg"
    city_id = 0
    try:
        res = requests.get("http://api.openweathermap.org/data/2.5/find",
                    params={'q': s_city, 'type': 'like', 'units': 'metric', 'APPID': WEATHER_API_KEY})
        data = res.json()
        cities = ["{} ({})".format(d['name'], d['sys']['country'])
                for d in data['list']]
        print("city:", cities)
        city_id = data['list'][0]['id']
        print('city_id=', city_id)
    except Exception as e:
        print("Exception (find):", e)
        pass

# ─────────────────────────────────────────────────────────────────────────────
#  Subscriber persistence
# ─────────────────────────────────────────────────────────────────────────────


def load_subscribers() -> set[int]:
    """Load subscriber chat IDs from disk."""
    if SUBSCRIBERS_FILE.exists():
        try:
            return set(json.loads(SUBSCRIBERS_FILE.read_text()))
        except Exception as exc:
            logger.error("Failed to load subscribers: %s", exc)
    return set()


def save_subscribers(subs: set[int]) -> None:
    """Persist subscriber chat IDs to disk."""
    try:
        SUBSCRIBERS_FILE.write_text(json.dumps(list(subs)))
    except Exception as exc:
        logger.error("Failed to save subscribers: %s", exc)


# In-memory subscriber set (source of truth while the bot runs)
subscribers: set[int] = load_subscribers()

# ─────────────────────────────────────────────────────────────────────────────
#  Helpers
# ─────────────────────────────────────────────────────────────────────────────


def build_keyboard() -> InlineKeyboardMarkup:
    """Return the inline keyboard with both action buttons."""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(FIXED_BUTTON_LABEL, callback_data="fixed")],
        [InlineKeyboardButton(AI_BUTTON_LABEL, callback_data="ai_generate")],
    ])


async def generate_ai_message(prompt: str = AI_PROMPT) -> str:
    """Call GigaChat in a thread so the event loop isn't blocked."""
    loop = asyncio.get_running_loop()
    response = await loop.run_in_executor(None, lambda: giga.chat(prompt))
    return response.choices[0].message.content


def build_weather_prompt() -> str | None:
    """
    Fetch weather and build the poetry prompt.
    Returns None (and logs the error) if weather data is unavailable.
    """
    try:
        weather_data = get_weather(CITY, WEATHER_API_KEY, UNITS)
        description = display_weather(weather_data, UNITS)
        return (
            f"Сегодня {description}. "
            "Сочини пару стихотворных строк про это. "
            "В ответ напиши только их. "
            "Концентрируйся на потенциальных ощущениях"
        )
    except requests.exceptions.HTTPError as exc:
        logger.error("Weather HTTP error: %s — %s", exc.response.status_code, exc.response.text)
    except requests.exceptions.ConnectionError:
        logger.error("Weather connection error: check your internet connection.")
    except requests.exceptions.RequestException as exc:
        logger.error("Weather request failed: %s", exc)
    return None

# ─────────────────────────────────────────────────────────────────────────────
#  Command handlers
# ─────────────────────────────────────────────────────────────────────────────


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start."""
    await update.message.reply_text(
        "👋 Прив!\n\n"
        f"Ежедневно могу кое-что присылать в {SCHEDULE_HOUR:02d}:{SCHEDULE_MINUTE:02d} ({TIMEZONE}).\n\n"
        "Комманды:\n"
        "  /subscribe   — подписаца на расслыку\n"
        "  /unsubscribe — прекратить рассылку\n"
        "  /menu        — если вдохновения не хватает, жмякай сюды\n"
        "  /status      — проверить статус подписки",
    )


async def subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Add this chat to the subscriber list."""
    chat_id = update.effective_chat.id
    if chat_id in subscribers:
        await update.message.reply_text("✅ You're already subscribed!")
        return

    subscribers.add(chat_id)
    save_subscribers(subscribers)
    logger.info("New subscriber: %s (total: %d)", chat_id, len(subscribers))
    await update.message.reply_text(
        f"🔔 Я запомнил тебя!!! Жди меня в "
        f"{SCHEDULE_HOUR:02d}:{SCHEDULE_MINUTE:02d} ({TIMEZONE}).\n\n"
        "А если ты боишься моей мощи, то жмякай /unsubscribe"
    )


async def unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remove this chat from the subscriber list."""
    chat_id = update.effective_chat.id
    if chat_id not in subscribers:
        await update.message.reply_text("ℹ️ You're not subscribed.")
        return

    subscribers.discard(chat_id)
    save_subscribers(subscribers)
    logger.info("Unsubscribed: %s (total: %d)", chat_id, len(subscribers))
    await update.message.reply_text("🔕 Ты отписана от движа.")


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Report subscription status for this chat."""
    chat_id = update.effective_chat.id
    if chat_id in subscribers:
        await update.message.reply_text(
            f"✅ Ты в игре.\n"
            f"Жди меня: сегодня/завтра в {SCHEDULE_HOUR:02d}:{SCHEDULE_MINUTE:02d} ({TIMEZONE})."
        )
    else:
        await update.message.reply_text("❌ You are not subscribed. Use /subscribe to sign up.")


async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /menu — show the keyboard."""
    await update.message.reply_text("Choose an action 👇", reply_markup=build_keyboard())

# ─────────────────────────────────────────────────────────────────────────────
#  Callback handlers
# ─────────────────────────────────────────────────────────────────────────────


async def fixed_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Respond to the fixed-message button."""
    query = update.callback_query
    await query.answer()
    await query.message.reply_text(FIXED_BUTTON_MESSAGE)
    prompt = build_weather_prompt()
    if prompt is None:
        logger.error("Skipping daily broadcast — could not build weather prompt.")
        return
    try:
        response = giga.chat(prompt)
        answer = response.choices[0].message.content
    except Exception as exc:
        logger.error("GigaChat error during daily broadcast: %s", exc)
        return
    await query.message.reply_text(answer)    


async def ai_button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generate a message with GigaChat and send it."""
    query = update.callback_query
    await query.answer("Думаю...")
    await context.bot.send_chat_action(chat_id=query.message.chat_id, action="typing")

    try:
        ai_text = await generate_ai_message()
        await query.message.reply_text(f"🤖 {ai_text}")
    except Exception as exc:
        logger.error("GigaChat API error: %s", exc)
        await query.message.reply_text("Sorry, I couldn't generate a message right now. Please try again.")

# ─────────────────────────────────────────────────────────────────────────────
#  Scheduled job
# ─────────────────────────────────────────────────────────────────────────────


def send_daily_message(application: Application) -> None:
    """Broadcast the daily weather-poem to all current subscribers."""
    prompt = build_weather_prompt()
    if prompt is None:
        logger.error("Skipping daily broadcast — could not build weather prompt.")
        return

    try:
        response = giga.chat(prompt)
        answer = response.choices[0].message.content
    except Exception as exc:
        logger.error("GigaChat error during daily broadcast: %s", exc)
        return

    async def _broadcast() -> None:
        if not subscribers:
            logger.info("Daily message triggered but no subscribers.")
            return

        logger.info("Broadcasting daily message to %d subscriber(s).", len(subscribers))
        failed: list[int] = []

        for chat_id in list(subscribers):
            try:
                await application.bot.send_message(
                    chat_id=chat_id,
                    text=answer,
                    reply_markup=build_keyboard(),
                )
            except Exception as exc:
                logger.warning("Failed to send to %s: %s", chat_id, exc)
                error_str = str(exc).lower()
                if any(k in error_str for k in ("blocked", "chat not found", "deactivated")):
                    failed.append(chat_id)

        if failed:
            for chat_id in failed:
                subscribers.discard(chat_id)
            save_subscribers(subscribers)
            logger.info("Auto-removed %d unreachable subscriber(s).", len(failed))

    asyncio.run_coroutine_threadsafe(_broadcast(), application.update_queue._loop)

# ─────────────────────────────────────────────────────────────────────────────
#  Main
# ─────────────────────────────────────────────────────────────────────────────


def main() -> None:
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("subscribe", subscribe))
    app.add_handler(CommandHandler("unsubscribe", unsubscribe))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("menu", menu))

    app.add_handler(CallbackQueryHandler(fixed_button_callback, pattern="^fixed$"))
    app.add_handler(CallbackQueryHandler(ai_button_callback, pattern="^ai_generate$"))

    tz = pytz.timezone(TIMEZONE)
    scheduler = BackgroundScheduler(timezone=tz)
    scheduler.add_job(
        send_daily_message,
        trigger=CronTrigger(hour=SCHEDULE_HOUR, minute=SCHEDULE_MINUTE, timezone=tz),
        args=[app],
        id="daily_message",
        replace_existing=True,
    )
    scheduler.start()
    logger.info(
        "Scheduler started — daily message at %02d:%02d %s | %d subscriber(s) loaded",
        SCHEDULE_HOUR,
        SCHEDULE_MINUTE,
        TIMEZONE,
        len(subscribers),
    )

    app.run_polling(allowed_updates=Update.ALL_TYPES)
    scheduler.shutdown()


if __name__ == "__main__":
    main()