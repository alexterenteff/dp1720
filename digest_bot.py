import requests
import os
import sys
import re
from datetime import datetime, timedelta, timezone

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")
YC_API_KEY = os.environ.get("YC_API_KEY")
YC_FOLDER_ID = os.environ.get("YC_FOLDER_ID")

# ===== ОБНОВЛЁННЫЙ СПИСОК КАНАЛОВ =====
SOURCES = [
    "Oskar_Hartmann",
    "rybakovigor",
    "sokolovskiy",
    "EmpathyBiz",
    "TRANSFORMATOR_TV",
    "semchurin_live",
    "mspiridonov",
    "chernyshev",
    "grebenukm",
    "MargulanSeissembai",
    "ruminblog",
    "honestmarketing",
    "hikollegi",          # возвращён
    "durov_russia"        # возвращён
]

MAX_AGE_HOURS = 72
POSTS_LIMIT_PER_SOURCE = 20

def parse_channel(channel_name, limit):
    url = f"https://t.me/s/{channel_name}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    posts = []
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code != 200:
            return posts
        
        html = r.text
        post_ids = re.findall(r'data-post="([^"]+)"', html)
        texts = re.findall(r'<div class="tgme_widget_message_text[^>]*>(.*?)</div>', html, re.DOTALL)
        dates = re.findall(r'<time datetime="([^"]+)"', html)

        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=MAX_AGE_HOURS)
        
        for i, raw_text in enumerate(texts[:limit]):
            clean = re.sub(r'<[^>]+>', '', raw_text)
            clean = clean.replace('&quot;', '"').replace('&amp;', '&').strip()
            if not clean or len(clean) < 30:
                continue
            
            post_date = None
            if i < len(dates):
                try:
                    d_str = dates[i].replace('Z', '+00:00')
                    post_date = datetime.fromisoformat(d_str)
                except:
                    pass
            
            if post_date and post_date < cutoff_time:
                continue
            
            posts.append({
                'text': clean[:2500],
                'link': f"https://t.me/{post_ids[i]}" if i < len(post_ids) else f"https://t.me/{channel_name}",
                'author': channel_name
            })
    except Exception as e:
        print(f"Ошибка @{channel_name}: {e}")
    return posts

def get_author_display_name(author_username):
    names = {
        "Oskar_Hartmann": "Оскар Хартманн",
        "rybakovigor": "Игорь Рыбаков",
        "sokolovskiy": "Александр Соколовский",
        "EmpathyBiz": "Евгений Щепин",
        "TRANSFORMATOR_TV": "Дмитрий Портнягин",
        "semchurin_live": "Никита Семчурин",
        "mspiridonov": "Максим Спиридонов",
        "chernyshev": "Александр Чернышев",
        "grebenukm": "Михаил Гребенюк",
        "MargulanSeissembai": "Маргулан Сейсембаев",
        "ruminblog": "Алексей Румянцев",
        "honestmarketing": "Макс Корольков",
        "hikollegi": "Hikollegi",
        "durov_russia": "Durov Russia"
    }
    return names.get(author_username, f"@{author_username}")

def generate_summary(text, author_name):
    if not YC_API_KEY or not YC_FOLDER_ID:
        return text[:200]
    try:
        url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
        headers = {
            "Authorization": f"Api-Key {YC_API_KEY}",
            "x-folder-id": YC_FOLDER_ID,
            "Content-Type": "application/json"
        }
        prompt = f"Сделай краткое саммари этого поста (максимум 250 символов, 2 предложения):\n\n{text[:1500]}"
        payload = {
            "modelUri": f"gpt://{YC_FOLDER_ID}/yandexgpt-lite",
            "completionOptions": {"temperature": 0.6, "maxTokens": 300},
            "messages": [{"role": "user", "text": prompt}]
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=40)
        if resp.status_code == 200:
            return resp.json()['result']['alternatives'][0]['message']['text'].strip()[:250]
    except Exception as e:
        print(f"YandexGPT ошибка: {e}")
    return text[:200]

def send_to_telegram(posts):
    if not posts:
        msg = "📭 За последние 3 дня новых постов нет."
    else:
        msg = "📌 <b>Личный дайджест — всё, что написали за 3 дня</b>\n\n"
        for idx, p in enumerate(posts, 1):
            msg += f"{idx}. <b>{p['author']}</b>\n"
            msg += f"{p['summary']}\n"
            msg += f"🔗 <a href=\"{p['link']}\">Читать полностью</a>\n\n"
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHANNEL_ID,
        "text": msg,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        r = requests.post(url, json=payload, timeout=15)
        return r.json().get('ok', False)
    except Exception as e:
        print(f"Ошибка отправки: {e}")
        return False

def main():
    print("🚀 Личная читалка предпринимателей")
    print(f"📡 Источников: {len(SOURCES)}")
    print(f"⏰ Посты за последние {MAX_AGE_HOURS} часов")
    
    if not BOT_TOKEN or not CHANNEL_ID:
        print("❌ Нет TELEGRAM_BOT_TOKEN или CHANNEL_ID")
        sys.exit(1)

    all_posts = []
    for ch in SOURCES:
        posts = parse_channel(ch, POSTS_LIMIT_PER_SOURCE)
        for p in posts:
            author = get_author_display_name(p['author'])
            summary = generate_summary(p['text'], author)
            all_posts.append({
                'summary': summary,
                'link': p['link'],
                'author': author
            })
    
    print(f"📊 Собрано постов: {len(all_posts)}")
    
    if all_posts:
        success = send_to_telegram(all_posts)
        if success:
            print("✅ Дайджест опубликован!")
        else:
            print("❌ Ошибка публикации")
    else:
        print("Нет постов за последние 3 дня")

if __name__ == "__main__":
    main()
