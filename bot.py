import os
import re
from dotenv import load_dotenv
from threading import Thread
from http.server import HTTPServer, BaseHTTPRequestHandler

from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp

# Load environment variables from the .env file
load_dotenv()

# --- CONFIGURATION ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
DOWNLOAD_DIR = "downloads"

# Ensure the download directory exists on your system
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

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
    """Sends a welcome message in English when the /start command is issued."""
    welcome_text = (
        "👋 Welcome to FetchIt Video Downloader!\n\n"
        "Send me a video or reel link from YouTube, Instagram, Facebook, etc., "
        "and I will download it for you instantly."
    )
    await update.message.reply_text(welcome_text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles incoming URL messages and downloads media with English feedback."""
    url = update.message.text
    chat_id = update.message.chat_id

    # Validate if the incoming text is a valid URL
    if not re.match(r'^https?://', url):
        await update.message.reply_text("❌ Please send a valid HTTP or HTTPS URL.")
        return

    status_message = await update.message.reply_text("⚡ Processing quickly... Please wait.")

    # Optimized yt-dlp configurations with custom headers to prevent blocking
    ydl_opts = {
        'format': 'best[ext=mp4]/best', 
        'outtmpl': f'{DOWNLOAD_DIR}/%(id)s.%(ext)s',
        'quiet': True,
        'no_warnings': True,
        'geo_bypass': True,
        'nocheckcertificate': True,
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        },
        'max_filesize': 50 * 1024 * 1024, # 50MB limit for Telegram bots
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

            # Send the video file back to the user
            with open(file_to_send, 'rb') as video_file:
                await context.bot.send_video(
                    chat_id=chat_id, 
                    video=video_file, 
                    caption=title,
                    read_timeout=45,
                    write_timeout=45
                )

            # Cleanup local storage
            for file in downloaded_files:
                try:
                    os.remove(os.path.join(DOWNLOAD_DIR, file))
                except:
                    pass

            await context.bot.delete_message(chat_id=chat_id, message_id=status_message.message_id)

    except Exception as e:
        error_text = "❌ Failed to download. Ensure the link is public and supported."
        await context.bot.edit_message_text(error_text, chat_id=chat_id, message_id=status_message.message_id)

def main():
    """Starts the bot with appropriate timeouts."""
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .read_timeout(45)
        .write_timeout(45)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("✅ Bot is successfully running in English mode!")
    app.run_polling()

if __name__ == '__main__':
    main()