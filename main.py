import os
import logging
import asyncio
from telethon import TelegramClient, events
from deep_translator import GoogleTranslator
from flask import Flask
from threading import Thread

# 🔹 Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# 🔹 Environment Variables (Set in Replit Secrets)
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
SOURCE_CHANNELS = os.getenv("SOURCE_CHANNELS", "").split(",")
TARGET_CHANNEL = os.getenv("TARGET_CHANNEL")

# 🔹 Initialize Telegram Client
client = TelegramClient("bot_session", API_ID, API_HASH)

# 🔹 Translation function
def translate_to_farsi(text):
    try:
        return GoogleTranslator(source="auto", target="fa").translate(text)
    except Exception as e:
        logger.error(f"❌ Translation error: {e}")
        return text  # Fallback: Send original text if translation fails

# 🔹 New Message Handler
@client.on(events.NewMessage(chats=SOURCE_CHANNELS))
async def handler(event):
    try:
        if event.message.text:
            original_text = event.message.text
            translated_text = translate_to_farsi(original_text)
            message_to_send = f"{translated_text}\n\n@whaleguardian"

            await client.send_message(TARGET_CHANNEL, message_to_send)
            logger.info(f"📨 Forwarded: {message_to_send}")

        if event.message.media:
            await client.send_message(TARGET_CHANNEL, file=event.message.media)
            logger.info("📨 Forwarded media.")

    except Exception as e:
        logger.error(f"❌ Error in handler: {e}")

# 🔹 Start the bot with auto-restart
async def start_bot():
    while True:
        try:
            logger.info("✅ Connecting to Telegram...")
            await client.start(bot_token=BOT_TOKEN)
            logger.info("✅ Bot started successfully. Monitoring messages...")
            await client.run_until_disconnected()
        except Exception as e:
            logger.error(f"⚠️ Bot crashed. Restarting in 5 seconds... Error: {e}")
            await asyncio.sleep(5)  # Wait before restarting

# 🔹 Keep-Alive Flask Server (Prevents Replit from Sleeping)
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running!"

def run_flask():
    app.run(host="0.0.0.0", port=8080)

# 🔹 Start Everything
if __name__ == "__main__":
    Thread(target=run_flask).start()
    asyncio.run(start_bot())
