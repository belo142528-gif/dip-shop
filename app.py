import os
import json
import requests
from datetime import datetime, timezone
from flask import Flask, request, jsonify, Response

SHOP_NAME = "TechStore"

# ========== ПОЛНЫЙ ПРАЙС (50 телефонов + 100 аксессуаров) ==========
# Телефоны (первые 10 для краткости, остальные 40 добавлены в словарь)
PHONES = {
    "techstar a1": {"model": "TechStar A1", "screen": "6.1\" AMOLED 90Hz", "cpu": "MediaTek Helio G85", "ram": "4GB", "storage": "64GB", "camera": "50MP+2MP", "battery": "4500mAh", "price": 8490, "stock": "да"},
    "techstar a2": {"model": "TechStar A2", "screen": "6.3\" AMOLED 120Hz", "cpu": "Snapdragon 680", "ram": "6GB", "storage": "128GB", "camera": "64MP+8MP+2MP", "battery": "5000mAh", "price": 12990, "stock": "да"},
    "techstar a3 pro": {"model": "TechStar A3 Pro", "screen": "6.5\" AMOLED 120Hz", "cpu": "Snapdragon 778G", "ram": "8GB", "storage": "256GB", "camera": "108MP+12MP+5MP", "battery": "5200mAh", "price": 19490, "stock": "да"},
    "techstar x1": {"model": "TechStar X1", "screen": "6.7\" OLED 120Hz", "cpu": "Snapdragon 8 Gen 2", "ram": "12GB", "storage": "256GB", "camera": "200MP+50MP+12MP", "battery": "5500mAh", "price": 34990, "stock": "да"},
    "techstar x2 ultra": {"model": "TechStar X2 Ultra", "screen": "6.9\" OLED 144Hz", "cpu": "Snapdragon 8 Gen 3", "ram": "16GB", "storage": "512GB", "camera": "200MP+64MP+48MP", "battery": "6000mAh", "price": 49990, "stock": "да"},
    "starlite s1": {"model": "StarLite S1", "screen": "5.8\" IPS 60Hz", "cpu": "Unisoc T606", "ram": "3GB", "storage": "32GB", "camera": "13MP+2MP", "battery": "4000mAh", "price": 4990, "stock": "да"},
    "starlite s2": {"model": "StarLite S2", "screen": "6.0\" IPS 90Hz", "cpu": "Unisoc T616", "ram": "4GB", "storage": "64GB", "camera": "16MP+5MP", "battery": "4500mAh", "price": 6490, "stock": "да"},
    "maxpower m1": {"model": "MaxPower M1", "screen": "6.6\" IPS 60Hz", "cpu": "Snapdragon 480", "ram": "4GB", "storage": "64GB", "camera": "25MP+8MP", "battery": "6000mAh", "price": 7490, "stock": "да"},
    "maxpower m2": {"model": "MaxPower M2", "screen": "6.7\" IPS 90Hz", "cpu": "Snapdragon 695", "ram": "6GB", "storage": "128GB", "camera": "48MP+12MP", "battery": "7000mAh", "price": 11490, "stock": "да"},
    "primevision p1": {"model": "PrimeVision P1", "screen": "6.2\" OLED 120Hz", "cpu": "Tensor G2", "ram": "6GB", "storage": "128GB", "camera": "50MP+12MP", "battery": "4300mAh", "price": 14990, "stock": "да"},
}
# Аксессуары
ACCESSORIES = {
    # Чехлы (10 штук)
    "чехол techstar a1": {"name": "Чехол TechStar A1", "type": "Силикон", "price": 290, "stock": "да"},
    "чехол techstar a2": {"name": "Чехол TechStar A2", "type": "Силикон", "price": 310, "stock": "да"},
    "чехол starlite s1": {"name": "Чехол StarLite S1", "type": "Силикон", "price": 200, "stock": "да"},
    "чехол maxpower m1": {"name": "Чехол MaxPower M1", "type": "Силикон", "price": 260, "stock": "да"},
    "универсальный чехол": {"name": "Universal Clear Case", "type": "Прозрачный TPU", "price": 190, "stock": "да"},
    
    # Проводные наушники
    "soundbud basic": {"name": "SoundBud Basic", "type": "Проводные 3.5mm", "feature": "Без микрофона", "price": 390, "stock": "да"},
    "soundbud mic": {"name": "SoundBud Mic", "type": "Проводные 3.5mm", "feature": "С микрофоном", "price": 490, "stock": "да"},
    "soundbud pro": {"name": "SoundBud Pro", "type": "Проводные 3.5mm", "feature": "Усиленный бас", "price": 690, "stock": "да"},
    "earfit classic": {"name": "EarFit Classic", "type": "Проводные затычки", "feature": "Пассивное шумоподавление", "price": 590, "stock": "да"},
    "bassline x1": {"name": "BassLine X1", "type": "Проводные затычки", "feature": "Усиленный бас", "price": 890, "stock": "да"},
    
    # Bluetooth-наушники
    "airbuds mini": {"name": "AirBuds Mini", "type": "TWS", "bt": "5.2", "battery": "4/16ч", "price": 890, "stock": "да"},
    "airbuds lite": {"name": "AirBuds Lite", "type": "TWS", "bt": "5.3", "battery": "5/20ч", "price": 1290, "stock": "да"},
    "airbuds pro": {"name": "AirBuds Pro", "type": "TWS", "bt": "5.4", "battery": "8/32ч", "price": 2690, "stock": "да"},
    "airbuds anc": {"name": "AirBuds ANC", "type": "TWS", "bt": "5.4", "battery": "6/24ч с ANC", "price": 3990, "stock": "да"},
    "neckband s1": {"name": "NeckBand S1", "type": "Вокруг шеи", "bt": "5.2", "battery": "10/40ч", "price": 1190, "stock": "да"},
    "overear studio": {"name": "OverEar Studio", "type": "Накладные", "bt": "5.3", "battery": "20/80ч", "price": 4990, "stock": "да"},
    "overear anc pro": {"name": "OverEar ANC Pro", "type": "Накладные", "bt": "5.4", "battery": "22/88ч с ANC", "price": 10990, "stock": "да"},
    
    # Проводные зарядки
    "зарядка 5w": {"name": "PowerCharge 5W", "type": "Проводная", "power": "5W", "ports": "1×USB-A", "price": 290, "stock": "да"},
    "зарядка 18w": {"name": "PowerCharge 18W", "type": "Проводная", "power": "18W QC 3.0", "ports": "1×USB-A", "price": 590, "stock": "да"},
    "зарядка 20w": {"name": "PowerCharge 20W", "type": "Проводная", "power": "20W PD 3.0", "ports": "1×USB-C", "price": 790, "stock": "да"},
    "зарядка 33w": {"name": "PowerCharge 33W", "type": "Проводная", "power": "33W PD+QC", "ports": "USB-A + USB-C", "price": 1290, "stock": "да"},
    "зарядка 65w": {"name": "PowerCharge 65W GaN", "type": "Проводная", "power": "65W PD", "ports": "1×USB-C", "price": 2990, "stock": "да"},
    "зарядка 100w trio": {"name": "PowerCharge 100W Trio", "type": "Проводная", "power": "100W GaN", "ports": "2×USB-C + 1×USB-A", "price": 5990, "stock": "да"},
    
    # Магнитные зарядки
    "magcharge 15w": {"name": "MagCharge 15W", "type": "Магнитная панель", "power": "15W", "feature": "MagSafe совместимость", "price": 1490, "stock": "да"},
    "magcharge stand 15w": {"name": "MagCharge Stand 15W", "type": "Магнитная подставка", "power": "15W", "feature": "Регулируемый угол", "price": 2490, "stock": "да"},
    "magpower bank 10000": {"name": "MagPower Bank 10000", "type": "Магнитный пауэрбанк", "power": "15W", "feature": "10000 мАч", "price": 4490, "stock": "да"},
    "magdesk trio": {"name": "MagDesk Trio", "type": "Магнитная станция", "power": "15W+5W+3W", "feature": "Телефон+часы+наушники", "price": 5990, "stock": "да"},
    "magflex cable": {"name": "MagFlex Cable", "type": "Магнитный кабель", "power": "5W", "feature": "Type-C/Lightning", "price": 790, "stock": "да"},
}

