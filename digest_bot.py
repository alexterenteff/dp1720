import requests
import os
import sys
import re
import json
from datetime import datetime, timedelta, timezone

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")
YC_API_KEY = os.environ.get("YC_API_KEY")
YC_FOLDER_ID = os.environ.get("YC_FOLDER_ID")

# ===== АКТУАЛЬНЫЕ КАНАЛЫ SELF-MADE ПРЕДПРИНИМАТЕЛЕЙ =====
SOURCES = [
    "ovchinnikov_stepan",     # Степан Овчинников — IT-предприниматель [citation:2][citation:7]
    "mikerybakov",            # Михаил Рыбаков — бизнес-консультант, коуч [citation:3]
    "grebenukm",              # Михаил Гребенюк — развитие малого бизнеса [citation:9]
    "kutergin_v_ogne",        # Кутергин — сооснователь YouDo [citation:1]
    "bogdanissimmo",          # Путь AI-стартапа к $100K/месяц [citation:1]
    "serafim_livestream",     # Стартап после Y Combinator [citation:1]
    "matvey_kukuy",           # Матвей Кукуй — стартапы и технологии [citation:1]
    "kyrillic",               # Запуск стартапов за рубежом [citation:1]
    "street_mba",             # Венчур по понятиям [citation:1]
    "a_cherniak"              # Алексей Черняк — AI, стартапы, инвестиции [citation:1]
]

POSTS_LIMIT_PER_SOURCE = 4      # сколько постов берём с каждого канала
MAX_POSTS_IN_DIGEST = 10        # итоговое количество пунктов в дайджесте
MAX_AGE_DAYS = 7                # посты не старше 7 дней
HISTORY_FILE = "published.json"

def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return []

def save_history(history):
    with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def commit_and_push():
    try:
        import subprocess
        subprocess.run(['git', 'config', 'user.name', 'github-actions[bot]'], check=False)
        subprocess.run(['git', 'config', 'user.email', 'github-actions[bot]@users.noreply.github.com'], check=False)
        subprocess.run(['git', 'add', HISTORY_FILE], check=False)
        result = subprocess.run(['git', 'diff', '--cached', '--quiet'], check=False)
        if result.returncode != 0:
            subprocess.run(['git', 'commit', '-m', f'Update history {datetime.now().strftime("%Y-%m-%d")}', '--quiet'], check=False)
            subprocess.run(['git', 'push', '--quiet'], check=False)
            print("✅ История сохранена")
    except Exception as e:
        print(f"⚠️ Git error: {e}")

def parse_channel(channel_name, limit):
    """Парсит публичный Telegram-канал"""
    url = f"https://t.me/s/{channel_name}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    posts = []
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code != 200:
            print(f"  ❌ Канал @{channel_name} не найден (статус {r.status_code})")
            return posts
        
        html = r.text
        post_ids = re.findall(r'data-post="([^"]+)"', html)
        texts = re.findall(r'<div class="tgme_widget_message_text[^>]*>(.*?)</div>', html, re.DOTALL)
        dates = re.findall(r'<time datetime="([^"]+)"', html)

        cutoff_time = datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)
        
        for i, raw_text in enumerate(texts[:limit]):
            clean = re.sub(r'<[^>]+>', '', raw_text)
            clean = clean.replace('&quot;', '"').replace('&amp;', '&').strip()
            if not clean or len(clean) < 50:
                continue
            
            # Проверка свежести
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
                'unique_id': post_ids[i] if i < len(post_ids) else None,
                'date': post_date
            })
        print(f"  ✅ @{channel_name}: найдено {len(posts)} свежих постов")
    except Exception as e:
        print(f"  ❌ Ошибка @{channel_name}: {e}")
    return posts

