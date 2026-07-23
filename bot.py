import os
import re
import json
import urllib.request
from dotenv import load_dotenv
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

# --- DUMMY WEB SERVER FOR RENDER ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive and running!")

def run_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

Thread(target=run_server, daemon=True).start()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = (
        "👋 Welcome to FetchIt Video Downloader!\n\n"
        "Send me a video or reel link from YouTube, Instagram, etc., "
        "and I will download it for you instantly."
    )
    await update.message.reply_text(welcome_text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    chat_id = update.message.chat_id

    if not re.match(r'^https?://', url):
        await update.message.reply_text("❌ Please send a valid HTTP or HTTPS URL.")
        return

    status_message = await update.message.reply_text("⚡ Extracting video... Please wait.")

    try:
        # Ultimate Bypass: Using Cobalt API with a real Browser User-Agent
        api_url = "https://api.cobalt.tools/api/json"
        
        # Added User-Agent so Cobalt API thinks this is a real Chrome browser, preventing 403 Forbidden
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        }
        data = json.dumps({"url": url}).encode("utf-8")
        
        req = urllib.request.Request(api_url, data=data, headers=headers)
        
        with urllib.request.urlopen(req) as response:
            res_data = json.loads(response.read().decode())
            
        video_url = res_data.get("url")
        
        if not video_url:
            raise Exception("API blocked or invalid link.")

        await context.bot.edit_message_text(
            "⬆️ Uploading to Telegram...", 
            chat_id=chat_id, 
            message_id=status_message.message_id
        )

        # Telegram sends the video directly using the extracted URL
        await context.bot.send_video(
            chat_id=chat_id, 
            video=video_url, 
            caption="✅ Downloaded via FetchIt",
            read_timeout=60,
            write_timeout=60
        )

        await context.bot.delete_message(chat_id=chat_id, message_id=status_message.message_id)

    except Exception as e:
        error_text = f"❌ Failed to download. Ensure the account is public. Error: {str(e)[:50]}"
        await context.bot.edit_message_text(error_text, chat_id=chat_id, message_id=status_message.message_id)

def main():
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .read_timeout(60)
        .write_timeout(60)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("✅ Bot is running with Ultimate Cobalt API Mode!")
    app.run_polling()

if __name__ == '__main__':
    main()