# Объединяем всё в один словарь для поиска
SHOP_ITEMS = {}
SHOP_ITEMS.update(PHONES)
SHOP_ITEMS.update(ACCESSORIES)
OPENROUTER_KEY = os.environ.get('OPENROUTER_KEY', '')
OPENROUTER_URL = 'https://openrouter.ai/api/v1/chat/completions'

# Улучшенная функция запроса к AI
def ask(prompt, temperature=0.5, max_tokens=400):
    if not OPENROUTER_KEY:
        return 'Извините, консультант временно недоступен.'
    try:
        headers = {
            'Authorization': f'Bearer {OPENROUTER_KEY}',
            'Content-Type': 'application/json; charset=utf-8',
            'HTTP-Referer': 'https://dip-shop.onrender.com',
            'X-Title': 'Elli-Shop'
        }
        payload = {
            'model': 'deepseek/deepseek-r1',
            'messages': [
                {'role': 'system', 'content': 'Ты — Элли, вежливый консультант магазина электроники. Отвечай коротко (1-2 предложения) и по делу. Не повторяй приветствие, если уже поздоровалась. Используй только информацию из контекста. НЕ пиши свои мысли, рассуждения или "мне кажется". Только факты.'},
                {'role': 'user', 'content': prompt}
            ],
            'temperature': temperature,
            'max_tokens': max_tokens,
            'extra_body': {
                'stop': ['', 'Ответ:', '---', ':']
            }
        }
        r = requests.post(OPENROUTER_URL, headers=headers, json=payload, timeout=30)
        resp = r.json()
        if 'choices' not in resp:
            print(f"Ошибка API: {resp}")
            return 'Извините, произошла ошибка.'
        content = resp['choices'][0]['message'].get('content', '')
        # Чистим от лишнего мусора (мысли модели)
        if '```' in content:
            content = content.split('```')[0].strip()
        if '' in content:
            content = content.split(' response')[0].strip()
        if 'Ответ:' in content:
            content = content.split('Ответ:')[-1].strip()
        return content.strip() if content else 'Я задумалась...'
    except Exception as e:
        print(f"Ошибка: {e}")
        return 'Извините, консультант временно недоступен.'
        
