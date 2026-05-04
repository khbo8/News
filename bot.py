import feedparser
import sqlite3
import requests
import time
import threading
import os
import html
import re
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from deep_translator import GoogleTranslator

# ================= الإعدادات =================
BOT_TOKEN = "7322365145:AAG0Dr8DWcTOZymxncpNNgYtAkw1F9JaSfA"
CHANNEL_ID = "@AkhbarNow2"
CHANNEL_LINK = "https://t.me/AkhbarNow2"

# قائمة المصادر
SOURCES = [
    {"url": "https://www.aljazeera.net/aljazeerarss", "name": "الجزيرة", "translate": False},
    {"url": "https://www.skynewsarabia.com/rss.xml", "name": "سكاي نيوز عربية", "translate": False},
    {"url": "https://arabic.rt.com/rss/", "name": "RT Arabic", "translate": False},
    {"url": "https://www.alarabiya.net/.mrss/ar/last-24-hours.xml", "name": "العربية", "translate": False},
    {"url": "https://www.bbc.com/arabic/index.xml", "name": "BBC News عربي", "translate": False},
    {"url": "http://arabic.cnn.com/rss/cnnarabic_world.rss", "name": "CNN بالعربية", "translate": False},
    {"url": "https://rss.nytimes.com/services/xml/rss/nyt/World.xml", "name": "New York Times", "translate": True},
    {"url": "https://www.reutersagency.com/feed/?best-topics=world-news&post_type=best", "name": "Reuters", "translate": True},
]

ISLAMIC_CONTENT = {
    "07": {"type": "ذكر", "title": "☀️ أذكار الصباح", "content": "أصبحنا وأصبح الملك لله، والحمد لله، لا إله إلا الله وحده لا شريك له."},
    "13": {"type": "قرآن", "title": "📖 الورد اليومي", "content": "قال تعالى: (إِنَّ هَٰذَا الْقُرْآنَ يَهْدِي لِلَّتِي هِيَ أَقْوَمُ)\nتلاوة خاشعة: https://youtu.be/dQw4w9WgXcQ"},
    "18": {"type": "دعاء", "title": "🌆 دعاء المغرب", "content": "اللهم بك أمسينا، وبك أصبحنا، وبك نحيا، وبك نموت، وإليك المصير."},
    "22": {"type": "ذكر", "title": "🌙 أذكار النوم", "content": "باسمك ربي وضعت جنبي، وبك أرفعه، فإن أمسكت نفسي فارحمها."}
}

current_status = "بدء التشغيل..."
recent_logs = []
sent_adhkar_today = ""

# ==============================================

