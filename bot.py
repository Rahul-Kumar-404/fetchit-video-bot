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

# --- DUMMY WEB SERVER FOR RENDER (To satisfy Web Service port requirement) ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive and running!")

def run_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

# Start the dummy server in a separate background thread
Thread(target=run_server, daemon=True).start()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Sends a welcome message when the /start command is issued."""
    welcome_text = (
        "👋 Welcome! Send me a video or reel link from YouTube, Instagram, Facebook, etc., "
        "and I will download it for you instantly."
    )
    await update.message.reply_text(welcome_text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles incoming text messages containing URLs."""
    url = update.message.text
    chat_id = update.message.chat_id

    # Basic URL validation to ensure it starts with http or https
    if not re.match(r'^https?://', url):
        await update.message.reply_text("❌ Please send a valid HTTP or HTTPS URL.")
        return

    status_message = await update.message.reply_text("⚡ Processing quickly... Please wait.")

    # Fast yt-dlp configuration to ensure quick downloads
    ydl_opts = {
        'format': 'best[ext=mp4]/bestvideo+bestaudio/best', 
        'outtmpl': f'{DOWNLOAD_DIR}/%(id)s.%(ext)s',
        'quiet': True,
        'max_filesize': 50 * 1024 * 1024, # Limits file size to 50MB for Telegram
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Extract media information and download it locally
            info = ydl.extract_info(url, download=True)
            video_id = info.get('id', 'unknown')
            title = info.get('title', 'Downloaded Media')
            
            # Find all downloaded files associated with this specific link
            downloaded_files = [f for f in os.listdir(DOWNLOAD_DIR) if video_id in f]
            
            if not downloaded_files:
                raise Exception("Could not find the downloaded file.")

            await context.bot.edit_message_text(
                "⬆️ Uploading to Telegram...", 
                chat_id=chat_id, 
                message_id=status_message.message_id
            )

            # Sort files to prioritize video formats (.mp4)
            downloaded_files.sort(key=lambda x: 1 if x.endswith(('.mp4', '.mkv', '.webm')) else 2)
            
            # Select the file to send back to the user
            file_to_send = os.path.join(DOWNLOAD_DIR, downloaded_files[0])

            # Send the video file with an optimized 45-second timeout for quick feedback
            with open(file_to_send, 'rb') as video_file:
                await context.bot.send_video(
                    chat_id=chat_id, 
                    video=video_file, 
                    caption=title,
                    read_timeout=45,
                    write_timeout=45
                )

            # Clean up the directory by deleting the file immediately
            for file in downloaded_files:
                try:
                    os.remove(os.path.join(DOWNLOAD_DIR, file))
                except:
                    pass

            await context.bot.delete_message(chat_id=chat_id, message_id=status_message.message_id)

    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e)
        if "No video formats found" in error_msg:
            error_text = "❌ No video found in this link. Please note that this bot supports Videos and Reels only, not photos."
        else:
            error_text = "❌ Failed to download. Ensure the link is public and supported."
        
        await context.bot.edit_message_text(error_text, chat_id=chat_id, message_id=status_message.message_id)
        
    except Exception as e:
        if "Timed out" in str(e):
            error_text = "❌ Request Timed Out. File badi hai ya internet slow hai, kripya choti video ke sath try karein."
        else:
            error_text = f"❌ An error occurred: {str(e)}\n\n*Note: Telegram limits bot file uploads to 50MB.*"
        
        await context.bot.edit_message_text(error_text, chat_id=chat_id, message_id=status_message.message_id)

def main():
    """Initializes and starts the Telegram bot with balanced 45-second timeouts."""
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .read_timeout(45)
        .write_timeout(45)
        .build()
    )

    # Register command and message handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("✅ Bot is successfully running with fast response mode! Press Ctrl+C to stop.")
    
    app.run_polling()

if __name__ == '__main__':
    main()