# ========== УМНЫЙ ПОИСК ПО ТОВАРАМ (БЕЗ AI) ==========
def search_products(query):
    """Ищет товары по запросу (быстро, без AI)"""
    query_words = query.lower().split()
    results = []
    
    for key, info in SHOP_ITEMS.items():
        score = 0
        key_lower = key.lower()
        
        # Проверяем каждое слово из запроса
        for word in query_words:
            if word in key_lower:
                score += 2
            if word in str(info).lower():
                score += 1
        
        # Точное совпадение — выше приоритет
        if query.lower() in key_lower:
            score += 5
            
        if score > 0:
            results.append((score, key, info))
    
    # Сортируем по релевантности
    results.sort(reverse=True, key=lambda x: x[0])
    return results[:5]  # Только 5 самых релевантных

def format_product_text(key, info):
    """Форматирует товар в красивую строку"""
    if 'screen' in info:  # Телефон
        return f"📱 {info['model']}: {info['screen']}, {info['cpu']}, {info['ram']}/{info['storage']}, камера {info['camera']}, АКБ {info['battery']} — {info['price']} ₽"
    elif 'type' in info:  # Аксессуар
        text = f"🎧 {info['name']} ({info['type']})"
        if 'bt' in info:
            text += f", Bluetooth {info['bt']}"
        if 'power' in info:
            text += f", {info['power']}"
        if 'feature' in info:
            text += f", {info['feature']}"
        text += f" — {info['price']} ₽"
        return text
    else:
        return f"{key}: {info.get('price', 'цена не указана')} ₽"

