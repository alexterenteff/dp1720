import requests
import os
import sys
import re
from datetime import datetime, timedelta, timezone

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")
YC_API_KEY = os.environ.get("YC_API_KEY")
YC_FOLDER_ID = os.environ.get("YC_FOLDER_ID")

# ===== ВАШИ КАНАЛЫ =====
SOURCES = [
    # Основные авторы
    "Oskar_Hartmann",        # Оскар Хартманн
    "rybakovigor",           # Игорь Рыбаков
    "sokolovskiy",           # Александр Соколовский
    "EmpathyBiz",            # Евгений Щепин
    "TRANSFORMATOR_TV",      # Дмитрий Портнягин
    "semchurin_live",        # Никита Семчурин
    "spiridonovmax",         # Максим Спиридонов
    "chernyshev",            # Александр Чернышев
    "grebenukm",             # Михаил Гребенюк ✅ добавлен
]

MAX_AGE_HOURS = 24           # только за последние 24 часа
POSTS_LIMIT_PER_SOURCE = 20  # берём до 20 постов с канала (на случай, если блогер пишет много)

def parse_channel(channel_name, limit):
    url = f"https://t.me/s/{channel_name}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    posts = []
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code != 200:
            print(f"  ❌ Канал @{channel_name} не найден")
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
                'author': channel_name,
                'date': post_date
            })
        print(f"  ✅ @{channel_name}: найдено {len(posts)} постов за 24 часа")
    except Exception as e:
        print(f"  ❌ Ошибка @{channel_name}: {e}")
    return posts

def get_author_display_name(author_username):
    author_names = {
        "Oskar_Hartmann": "Оскар Хартманн",
        "rybakovigor": "Игорь Рыбаков",
        "sokolovskiy": "Александр Соколовский",
        "EmpathyBiz": "Евгений Щепин",
        "TRANSFORMATOR_TV": "Дмитрий Портнягин",
        "semchurin_live": "Никита Семчурин",
        "spiridonovmax": "Максим Спиридонов",
        "chernyshev": "Александр Чернышев",
        "grebenukm": "Михаил Гребенюк"
    }
    return author_names.get(author_username, f"@{author_username}")

def generate_summary(text, author_name):
    """YandexGPT делает короткое саммари (без заголовка)"""
    if not YC_API_KEY or not YC_FOLDER_ID:
        return text[:200]
    try:
        url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
        headers = {
            "Authorization": f"Api-Key {YC_API_KEY}",
            "x-folder-id": YC_FOLDER_ID,
            "Content-Type": "application/json"
        }
        prompt = f"""Сделай краткое саммари этого поста (максимум 250 символов, 2 предложения). Сохрани главную мысль.

Пост:
{text[:1500]}"""
        payload = {
            "modelUri": f"gpt://{YC_FOLDER_ID}/yandexgpt-lite",
            "completionOptions": {"temperature": 0.6, "maxTokens": 300},
            "messages": [{"role": "user", "text": prompt}]
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=40)
        if resp.status_code == 200:
            content = resp.json()['result']['alternatives'][0]['message']['text']
            return content.strip()[:250]
    except Exception as e:
        print(f"  ⚠️ YandexGPT ошибка: {e}")
    return text[:200]

def collect_all_posts():
    all_posts = []
    for ch in SOURCES:
        print(f"📡 Парсинг @{ch}...")
        posts = parse_channel(ch, POSTS_LIMIT_PER_SOURCE)
        for p in posts:
            author_display = get_author_display_name(p['author'])
            summary = generate_summary(p['text'], author_display)
            all_posts.append({
                'summary': summary,
                'link': p['link'],
                'author': author_display
            })
            print(f"  ✅ Добавлен пост от {author_display}")
    return all_posts

def send_to_telegram(posts):
    if not posts:
        msg = "📭 За последние 24 часа новых постов нет."
    else:
        msg = "📌 <b>Личный дайджест — всё, что написали за сутки</b>\n\n"
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
        print(f"❌ Ошибка отправки: {e}")
        return False

def main():
    print("🚀 Личная читалка предпринимателей")
    print(f"📡 Каналы: {', '.join(SOURCES)}")
    print(f"⏰ Посты за последние 24 часа")
    
    if not BOT_TOKEN or not CHANNEL_ID:
        print("❌ Нет TELEGRAM_BOT_TOKEN или CHANNEL_ID")
        sys.exit(1)

    posts = collect_all_posts()
    print(f"📊 Собрано постов: {len(posts)}")
    
    if posts:
        success = send_to_telegram(posts)
        if success:
            print("✅ Дайджест опубликован!")
        else:
            print("❌ Ошибка публикации")
    else:
        print("Нет новых постов за последние 24 часа")

if __name__ == "__main__":
    main()
