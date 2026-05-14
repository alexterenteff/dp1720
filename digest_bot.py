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

# ===== РАСШИРЕННЫЙ СПИСОК КАНАЛОВ =====
SOURCES = [
    # Новые авторы
    "Oskar_Hartmann",        # Оскар Хартманн — бизнес-ангел, стартапы
    "rybakovigor",           # Игорь Рыбаков — миллиардер, масштабирование
    "sokolovskiy",           # Александр Соколовский — digital, AI
    "EmpathyBiz",            # Евгений Щепин — управление, люди, бренд
    "TRANSFORMATOR_TV",      # Дмитрий Портнягин — бизнес-блогер СНГ
    "semchurin_live",        # Никита Семчурин — Telegram, медиа
    "spiridonovmax",         # Максим Спиридонов — IT, инвестиции
    "chernyshev",            # Александр Чернышев — маркетинг, продажи

    # Остальные предпринимательские каналы
    "the_edinorog",
    "rus_venture",
    "temnaya_storona",
    "street_mba",
    "serafim_livestream",
    "bogdanissimmo",
    "kyrillic",
    "kumar_solo",
    "indeks_dyatla",
    "molyanov",
    "maximspiridonov",
    "sostoyanie_potoka",
    "trevozhny_hr",
    "glavred_club",
    "zhenya_lepekhin",
    "fedorinsights",
    "MargulanSeissembai",
    "ovchinnikov_stepan",
    "grebenukm",
    "kutergin_v_ogne",
    "matvey_kukuy",
    "a_cherniak"
]

POSTS_LIMIT_PER_SOURCE = 3
MAX_POSTS_IN_DIGEST = 10
MAX_AGE_DAYS = 7
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

        cutoff_time = datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS)
        
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
            
            if post_date and post_date < cutoff_time:
                continue
            
            posts.append({
                'text': clean[:2500],
                'link': f"https://t.me/{post_ids[i]}" if i < len(post_ids) else f"https://t.me/{channel_name}",
                'unique_id': post_ids[i] if i < len(post_ids) else None,
                'author': channel_name,
                'date': post_date
            })
        print(f"  ✅ @{channel_name}: найдено {len(posts)} постов за {MAX_AGE_DAYS} дней")
    except Exception as e:
        print(f"  ❌ Ошибка @{channel_name}: {e}")
    return posts

def get_author_display_name(author_username):
    author_names = {
        # Новые авторы
        "Oskar_Hartmann": "Оскар Хартманн",
        "rybakovigor": "Игорь Рыбаков",
        "sokolovskiy": "Александр Соколовский",
        "EmpathyBiz": "Евгений Щепин",
        "TRANSFORMATOR_TV": "Дмитрий Портнягин",
        "semchurin_live": "Никита Семчурин",
        "spiridonovmax": "Максим Спиридонов",
        "chernyshev": "Александр Чернышев",
        # Стартапы и венчур
        "the_edinorog": "The Edinorog 🦄",
        "rus_venture": "Русский венчур",
        "temnaya_storona": "Темная сторона / Аркадий Морейнис",
        "street_mba": "Венчур по понятиям",
        "serafim_livestream": "Serafim Livestream",
        "bogdanissimmo": "BOGDANISSSIMO",
        "kyrillic": "Kyrillic",
        "kumar_solo": "Kumar & Solo",
        "indeks_dyatla": "Индекс дятла",
        # Управление и бизнес
        "molyanov": "Павел Молянов",
        "maximspiridonov": "Максим Спиридонов",
        "sostoyanie_potoka": "состояние потока / Наиля Асланова",
        "trevozhny_hr": "тревожный эйчар",
        "glavred_club": "Клуб главредов",
        "zhenya_lepekhin": "Женя Лепёхин",
        # Ваши авторы
        "fedorinsights": "Фёдор Овчинников",
        "MargulanSeissembai": "Маргулан Сейсембаев",
        "ovchinnikov_stepan": "Степан Овчинников",
        "grebenukm": "Михаил Гребенюк",
        "kutergin_v_ogne": "Кутергин в огне",
        "matvey_kukuy": "Матвей Кукуй",
        "a_cherniak": "Алексей Черняк"
    }
    return author_names.get(author_username, f"@{author_username}")

def generate_title_and_summary(text, author_name):
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
                print(f"  ⏭️ Пропуск (уже публиковался)")
                continue
            if p['unique_id']:
                published_ids.append(p['unique_id'])
            author_display = get_author_display_name(p['author'])
            title, summ = generate_title_and_summary(p['text'], author_display)
            all_posts.append({
                'title': title,
                'summary': summ,
                'link': p['link'],
                'author': author_display
            })
            print(f"  ✅ Добавлено: {title[:50]}...")
            if len(all_posts) >= MAX_POSTS_IN_DIGEST:
                break
        if len(all_posts) >= MAX_POSTS_IN_DIGEST:
            break
    return all_posts[:MAX_POSTS_IN_DIGEST]

def send_digest(posts):
    if not posts:
        msg = f"🤖 За последние {MAX_AGE_DAYS} дней нет новых постов от предпринимателей.\n\n📱 Подпишись: " + CHANNEL_ID
    else:
        msg = "🔥 <b>Дайджест российских предпринимателей</b>\n\n"
        for idx, p in enumerate(posts, 1):
            msg += f"{idx}. <b>{p['title']}</b>\n"
            msg += f"{p['summary']}\n"
            msg += f"🔗 <a href=\"{p['link']}\">Читать источник — {p['author']}</a>\n\n"
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
    print("🚀 Запуск дайджеста предпринимателей")
    print(f"📡 Источников: {len(SOURCES)}")
    print(f"⏰ Посты за последние {MAX_AGE_DAYS} дней")
    
    if not BOT_TOKEN or not CHANNEL_ID:
        print("❌ Нет TELEGRAM_BOT_TOKEN или CHANNEL_ID")
        sys.exit(1)

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
        print(f"Нет новых постов за последние {MAX_AGE_DAYS} дней")
        sys.exit(0)

if __name__ == "__main__":
    main()