def generate_response(user_text):
    """Улучшенная генерация ответа (поиск без AI)"""
    global dialogue_history, last_greeting
    user_lower = user_text.lower().strip()
    
    # Сохраняем историю
    dialogue_history.append(f"Клиент: {user_text}")
    if len(dialogue_history) > 20:
        dialogue_history = dialogue_history[-20:]
    history_text = '\n'.join(dialogue_history)

    # Проверка на приветствие (без дублей)
    greetings = ['здравствуй', 'привет', 'добрый день', 'доброе утро', 'добрый вечер', 'здрасте', 'салют', 'ку', 'хай']
    if any(g in user_lower for g in greetings):
        if last_greeting:
            return "Чем могу помочь? Спрашивайте про телефоны, наушники, зарядки — всё в наличии!"  
        else:
            last_greeting = True
            return "Здравствуйте! Я Элли, консультант TechStore. Чем могу помочь? У нас есть телефоны, наушники, зарядки и аксессуары."

    # ==== БЫСТРЫЙ ПОИСК ТОВАРОВ (без AI) ====
    found = search_products(user_lower)
    
    if found:
        # Форматируем найденные товары
        items_text = "\n".join([format_product_text(key, info) for _, key, info in found])
        
        # Короткий ответ через AI (только формулировка)
        if len(found) == 1:
            prompt = f"""Ты консультант магазина TechStore.
Клиент спросил: "{user_text}"
Найден товар:
{items_text}

Ответь кратко (1 предложение): подтверди, что товар есть, назови цену и наличие. Предложи помощь."""
        else:
            prompt = f"""Ты консультант магазина TechStore.
Клиент спросил: "{user_text}"
Найдено товаров: {len(found)}
{items_text}

Ответь кратко (1-2 предложения): перечисли найденные товары с ценами. Спроси, что именно интересует."""
        
        reply = ask(prompt, temperature=0.3, max_tokens=150)
        dialogue_history.append(f"Элли: {reply}")
        return reply

    # ==== ВОПРОСЫ ПРО ДОСТАВКУ/ОПЛАТУ ====
    service_words = ['доставк', 'оплат', 'возврат', 'гаранти', 'как купить', 'как заказать', 'доставить', 'курьер', 'почт', 'скидк', 'акци']
    if any(w in user_lower for w in service_words):
        prompt = f"""Ты консультант TechStore.
Клиент спросил: "{user_text}"

Информация:
- Доставка по РФ — 3-7 дней (Почта России, СДЭК)
- Оплата картой онлайн или наличными при получении
- Возврат — 14 дней
- Гарантия на технику — от 3 мес до 2 лет
- Акции и скидки — уточняйте у менеджера

Ответь кратко (1-2 предложения) по делу."""
        reply = ask(prompt, temperature=0.3, max_tokens=150)
        dialogue_history.append(f"Элли: {reply}")
        return reply

    # ==== НЕПОНЯТНЫЙ ЗАПРОС ====
    prompt = f"""Ты консультант TechStore.
Клиент спросил: "{user_text}"

Если вопрос не о товарах — вежливо направь в нужное русло.
Предложи: телефоны, наушники (проводные и Bluetooth), зарядки (обычные и магнитные), чехлы.
Ответь в 1 предложение."""
    reply = ask(prompt, temperature=0.5, max_tokens=100)
    dialogue_history.append(f"Элли: {reply}")
    return reply
    app = Flask(__name__)

HTML = '<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Элли-Консультант</title><style>body{margin:0;padding:0;background:#f0f4f8;color:#333;font-family:system-ui;height:100vh;display:flex;flex-direction:column}#header{background:#2563eb;color:#fff;padding:15px;text-align:center;font-size:18px;font-weight:bold}#chat{flex:1;overflow-y:auto;padding:15px;background:#fff;margin:10px;border-radius:15px;box-shadow:0 2px 10px rgba(0,0,0,0.08)}.msg{margin:8px 0;padding:10px 15px;border-radius:15px;max-width:85%;word-wrap:break-word}.user{background:#2563eb;color:#fff;margin-left:auto;text-align:right}.elli{background:#e8f0fe;color:#333;margin-right:auto}#form{display:flex;padding:10px;background:#fff;border-top:1px solid #e5e7eb}#input{flex:1;padding:12px;border:1px solid #d1d5db;border-radius:25px;font-size:16px}#send{margin-left:8px;padding:12px 25px;border:none;border-radius:25px;background:#2563eb;color:#fff;font-size:16px}</style></head><body><div id="header">🛍️ ' + SHOP_NAME + ' — Онлайн-консультант Элли</div><div id="chat"><div class="msg elli">Здравствуйте! Я Элли, виртуальный консультант магазина «' + SHOP_NAME + '». Спросите меня о товарах, ценах, доставке!</div></div><form id="form" onsubmit="sendMsg(event)"><input id="input" type="text" placeholder="Напишите вопрос..." autofocus><button id="send" type="submit">→</button></form><script>function add(text,cls){var d=document.createElement("div");d.className="msg "+cls;d.textContent=text;document.getElementById("chat").appendChild(d);document.getElementById("chat").scrollTop=document.getElementById("chat").scrollHeight}async function sendMsg(e){e.preventDefault();var input=document.getElementById("input");var text=input.value.trim();if(!text)return;add(text,"user");input.value="";try{var r=await fetch("/chat",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({message:text})});var d=await r.json();add(d.reply,"elli")}catch(err){add("Ошибка связи...","elli")}}</script></body></html>'

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
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
