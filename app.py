import os
import json
import sqlite3
import requests
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string, redirect, url_for, session

app = Flask(__name__)
app.secret_key = os.urandom(24)

SHOP_NAME = "TechStore"
ADMIN_PASSWORD = "12345"
OPENROUTER_KEY = os.environ.get('OPENROUTER_KEY', '')
OPENROUTER_URL = 'https://openrouter.ai/api/v1/chat/completions'

def init_db():
    conn = sqlite3.connect('products.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS products
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  name TEXT NOT NULL,
                  price INTEGER NOT NULL,
                  stock TEXT NOT NULL,
                  category TEXT,
                  specs TEXT,
                  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''')
    conn.commit()
    conn.close()

def add_product(name, price, stock, category="", specs=""):
    conn = sqlite3.connect('products.db')
    c = conn.cursor()
    c.execute("INSERT INTO products (name, price, stock, category, specs) VALUES (?, ?, ?, ?, ?)",
              (name, price, stock, category, specs))
    conn.commit()
    conn.close()

def get_all_products():
    conn = sqlite3.connect('products.db')
    c = conn.cursor()
    c.execute("SELECT * FROM products ORDER BY id DESC")
    rows = c.fetchall()
    conn.close()
    return rows

def search_products(query):
    conn = sqlite3.connect('products.db')
    c = conn.cursor()
    c.execute("SELECT * FROM products WHERE name LIKE ? OR category LIKE ? ORDER BY id DESC", (f'%{query}%', f'%{query}%'))
    rows = c.fetchall()
    conn.close()
    return rows

def format_product_text(product):
    if len(product) >= 5:
        name = product[1]
        price = product[2]
        stock = product[3]
        category = product[4] or ""
        specs = product[5] or ""
        text = f"📦 {name}"
        if category:
            text += f" ({category})"
        if specs:
            text += f" - {specs}"
        text += f" — {price} ₽, в наличии: {stock}"
        return text
    return str(product)

init_db()

if len(get_all_products()) == 0:
    test_products = [
        ("TechStar A1", 8490, "да", "Смартфоны", "6.1\" AMOLED, 4/64GB"),
        ("TechStar A2", 12990, "да", "Смартфоны", "6.3\" AMOLED, 6/128GB"),
        ("TechStar X1", 34990, "да", "Смартфоны", "6.7\" OLED, 12/256GB"),
        ("AirBuds Pro", 2690, "да", "Наушники", "TWS, Bluetooth 5.4, 8/32ч"),
        ("AirBuds Lite", 1290, "да", "Наушники", "TWS, Bluetooth 5.3, 5/20ч"),
        ("MagCharge 15W", 1490, "да", "Зарядки", "Магнитная панель 15W"),
        ("PowerCharge 20W", 790, "да", "Зарядки", "Проводная, USB-C, PD 3.0"),
        ("Чехол TechStar A1", 290, "да", "Аксессуары", "Силиконовый чехол"),
        ("Чехол Universal", 190, "да", "Аксессуары", "Прозрачный TPU"),
    ]
    for p in test_products:
        add_product(*p)
        def ask_ai(user_message, dialogue_history, products_context):
    if not OPENROUTER_KEY:
        return None
    try:
        system_prompt = f"""Ты — Элли, дружелюбный консультант интернет-магазина «{SHOP_NAME}». 
Твоя задача — помогать клиентам выбирать товары, отвечать на вопросы о наличии, ценах, характеристиках, доставке и оплате.

ПРАВИЛА:
1. Отвечай коротко и по делу (1-3 предложения).
2. Если клиент спрашивает о товарах — используй ДАННЫЕ ИЗ БАЗЫ ниже.
3. Если точного товара нет в базе — предложи похожие.
4. Если клиент просит совет — посоветуй на основе его потребностей.
5. Не выдумывай товары, которых нет в базе.
6. Для вопросов о доставке/оплате: Доставка по РФ — 3-7 дней (Почта, СДЭК). Оплата картой онлайн или наличными при получении. Возврат — 14 дней. Гарантия до 2 лет.
7. Если клиент спрашивает то, чего точно нет в ассортименте (ноутбуки, планшеты) — скажи, что их нет, и предложи смартфоны/наушники/зарядки.

БАЗА ТОВАРОВ (цены в рублях):
{products_context}

ИСТОРИЯ ДИАЛОГА:
{dialogue_history}

Клиент: {user_message}
Элли:"""

        headers = {
            'Authorization': f'Bearer {OPENROUTER_KEY}',
            'Content-Type': 'application/json; charset=utf-8',
            'HTTP-Referer': 'https://dip-shop.onrender.com',
            'X-Title': 'Elli-Shop'
        }
        payload = {
            'model': 'deepseek/deepseek-chat',
            'messages': [
                {'role': 'user', 'content': system_prompt}
            ],
            'temperature': 0.5,
            'max_tokens': 250
        }
        r = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=15)
        resp = r.json()
        if 'choices' in resp:
            content = resp['choices'][0]['message'].get('content', '')
            if '```' in content:
                content = content.split('```')[0].strip()
            return content.strip() if content else None
        return None
    except Exception as e:
        print(f"Ошибка AI: {e}")
        return None

dialogue_history = []

def generate_response(user_text):
    global dialogue_history
    user_lower = user_text.lower().strip()
    
    dialogue_history.append(f"Клиент: {user_text}")
    if len(dialogue_history) > 20:
        dialogue_history = dialogue_history[-20:]
    
    # Синонимы для поиска
    search_text = user_lower.replace('телефон', 'смартфон').replace('мобильн', 'смартфон')
    
    # Простые приветствия — без AI
    greetings = ['здравствуй', 'привет', 'добрый день', 'доброе утро', 'добрый вечер', 'здрасте', 'салют', 'ку', 'хай']
    is_pure_greeting = user_lower.strip() in greetings or user_lower.strip() in ['привет!', 'здравствуйте!', 'ку!', 'хай!']
    
    if is_pure_greeting and len(dialogue_history) <= 2:
        return "Здравствуйте! Я Элли, консультант TechStore. Чем могу помочь? У нас есть телефоны, наушники, зарядки и аксессуары."
    
    # Простые вопросы о доставке/оплате — без AI
    service_only = ['как заказать', 'как купить', 'доставк', 'оплат', 'возврат', 'гаранти', 'доставить', 'курьер', 'почт']
    if any(w in user_lower for w in service_only) and len(user_lower) < 40:
        return "🚚 Доставка по РФ — 3-7 дней (Почта, СДЭК). Оплата картой онлайн или наличными при получении. Возврат — 14 дней. Гарантия до 2 лет."
    
    # Ищем товары в базе
    found = search_products(search_text)
    
    # Если товаров 0 или вопрос сложный — подключаем AI
    if not found or len(user_lower) > 30 or '?' in user_text or 'какой' in user_lower or 'посоветуй' in user_lower or 'что лучше' in user_lower:
        # Собираем контекст из базы
        if found:
            products_context = "\n".join([format_product_text(p) for p in found[:15]])
        else:
            # Если ничего не найдено — даём AI все категории
            all_products = get_all_products()
            products_context = "\n".join([format_product_text(p) for p in all_products[:20]])
        
        history_text = "\n".join(dialogue_history[-6:])
        ai_response = ask_ai(user_text, history_text, products_context)
        
        if ai_response:
            dialogue_history.append(f"Элли: {ai_response}")
            return ai_response
    
    # Если AI не сработал — отвечаем сами
    if found:
        items_text = "\n".join([format_product_text(p) for p in found[:5]])
        if len(found) == 1:
            return f"Нашёл! {items_text}. Что-то ещё?"
        else:
            return f"Нашёл несколько вариантов:\n{items_text}\n\nКакой именно вас интересует?"
    
    # Ничего не найдено и AI не ответил
    return "Я не совсем поняла запрос. У нас есть смартфоны, наушники, зарядки и чехлы. Напишите модель или категорию, и я покажу цены."
    ADMIN_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Админка TechStore</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: system-ui; background: #f0f4f8; padding: 20px; }
        .container { max-width: 1200px; margin: 0 auto; background: white; border-radius: 15px; padding: 25px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { margin-bottom: 20px; color: #2563eb; }
        .btn { display: inline-block; padding: 8px 16px; background: #2563eb; color: white; border: none; border-radius: 8px; cursor: pointer; text-decoration: none; font-size: 14px; }
        .btn-danger { background: #dc2626; }
        .btn-success { background: #16a34a; }
        .btn-warning { background: #f59e0b; }
        table { width: 100%; border-collapse: collapse; margin-top: 20px; }
        th, td { padding: 10px; text-align: left; border-bottom: 1px solid #e5e7eb; }
        th { background: #f8fafc; font-weight: 600; }
        .actions a { margin-right: 8px; }
        .form-group { margin-bottom: 15px; }
        .form-group label { display: block; font-weight: 600; margin-bottom: 5px; }
        .form-group input, .form-group textarea, .form-group select { width: 100%; padding: 8px; border: 1px solid #d1d5db; border-radius: 8px; }
        .form-row { display: grid; grid-template-columns: 1fr 1fr; gap: 15px; }
        .logout { float: right; }
        .flash { padding: 10px; border-radius: 8px; margin-bottom: 15px; }
        .flash-success { background: #dcfce7; color: #166534; }
        .flash-error { background: #fee2e2; color: #991b1b; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🛍️ Админка TechStore</h1>
        <a href="/" class="btn" target="_blank">Чат с Элли</a>
        <a href="/admin/logout" class="btn btn-danger logout">Выйти</a>
        <hr style="margin: 15px 0;">
        
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="flash flash-{{ category }}">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        
        <h2>Добавить товар</h2>
        <form method="POST" action="/admin/add">
            <div class="form-row">
                <div class="form-group">
                    <label>Название</label>
                    <input type="text" name="name" required>
                </div>
                <div class="form-group">
                    <label>Цена (₽)</label>
                    <input type="number" name="price" required>
                </div>
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label>Наличие</label>
                    <select name="stock">
                        <option value="да">В наличии</option>
                        <option value="нет">Нет</option>
                        <option value="под заказ">Под заказ</option>
                    </select>
                </div>
                <div class="form-group">
                    <label>Категория</label>
                    <input type="text" name="category" placeholder="Смартфоны, Наушники, Зарядки...">
                </div>
            </div>
            <div class="form-group">
                <label>Характеристики</label>
                <input type="text" name="specs" placeholder='6.1" AMOLED, 4/64GB, 50MP...'>
            </div>
            <button type="submit" class="btn btn-success">➕ Добавить</button>
        </form>
        
        <h2 style="margin-top: 30px;">Все товары</h2>
        <table>
            <thead>
                <tr>
                    <th>ID</th>
                    <th>Название</th>
                    <th>Цена</th>
                    <th>Наличие</th>
                    <th>Категория</th>
                    <th>Характеристики</th>
                    <th>Действия</th>
                </tr>
            </thead>
            <tbody>
                {% for p in products %}
                <tr>
                    <td>{{ p[0] }}</td>
                    <td>{{ p[1] }}</td>
                    <td>{{ p[2] }} ₽</td>
                    <td>{{ p[3] }}</td>
                    <td>{{ p[4] or '-' }}</td>
                    <td>{{ p[5] or '-' }}</td>
                    <td class="actions">
                        <a href="/admin/edit/{{ p[0] }}" class="btn btn-warning">✏️</a>
                        <a href="/admin/delete/{{ p[0] }}" class="btn btn-danger" onclick="return confirm('Удалить?')">🗑️</a>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
</body>
</html>
"""

EDIT_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Редактировать товар</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: system-ui; background: #f0f4f8; padding: 20px; }
        .container { max-width: 600px; margin: 0 auto; background: white; border-radius: 15px; padding: 25px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { margin-bottom: 20px; color: #2563eb; }
        .btn { display: inline-block; padding: 8px 16px; background: #2563eb; color: white; border: none; border-radius: 8px; cursor: pointer; text-decoration: none; font-size: 14px; }
        .btn-success { background: #16a34a; }
        .btn-secondary { background: #6b7280; }
        .form-group { margin-bottom: 15px; }
        .form-group label { display: block; font-weight: 600; margin-bottom: 5px; }
        .form-group input, .form-group textarea, .form-group select { width: 100%; padding: 8px; border: 1px solid #d1d5db; border-radius: 8px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>✏️ Редактировать товар</h1>
        <form method="POST">
            <div class="form-group">
                <label>Название</label>
                <input type="text" name="name" value="{{ product[1] }}" required>
            </div>
            <div class="form-group">
                <label>Цена (₽)</label>
                <input type="number" name="price" value="{{ product[2] }}" required>
            </div>
            <div class="form-group">
                <label>Наличие</label>
                <select name="stock">
                    <option value="да" {% if product[3] == 'да' %}selected{% endif %}>В наличии</option>
                    <option value="нет" {% if product[3] == 'нет' %}selected{% endif %}>Нет</option>
                    <option value="под заказ" {% if product[3] == 'под заказ' %}selected{% endif %}>Под заказ</option>
                </select>
            </div>
            <div class="form-group">
                <label>Категория</label>
                <input type="text" name="category" value="{{ product[4] or '' }}">
            </div>
            <div class="form-group">
                <label>Характеристики</label>
                <input type="text" name="specs" value="{{ product[5] or '' }}">
            </div>
            <button type="submit" class="btn btn-success">💾 Сохранить</button>
            <a href="/admin" class="btn btn-secondary">Отмена</a>
        </form>
    </div>
</body>
</html>
"""
@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session['admin'] = True
            return redirect('/admin/dashboard')
        return 'Неверный пароль!', 403
    if session.get('admin'):
        return redirect('/admin/dashboard')
    return '''
    <!DOCTYPE html>
    <html>
    <head><meta charset="utf-8"><title>Вход в админку</title>
    <style>
        body { font-family: system-ui; background: #f0f4f8; display: flex; justify-content: center; align-items: center; height: 100vh; }
        .login { background: white; padding: 40px; border-radius: 15px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); width: 300px; }
        input { width: 100%; padding: 10px; margin: 10px 0; border: 1px solid #d1d5db; border-radius: 8px; }
        button { width: 100%; padding: 10px; background: #2563eb; color: white; border: none; border-radius: 8px; cursor: pointer; }
    </style>
    </head>
    <body>
    <div class="login">
        <h2>🔐 Вход в админку</h2>
        <form method="POST">
            <input type="password" name="password" placeholder="Пароль" required>
            <button type="submit">Войти</button>
        </form>
    </div>
    </body>
    </html>
    '''

@app.route('/admin/dashboard')
def admin_dashboard():
    if not session.get('admin'):
        return redirect('/admin')
    products = get_all_products()
    return render_template_string(ADMIN_TEMPLATE, products=products)

@app.route('/admin/add', methods=['POST'])
def admin_add():
    if not session.get('admin'):
        return redirect('/admin')
    name = request.form.get('name')
    price = int(request.form.get('price', 0))
    stock = request.form.get('stock', 'да')
    category = request.form.get('category', '')
    specs = request.form.get('specs', '')
    add_product(name, price, stock, category, specs)
    return redirect('/admin/dashboard')

@app.route('/admin/delete/<int:product_id>')
def admin_delete(product_id):
    if not session.get('admin'):
        return redirect('/admin')
    conn = sqlite3.connect('products.db')
    c = conn.cursor()
    c.execute("DELETE FROM products WHERE id = ?", (product_id,))
    conn.commit()
    conn.close()
    return redirect('/admin/dashboard')

@app.route('/admin/edit/<int:product_id>', methods=['GET', 'POST'])
def admin_edit(product_id):
    if not session.get('admin'):
        return redirect('/admin')
    conn = sqlite3.connect('products.db')
    c = conn.cursor()
    if request.method == 'POST':
        name = request.form.get('name')
        price = int(request.form.get('price', 0))
        stock = request.form.get('stock', 'да')
        category = request.form.get('category', '')
        specs = request.form.get('specs', '')
        c.execute("UPDATE products SET name=?, price=?, stock=?, category=?, specs=? WHERE id=?", 
                  (name, price, stock, category, specs, product_id))
        conn.commit()
        conn.close()
        return redirect('/admin/dashboard')
    c.execute("SELECT * FROM products WHERE id = ?", (product_id,))
    product = c.fetchone()
    conn.close()
    return render_template_string(EDIT_TEMPLATE, product=product)

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    return redirect('/admin')

HTML = '<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Элли-Консультант</title><style>body{margin:0;padding:0;background:#f0f4f8;color:#333;font-family:system-ui;height:100vh;display:flex;flex-direction:column}#header{background:#2563eb;color:#fff;padding:15px;text-align:center;font-size:18px;font-weight:bold}#chat{flex:1;overflow-y:auto;padding:15px;background:#fff;margin:10px;border-radius:15px;box-shadow:0 2px 10px rgba(0,0,0,0.08)}.msg{margin:8px 0;padding:10px 15px;border-radius:15px;max-width:85%;word-wrap:break-word}.user{background:#2563eb;color:#fff;margin-left:auto;text-align:right}.elli{background:#e8f0fe;color:#333;margin-right:auto}#form{display:flex;padding:10px;background:#fff;border-top:1px solid #e5e7eb}#input{flex:1;padding:12px;border:1px solid #d1d5db;border-radius:25px;font-size:16px}#send{margin-left:8px;padding:12px 25px;border:none;border-radius:25px;background:#2563eb;color:#fff;font-size:16px}</style></head><body><div id="header">🛍️ ' + SHOP_NAME + ' — Онлайн-консультант Элли <a href="/admin" style="color:white;font-size:14px;margin-left:20px;">⚙️ Админка</a></div><div id="chat"><div class="msg elli">Здравствуйте! Я Элли, виртуальный консультант магазина «' + SHOP_NAME + '». Спросите меня о товарах, ценах, доставке!</div></div><form id="form" onsubmit="sendMsg(event)"><input id="input" type="text" placeholder="Напишите вопрос..." autofocus><button id="send" type="submit">→</button></form><script>function add(text,cls){var d=document.createElement("div");d.className="msg "+cls;d.textContent=text;document.getElementById("chat").appendChild(d);document.getElementById("chat").scrollTop=document.getElementById("chat").scrollHeight}async function sendMsg(e){e.preventDefault();var input=document.getElementById("input");var text=input.value.trim();if(!text)return;add(text,"user");input.value="";try{var r=await fetch("/chat",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({message:text})});var d=await r.json();add(d.reply,"elli")}catch(err){add("Ошибка связи...","elli")}}</script></body></html>'

@app.route('/')
def home():
    return HTML

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_text = data.get('message', '')
    reply = generate_response(user_text)
    return jsonify({'reply': reply})

if __name__ == '__main__':
    print(f"🛍️ Элли-консультант магазина «{SHOP_NAME}» запущена.")
    print(f"🔐 Админка: http://127.0.0.1:5000/admin (пароль: {ADMIN_PASSWORD})")
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