# --- واجهة المستخدم (Dark Mode UI) ---
class WebHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        logs_html = "".join([f"<div class='log-item'>{log}</div>" for log in reversed(recent_logs[-20:])])
        html_content = f"""
        <html>
            <head>
                <title>Control Panel | News Bot</title>
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <style>
                    body {{ background-color: #121212; color: #e0e0e0; font-family: 'Segoe UI', Tahoma; padding: 20px; direction: rtl; margin: 0; }}
                    .container {{ max-width: 800px; margin: auto; background: #1e1e1e; padding: 25px; border-radius: 15px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); }}
                    h1 {{ color: #00e676; border-bottom: 2px solid #333; padding-bottom: 10px; }}
                    .status-box {{ background: #263238; padding: 15px; border-radius: 8px; border-right: 5px solid #00e676; margin: 20px 0; }}
                    .log-container {{ background: #000; padding: 15px; border-radius: 8px; height: 350px; overflow-y: auto; font-family: monospace; font-size: 13px; }}
                    .log-item {{ border-bottom: 1px solid #222; padding: 5px 0; color: #81d4fa; }}
                    .footer {{ text-align: center; margin-top: 20px; color: #666; font-size: 12px; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>⚙️ لوحة تحكم بوت أخبار العالم</h1>
                    <div class="status-box">
                        <strong>الحالة الحالية:</strong> {current_status}
                    </div>
                    <h3>📜 سجل العمليات الأخير:</h3>
                    <div class="log-container">{logs_html}</div>
                    <div class="footer">البوت يعمل الآن بنظام المراقبة اللحظية 24/7</div>
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
    timestamp = datetime.now().strftime("%H:%M:%S")
    recent_logs.append(f"[{timestamp}] {text}")
    print(text)

def check_islamic_tasks():
    global sent_adhkar_today
    now = datetime.now()
    hour = now.strftime("%H")
    today = now.strftime("%Y-%m-%d")

    if hour in ISLAMIC_CONTENT and sent_adhkar_today != f"{today}_{hour}":
        task = ISLAMIC_CONTENT[hour]
        add_log(f"إرسال {task['title']} إلى القناة...")
        msg = f"✨ *{task['title']}*\n\n{task['content']}\n\n📍 ورد المسلم اليومي\n\n🔹 *قناة أخبار العالم*\n✅ تابعنا لتصلك آخر المستجدات فورا!\n🔗 [انضم إلينا هنا]({CHANNEL_LINK})"
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": CHANNEL_ID, "text": msg, "parse_mode": "Markdown", "disable_web_page_preview": False})
        sent_adhkar_today = f"{today}_{hour}"

def clean_text(raw_html):
    if not raw_html: return ""
    cleanr = re.compile('<.*?>')
    return html.unescape(re.sub(cleanr, '', raw_html).strip())

def translate_text(text):
    try:
        return GoogleTranslator(source='auto', target='ar').translate(text)
    except:
        return text

def send_to_telegram(title, description, link, image_url, source_name):
    footer = f"\n\n🔹 *قناة أخبار العالم*\n✅ تابعنا لتصلك آخر المستجدات لحظة بلحظة!\n🔗 [انضم إلينا هنا]({CHANNEL_LINK})"
    full_message = f"🔴 *{title}*\n\n{description}\n\n📍 المصدر: {source_name}{footer}"
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/" + ("sendPhoto" if image_url else "sendMessage")
    payload = {"chat_id": CHANNEL_ID, "parse_mode": "Markdown", ("photo" if image_url else "text"): (image_url if image_url else full_message)}
    if image_url: payload["caption"] = full_message

    try:
        response = requests.post(url, data=payload)
        if response.status_code != 200:
            add_log(f"❌ فشل إرسال الخبر لتليجرام: {response.text}")
            return False
        return True
    except Exception as e: 
        add_log(f"❌ خطأ في الاتصال بتليجرام: {e}")
        return False

first_run = True

def start_bot():
    global first_run
    conn = sqlite3.connect('news_bot.db')
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS sent_news (id INTEGER PRIMARY KEY AUTOINCREMENT, link TEXT UNIQUE)')
    conn.commit()

    # رأس متصفح وهمي لتجاوز حظر المواقع
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Cache-Control': 'no-cache'
    }

    while True:
        check_islamic_tasks()

        for source in SOURCES:
            add_log(f"فحص مصدر: {source['name']}...")
            try:
                # استخدام requests مع المتصفح الوهمي لتجاوز الحماية
                response = requests.get(source['url'], headers=headers, timeout=15)
                feed = feedparser.parse(response.content)
                
                if len(feed.entries) == 0:
                    add_log(f"⚠️ تحذير: لم يتم جلب أي أخبار من {source['name']} (قد يكون الرابط محظوراً أو فارغاً)")
                    continue
                else:
                    add_log(f"✅ تم العثور على {len(feed.entries)} خبر في {source['name']}")

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
                                add_log(f"ترجمة خبر من {source['name']}...")
                                title = translate_text(title)
                                desc = translate_text(desc)

                            img = ""
                            if 'links' in entry:
                                for l in entry.links:
                                    if 'image' in l.get('type', ''): img = l.get('href', '')

                            add_log(f"إرسال خبر جديد من {source['name']}")
                            if send_to_telegram(title, desc, link, img, source['name']):
                                cursor.execute('INSERT INTO sent_news (link) VALUES (?)', (link,))
                                conn.commit()
                                time.sleep(3)
            except Exception as e:
                add_log(f"❌ خطأ أثناء الاتصال بمصدر {source['name']}")
                
        first_run = False
        add_log("اكتملت الجولة. جاري الانتظار 120 ثانية...")
        time.sleep(120)

if __name__ == "__main__":
    threading.Thread(target=lambda: HTTPServer(('0.0.0.0', int(os.environ.get("PORT", 8080))), WebHandler).serve_forever(), daemon=True).start()
    start_bot()
