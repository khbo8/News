import feedparser
import sqlite3
import requests
import time
import threading
import os
import html
import re
from http.server import BaseHTTPRequestHandler, HTTPServer
from deep_translator import GoogleTranslator

# ================= الإعدادات =================
BOT_TOKEN = "7322365145:AAG0Dr8DWcTOZymxncpNNgYtAkw1F9JaSfA"
CHANNEL_ID = "@worldnews014"

# قائمة المصادر (الرابط، الاسم الظاهر، هل يحتاج ترجمة؟)
SOURCES = [
    {"url": "https://www.aljazeera.net/aljazeerarss", "name": "الجزيرة", "translate": False},
    {"url": "https://www.skynewsarabia.com/rss.xml", "name": "سكاي نيوز عربية", "translate": False},
    {"url": "https://arabic.rt.com/rss/", "name": "RT Arabic", "translate": False},
    {"url": "https://www.alarabiya.net/.mrss/ar/last-24-hours.xml", "name": "العربية", "translate": False},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml", "name": "New York Times", "translate": True},
]

# متغيرات لمراقبة حالة البوت وعرضها على الموقع
current_status = "بدء التشغيل..."
recent_logs = []

# ==============================================

# --- خادم الويب لعرض الحالة ---
class WebHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        logs_html = "".join([f"<li>{log}</li>" for log in reversed(recent_logs[-10:])])
        html_content = f"""
        <html>
            <head><title>News Bot Status</title><style>body{{font-family:Arial; padding:20px; direction:rtl;}} .status{{color:green; font-weight:bold;}}</style></head>
            <body>
                <h1>🤖 حالة بوت الأخبار</h1>
                <p>الحالة الحالية: <span class="status">{current_status}</span></p>
                <h3>آخر العمليات:</h3>
                <ul>{logs_html}</ul>
            </body>
        </html>
        """
        self.wfile.write(html_content.encode('utf-8'))

def add_log(text):
    global current_status
    current_status = text
    timestamp = time.strftime("%H:%M:%S")
    recent_logs.append(f"[{timestamp}] {text}")
    print(text)

def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), WebHandler)
    server.serve_forever()

# --- إدارة قاعدة البيانات ---
def setup_db():
    conn = sqlite3.connect('news_bot.db')
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS sent_news (id INTEGER PRIMARY KEY AUTOINCREMENT, link TEXT UNIQUE)')
    conn.commit()
    return conn

def is_news_sent(cursor, link):
    cursor.execute('SELECT link FROM sent_news WHERE link = ?', (link,))
    return cursor.fetchone() is not None

# --- تنظيف وترجمة النصوص ---
def clean_text(raw_html):
    cleanr = re.compile('<.*?>')
    cleantext = re.sub(cleanr, '', raw_html).strip()
    return html.unescape(cleantext)

def translate_text(text):
    try:
        if not text: return ""
        return GoogleTranslator(source='auto', target='ar').translate(text)
    except:
        return text

# --- الإرسال للتليجرام ---
def send_to_telegram(title, description, link, image_url, source_name):
    full_message = f"🔴 *{title}*\n\n{description}\n\n📍 المصدر: {source_name}\n🔗 [اقرأ التفاصيل]({link})"
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/" + ("sendPhoto" if image_url else "sendMessage")
    payload = {
        "chat_id": CHANNEL_ID,
        "parse_mode": "Markdown",
        ("photo" if image_url else "text"): (image_url if image_url else full_message)
    }
    if image_url: payload["caption"] = full_message

    try:
        requests.post(url, data=payload)
        return True
    except:
        return False

# --- المحرك الأساسي ---
first_run = True

def start_bot():
    global first_run
    conn = setup_db()
    cursor = conn.cursor()

    while True:
        for source in SOURCES:
            add_log(f"يتم الآن فحص: {source['name']}...")
            feed = feedparser.parse(source['url'])
            
            for entry in reversed(feed.entries):
                link = entry.link
                if not is_news_sent(cursor, link):
                    title = clean_text(entry.title)
                    desc = clean_text(entry.summary if 'summary' in entry else "")
                    
                    if source['translate']:
                        add_log(f"ترجمة خبر من {source['name']}...")
                        title = translate_text(title)
                        desc = translate_text(desc)

                    img = ""
                    if 'links' in entry:
                        for l in entry.links:
                            if 'image' in l.get('type', ''): img = l.get('href', '')

                    if first_run:
                        cursor.execute('INSERT INTO sent_news (link) VALUES (?)', (link,))
                        conn.commit()
                    else:
                        add_log(f"إرسال خبر من {source['name']} إلى تليجرام")
                        if send_to_telegram(title, desc, link, img, source['name']):
                            cursor.execute('INSERT INTO sent_news (link) VALUES (?)', (link,))
                            conn.commit()
                            time.sleep(2)
            
        first_run = False
        add_log("اكتمل الفحص. جاري الانتظار 5 دقائق...")
        time.sleep(300)

if __name__ == "__main__":
    threading.Thread(target=run_web_server, daemon=True).start()
    start_bot()
