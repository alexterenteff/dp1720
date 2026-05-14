import requests
import os
import sys
import re
import json
from datetime import datetime, timezone

# ===== НАСТРОЙКИ =====
SOURCES = [
    "vc_business",          # VC.ru — бизнес
    "teddy_business",       # Тедди Бизнес
    "business_people_ru",   # Бизнес люди
    "sekret_firmy",         # Секрет фирмы
    "besedka_biz"           # Беседка Бизнес
]

BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID")
YC_API_KEY = os.environ.get("YC_API_KEY")
YC_FOLDER_ID = os.environ.get("YC_FOLDER_ID")

POSTS_LIMIT_PER_SOURCE = 5      # сколько постов берём с каждого канала
MAX_POSTS_IN_DIGEST = 10        # итоговое количество пунктов в дайджесте
HISTORY_FILE = "published.json"

# ===== РАБОТА С ИСТОРИЕЙ =====
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
            subprocess.run(['git', 'commit', '-m', f'Update history {datetime.now()}', '--quiet'], check=False)
            subprocess.run(['git', 'push', '--quiet'], check=False)
            print("✅ История сохранена в репозиторий")
    except Exception as e:
        print(f"⚠️ Ошибка git: {e}")

# ===== ПАРСИНГ TELEGRAM-КАНАЛА =====
def parse_channel(channel_name, limit):
    url = f"https://t.me/s/{channel_name}"
    headers = {'User-Agent': 'Mozilla/5.0'}
    posts = []
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code != 200:
            return posts
        html = r.text
        post_ids = re.findall(r'data-post="([^"]+)"', html)
        texts = re.findall(r'<div class="tgme_widget_message_text[^>]*>(.*?)</div>', html, re.DOTALL)
        dates = re.findall(r'<time datetime="([^"]+)"', html)

        for i, raw_text in enumerate(texts[:limit]):
            clean = re.sub(r'<[^>]+>', '', raw_text)
            clean = clean.replace('&quot;', '"').replace('&amp;', '&').strip()
            if not clean or len(clean) < 50:
                continue
            post_date = None
            if i < len(dates):
                try:
                    d_str = dates[i].replace('Z', '+00:00')
                    post_date = datetime.fromisoformat(d_str)
                except:
                    pass
            # пропускаем посты старше 14 дней
            if post_date and (datetime.now(timezone.utc) - post_date).days > 14:
                continue
            posts.append({
                'text': clean[:2500],
                'link': f"https://t.me/{post_ids[i]}" if i < len(post_ids) else f"https://t.me/{channel_name}",
                'unique_id': post_ids[i] if i < len(post_ids) else None
            })
    except Exception as e:
        print(f"Ошибка при парсинге @{channel_name}: {e}")
    return posts

# ===== ЯНДЕКС GPT: ЗАГОЛОВОК + САММАРИ =====
def generate_title_and_summary(text):
    if not YC_API_KEY or not YC_FOLDER_ID:
        return text[:80], text[:300]
    try:
        url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
        headers = {
            "Authorization": f"Api-Key {YC_API_KEY}",
            "x-folder-id": YC_FOLDER_ID,
            "Content-Type": "application/json"
        }
        prompt = f"""Ты — редактор бизнес-дайджеста. Сделай из этого поста:
1. Короткий яркий заголовок (до 60 символов).
2. Саммари (2 предложения, максимум 250 символов).

Пост:
{text[:2000]}

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
        print(f"Ошибка YandexGPT: {e}")
    return text[:60], text[:250]

# ===== СБОР ВСЕХ ПОСТОВ =====
def collect_posts(published_ids):
    all_posts = []
    for ch in SOURCES:
        print(f"Парсинг @{ch}...")
        posts = parse_channel(ch, POSTS_LIMIT_PER_SOURCE)
        for p in posts:
            if p['unique_id'] and p['unique_id'] in published_ids:
                continue
            if p['unique_id']:
                published_ids.append(p['unique_id'])
            title, summ = generate_title_and_summary(p['text'])
            all_posts.append({
                'title': title,
                'summary': summ,
                'link': p['link']
            })
            if len(all_posts) >= MAX_POSTS_IN_DIGEST:
                break
        if len(all_posts) >= MAX_POSTS_IN_DIGEST:
            break
    return all_posts[:MAX_POSTS_IN_DIGEST]

# ===== ПУБЛИКАЦИЯ В TELEGRAM =====
def send_digest(posts):
    if not posts:
        msg = "🤖 За сегодня нет свежих постов.\n\n📱 Подпишись: " + CHANNEL_ID
    else:
        msg = "📌 **Бизнес-дайджест**\n\n"
        for idx, p in enumerate(posts, 1):
            msg += f"{idx}. <b>{p['title']}</b>\n"
            msg += f"{p['summary']}\n"
            msg += f"🔗 <a href=\"{p['link']}\">Источник</a>\n\n"
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
        print(f"Ошибка отправки: {e}")
        return False

# ===== MAIN =====
def main():
    print("🚀 Запуск бизнес-дайджеста")
    if not BOT_TOKEN or not CHANNEL_ID:
        print("❌ Нет TELEGRAM_BOT_TOKEN или CHANNEL_ID")
        sys.exit(1)
    if not YC_API_KEY or not YC_FOLDER_ID:
        print("⚠️ YandexGPT не будет работать — заголовки/саммари будут сырыми")

    history = load_history()
    posts = collect_posts(history)
    print(f"📊 Собрано пунктов: {len(posts)}")

    if posts:
        success = send_digest(posts)
        if success:
            save_history(history)
            commit_and_push()
            print("✅ Дайджест опубликован")
        else:
            print("❌ Ошибка публикации")
    else:
        print("Нет новых постов")
        sys.exit(0)

if __name__ == "__main__":
    main()
