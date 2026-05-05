import feedparser
import sqlite3
import requests
import time
import threading
import os
import html
import re
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from deep_translator import GoogleTranslator

# ================= الإعدادات الأساسية =================
BOT_TOKEN = "7322365145:AAG0Dr8DWcTOZymxncpNNgYtAkw1F9JaSfA"
CHANNEL_ID = "@AkhbarNow2"
CHANNEL_LINK = "https://t.me/AkhbarNow2"

# قائمة المصادر مع روابط مستقرة
SOURCES = [
    {"url": "https://www.aljazeera.net/aljazeerarss", "name": "الجزيرة", "translate": False},
    {"url": "https://www.skynewsarabia.com/rss.xml", "name": "سكاي نيوز عربية", "translate": False},
    {"url": "https://arabic.rt.com/rss/", "name": "RT Arabic", "translate": False},
    {"url": "https://www.alarabiya.net/.mrss/ar/index.xml", "name": "العربية", "translate": False},
    {"url": "https://www.bbc.com/arabic/index.xml", "name": "BBC News عربي", "translate": False},
    {"url": "http://arabic.cnn.com/rss/cnnarabic_world.rss", "name": "CNN بالعربية", "translate": False},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml", "name": "New York Times", "translate": True},
    {"url": "https://www.reutersagency.com/feed/?best-topics=world-news&post_type=best", "name": "Reuters", "translate": True},
]

# مواعيد الأذكار والورد اليومي (بتوقيت اليمن)
ISLAMIC_CONTENT = {
    "07": {"type": "ذكر", "title": "☀️ أذكار الصباح", "content": "أصبحنا وأصبح الملك لله، والحمد لله، لا إله إلا الله وحده لا شريك له."},
    "13": {"type": "قرآن", "title": "📖 الورد اليومي", "content": "قال تعالى: (إِنَّ هَٰذَا الْقُرْآنَ يَهْدِي لِلَّتِي هِيَ أَقْوَمُ)\nتلاوة خاشعة لراحة قلبك من قناة أخبار العالم."},
    "18": {"type": "دعاء", "title": "🌆 دعاء المغرب", "content": "اللهم بك أمسينا، وبك أصبحنا، وبك نحيا، وبك نموت، وإليك المصير."},
    "22": {"type": "ذكر", "title": "🌙 أذكار النوم", "content": "باسمك ربي وضعت جنبي، وبك أرفعه، فإن أمسكت نفسي فارحمها."}
}

current_status = "بدء التشغيل..."
recent_logs = []
sent_adhkar_today = ""

# ================= لوحة التحكم الاحترافية (Dark Mode) =================
class WebHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        logs_html = "".join([f"<div class='log-item'>{log}</div>" for log in reversed(recent_logs[-25:])])
        html_content = f"""
        <html>
            <head>
                <title>Control Panel | News Bot</title>
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <style>
                    body {{ background-color: #0f0f0f; color: #f0f0f0; font-family: 'Segoe UI', Tahoma; padding: 15px; direction: rtl; margin: 0; }}
                    .container {{ max-width: 900px; margin: auto; background: #1a1a1a; padding: 20px; border-radius: 12px; border: 1px solid #333; }}
                    h1 {{ color: #00ff88; text-align: center; font-size: 24px; }}
                    .status-box {{ background: #222; padding: 12px; border-radius: 8px; border-right: 4px solid #00ff88; margin-bottom: 15px; }}
                    .log-container {{ background: #000; padding: 10px; border-radius: 6px; height: 400px; overflow-y: auto; font-family: 'Consolas', monospace; font-size: 12px; }}
                    .log-item {{ border-bottom: 1px solid #111; padding: 4px 0; color: #00d2ff; }}
                    .footer {{ text-align: center; margin-top: 15px; color: #555; font-size: 11px; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>⚙️ نظام أتمتة أخبار العالم</h1>
                    <div class="status-box"><strong>الحالة:</strong> {current_status}</div>
                    <div class="log-container">{logs_html}</div>
                    <div class="footer">توقيت السيرفر المحدث: {datetime.now().strftime("%H:%M:%S")}</div>
                </div>
            </body>
        </html>
        """
        self.wfile.write(html_content.encode('utf-8'))

    def do_HEAD(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()

def add_log(text):
    global current_status
    current_status = text
    # عرض الوقت في السجلات بتوقيت اليمن أيضاً
    yemen_now = datetime.utcnow() + timedelta(hours=3)
    timestamp = yemen_now.strftime("%H:%M:%S")
    recent_logs.append(f"[{timestamp}] {text}")
    print(text)

# --- المهام الدينية (توقيت اليمن) ---
def check_islamic_tasks():
    global sent_adhkar_today
    # تحويل توقيت السيرفر إلى توقيت اليمن (جرينتش + 3)
    yemen_time = datetime.utcnow() + timedelta(hours=3)
    hour = yemen_time.strftime("%H")
    today = yemen_time.strftime("%Y-%m-%d")

    if hour in ISLAMIC_CONTENT and sent_adhkar_today != f"{today}_{hour}":
        task = ISLAMIC_CONTENT[hour]
        add_log(f"⏰ حان موعد {task['title']} - جارِ الإرسال...")
        msg = f"✨ *{task['title']}*\n\n{task['content']}\n\n📍 ورد المسلم اليومي\n\n🔹 *قناة أخبار العالم*\n✅ تابعنا لكل جديد فورا!\n🔗 [انضم إلينا هنا]({CHANNEL_LINK})"
        
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHANNEL_ID, "text": msg, "parse_mode": "Markdown"})
        sent_adhkar_today = f"{today}_{hour}"

