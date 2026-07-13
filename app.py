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

def ask(prompt, temperature=0.7, max_tokens=600):
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
# ПАМЯТЬ ДИАЛОГА (простая, в оперативной памяти)
# ============================================================

dialogue_history = []  # хранит последние 10 сообщений

def generate_response(user_text):
    global dialogue_history
    user_lower = user_text.lower()
    
    # Сохраняем сообщение клиента
    dialogue_history.append(f"Клиент: {user_text}")
    if len(dialogue_history) > 10:
        dialogue_history = dialogue_history[-10:]
    
    history_text = '\n'.join(dialogue_history)
    
    # Проверяем, есть ли товар в каталоге
    found_items = []
    for item, info in SHOP_ITEMS.items():
        if item in user_lower:
            found_items.append(f"{item.upper()}: цена {info['цена']}, в наличии: {info['в наличии']}, гарантия: {info['гарантия']}")
    
    if found_items:
        items_text = '\n'.join(found_items)
        prompt = f"""Ты — вежливый консультант магазина «{SHOP_NAME}», тебя зовут Элли. 

История диалога:
{history_text}

Информация о товарах:
{SHOP_INFO}

Клиент спросил: "{user_text}"

В каталоге найдено:
{items_text}

Ответь клиенту (1-3 предложения). Не представляйся заново, если уже представлялась в этом диалоге. Просто ответь по делу: цена, наличие, гарантия. Предложи помощь с другими товарами. Будь вежлива. Не используй markdown."""
        reply = ask(prompt)
        dialogue_history.append(f"Элли: {reply}")
        return reply
    
    # Проверяем вопросы о доставке/оплате
    service_words = ['доставка', 'оплата', 'возврат', 'гарантия', 'как купить', 'как заказать', 'доставить']
    is_service_question = any(w in user_lower for w in service_words)
    
    if is_service_question:
        prompt = f"""Ты — вежливый консультант магазина «{SHOP_NAME}», тебя зовут Элли. 

История диалога:
{history_text}

Информация о магазине:
{SHOP_INFO}

Клиент спросил: "{user_text}"

Это вопрос о доставке/оплате/возврате. Ответь чётко по информации магазина (2-3 предложения). Не представляйся заново. Предложи помощь с товарами. Будь вежлива. Не используй markdown."""
        reply = ask(prompt)
        dialogue_history.append(f"Элли: {reply}")
        return reply
    
    # Общий вопрос
    prompt = f"""Ты — вежливый консультант магазина «{SHOP_NAME}», тебя зовут Элли. 

История диалога:
{history_text}

Информация о магазине:
{SHOP_INFO}

Клиент спросил: "{user_text}"

Ответь клиенту (1-3 предложения). Не представляйся заново. Если товара нет в каталоге — предложи похожие. Если вопрос не по теме — вежливо скажи, что ты консультант. Будь вежлива. Не используй markdown."""
    reply = ask(prompt)
    dialogue_history.append(f"Элли: {reply}")
    return reply
