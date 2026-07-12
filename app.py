import os
import json
import requests
from datetime import datetime, timezone
from flask import Flask, request, jsonify, Response

# ============================================================
# НАСТРОЙКИ МАГАЗИНА
# ============================================================

SHOP_NAME = "Твой Магазин"
SHOP_ITEMS = {
    "телефон": {"цена": "15 000 ₽", "в наличии": "да", "гарантия": "1 год"},
    "ноутбук": {"цена": "45 000 ₽", "в наличии": "да", "гарантия": "2 года"},
    "наушники": {"цена": "3 500 ₽", "в наличии": "да", "гарантия": "6 мес"},
    "часы": {"цена": "8 000 ₽", "в наличии": "нет", "гарантия": "1 год"},
    "планшет": {"цена": "25 000 ₽", "в наличии": "да", "гарантия": "1 год"},
    "колонка": {"цена": "5 000 ₽", "в наличии": "да", "гарантия": "1 год"},
    "клавиатура": {"цена": "2 500 ₽", "в наличии": "да", "гарантия": "3 мес"},
    "мышка": {"цена": "1 500 ₽", "в наличии": "да", "гарантия": "3 мес"},
}

SHOP_INFO = f"""
Магазин: {SHOP_NAME}
Товары: {', '.join(SHOP_ITEMS.keys())}
Доставка: по РФ, 3-7 дней
Оплата: картой, наличными при получении
Возврат: 14 дней
"""

# ============================================================
# КЛЮЧИ
# ============================================================

OPENROUTER_KEY = os.environ.get('OPENROUTER_KEY', '')
OPENROUTER_URL = 'https://openrouter.ai/api/v1/chat/completions'

# ============================================================
# ЗАПРОС К МОДЕЛИ
# ============================================================

def ask(prompt, temperature=0.7, max_tokens=400):
    if not OPENROUTER_KEY:
        return 'Извините, консультант временно недоступен.'
    
    try:
        headers = {
            'Authorization': f'Bearer {OPENROUTER_KEY}',
            'Content-Type': 'application/json; charset=utf-8',
            'HTTP-Referer': 'https://dip-shop.onrender.com',
            'X-Title': 'Dip-Shop'
        }
        payload = {
            'model': 'deepseek/deepseek-r1',
            'messages': [{'role': 'user', 'content': prompt}],
            'temperature': temperature,
            'max_tokens': max_tokens
        }
        r = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=60)
        resp = r.json()
        
        if 'choices' not in resp:
            return 'Извините, произошла ошибка. Попробуйте позже.'
        
        content = resp['choices'][0]['message'].get('content', '')
        if not content:
            return 'Я задумалась... Задайте вопрос иначе.'
        return content.strip()
    except:
        return 'Извините, консультант временно недоступен.'

# ============================================================
# ОСНОВНАЯ ЛОГИКА
# ============================================================

def generate_response(user_text):
    user_lower = user_text.lower()
    
    # Проверяем, есть ли товар в каталоге
    found_items = []
    for item, info in SHOP_ITEMS.items():
        if item in user_lower:
            found_items.append(f"{item.upper()}: цена {info['цена']}, в наличии: {info['в наличии']}, гарантия: {info['гарантия']}")
    
    if found_items:
        items_text = '\n'.join(found_items)
        prompt = f"""Ты — вежливый консультант магазина «{SHOP_NAME}». 

Информация о товарах:
{SHOP_INFO}

Клиент спросил: "{user_text}"

Вот что мы нашли в каталоге:
{items_text}

Ответь клиенту (1-3 предложения):
1. Представься и назови магазин.
2. Расскажи о товаре: цена, наличие, гарантия.
3. Предложи помощь с другими товарами.
Будь вежлива и полезна. Не используй markdown."""
        return ask(prompt)
    
    # Если товар не найден
    prompt = f"""Ты — вежливый консультант магазина «{SHOP_NAME}». 

Информация о магазине:
{SHOP_INFO}

Клиент спросил: "{user_text}"

Ответь клиенту (1-3 предложения):
1. Представься.
2. Если вопрос о товаре, которого нет в каталоге — вежливо скажи об этом и предложи похожие товары.
3. Если вопрос о доставке, оплате, возврате — ответь по информации магазина.
4. Если вопрос не по теме магазина — вежливо скажи, что ты консультант по товарам.
Будь вежлива и полезна. Не используй markdown."""
    return ask(prompt)
    # ============================================================
# FLASK
# ============================================================

app = Flask(__name__)

HTML = '<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Дип-Консультант</title><style>body{margin:0;padding:0;background:#f5f5f5;color:#333;font-family:system-ui;height:100vh;display:flex;flex-direction:column}#header{background:#1a73e8;color:#fff;padding:15px;text-align:center;font-size:18px;font-weight:bold}#chat{flex:1;overflow-y:auto;padding:15px;background:#fff;margin:10px;border-radius:15px;box-shadow:0 2px 10px rgba(0,0,0,0.1)}.msg{margin:8px 0;padding:10px 15px;border-radius:15px;max-width:85%;word-wrap:break-word}.user{background:#1a73e8;color:#fff;margin-left:auto;text-align:right}.dip{background:#e8e8e8;color:#333;margin-right:auto}#form{display:flex;padding:10px;background:#fff;border-top:1px solid #ddd}#input{flex:1;padding:12px;border:1px solid #ddd;border-radius:25px;font-size:16px}#send{margin-left:8px;padding:12px 25px;border:none;border-radius:25px;background:#1a73e8;color:#fff;font-size:16px}</style></head><body><div id="header">🛍️ ' + SHOP_NAME + ' — Онлайн-консультант</div><div id="chat"><div class="msg dip">Здравствуйте! Я Дип, виртуальный консультант магазина «' + SHOP_NAME + '». Спросите меня о товарах, ценах, доставке!</div></div><form id="form" onsubmit="sendMsg(event)"><input id="input" type="text" placeholder="Напишите вопрос..." autofocus><button id="send" type="submit">→</button></form><script>function add(text,cls){var d=document.createElement("div");d.className="msg "+cls;d.textContent=text;document.getElementById("chat").appendChild(d);document.getElementById("chat").scrollTop=document.getElementById("chat").scrollHeight}async function sendMsg(e){e.preventDefault();var input=document.getElementById("input");var text=input.value.trim();if(!text)return;add(text,"user");input.value="";try{var r=await fetch("/chat",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({message:text})});var d=await r.json();add(d.reply,"dip")}catch(err){add("Ошибка связи...","dip")}}</script></body></html>'

@app.route('/')
def home():
    return HTML

@app.route('/chat', methods=['POST'])
def chat():
    data = request.json
    user_text = data.get('message', '')
    reply = generate_response(user_text)
    return jsonify({'reply': reply})

# ============================================================
# ЗАПУСК
# ============================================================

if __name__ == '__main__':
    print(f"🛍️ Дип-консультант магазина «{SHOP_NAME}» запущена.")
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