# --- معالجة النصوص ---
def clean_text(raw_html):
    if not raw_html: return ""
    cleanr = re.compile('<.*?>')
    return html.unescape(re.sub(cleanr, '', raw_html).strip())

def translate_text(text):
    try: return GoogleTranslator(source='auto', target='ar').translate(text)
    except: return text

# --- نظام الإرسال الذكي ---
def send_to_telegram(title, description, link, image_url, source_name):
    # ربط المصدر برابط الخبر
    footer = f"\n\n📍 المصدر: [{source_name}]({link})"
    signature = f"\n\n🔹 *قناة أخبار العالم*\n✅ تابعنا لكل جديد فورا!\n🔗 [انضم إلينا هنا]({CHANNEL_LINK})"
    full_message = f"🔴 *{title}*\n\n{description}{footer}{signature}"
    
    # 1. محاولة الإرسال مع صورة
    if image_url:
        url_photo = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
        payload = {"chat_id": CHANNEL_ID, "parse_mode": "Markdown", "photo": image_url, "caption": full_message}
        resp = requests.post(url_photo, data=payload)
        if resp.status_code == 200: return True
        else: add_log(f"⚠️ فشلت الصورة من {source_name}، جاري الإرسال كنص...")

    # 2. الإرسال كنص (الخطة البديلة)
    url_text = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload_text = {"chat_id": CHANNEL_ID, "parse_mode": "Markdown", "text": full_message, "disable_web_page_preview": False}
    resp_text = requests.post(url_text, data=payload_text)
    return resp_text.status_code == 200

# --- المحرك الرئيسي ---
first_run = True

def start_bot():
    global first_run
    conn = sqlite3.connect('news_bot.db')
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS sent_news (id INTEGER PRIMARY KEY AUTOINCREMENT, link TEXT UNIQUE)')
    conn.commit()

    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

    while True:
        check_islamic_tasks()

        for source in SOURCES:
            add_log(f"فحص: {source['name']}...")
            try:
                response = requests.get(source['url'], headers=headers, timeout=15)
                feed = feedparser.parse(response.content)
                
                if len(feed.entries) > 0:
                    for entry in reversed(feed.entries):
                        link = entry.link
                        cursor.execute('SELECT link FROM sent_news WHERE link = ?', (link,))
                        if cursor.fetchone() is None:
                            title = clean_text(entry.title)
                            desc = clean_text(entry.summary if 'summary' in entry else "")
                            
                            if first_run:
                                cursor.execute('INSERT INTO sent_news (link) VALUES (?)', (link,))
                                conn.commit()
                            else:
                                if source['translate']:
                                    add_log(f"ترجمة من {source['name']}...")
                                    title = translate_text(title)
                                    desc = translate_text(desc)

                                img = ""
                                if 'links' in entry:
                                    for l in entry.links:
                                        if 'image' in l.get('type', ''): img = l.get('href', '')

                                if send_to_telegram(title, desc, link, img, source['name']):
                                    add_log(f"✅ تم إرسال خبر من {source['name']}")
                                    cursor.execute('INSERT INTO sent_news (link) VALUES (?)', (link,))
                                    conn.commit()
                                    time.sleep(3)
            except: add_log(f"❌ خطأ في {source['name']}")
                
        first_run = False
        add_log("💤 انتظار 120 ثانية...")
        time.sleep(120)

if __name__ == "__main__":
    # تشغيل خادم الويب
    threading.Thread(target=lambda: HTTPServer(('0.0.0.0', int(os.environ.get("PORT", 8080))), WebHandler).serve_forever(), daemon=True).start()
    # تشغيل البوت
    start_bot()
