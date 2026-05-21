import requests
import os
import sys
import re
from datetime import datetime, timedelta, timezone

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")
YC_API_KEY = os.environ.get("YC_API_KEY")
YC_FOLDER_ID = os.environ.get("YC_FOLDER_ID")

SOURCES = [
    "Oskar_Hartmann",
    "rybakovigor",
    "sokolovskiy",
    "EmpathyBiz",
    "TRANSFORMATOR_TV",
    "semchurin_live",
    "spiridonovmax",
    "chernyshev",
    "grebenukm"
]

MAX_AGE_HOURS = 24
POSTS_LIMIT_PER_SOURCE = 20

def parse_channel(channel_name, limit):
    url = f"https://t.me/s/{channel_name}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    posts = []
    print(f"  🔍 Начинаю парсинг @{channel_name}...")
    
    try:
        r = requests.get(url, headers=headers, timeout=15)
        print(f"  📡 HTTP статус: {r.status_code}")
        
        if r.status_code != 200:
            print(f"  ❌ Канал @{channel_name} не найден (статус {r.status_code})")
            return posts
        
        html = r.text
        post_ids = re.findall(r'data-post="([^"]+)"', html)
        texts = re.findall(r'<div class="tgme_widget_message_text[^>]*>(.*?)</div>', html, re.DOTALL)
        dates = re.findall(r'<time datetime="([^"]+)"', html)
        
        print(f"  📊 Найдено элементов: texts={len(texts)}, dates={len(dates)}, ids={len(post_ids)}")
        
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=MAX_AGE_HOURS)
        print(f"  ⏰ Отсечка: {cutoff_time.strftime('%Y-%m-%d %H:%M:%S')} UTC")
        
        for i, raw_text in enumerate(texts[:limit]):
            clean = re.sub(r'<[^>]+>', '', raw_text)
            clean = clean.replace('&quot;', '"').replace('&amp;', '&').strip()
            
            if not clean:
                print(f"  ⏭️ Пост {i+1}: пустой, пропуск")
                continue
            if len(clean) < 30:
                print(f"  ⏭️ Пост {i+1}: слишком короткий ({len(clean)} символов), пропуск")
                continue
            
            post_date = None
            if i < len(dates):
                try:
                    d_str = dates[i].replace('Z', '+00:00')
                    post_date = datetime.fromisoformat(d_str)
                    print(f"  📅 Пост {i+1}: дата {post_date.strftime('%Y-%m-%d %H:%M')}")
                except Exception as e:
                    print(f"  ⚠️ Пост {i+1}: ошибка парсинга даты — {e}")
            
            if post_date and post_date < cutoff_time:
                print(f"  ⏭️ Пост {i+1}: старый ({post_date.strftime('%Y-%m-%d')}), пропуск")
                continue
            
            print(f"  ✅ Пост {i+1}: подходит! Длина {len(clean)} символов")
            posts.append({
                'text': clean[:2500],
                'link': f"https://t.me/{post_ids[i]}" if i < len(post_ids) else f"https://t.me/{channel_name}",
                'author': channel_name,
                'date': post_date
            })
        
        print(f"  📊 @{channel_name}: итого подходящих постов — {len(posts)}")
        
    except Exception as e:
        print(f"  ❌ Ошибка @{channel_name}: {e}")
    
    return posts

def get_author_display_name(author_username):
    names = {
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
        print(f"  ⚠️ YandexGPT ошибка: {e}")
    return text[:200]

def send_to_telegram(posts):
    if not posts:
        msg = "📭 За последние 24 часа новых постов нет."
        print("📭 Сообщение: нет постов")
    else:
        msg = "📌 <b>Личный дайджест — всё, что написали за сутки</b>\n\n"
        for idx, p in enumerate(posts, 1):
            msg += f"{idx}. <b>{p['author']}</b>\n"
            msg += f"{p['summary']}\n"
            msg += f"🔗 <a href=\"{p['link']}\">Читать полностью</a>\n\n"
        print(f"📤 Подготовлено сообщение с {len(posts)} постами")
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHANNEL_ID,
        "text": msg,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        r = requests.post(url, json=payload, timeout=15)
        print(f"📡 Telegram ответ: {r.status_code} — {r.text[:200]}")
        return r.json().get('ok', False)
    except Exception as e:
        print(f"❌ Ошибка отправки: {e}")
        return False

def main():
    print("=" * 60)
    print("🚀 ЛИЧНАЯ ЧИТАЛКА — ДИАГНОСТИЧЕСКИЙ РЕЖИМ")
    print("=" * 60)
    
    print(f"\n📡 Каналы: {', '.join(SOURCES)}")
    print(f"⏰ Посты за последние {MAX_AGE_HOURS} часов")
    print(f"🔑 TELEGRAM_BOT_TOKEN: {'✅ есть' if BOT_TOKEN else '❌ НЕТ'}")
    print(f"🔑 CHANNEL_ID: {'✅ есть' if CHANNEL_ID else '❌ НЕТ'}")
    print(f"🔑 YC_API_KEY: {'✅ есть' if YC_API_KEY else '❌ НЕТ'}")
    print(f"🔑 YC_FOLDER_ID: {'✅ есть' if YC_FOLDER_ID else '❌ НЕТ'}")
    
    if not BOT_TOKEN or not CHANNEL_ID:
        print("❌ Ошибка: нет TELEGRAM_BOT_TOKEN или CHANNEL_ID")
        sys.exit(1)
    
    all_posts = []
    for ch in SOURCES:
        print(f"\n--- Обработка @{ch} ---")
        posts = parse_channel(ch, POSTS_LIMIT_PER_SOURCE)
        for p in posts:
            author = get_author_display_name(p['author'])
            print(f"  📝 Генерация саммари для @{ch}...")
            summary = generate_summary(p['text'], author)
            all_posts.append({
                'summary': summary,
                'link': p['link'],
                'author': author
            })
    
    print(f"\n📊 ВСЕГО СОБРАНО ПОСТОВ: {len(all_posts)}")
    
    if all_posts:
        print("📤 Отправляем в Telegram...")
        success = send_to_telegram(all_posts)
        if success:
            print("✅ Дайджест опубликован!")
        else:
            print("❌ Ошибка публикации")
            sys.exit(1)
    else:
        print("📭 Нет постов за последние 24 часа")
        sys.exit(0)

if __name__ == "__main__":
    main()