def generate_title_and_summary(text):
    """YandexGPT: заголовок + саммари"""
    if not YC_API_KEY or not YC_FOLDER_ID:
        return text[:60], text[:250]
    try:
        url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
        headers = {
            "Authorization": f"Api-Key {YC_API_KEY}",
            "x-folder-id": YC_FOLDER_ID,
            "Content-Type": "application/json"
        }
        prompt = f"""Ты — редактор бизнес-дайджеста. Сделай из этого поста предпринимателя:
1. Яркий заголовок (до 60 символов).
2. Саммари (2 предложения, до 250 символов).

Пост:
{text[:1800]}

Ответ строго в формате:
ЗАГОЛОВОК: <заголовок>
САММАРИ: <саммари>"""
        payload = {
            "modelUri": f"gpt://{YC_FOLDER_ID}/yandexgpt-lite",
            "completionOptions": {"temperature": 0.6, "maxTokens": 350},
            "messages": [{"role": "user", "text": prompt}]
        }
        resp = requests.post(url, headers=headers, json=payload, timeout=40)
        if resp.status_code == 200:
            content = resp.json()['result']['alternatives'][0]['message']['text']
            title_match = re.search(r'ЗАГОЛОВОК:\s*(.*?)(?:\n|$)', content, re.IGNORECASE)
            summary_match = re.search(r'САММАРИ:\s*(.*?)(?:\n|$)', content, re.IGNORECASE | re.DOTALL)
            title = title_match.group(1).strip() if title_match else text[:60]
            summary = summary_match.group(1).strip() if summary_match else text[:250]
            if len(title) > 80:
                title = title[:77] + "..."
            return title, summary
    except Exception as e:
        print(f"  ⚠️ YandexGPT ошибка: {e}")
    return text[:60], text[:250]

def collect_posts(published_ids):
    all_posts = []
    for ch in SOURCES:
        print(f"📡 Парсинг @{ch}...")
        posts = parse_channel(ch, POSTS_LIMIT_PER_SOURCE)
        for p in posts:
            if p['unique_id'] and p['unique_id'] in published_ids:
                print(f"  ⏭️ Пропуск (уже публиковался): {p['text'][:40]}...")
                continue
            if p['unique_id']:
                published_ids.append(p['unique_id'])
            title, summ = generate_title_and_summary(p['text'])
            all_posts.append({
                'title': title,
                'summary': summ,
                'link': p['link']
            })
            print(f"  ✅ Добавлено: {title[:50]}...")
            if len(all_posts) >= MAX_POSTS_IN_DIGEST:
                break
        if len(all_posts) >= MAX_POSTS_IN_DIGEST:
            break
    return all_posts[:MAX_POSTS_IN_DIGEST]

def send_digest(posts):
    if not posts:
        msg = "🤖 За сегодня нет свежих постов от предпринимателей.\n\n📱 Подпишись: " + CHANNEL_ID
    else:
        msg = "🔥 <b>Дайджест российских предпринимателей</b>\n\n"
        for idx, p in enumerate(posts, 1):
            msg += f"{idx}. <b>{p['title']}</b>\n"
            msg += f"{p['summary']}\n"
            msg += f"🔗 <a href=\"{p['link']}\">Читать источник</a>\n\n"
        msg += "\n💡 Подпишись: " + CHANNEL_ID
    
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
    print("🚀 Запуск дайджеста self-made предпринимателей")
    print(f"📡 Источники: {', '.join(SOURCES)}")
    print(f"⏰ Посты не старше {MAX_AGE_DAYS} дней")
    
    if not BOT_TOKEN or not CHANNEL_ID:
        print("❌ Нет TELEGRAM_BOT_TOKEN или CHANNEL_ID")
        sys.exit(1)
    if not YC_API_KEY or not YC_FOLDER_ID:
        print("⚠️ YandexGPT не настроен — заголовки будут сырыми")

    history = load_history()
    print(f"📚 В истории {len(history)} постов")
    
    posts = collect_posts(history)
    print(f"📊 Собрано пунктов: {len(posts)}")
    
    if posts:
        success = send_digest(posts)
        if success:
            save_history(history)
            commit_and_push()
            print("✅ Дайджест опубликован!")
        else:
            print("❌ Ошибка публикации")
    else:
        print("Нет новых постов")
        sys.exit(0)

if __name__ == "__main__":
    main()
