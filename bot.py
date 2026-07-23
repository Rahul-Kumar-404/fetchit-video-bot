import os
import re
from dotenv import load_dotenv
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DOWNLOAD_DIR = "downloads"

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

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

    status_message = await update.message.reply_text("⚡ Processing quickly... Please wait.")

    # Robust options using 'mweb' (Mobile Web) client to bypass sign-in and bot checks on Render
    ydl_opts = {
        'format': 'best[ext=mp4]/best', 
        'outtmpl': f'{DOWNLOAD_DIR}/%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'geo_bypass': True,
        'nocheckcertificate': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['mweb', 'android']
            }
        },
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        },
        'max_filesize': 50 * 1024 * 1024,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_id = info.get('id', 'unknown')
            title = info.get('title', 'Downloaded Media')
            
            downloaded_files = [f for f in os.listdir(DOWNLOAD_DIR) if video_id in f]
            
            if not downloaded_files:
                raise Exception("Could not find the downloaded file.")

            await context.bot.edit_message_text(
                "⬆️ Uploading to Telegram...", 
                chat_id=chat_id, 
                message_id=status_message.message_id
            )

            downloaded_files.sort(key=lambda x: 1 if x.endswith(('.mp4', '.mkv', '.webm')) else 2)
            file_to_send = os.path.join(DOWNLOAD_DIR, downloaded_files[0])

            with open(file_to_send, 'rb') as video_file:
                await context.bot.send_video(
                    chat_id=chat_id, 
                    video=video_file, 
                    caption=title,
                    read_timeout=45,
                    write_timeout=45
                )

            for file in downloaded_files:
                try:
                    os.remove(os.path.join(DOWNLOAD_DIR, file))
                except:
                    pass

            await context.bot.delete_message(chat_id=chat_id, message_id=status_message.message_id)

    except Exception as e:
        # Now it will show the exact error so we know what's happening if it fails
        error_text = f"❌ Error: {str(e)[:150]}"
        await context.bot.edit_message_text(error_text, chat_id=chat_id, message_id=status_message.message_id)

def main():
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .read_timeout(45)
        .write_timeout(45)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("✅ Bot is running successfully with mweb client!")
    app.run_polling()

if __name__ == '__main__':
    main()