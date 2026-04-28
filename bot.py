import telebot
import sqlite3
import json
import os
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask, request
import threading
import time

TOKEN = '8677541621:AAH4jT0vNypccnBi7a5Ln_V__8i59ycYX2o'
ADMIN_USERNAME = 'darzork'

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# --- База данных ---
conn = sqlite3.connect('game.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    username TEXT,
    first_name TEXT,
    balance INTEGER DEFAULT 0
)
''')
conn.commit()

ADMIN_FILE = 'admin_data.json'

def load_admin_id():
    if os.path.exists(ADMIN_FILE):
        with open(ADMIN_FILE, 'r') as f:
            data = json.load(f)
            return data.get('admin_id')
    return None

def save_admin_id(admin_id):
    with open(ADMIN_FILE, 'w') as f:
        json.dump({'admin_id': admin_id}, f)

def is_admin(user_id):
    admin_id = load_admin_id()
    return admin_id and str(user_id) == str(admin_id)

def find_user(identifier):
    clean_id = identifier.replace('@', '')
    if clean_id.isdigit():
        cursor.execute('SELECT user_id, username, first_name, balance FROM users WHERE user_id = ?', (clean_id,))
        result = cursor.fetchone()
        if result:
            return result
    cursor.execute('SELECT user_id, username, first_name, balance FROM users WHERE username = ?', (clean_id,))
    return cursor.fetchone()

def get_keyboard(user_id):
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = ['/start', '/balance', '/pay', '/top', '/help', '/shop']
    if is_admin(user_id):
        buttons.append('/players')
        buttons.append('/give')
    markup.add(*[KeyboardButton(b) for b in buttons])
    return markup

def get_donate_keyboard():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("⭐ 25 Stars - 10 млрд", callback_data="donate_25"),
        InlineKeyboardButton("⭐ 50 Stars - 25 млрд", callback_data="donate_50"),
        InlineKeyboardButton("⭐ 75 Stars - 55 млрд", callback_data="donate_75"),
        InlineKeyboardButton("⭐ 100 Stars - 200 млрд", callback_data="donate_100"),
        InlineKeyboardButton("⭐ 1000 Stars - 1 монета", callback_data="donate_1000")
    )
    return markup

@bot.message_handler(commands=['start'])
def start(message):
    user_id = str(message.from_user.id)
    username = message.from_user.username
    first_name = message.from_user.first_name
    
    if username and username.lower() == ADMIN_USERNAME.lower():
        if not load_admin_id():
            save_admin_id(user_id)
            bot.send_message(user_id, "👑 ВЫ АДМИНИСТРАТОР!")
    
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    if cursor.fetchone():
        bot.send_message(user_id, "✅ Вы уже зарегистрированы!", reply_markup=get_keyboard(user_id))
        return
    
    cursor.execute('INSERT INTO users (user_id, username, first_name, balance) VALUES (?, ?, ?, ?)',
                   (user_id, username, first_name, 0))
    conn.commit()
    bot.send_message(user_id, f"🎉 Добро пожаловать, {first_name}!\n💰 Баланс: 0", reply_markup=get_keyboard(user_id))

@bot.message_handler(commands=['help'])
def help_command(message):
    user_id = str(message.from_user.id)
    text = "📋 *КОМАНДЫ:*\n\n/start - Регистрация\n/balance - Баланс\n/pay - Перевод\n/top - Топ\n/shop - Донат\n/help - Помощь"
    if is_admin(user_id):
        text += "\n/give - Выдать монеты\n/players - Список игроков"
    bot.send_message(user_id, text, parse_mode='Markdown', reply_markup=get_keyboard(user_id))

@bot.message_handler(commands=['players'])
def list_players(message):
    user_id = str(message.from_user.id)
    if not is_admin(user_id):
        bot.send_message(user_id, "❌ Только админ!")
        return
    cursor.execute('SELECT user_id, username, first_name, balance FROM users')
    players = cursor.fetchall()
    if not players:
        bot.send_message(user_id, "Нет игроков")
        return
    text = "👥 *ИГРОКИ:*\n\n"
    for i, p in enumerate(players, 1):
        text += f"{i}. {p[2]} (@{p[1] or 'нет'}) | ID: `{p[0]}` | 💰 {p[3]}\n"
    bot.send_message(user_id, text, parse_mode='Markdown')

@bot.message_handler(commands=['balance'])
def balance(message):
    user_id = str(message.from_user.id)
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    result = cursor.fetchone()
    if result:
        bot.send_message(user_id, f"💰 Баланс: {result[0]:,} монет".replace(',', ' '), reply_markup=get_keyboard(user_id))

@bot.message_handler(commands=['shop'])
def shop(message):
    bot.send_message(message.chat.id, "⭐ *MAGIC SHOP*\n\n25⭐ → 10 млрд\n50⭐ → 25 млрд\n75⭐ → 55 млрд\n100⭐ → 200 млрд\n1000⭐ → 1 монета", 
                     parse_mode='Markdown', reply_markup=get_donate_keyboard())

@bot.callback_query_handler(func=lambda call: call.data.startswith('donate_'))
def handle_donate(call):
    stars = call.data.split('_')[1]
    tariffs = {'25': 10000000000, '50': 25000000000, '75': 55000000000, '100': 200000000000, '1000': 1}
    if stars not in tariffs:
        bot.answer_callback_query(call.id, "Ошибка")
        return
    bot.send_invoice(call.message.chat.id, f"Покупка {tariffs[stars]:,} монет".replace(',', ' '), 
                     f"⭐ {stars} Stars", f"stars_{stars}", "", "XTR", 
                     [telebot.types.LabeledPrice(label=f"{stars} Stars", amount=int(stars))])

@bot.pre_checkout_query_handler(func=lambda q: True)
def pre_checkout(q):
    bot.answer_pre_checkout_query(q.id, ok=True)

@bot.message_handler(content_types=['successful_payment'])
def successful_payment(message):
    user_id = str(message.from_user.id)
    stars = message.successful_payment.invoice_payload.split('_')[1]
    tariffs = {'25': 10000000000, '50': 25000000000, '75': 55000000000, '100': 200000000000, '1000': 1}
    amount = tariffs.get(stars, 0)
    cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
    conn.commit()
    bot.send_message(user_id, f"✅ +{amount:,} монет!".replace(',', ' '))

@bot.message_handler(commands=['pay'])
def pay_start(message):
    bot.send_message(message.chat.id, "Отправь: `@username 100`", parse_mode='Markdown')
    bot.register_next_step_handler(message, process_pay)

def process_pay(message):
    user_id = str(message.from_user.id)
    parts = message.text.split()
    if len(parts) != 2:
        bot.send_message(user_id, "❌ Формат: @username 100")
        return
    try:
        amount = int(parts[1])
    except:
        bot.send_message(user_id, "❌ Сумма числом")
        return
    recipient = find_user(parts[0])
    if not recipient:
        bot.send_message(user_id, "❌ Пользователь не найден")
        return
    cursor.execute('UPDATE users SET balance = balance - ? WHERE user_id = ?', (amount, user_id))
    cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, recipient[0]))
    conn.commit()
    bot.send_message(user_id, "✅ Переведено!")

@bot.message_handler(commands=['give'])
def give_start(message):
    if not is_admin(str(message.from_user.id)):
        bot.send_message(message.chat.id, "❌ Только админ!")
        return
    bot.send_message(message.chat.id, "Отправь: `@username 500`", parse_mode='Markdown')
    bot.register_next_step_handler(message, process_give)

def process_give(message):
    user_id = str(message.from_user.id)
    if not is_admin(user_id):
        return
    parts = message.text.split()
    if len(parts) != 2:
        return
    try:
        amount = int(parts[1])
    except:
        return
    recipient = find_user(parts[0])
    if recipient:
        cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, recipient[0]))
        conn.commit()
        bot.send_message(user_id, f"✅ Выдано {amount} монет")

@bot.message_handler(commands=['top'])
def top(message):
    cursor.execute('SELECT first_name, username, balance FROM users ORDER BY balance DESC LIMIT 10')
    top_players = cursor.fetchall()
    text = "🏆 *ТОП 10:*\n"
    for i, p in enumerate(top_players, 1):
        text += f"{i}. {p[0]} (@{p[1] or 'нет'}) — {p[2]} монет\n"
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

# --- Webhook для Render ---
@app.route('/' + TOKEN, methods=['POST'])
def webhook():
    update = telebot.types.Update.de_json(request.stream.read().decode('utf-8'))
    bot.process_new_updates([update])
    return 'ok', 200

@app.route('/')
def index():
    return 'Bot is running!', 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    bot.remove_webhook()
    time.sleep(1)
    bot.set_webhook(url=f'https://your-app-name.onrender.com/{TOKEN}')  # ⚠️ ЗАМЕНИ НА СВОЙ URL
    app.run(host='0.0.0.0', port=port)
