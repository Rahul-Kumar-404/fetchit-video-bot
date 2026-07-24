import os
import re
import urllib.request
import random
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

# --- FREE PROXY SCRAPER ---
def get_free_proxy():
    """Fetches a random free HTTP proxy to bypass IP bans."""
    try:
        # Fetching Elite Anonymous proxies that support HTTPS
        url = "https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=5000&ssl=yes&anonymity=elite"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req) as response:
            proxies = response.read().decode('utf-8').strip().split('\r\n')
            if proxies:
                return f"http://{random.choice(proxies)}"
    except Exception as e:
        print(f"Proxy fetch error: {e}")
    return None

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

    status_message = await update.message.reply_text("⚡ Extracting video securely... Please wait.")

    max_retries = 3
    download_successful = False
    error_reason = ""

    # Try downloading up to 3 times with different proxies
    for attempt in range(max_retries):
        proxy = get_free_proxy()
        print(f"Attempt {attempt + 1}: Using proxy {proxy}")
        
        ydl_opts = {
            'format': 'best[ext=mp4]/best', 
            'outtmpl': f'{DOWNLOAD_DIR}/%(id)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'geo_bypass': True,
            'nocheckcertificate': True,
            'proxy': proxy, # Injecting the free proxy here
            'extractor_args': {
                'youtube': {'player_client': ['web']},
                'instagram': {'api_version': 'v1'}
            },
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            },
            'max_filesize': 50 * 1024 * 1024,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                video_id = info.get('id', 'unknown')
                title = info.get('title', 'Downloaded Media')
                download_successful = True
                break # Exit the loop if download is successful

        except Exception as e:
            error_reason = str(e)
            print(f"Failed with proxy {proxy}. Retrying...")
            continue # Try the next proxy

    if not download_successful:
        error_text = f"❌ Failed to download after {max_retries} attempts. The link might be private or blocked."
        await context.bot.edit_message_text(error_text, chat_id=chat_id, message_id=status_message.message_id)
        return

    try:
        downloaded_files = [f for f in os.listdir(DOWNLOAD_DIR) if video_id in f]
        
        if not downloaded_files:
            raise Exception("File not saved correctly.")

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
                caption="✅ Downloaded via FetchIt",
                read_timeout=60,
                write_timeout=60
            )

        # Cleanup
        for file in downloaded_files:
            try:
                os.remove(os.path.join(DOWNLOAD_DIR, file))
            except:
                pass

        await context.bot.delete_message(chat_id=chat_id, message_id=status_message.message_id)

    except Exception as e:
        error_text = "❌ Error uploading the file to Telegram."
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

    print("✅ Bot is running with Auto Proxy Rotator!")
    app.run_polling()

if __name__ == '__main__':
    main()