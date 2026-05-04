import feedparser
import sqlite3
import requests
import time
import threading
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
import re

# ================= الإعدادات =================
BOT_TOKEN = "7322365145:AAG0Dr8DWcTOZymxncpNNgYtAkw1F9JaSfA"
CHANNEL_ID = "@worldnews014" 
RSS_URL = "https://www.aljazeera.net/aljazeerarss" 
# ==============================================

# --- 0. خادم ويب وهمي لاستضافة Render/Koyeb ---
class DummyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type','text/plain')
        self.end_headers()
        self.wfile.write(b"Bot is running successfully!")

def run_dummy_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), DummyHandler)
    server.serve_forever()

# --- 1. إعداد قاعدة البيانات ---
def setup_db():
    conn = sqlite3.connect('news_bot.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sent_news (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            link TEXT UNIQUE
        )
    ''')
    conn.commit()
    return conn

def is_news_sent(cursor, link):
    cursor.execute('SELECT link FROM sent_news WHERE link = ?', (link,))
    return cursor.fetchone() is not None

# --- 2. الإرسال إلى تليجرام ---
def send_to_telegram(title, description, link, image_url):
    message = f"🔴 *{title}*\n\n{description}\n\n🔗 [اقرأ التفاصيل]({link})"
    
    if image_url:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        payload = {"chat_id": CHANNEL_ID, "photo": image_url, "caption": message, "parse_mode": "Markdown"}
    else:
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {"chat_id": CHANNEL_ID, "text": message, "parse_mode": "Markdown"}
    
    try:
        response = requests.post(url, data=payload)
        return response.status_code == 200
    except Exception as e:
        print(f"Error: {e}")
        return False

# --- 3. تنظيف النصوص من أكواد HTML ---
def clean_html(raw_html):
    cleanr = re.compile('<.*?>')
    return re.sub(cleanr, '', raw_html).strip()

# --- 4. المحرك الأساسي ---
first_run = True # متغير لمعرفة إذا كان هذا أول تشغيل للسيرفر

def fetch_and_send():
    global first_run
    conn = setup_db()
    cursor = conn.cursor()
    feed = feedparser.parse(RSS_URL)
    
    print(f"تم جلب {len(feed.entries)} خبر من الرابط.")

    for entry in reversed(feed.entries):
        link = entry.link
        
        if not is_news_sent(cursor, link):
            title = entry.title
            description = clean_html(entry.summary if 'summary' in entry else "")
            
            image_url = ""
            if 'links' in entry:
                for link_item in entry.links:
                    if 'image' in link_item.get('type', ''):
                        image_url = link_item.get('href', '')
            
            if first_run:
                # في أول تشغيل، نحفظ الأخبار في قاعدة البيانات فقط لكي لا نرسلها دفعة واحدة
                cursor.execute('INSERT INTO sent_news (link) VALUES (?)', (link,))
                conn.commit()
            else:
                # إذا لم يكن أول تشغيل، فهذا خبر جديد تماماً، أرسله!
                print(f"إرسال خبر جديد: {title}")
                if send_to_telegram(title, description, link, image_url):
                    cursor.execute('INSERT INTO sent_news (link) VALUES (?)', (link,))
                    conn.commit()
                    time.sleep(3)

    first_run = False # انتهاء حالة أول تشغيل
    conn.close()

# --- 5. التشغيل ---
if __name__ == "__main__":
    # تشغيل الخادم الوهمي في مسار خلفي
    threading.Thread(target=run_dummy_server, daemon=True).start()
    
    print("🚀 تم تشغيل البوت... يراقب الأخبار الآن.")
    while True:
        try:
            fetch_and_send()
        except Exception as e:
            print(f"⚠️ خطأ غير متوقع: {e}")
        
        print("⏳ جاري الانتظار 5 دقائق...")
        time.sleep(300)
