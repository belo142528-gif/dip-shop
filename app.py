import os
import sqlite3
import hashlib
import json
import requests
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string, session, redirect

SHOP_NAME = "TechStore"
OPENROUTER_KEY = os.environ.get('OPENROUTER_KEY', '')
ADMIN_PASSWORD = "admin123"
DB_PATH = 'shop.db'
PAGE_SIZE = 20

def get_db():
    return sqlite3.connect(DB_PATH)

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL, price INTEGER NOT NULL, stock TEXT NOT NULL,
        category TEXT, specs TEXT, description TEXT, brand TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('''CREATE VIRTUAL TABLE IF NOT EXISTS products_fts 
                 USING fts5(name, category, specs, description, brand)''')
    c.execute('''CREATE TRIGGER IF NOT EXISTS products_fts_insert 
        AFTER INSERT ON products BEGIN
            INSERT INTO products_fts(rowid, name, category, specs, description, brand)
            VALUES (new.id, new.name, new.category, new.specs, new.description, new.brand);
        END''')
    c.execute('''CREATE TRIGGER IF NOT EXISTS products_fts_update 
        AFTER UPDATE ON products BEGIN
            UPDATE products_fts SET name=NEW.name, category=NEW.category, 
            specs=NEW.specs, description=NEW.description, brand=NEW.brand WHERE rowid=NEW.id;
        END''')
    c.execute('''CREATE TRIGGER IF NOT EXISTS products_fts_delete 
        AFTER DELETE ON products BEGIN DELETE FROM products_fts WHERE rowid=OLD.id; END''')
    c.execute('CREATE INDEX IF NOT EXISTS idx_products_category ON products(category)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_products_price ON products(price)')
    c.execute('CREATE INDEX IF NOT EXISTS idx_products_brand ON products(brand)')
    c.execute('''CREATE TABLE IF NOT EXISTS conversations (
        id INTEGER PRIMARY KEY AUTOINCREMENT, session_id TEXT NOT NULL,
        role TEXT NOT NULL, content TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('CREATE INDEX IF NOT EXISTS idx_conv_session ON conversations(session_id)')
    c.execute('''CREATE TABLE IF NOT EXISTS response_cache (
        id INTEGER PRIMARY KEY AUTOINCREMENT, query_hash TEXT UNIQUE,
        response TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    c.execute('CREATE INDEX IF NOT EXISTS idx_cache_hash ON response_cache(query_hash)')
    conn.commit()
    conn.close()

def add_product(name, price, stock, category="", specs="", description="", brand=""):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO products (name, price, stock, category, specs, description, brand) VALUES (?,?,?,?,?,?,?)",
              (name, price, stock, category, specs, description, brand))
    conn.commit()
    conn.close()

def search_products_fts(query, limit=15):
    conn = get_db()
    c = conn.cursor()
    query_parts = query.split()
    fts_query = ' OR '.join([f'{part}*' for part in query_parts])
    c.execute("SELECT p.* FROM products p JOIN products_fts f ON p.id = f.rowid WHERE products_fts MATCH ? ORDER BY rank LIMIT ?", (fts_query, limit))
    rows = c.fetchall()
    conn.close()
    return rows

def get_all_products_paginated(page=1, page_size=20):
    conn = get_db()
    c = conn.cursor()
    offset = (page - 1) * page_size
    c.execute("SELECT * FROM products ORDER BY id DESC LIMIT ? OFFSET ?", (page_size, offset))
    rows = c.fetchall()
    c.execute("SELECT COUNT(*) FROM products")
    total = c.fetchone()[0]
    conn.close()
    return rows, total

def get_all_products():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM products ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    return rows

def get_product_by_id(product_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    row = c.fetchone()
    conn.close()
    return row

def update_product(product_id, name, price, stock, category, specs, description, brand):
    conn = get_db()
    c = conn.cursor()
    c.execute("UPDATE products SET name=?, price=?, stock=?, category=?, specs=?, description=?, brand=? WHERE id=?",
              (name, price, stock, category, specs, description, brand, product_id))
    conn.commit()
    conn.close()

def delete_product(product_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()
    conn.close()

def get_products_count():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM products")
    count = c.fetchone()[0]
    conn.close()
    return count

def get_categories():
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT DISTINCT category FROM products WHERE category != '' ORDER BY category")
    rows = c.fetchall()
    conn.close()
    return [r[0] for r in rows]

def save_message(session_id, role, content):
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT INTO conversations (session_id, role, content) VALUES (?,?,?)", (session_id, role, content))
    conn.commit()
    conn.close()

def get_conversation_history(session_id, limit=8):
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT role, content FROM conversations WHERE session_id = ? ORDER BY created_at DESC LIMIT ?", (session_id, limit))
    rows = c.fetchall()
    conn.close()
    return [(r[0], r[1]) for r in reversed(rows)]

def clear_conversation(session_id):
    conn = get_db()
    c = conn.cursor()
    c.execute("DELETE FROM conversations WHERE session_id = ?", (session_id,))
    conn.commit()
    conn.close()

def get_cache_key(text):
    return hashlib.md5(text.lower().encode()).hexdigest()

def get_cached_response(query):
    key = get_cache_key(query)
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT response FROM response_cache WHERE query_hash = ?", (key,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else None

def cache_response(query, response):
    key = get_cache_key(query)
    conn = get_db()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO response_cache (query_hash, response) VALUES (?,?)", (key, response))
    conn.commit()
    conn.close()
    
STOP_WORDS = {
    'это', 'что', 'было', 'быть', 'есть', 'который', 'сказал',
    'ответь', 'свой', 'себя', 'тебе', 'тебя', 'мне', 'меня',
    'мой', 'моя', 'моё', 'мои', 'просто', 'ещё', 'уже', 'очень',
    'только', 'всё', 'весь', 'этот', 'эта', 'эти', 'как', 'так',
    'для', 'что', 'вот', 'если', 'она', 'они', 'оно', 'его', 'её',
    'им', 'их', 'да', 'нет', 'или', 'бы', 'ли', 'же', 'то', 'от',
    'по', 'на', 'в', 'с', 'и', 'а', 'но', 'к', 'у', 'из', 'за',
    'при', 'про', 'до', 'под', 'над', 'об', 'во', 'со', 'ко',
}

def text_to_vector(text):
    if not text:
        return {}
    text_lower = text.lower()
    words = []
    for w in text_lower.split():
        w = ''.join(c for c in w if c.isalnum() or c in '-_')
        if len(w) >= 2 and w not in STOP_WORDS:
            words.append(w)
    if not words:
        return {}
    vector = {}
    for w in words:
        vector[w] = vector.get(w, 0) + 1
    total = sum(vector.values())
    if total > 0:
        for w in vector:
            vector[w] = vector[w] / total
    return vector

def cosine_similarity(vec1, vec2):
    if not vec1 or not vec2:
        return 0.0
    all_words = set(vec1.keys()) | set(vec2.keys())
    dot = sum(vec1.get(w, 0) * vec2.get(w, 0) for w in all_words)
    mag1 = sum(v ** 2 for v in vec1.values()) ** 0.5
    mag2 = sum(v ** 2 for v in vec2.values()) ** 0.5
    if mag1 == 0 or mag2 == 0:
        return 0.0
    return dot / (mag1 * mag2)

def semantic_search_optimized(query, limit=10, threshold=0.12):
    query_vec = text_to_vector(query)
    if not query_vec:
        return []
    candidates = search_products_fts(query, limit=50)
    if not candidates:
        candidates = get_all_products()[:200]
    scored = []
    for p in candidates:
        product_text = f"{p[1]} {p[4] or ''} {p[5] or ''} {p[6] or ''} {p[7] or ''}"
        product_vec = text_to_vector(product_text)
        score = cosine_similarity(query_vec, product_vec)
        if score >= threshold:
            scored.append((score, p))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in scored[:limit]]

def smart_search(query, limit=15):
    fts_results = search_products_fts(query, limit=limit)
    if len(fts_results) >= limit:
        return fts_results[:limit]
    semantic_results = semantic_search_optimized(query, limit=limit - len(fts_results))
    seen_ids = {p[0] for p in fts_results}
    combined = list(fts_results)
    for p in semantic_results:
        if p[0] not in seen_ids:
            combined.append(p)
            seen_ids.add(p[0])
    return combined[:limit]

def format_product_text(product):
    if not product or len(product) < 3:
        return str(product)
    name = product[1]
    price = product[2]
    stock = product[3]
    category = product[4] or ""
    specs = product[5] or ""
    description = product[6] or ""
    brand = product[7] or ""
    line = f"📦 {name}"
    if brand:
        line += f" ({brand})"
    if category:
        line += f" [{category}]"
    if specs:
        line += f" — {specs}"
    line += f" — {price} ₽"
    if stock == 'да':
        line += " ✅ в наличии"
    elif stock == 'под заказ':
        line += " 📦 под заказ"
    else:
        line += " ❌ нет"
    return line

def get_product_context(products, limit=8):
    if not products:
        return "Нет подходящих товаров"
    return '\n'.join([format_product_text(p) for p in products[:limit]])
    
def detect_intent(text):
    text_lower = text.lower()
    search_keywords = ['найди', 'поищи', 'покажи', 'есть ли', 'какой', 'что есть', 
                       'хочу купить', 'интересует', 'нужен', 'подбери', 'посоветуй',
                       'вариант', 'модель', 'выбрать', 'рекомендуй']
    if any(kw in text_lower for kw in search_keywords):
        return 'search'
    stock_keywords = ['в наличии', 'есть в магазине', 'можно купить', 'доступно']
    if any(kw in text_lower for kw in stock_keywords):
        return 'stock'
    compare_keywords = ['сравни', 'что лучше', 'какой выбрать', 'отличие', 'разница']
    if any(kw in text_lower for kw in compare_keywords):
        return 'compare'
    service_keywords = ['доставка', 'оплата', 'возврат', 'гарантия', 'курьер', 
                        'почта', 'заказ', 'оформить', 'цен']
    if any(kw in text_lower for kw in service_keywords):
        return 'service'
    if len(text) < 30 and any(kw in text_lower for kw in ['здравств', 'привет', 'добрый', 'салют', 'хай', 'ку']):
        return 'greeting'
    return 'general'

def ask_ai(prompt):
    if not OPENROUTER_KEY:
        return None
    try:
        headers = {
            'Authorization': f'Bearer {OPENROUTER_KEY}',
            'Content-Type': 'application/json; charset=utf-8',
            'HTTP-Referer': 'https://shop-bot.onrender.com',
            'X-Title': f'{SHOP_NAME}-Bot'
        }
        payload = {
            'model': 'deepseek/deepseek-chat',
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': 0.6,
            'max_tokens': 400
        }
        response = requests.post(
            'https://openrouter.ai/api/v1/chat/completions',
            headers=headers,
            json=payload,
            timeout=20
        )
        if response.status_code != 200:
            return None
        data = response.json()
        if 'choices' in data and len(data['choices']) > 0:
            content = data['choices'][0]['message'].get('content', '')
            return content.strip() if content else None
        return None
    except Exception as e:
        print(f"AI error: {e}")
        return None

def generate_response(user_text, session_id='default'):
    intent = detect_intent(user_text)
    history = get_conversation_history(session_id, 8)
    products = []
    if intent in ['search', 'stock', 'compare']:
        products = smart_search(user_text, limit=15)
    if intent == 'service' and len(user_text) < 50:
        cached = get_cached_response(user_text)
        if cached:
            save_message(session_id, 'user', user_text)
            save_message(session_id, 'assistant', cached)
            return cached
    product_context = get_product_context(products, 10) if products else "Нет подходящих товаров"
    history_text = '\n'.join([
        f"{'Покупатель' if role == 'user' else 'Элли'}: {content}"
        for role, content in history[-5:]
    ]) if history else "Нет предыдущих сообщений."
    intent_instruction = {
        'search': 'Сфокусируйся на поиске и предложении товаров. Предложи 2-3 варианта.',
        'stock': 'Уточни наличие товара и дай чёткий ответ.',
        'compare': 'Сравни товары и помоги выбрать лучший.',
        'service': 'Дай полную информацию по доставке, оплате, возврату.',
        'greeting': 'Поприветствуй покупателя и предложи помощь.',
        'general': 'Ответь на вопрос профессионально и дружелюбно.'
    }
    prompt = f"""Ты — Элли, профессиональный консультант магазина «{SHOP_NAME}».

ИНСТРУКЦИЯ: {intent_instruction.get(intent, 'Ответь профессионально.')}

ПРАВИЛА:
1. Отвечай кратко (2-3 предложения)
2. Используй ДАННЫЕ ИЗ БАЗЫ НИЖЕ
3. Не выдумывай характеристики
4. Если нет точного товара — предложи аналоги
5. Доставка 3-7 дней (Почта, СДЭК). Оплата картой или наличными. Возврат 14 дней.

БАЗА ТОВАРОВ (найдено {len(products)} товаров):
{product_context}

ИСТОРИЯ:
{history_text}

Покупатель: {user_text}
Элли:"""
    response = ask_ai(prompt)
    if not response:
        if products:
            if len(products) == 1:
                response = f"Нашёл: {format_product_text(products[0])}. Хотите узнать подробнее?"
            else:
                context = get_product_context(products[:5])
                response = f"Нашёл несколько вариантов:\n{context}\n\nКакой вас интересует?"
        else:
            response = "Не нашла точного совпадения. Попробуйте другие ключевые слова или посмотрите все категории."
    save_message(session_id, 'user', user_text)
    save_message(session_id, 'assistant', response)
    if intent == 'service' and len(user_text) < 50:
        cache_response(user_text, response)
    return response
    
app = Flask(__name__)
app.secret_key = os.urandom(24)

INDEX_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{{ shop_name }}</title>
    <style>
        *{margin:0;padding:0;box-sizing:border-box}
        body{font-family:system-ui;background:#f0f4f8;height:100vh;display:flex;flex-direction:column}
        #header{background:linear-gradient(135deg,#2563eb,#1d4ed8);color:#fff;padding:15px;text-align:center;font-weight:bold;flex-shrink:0}
        #header a{color:rgba(255,255,255,0.8);font-size:14px;margin-left:15px;text-decoration:none}
        #chat{flex:1;overflow-y:auto;padding:15px;background:#fff;margin:10px;border-radius:15px}
        .msg{margin:8px 0;padding:10px 15px;border-radius:15px;max-width:85%;word-wrap:break-word;white-space:pre-wrap}
        .user{background:#2563eb;color:#fff;margin-left:auto;text-align:right}
        .bot{background:#e8f0fe;color:#1a1a2e;margin-right:auto}
        #form{display:flex;padding:10px;background:#fff;border-top:1px solid #e5e7eb;flex-shrink:0}
        #input{flex:1;padding:12px;border:1px solid #d1d5db;border-radius:25px;font-size:16px;outline:none}
        #input:focus{border-color:#2563eb}
        #send{margin-left:8px;padding:12px 25px;border:none;border-radius:25px;background:#2563eb;color:#fff;font-size:16px;cursor:pointer}
        #send:hover{background:#1d4ed8}
        @media(max-width:480px){#chat{margin:5px}#send{padding:12px 16px}}
    </style>
</head>
<body>
    <div id="header">
        🛍️ {{ shop_name }} — Консультант
        <a href="/clear" onclick="return confirm('Очистить историю?')">🗑️ Очистить</a>
        <a href="/admin">⚙️ Админка</a>
    </div>
    <div id="chat">
        <div class="msg bot">👋 Здравствуйте! Я Элли. Что ищете?</div>
    </div>
    <form id="form" onsubmit="sendMsg(event)">
        <input id="input" type="text" placeholder="Напишите вопрос..." autofocus>
        <button id="send" type="submit">→</button>
    </form>
    <script>
        function add(t,c){var d=document.createElement('div');d.className='msg '+c;d.textContent=t;document.getElementById('chat').appendChild(d);document.getElementById('chat').scrollTop=document.getElementById('chat').scrollHeight}
        async function sendMsg(e){e.preventDefault();var input=document.getElementById('input');var t=input.value.trim();if(!t)return;add(t,'user');input.value='';try{var r=await fetch('/chat',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:t})});var d=await r.json();add(d.reply,'bot')}catch(err){add('Ошибка связи...','bot')}}
        document.getElementById('input').addEventListener('keydown',function(e){if(e.key==='Enter'){e.preventDefault();document.getElementById('send').click()}});
    </script>
</body>
</html>
"""

ADMIN_HTML = """
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Админка</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:system-ui;background:#f0f4f8;padding:20px}
.container{max-width:1200px;margin:0 auto;background:#fff;border-radius:15px;padding:25px}
h1{color:#2563eb;margin-bottom:15px}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(120px,1fr));gap:15px;margin:15px 0}
.stat-card{background:#f8fafc;padding:15px;border-radius:10px;text-align:center}
.stat-card .number{font-size:24px;font-weight:700;color:#2563eb}
.stat-card .label{font-size:12px;color:#64748b}
table{width:100%;border-collapse:collapse;margin-top:15px}
th,td{padding:10px;text-align:left;border-bottom:1px solid #e5e7eb}
th{background:#f8fafc;font-weight:600}
.btn{display:inline-block;padding:8px 16px;border:none;border-radius:8px;cursor:pointer;text-decoration:none;font-size:14px}
.btn-primary{background:#2563eb;color:#fff}
.btn-danger{background:#dc2626;color:#fff}
.btn-success{background:#16a34a;color:#fff}
.btn-warning{background:#f59e0b;color:#fff}
.btn-sm{padding:4px 10px;font-size:12px}
.form-group{margin-bottom:12px}
.form-group label{display:block;font-weight:600;margin-bottom:4px;font-size:14px}
.form-group input,.form-group select{width:100%;padding:8px 12px;border:1px solid #d1d5db;border-radius:8px}
.form-row{display:grid;grid-template-columns:1fr 1fr;gap:15px}
.pagination{display:flex;gap:5px;margin:15px 0;flex-wrap:wrap}
.pagination a,.pagination span{padding:8px 14px;border:1px solid #e5e7eb;border-radius:8px;text-decoration:none;color:#2563eb}
.pagination .active{background:#2563eb;color:#fff;border-color:#2563eb}
.header-actions{display:flex;gap:10px;flex-wrap:wrap;align-items:center}
@media(max-width:600px){.form-row{grid-template-columns:1fr}}
</style>
</head>
<body>
<div class="container">
    <div class="header-actions">
        <h1>🛍️ Админка</h1>
        <a href="/" class="btn btn-primary">← В чат</a>
        <a href="/admin/logout" class="btn btn-danger">Выйти</a>
    </div>
    <div class="stats">
        <div class="stat-card"><div class="number">{{ total }}</div><div class="label">Всего</div></div>
        <div class="stat-card"><div class="number">{{ in_stock }}</div><div class="label">В наличии</div></div>
        <div class="stat-card"><div class="number">{{ categories|length }}</div><div class="label">Категорий</div></div>
    </div>
    <h2>➕ Добавить товар</h2>
    <form method="POST" action="/admin/add">
        <div class="form-row">
            <div class="form-group"><label>Название *</label><input type="text" name="name" required></div>
            <div class="form-group"><label>Цена *</label><input type="number" name="price" required></div>
        </div>
        <div class="form-row">
            <div class="form-group"><label>Наличие</label><select name="stock"><option value="да">В наличии</option><option value="под заказ">Под заказ</option><option value="нет">Нет</option></select></div>
            <div class="form-group"><label>Категория</label><input type="text" name="category"></div>
        </div>
        <div class="form-row">
            <div class="form-group"><label>Бренд</label><input type="text" name="brand"></div>
            <div class="form-group"><label>Характеристики</label><input type="text" name="specs"></div>
        </div>
        <div class="form-group"><label>Описание</label><input type="text" name="description"></div>
        <button type="submit" class="btn btn-success">➕ Добавить</button>
    </form>
    <h2 style="margin-top:20px;">📦 Товары ({{ total }})</h2>
    <div class="pagination">
        {% for p in range(1, total_pages + 1) %}
            {% if p == page %}<span class="active">{{ p }}</span>
            {% else %}<a href="?page={{ p }}">{{ p }}</a>{% endif %}
        {% endfor %}
    </div>
    <table>
        <tr><th>Название</th><th>Цена</th><th>Наличие</th><th>Категория</th><th>Действия</th></tr>
        {% for p in products %}
        <tr>
            <td><strong>{{ p[1] }}</strong><br><small>{{ p[7] or '' }} {{ p[5] or '' }}</small></td>
            <td>{{ p[2] }} ₽</td><td>{{ p[3] }}</td><td>{{ p[4] or '-' }}</td>
            <td>
                <a href="/admin/edit/{{ p[0] }}" class="btn btn-warning btn-sm">✏️</a>
                <a href="/admin/delete/{{ p[0] }}" class="btn btn-danger btn-sm" onclick="return confirm('Удалить?')">🗑️</a>
            </td>
        </tr>
        {% endfor %}
    </table>
</div>
</body>
</html>
"""

EDIT_HTML = """
<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Редактировать</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:system-ui;background:#f0f4f8;padding:20px}
.container{max-width:600px;margin:0 auto;background:#fff;border-radius:15px;padding:25px}
h1{color:#2563eb}
.form-group{margin-bottom:12px}
.form-group label{display:block;font-weight:600;margin-bottom:4px}
.form-group input,.form-group select{width:100%;padding:8px 12px;border:1px solid #d1d5db;border-radius:8px}
.actions{margin-top:15px;display:flex;gap:10px}
.btn{display:inline-block;padding:8px 16px;border:none;border-radius:8px;cursor:pointer;text-decoration:none}
.btn-success{background:#16a34a;color:#fff}
.btn-secondary{background:#6b7280;color:#fff}
</style>
</head>
<body>
<div class="container">
<h1>✏️ Редактировать</h1>
<form method="POST">
    <div class="form-group"><label>Название</label><input type="text" name="name" value="{{ p[1] }}" required></div>
    <div class="form-group"><label>Цена</label><input type="number" name="price" value="{{ p[2] }}" required></div>
    <div class="form-group"><label>Наличие</label><select name="stock"><option value="да" {% if p[3]=='да' %}selected{% endif %}>В наличии</option><option value="под заказ" {% if p[3]=='под заказ' %}selected{% endif %}>Под заказ</option><option value="нет" {% if p[3]=='нет' %}selected{% endif %}>Нет</option></select></div>
    <div class="form-group"><label>Категория</label><input type="text" name="category" value="{{ p[4] or '' }}"></div>
    <div class="form-group"><label>Бренд</label><input type="text" name="brand" value="{{ p[7] or '' }}"></div>
    <div class="form-group"><label>Характеристики</label><input type="text" name="specs" value="{{ p[5] or '' }}"></div>
    <div class="form-group"><label>Описание</label><input type="text" name="description" value="{{ p[6] or '' }}"></div>
    <div class="actions"><button type="submit" class="btn btn-success">💾 Сохранить</button><a href="/admin" class="btn btn-secondary">Отмена</a></div>
</form>
</div>
</body>
</html>
"""

LOGIN_HTML = """
<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Вход</title>
<style>
body{font-family:system-ui;background:#f0f4f8;display:flex;justify-content:center;align-items:center;height:100vh}
.login{background:#fff;padding:40px;border-radius:15px;width:300px;text-align:center}
input{width:100%;padding:10px;margin:10px 0;border:1px solid #d1d5db;border-radius:8px}
button{width:100%;padding:10px;background:#2563eb;color:#fff;border:none;border-radius:8px;cursor:pointer}
</style>
</head>
<body>
<div class="login"><h2>🔐 Вход</h2>
<form method="POST"><input type="password" name="password" placeholder="Пароль" required><button type="submit">Войти</button></form>
</div>
</body></html>
"""

@app.route('/')
def home():
    return render_template_string(INDEX_HTML, shop_name=SHOP_NAME)

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_text = data.get('message', '')
    session_id = request.remote_addr
    reply = generate_response(user_text, session_id)
    return jsonify({'reply': reply})

@app.route('/clear')
def clear():
    clear_conversation(request.remote_addr)
    return redirect('/')

@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if session.get('admin'):
        return redirect('/admin/dashboard')
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session['admin'] = True
            return redirect('/admin/dashboard')
    return render_template_string(LOGIN_HTML)

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin'):
        return redirect('/admin')
    page = int(request.args.get('page', 1))
    products, total = get_all_products_paginated(page, PAGE_SIZE)
    total_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
    all_products = get_all_products()
    in_stock = sum(1 for p in all_products if p[3] == 'да')
    categories = get_categories()
    return render_template_string(ADMIN_HTML, products=products, total=total,
                                   in_stock=in_stock, categories=categories,
                                   page=page, total_pages=total_pages)

@app.route('/admin/add', methods=['POST'])
def admin_add():
    if not session.get('admin'):
        return redirect('/admin')
    add_product(request.form.get('name'), int(request.form.get('price', 0)),
                request.form.get('stock', 'да'), request.form.get('category', ''),
                request.form.get('specs', ''), request.form.get('description', ''),
                request.form.get('brand', ''))
    return redirect('/admin/dashboard')

@app.route('/admin/edit/<int:product_id>', methods=['GET', 'POST'])
def admin_edit(product_id):
    if not session.get('admin'):
        return redirect('/admin')
    product = get_product_by_id(product_id)
    if not product:
        return redirect('/admin/dashboard')
    if request.method == 'POST':
        update_product(product_id, request.form.get('name'),
                       int(request.form.get('price', 0)), request.form.get('stock', 'да'),
                       request.form.get('category', ''), request.form.get('specs', ''),
                       request.form.get('description', ''), request.form.get('brand', ''))
        return redirect('/admin/dashboard')
    return render_template_string(EDIT_HTML, p=product)

@app.route('/admin/delete/<int:product_id>')
def admin_delete(product_id):
    if not session.get('admin'):
        return redirect('/admin')
    delete_product(product_id)
    return redirect('/admin/dashboard')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    return redirect('/admin')

if __name__ == '__main__':
    init_db()
    if get_products_count() == 0:
        test_products = [
            ("Samsung Galaxy S24", 89990, "да", "Смартфоны", '6.2" AMOLED, 8/256GB', "Флагман", "Samsung"),
            ("iPhone 15 Pro", 99990, "да", "Смартфоны", '6.1" OLED, 8/256GB', "Титан", "Apple"),
            ("Xiaomi 14", 69990, "да", "Смартфоны", '6.73" AMOLED, 12/512GB', "Snapdragon 8", "Xiaomi"),
            ("Sony WH-1000XM5", 29990, "да", "Наушники", "Беспроводные, ANC", "Шумоподавление", "Sony"),
            ("AirPods Pro 2", 24990, "да", "Наушники", "TWS, ANC", "Пространственное аудио", "Apple"),
            ("Anker 737", 9990, "да", "Зарядки", "100W GaN", "Для ноутбука", "Anker"),
            ("PowerBank 20000", 4990, "да", "Зарядки", "20000 мАч", "Для путешествий", "Xiaomi"),
        ]
        for p in test_products:
            add_product(*p)
        print(f"✅ Добавлено {len(test_products)} тестовых товаров")
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 Элли запущена: http://localhost:{port}")
    print(f"🔐 Админка: /admin (пароль: {ADMIN_PASSWORD})")
    print(f"📊 Товаров: {get_products_count()}")
    app.run(host='0.0.0.0', port=port)
