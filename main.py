# -*- coding: utf-8 -*-

import asyncio
import logging
import sqlite3
import os
from datetime import datetime, timedelta
import random

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, FSInputFile
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ===================== ГРЕЧЕСКИЙ АЛФАВИТ ДЛЯ НОМЕРОВ ЗАКАЗОВ =====================
GREEK_LETTERS = [
    "ALPHA", "BETA", "GAMMA", "DELTA", "EPSILON", "ZETA", "ETA", "THETA",
    "IOTA", "KAPPA", "LAMBDA", "MU", "NU", "XI", "OMICRON", "PI",
    "RHO", "SIGMA", "TAU", "UPSILON", "PHI", "CHI", "PSI", "OMEGA"
]

# ===================== НАСТРОЙКА БАЗЫ ДАННЫХ =====================
import os
DATA_DIR = "/persistent" if os.path.exists("/persistent") else "data"
os.makedirs(DATA_DIR, exist_ok=True)
DB_NAME = f"{DATA_DIR}/shop_bot.db"

# ===================== НАСТРОЙКИ =====================
BOT_TOKEN = "8886790065:AAGdMQdY0UXRFH1ZhQ7TtdS72nP2V5UmZO8"

ADMINS = [
    1244835178,
    7802858867,
]

DISPATCHER_USERNAME = "@sopranidi_support"
CEO_USERNAME = "@sopranidi"
CHANNEL_LINK = "https://t.me/ваш_канал"
BOT_LINK = "https://t.me/sopranidi_bot"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ===================== ФУНКЦИИ ДЛЯ ГЕНЕРАЦИИ КОДОВ =====================
def generate_order_code() -> str:
    """Генерирует уникальный код заказа: буква греческого алфавита + число."""
    greek_letter = random.choice(GREEK_LETTERS)
    number = random.randint(1000, 9999)
    return f"{greek_letter}{number}"

def generate_unique_order_code() -> str:
    """Генерирует уникальный код заказа, проверяя, что он не занят."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    
    max_attempts = 100
    for _ in range(max_attempts):
        code = generate_order_code()
        cur.execute("SELECT order_id FROM orders WHERE order_code = ?", (code,))
        if not cur.fetchone():
            conn.close()
            return code
    
    # Если не удалось сгенерировать уникальный код, используем время
    timestamp = str(int(datetime.now().timestamp()))[-6:]
    conn.close()
    return f"OMEGA{timestamp}"

# ===================== БАЗА ДАННЫХ =====================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    
    # Таблица пользователей
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            last_name TEXT,
            reg_date TEXT,
            last_action TEXT,
            action_date TEXT
        )
    """)
    
    # Таблица заказов с миграцией
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='orders'")
    table_exists = cur.fetchone()
    
    if table_exists:
        cur.execute("PRAGMA table_info(orders)")
        columns = [col[1] for col in cur.fetchall()]
        
        # Добавляем order_code, если его нет
        if "order_code" not in columns:
            # Создаём новую таблицу
            cur.execute("""
                CREATE TABLE orders_new (
                    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    service TEXT,
                    price INTEGER,
                    status TEXT,
                    created_at TEXT,
                    paid_at TEXT,
                    admin_price INTEGER DEFAULT 0,
                    admin_note TEXT DEFAULT '',
                    order_code TEXT UNIQUE,
                    FOREIGN KEY(user_id) REFERENCES users(user_id)
                )
            """)
            
            # Копируем данные
            cur.execute("""
                INSERT INTO orders_new (order_id, user_id, service, price, status, created_at, paid_at, admin_price, admin_note)
                SELECT order_id, user_id, service, price, status, created_at, paid_at, admin_price, admin_note
                FROM orders
            """)
            
            cur.execute("DROP TABLE orders")
            cur.execute("ALTER TABLE orders_new RENAME TO orders")
            logging.info("✅ Добавлена колонка order_code")
        
        # Добавляем остальные колонки если их нет
        cur.execute("PRAGMA table_info(orders)")
        columns = [col[1] for col in cur.fetchall()]
        if "admin_price" not in columns:
            cur.execute("ALTER TABLE orders ADD COLUMN admin_price INTEGER DEFAULT 0")
        if "admin_note" not in columns:
            cur.execute("ALTER TABLE orders ADD COLUMN admin_note TEXT DEFAULT ''")
    else:
        # Создаём таблицу с нуля
        cur.execute("""
            CREATE TABLE orders (
                order_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                service TEXT,
                price INTEGER,
                status TEXT,
                created_at TEXT,
                paid_at TEXT,
                admin_price INTEGER DEFAULT 0,
                admin_note TEXT DEFAULT '',
                order_code TEXT UNIQUE,
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        """)
        logging.info("✅ Таблица orders создана")
    
    # Таблицы логов
    cur.execute("""
        CREATE TABLE IF NOT EXISTS user_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT,
            details TEXT,
            timestamp TEXT,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    """)
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS admin_logs (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id INTEGER,
            action TEXT,
            details TEXT,
            timestamp TEXT
        )
    """)
    
    conn.commit()
    conn.close()
    logging.info("✅ База данных проверена/создана!")

def is_admin(user_id: int) -> bool:
    return user_id in ADMINS

def add_user(user_id: int, username: str, first_name: str, last_name: str = ""):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO users (user_id, username, first_name, last_name, reg_date) VALUES (?, ?, ?, ?, ?)",
        (user_id, username, first_name, last_name, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

def update_user_action(user_id: int, action: str):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET last_action = ?, action_date = ? WHERE user_id = ?",
        (action, datetime.now().isoformat(), user_id)
    )
    conn.commit()
    conn.close()

def add_user_log(user_id: int, action: str, details: str = ""):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO user_logs (user_id, action, details, timestamp) VALUES (?, ?, ?, ?)",
        (user_id, action, details, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

def add_admin_log(admin_id: int, action: str, details: str = ""):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO admin_logs (admin_id, action, details, timestamp) VALUES (?, ?, ?, ?)",
        (admin_id, action, details, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

def add_order(user_id: int, service: str, price: int) -> tuple:
    """Создаёт заказ и возвращает (order_id, order_code)."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    
    order_code = generate_unique_order_code()
    
    cur.execute(
        "INSERT INTO orders (user_id, service, price, status, created_at, order_code) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, service, price, "pending", datetime.now().isoformat(), order_code)
    )
    order_id = cur.lastrowid
    conn.commit()
    conn.close()
    return order_id, order_code

def update_order_status(order_id: int, status: str):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "UPDATE orders SET status = ?, paid_at = ? WHERE order_id = ?",
        (status, datetime.now().isoformat(), order_id)
    )
    conn.commit()
    conn.close()

def update_order_price(order_id: int, admin_price: int, admin_note: str = ""):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "UPDATE orders SET admin_price = ?, admin_note = ? WHERE order_id = ?",
        (admin_price, admin_note, order_id)
    )
    conn.commit()
    conn.close()

def delete_order(order_id: int):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("DELETE FROM orders WHERE order_id = ?", (order_id,))
    conn.commit()
    conn.close()

def delete_old_orders(days: int = 30):
    """Удаляет заказы старше указанного количества дней."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    
    cutoff_date = (datetime.now() - timedelta(days=days)).isoformat()
    
    cur.execute(
        "DELETE FROM orders WHERE created_at < ? AND status IN ('paid', 'cancelled')",
        (cutoff_date,)
    )
    deleted_count = cur.rowcount
    conn.commit()
    conn.close()
    return deleted_count

def get_order(order_id: int):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT order_id, user_id, service, price, status, created_at, paid_at, admin_price, admin_note, order_code
        FROM orders WHERE order_id = ?
    """, (order_id,))
    row = cur.fetchone()
    conn.close()
    return row

def get_order_by_code(order_code: str):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT order_id, user_id, service, price, status, created_at, paid_at, admin_price, admin_note, order_code
        FROM orders WHERE order_code = ?
    """, (order_code,))
    row = cur.fetchone()
    conn.close()
    return row

def get_user_orders(user_id: int):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "SELECT order_id, service, price, status, created_at, admin_price, order_code FROM orders WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,)
    )
    rows = cur.fetchall()
    conn.close()
    return rows

def get_all_users():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT user_id, username, first_name, last_name, reg_date, last_action, action_date FROM users ORDER BY reg_date DESC")
    rows = cur.fetchall()
    conn.close()
    return rows

def get_all_orders():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT o.order_id, o.user_id, u.username, o.service, o.price, o.status, o.created_at, o.paid_at, o.admin_price, o.admin_note, o.order_code
        FROM orders o
        LEFT JOIN users u ON o.user_id = u.user_id
        ORDER BY o.created_at DESC
    """)
    rows = cur.fetchall()
    conn.close()
    return rows

def get_user_logs(user_id: int, limit: int = 20):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "SELECT action, details, timestamp FROM user_logs WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?",
        (user_id, limit)
    )
    rows = cur.fetchall()
    conn.close()
    return rows

def get_stats():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    user_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM orders")
    total_orders = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM orders WHERE status='paid'")
    paid_orders = cur.fetchone()[0]
    cur.execute("SELECT SUM(price) FROM orders WHERE status='paid'")
    total_income = cur.fetchone()[0] or 0
    cur.execute("SELECT COUNT(*) FROM orders WHERE status='pending'")
    pending_orders = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM orders WHERE status='cancelled'")
    cancelled_orders = cur.fetchone()[0]
    conn.close()
    return {
        "users": user_count,
        "total_orders": total_orders,
        "paid_orders": paid_orders,
        "pending_orders": pending_orders,
        "cancelled_orders": cancelled_orders,
        "income": total_income
    }

# ===================== КЛАВИАТУРЫ =====================
def main_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📚 Заказать работу", callback_data="buy")
    builder.button(text="📂 Примеры работ", callback_data="examples")
    builder.button(text="📞 Поддержка", callback_data="support")
    builder.button(text="📋 Мои заказы", callback_data="my_orders")
    builder.button(text="ℹ️ О нас", callback_data="about")
    builder.adjust(2, 2, 1)
    return builder.as_markup()

def admin_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Статистика", callback_data="admin_stats")
    builder.button(text="👥 Пользователи", callback_data="admin_users")
    builder.button(text="📦 Заказы", callback_data="admin_orders")
    builder.button(text="🗑️ Удалить старые заказы", callback_data="admin_delete_old")
    builder.button(text="📋 Логи", callback_data="admin_logs")
    builder.button(text="🔙 В главное меню", callback_data="main_menu")
    builder.adjust(2, 2, 1)
    return builder.as_markup()

def services_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Курсовая работа (от 2500₽)", callback_data="service_coursework")
    builder.button(text="🎓 Школьный проект (от 1500₽)", callback_data="service_project")
    builder.button(text="📊 Отчёт по практике (от 3000₽)", callback_data="service_practice")
    builder.button(text="🔙 Назад", callback_data="main_menu")
    builder.adjust(1)
    return builder.as_markup()

def back_to_main_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 В главное меню", callback_data="main_menu")
    return builder.as_markup()

def users_keyboard(users: list, page: int = 0) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    start = page * 10
    end = start + 10
    page_users = users[start:end]
    for user in page_users:
        user_id, username, first_name, _, _, _, _ = user
        name = username or first_name or str(user_id)
        builder.button(text=f"👤 {name[:15]}", callback_data=f"user_{user_id}")
    nav_buttons = []
    if page > 0:
        nav_buttons.append(("◀️ Назад", f"users_page_{page-1}"))
    if end < len(users):
        nav_buttons.append(("Вперед ▶️", f"users_page_{page+1}"))
    for text, data in nav_buttons:
        builder.button(text=text, callback_data=data)
    builder.button(text="🔙 Назад", callback_data="admin_menu")
    builder.adjust(1)
    return builder.as_markup()

def orders_keyboard(orders: list, page: int = 0) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    start = page * 10
    end = start + 10
    page_orders = orders[start:end]
    for order in page_orders:
        order_id, user_id, username, service, price, status, _, _, admin_price, _, order_code = order
        status_emoji = "✅" if status == "paid" else "⏳" if status == "pending" else "❌"
        final_price = admin_price if admin_price > 0 else price
        display_code = order_code or f"#{order_id}"
        builder.button(
            text=f"{status_emoji} {display_code} - {service[:10]} ({final_price}₽)",
            callback_data=f"order_{order_id}"
        )
    nav_buttons = []
    if page > 0:
        nav_buttons.append(("◀️ Назад", f"orders_page_{page-1}"))
    if end < len(orders):
        nav_buttons.append(("Вперед ▶️", f"orders_page_{page+1}"))
    for text, data in nav_buttons:
        builder.button(text=text, callback_data=data)
    builder.button(text="🔙 Назад", callback_data="admin_menu")
    builder.adjust(1)
    return builder.as_markup()

def order_detail_keyboard(order_id: int, status: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    if status == "pending":
        builder.button(text="✅ Подтвердить оплату", callback_data=f"confirm_payment_{order_id}")
        builder.button(text="💰 Назначить цену", callback_data=f"set_price_{order_id}")
        builder.button(text="❌ Удалить заказ", callback_data=f"delete_order_{order_id}")
    
    builder.button(text="🔙 Назад к заказам", callback_data="admin_orders")
    builder.adjust(1)
    return builder.as_markup()

def order_user_keyboard(order_id: int, status: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    if status == "pending":
        builder.button(text="❌ Отменить заказ", callback_data=f"cancel_order_{order_id}")
    
    builder.button(text="🔄 Обновить", callback_data=f"refresh_order_{order_id}")
    builder.button(text="🔙 Назад", callback_data="my_orders")
    builder.adjust(1)
    return builder.as_markup()

# ===================== МАШИНЫ СОСТОЯНИЙ =====================
class SupportState(StatesGroup):
    waiting_for_message = State()

class AdminBroadcastState(StatesGroup):
    waiting_for_message = State()

class AdminSetPriceState(StatesGroup):
    waiting_for_price = State()
    waiting_for_note = State()

class AdminDeleteOldState(StatesGroup):
    waiting_for_days = State()

# ===================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====================
async def update_message(callback: CallbackQuery, text: str, reply_markup=None, parse_mode=None):
    try:
        await callback.message.edit_text(
            text,
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )
    except Exception as e:
        if "there is no text" in str(e):
            try:
                await callback.message.delete()
            except:
                pass
            await callback.message.answer(
                text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
        else:
            logging.error(f"Ошибка обновления: {e}")
            await callback.message.answer(
                text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )

async def send_safe_message(message: Message, text: str, reply_markup=None):
    try:
        await message.answer(text, reply_markup=reply_markup)
    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await message.answer(text, reply_markup=reply_markup)

# ===================== ОБРАБОТЧИКИ КОМАНД =====================
@dp.message(Command("start"))
async def cmd_start(message: Message):
    user = message.from_user
    add_user(user.id, user.username, user.first_name, user.last_name or "")
    update_user_action(user.id, "start")
    add_user_log(user.id, "start", "Запустил бота")
    text = (
        "🎵 Добро пожаловать в Sopranidi Corp.!\n\n"
        "Мы - команда профессионалов, помогающая студентам и школьникам "
        "создавать уникальные проекты, курсовые и отчёты.\n\n"
        "Выберите нужную услугу в меню ниже 👇"
    )
    try:
        photo = FSInputFile("logo.jpg")
        await message.answer_photo(photo=photo, caption=text, reply_markup=main_menu_keyboard())
    except Exception as e:
        logging.warning(f"Фото не найдено: {e}")
        await send_safe_message(message, text, main_menu_keyboard())

@dp.message(Command("help"))
async def cmd_help(message: Message):
    text = (
        "📖 Помощь\n\n"
        "/start - главное меню\n"
        "/buy - выбор услуги\n"
        "/examples - примеры работ\n"
        "/support - поддержка\n"
        "/my_orders - мои заказы\n\n"
        "Для администраторов:\n"
        "/admin - админ-панель"
    )
    await send_safe_message(message, text)

@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет доступа.")
        return
    add_admin_log(message.from_user.id, "admin_panel", "Открыл админ-панель")
    stats = get_stats()
    text = (
        "🔐 *Админ-панель Sopranidi Corp.*\n\n"
        f"👥 Пользователей: *{stats['users']}*\n"
        f"📦 Всего заказов: *{stats['total_orders']}*\n"
        f"✅ Оплаченных: *{stats['paid_orders']}*\n"
        f"⏳ Ожидают оплаты: *{stats['pending_orders']}*\n"
        f"❌ Отменённых: *{stats['cancelled_orders']}*\n"
        f"💰 Доход: *{stats['income']} руб.*\n\n"
        f"📌 Диспетчер: {DISPATCHER_USERNAME}\n"
        f"👤 CEO: {CEO_USERNAME}\n\n"
        "👇 Выберите действие:"
    )
    await send_safe_message(message, text, admin_menu_keyboard())

@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав.")
        return
    stats = get_stats()
    text = (
        f"📊 *Статистика*\n\n"
        f"👥 Пользователей: *{stats['users']}*\n"
        f"📦 Заказов: *{stats['total_orders']}*\n"
        f"✅ Оплачено: *{stats['paid_orders']}*\n"
        f"⏳ Ожидают: *{stats['pending_orders']}*\n"
        f"❌ Отменено: *{stats['cancelled_orders']}*\n"
        f"💰 Доход: *{stats['income']} руб.*"
    )
    await message.answer(text)

@dp.message(Command("broadcast"))
async def cmd_broadcast(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав.")
        return
    text = message.text.replace("/broadcast", "", 1).strip()
    if not text:
        await message.answer("📢 *Рассылка*\n\nВведите текст для рассылки всем пользователям:")
        await state.set_state(AdminBroadcastState.waiting_for_message)
        return
    users = get_all_users()
    sent = 0
    for uid in users:
        try:
            await bot.send_message(uid, text)
            sent += 1
            await asyncio.sleep(0.1)
        except:
            pass
    add_admin_log(message.from_user.id, "broadcast", f"Отправил рассылку {sent} пользователям")
    await message.answer(f"✅ Рассылка выполнена. Отправлено {sent} пользователям.")

# ===================== О КОМПАНИИ =====================
@dp.callback_query(F.data == "about")
async def cb_about(callback: CallbackQuery):
    user_id = callback.from_user.id
    update_user_action(user_id, "about")
    add_user_log(user_id, "about", "Открыл информацию о компании")
    
    text = (
        "ℹ️ *О компании Sopranidi Corp.*\n\n"
        "Sopranidi Corp. — это команда профессионалов, которая помогает "
        "студентам и школьникам создавать уникальные проекты, курсовые и отчёты. "
        "Мы работаем с 2023 года и за это время помогли более 500 клиентам.\n\n"
        "🌟 *Наши преимущества:*\n"
        "• Индивидуальный подход к каждому клиенту\n"
        "• Гарантия качества и оригинальности\n"
        "• Соблюдение сроков\n"
        "• Доступные цены\n\n"
        "📌 *Контакты:*\n"
        f"👤 Диспетчер: {DISPATCHER_USERNAME}\n"
        f"👤 CEO: {CEO_USERNAME}\n\n"
        "🔗 *Ссылки:*\n"
        f"📢 Канал: {CHANNEL_LINK}\n"
        f"🤖 Бот: {BOT_LINK}\n"
    )
    
    keyboard = InlineKeyboardBuilder()
    dispatcher_username = DISPATCHER_USERNAME.replace("@", "")
    ceo_username = CEO_USERNAME.replace("@", "")
    keyboard.button(text="👤 Связаться с диспетчером", url=f"https://t.me/{dispatcher_username}")
    keyboard.button(text="👤 Связаться с CEO", url=f"https://t.me/{ceo_username}")
    keyboard.button(text="📢 Перейти в канал", url=CHANNEL_LINK)
    keyboard.button(text="🤖 Перейти в бота", url=BOT_LINK)
    keyboard.button(text="🔙 Назад", callback_data="main_menu")
    keyboard.adjust(1)
    
    await update_message(callback, text, keyboard.as_markup())
    await callback.answer()

# ===================== АДМИН-ПАНЕЛЬ =====================
@dp.callback_query(F.data == "admin_stats")
async def cb_admin_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    stats = get_stats()
    add_admin_log(callback.from_user.id, "view_stats", "Просмотрел статистику")
    text = (
        "📊 *Статистика Sopranidi Corp.*\n\n"
        f"👥 Пользователей: *{stats['users']}*\n"
        f"📦 Всего заказов: *{stats['total_orders']}*\n"
        f"✅ Оплаченных: *{stats['paid_orders']}*\n"
        f"⏳ Ожидают оплаты: *{stats['pending_orders']}*\n"
        f"❌ Отменённых: *{stats['cancelled_orders']}*\n"
        f"💰 Доход: *{stats['income']} руб.*"
    )
    await update_message(callback, text, admin_menu_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "admin_users")
async def cb_admin_users(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    users = get_all_users()
    add_admin_log(callback.from_user.id, "view_users", f"Просмотрел список пользователей ({len(users)})")
    if not users:
        await update_message(callback, "👥 Пользователей пока нет.", admin_menu_keyboard())
        await callback.answer()
        return
    await update_message(callback, "👥 *Список пользователей:*", users_keyboard(users, 0))
    await callback.answer()

@dp.callback_query(F.data.startswith("users_page_"))
async def cb_users_page(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    page = int(callback.data.split("_")[2])
    users = get_all_users()
    await callback.message.edit_reply_markup(reply_markup=users_keyboard(users, page))
    await callback.answer()

@dp.callback_query(F.data.startswith("user_"))
async def cb_user_detail(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    user_id = int(callback.data.split("_")[1])
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT user_id, username, first_name, last_name, reg_date, last_action, action_date FROM users WHERE user_id = ?", (user_id,))
    user = cur.fetchone()
    conn.close()
    if not user:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return
    _, username, first_name, last_name, reg_date, last_action, action_date = user
    logs = get_user_logs(user_id)
    orders = get_user_orders(user_id)
    text = (
        f"👤 *Информация о пользователе*\n\n"
        f"🆔 ID: `{user_id}`\n"
        f"👤 Имя: {first_name} {last_name or ''}\n"
        f"📌 Username: @{username or 'Не указан'}\n"
        f"📅 Регистрация: {reg_date[:10]}\n"
        f"📌 Последнее действие: {last_action or 'Нет'}\n\n"
        f"📦 Заказов: {len(orders)}\n"
        f"✅ Оплачено: {len([o for o in orders if o[3] == 'paid'])}\n\n"
        f"📋 *Последние действия:*\n"
    )
    for action, details, timestamp in logs[:5]:
        time_str = datetime.fromisoformat(timestamp).strftime("%d.%m %H:%M")
        text += f"• {time_str} - {action} {details}\n"
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="📦 Заказы пользователя", callback_data=f"user_orders_{user_id}")
    keyboard.button(text="🔙 Назад", callback_data="admin_users")
    keyboard.adjust(1)
    await update_message(callback, text, keyboard.as_markup())
    await callback.answer()

@dp.callback_query(F.data.startswith("user_orders_"))
async def cb_user_orders_detail(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    user_id = int(callback.data.split("_")[2])
    orders = get_user_orders(user_id)
    if not orders:
        text = "📦 У пользователя нет заказов."
    else:
        text = f"📦 *Заказы пользователя (ID: {user_id}):*\n\n"
        for order in orders:
            order_id, service, price, status, created_at, admin_price, order_code = order
            status_text = "✅ Оплачен" if status == "paid" else "⏳ Ожидает" if status == "pending" else "❌ Отменён"
            final_price = admin_price if admin_price > 0 else price
            created = datetime.fromisoformat(created_at).strftime("%d.%m.%Y")
            display_code = order_code or f"#{order_id}"
            text += f"• {display_code}: {service} - {final_price} руб. ({status_text}) [{created}]\n"
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🔙 Назад", callback_data=f"user_{user_id}")
    keyboard.adjust(1)
    await update_message(callback, text, keyboard.as_markup())
    await callback.answer()

@dp.callback_query(F.data == "admin_orders")
async def cb_admin_orders(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    orders = get_all_orders()
    add_admin_log(callback.from_user.id, "view_orders", f"Просмотрел список заказов ({len(orders)})")
    if not orders:
        await update_message(callback, "📦 Заказов пока нет.", admin_menu_keyboard())
        await callback.answer()
        return
    await update_message(callback, "📦 *Список заказов:*", orders_keyboard(orders, 0))
    await callback.answer()

@dp.callback_query(F.data.startswith("orders_page_"))
async def cb_orders_page(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    page = int(callback.data.split("_")[2])
    orders = get_all_orders()
    await callback.message.edit_reply_markup(reply_markup=orders_keyboard(orders, page))
    await callback.answer()

@dp.callback_query(F.data.startswith("order_"))
async def cb_order_detail(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    order_id = int(callback.data.split("_")[1])
    order = get_order(order_id)
    if not order:
        await callback.answer("❌ Заказ не найден", show_alert=True)
        return
    
    order_id, user_id, service, price, status, created_at, paid_at, admin_price, admin_note, order_code = order
    status_text = "✅ Оплачен" if status == "paid" else "⏳ Ожидает оплаты" if status == "pending" else "❌ Отменён"
    final_price = admin_price if admin_price > 0 else price
    name = f"ID: {user_id}"
    display_code = order_code or f"#{order_id}"
    
    created = datetime.fromisoformat(created_at).strftime("%d.%m.%Y %H:%M")
    paid = datetime.fromisoformat(paid_at).strftime("%d.%m.%Y %H:%M") if paid_at else "Не оплачен"
    
    text = (
        f"📦 *Информация о заказе {display_code}*\n\n"
        f"👤 Пользователь: {name}\n"
        f"📝 Услуга: {service}\n"
        f"💰 Изначальная цена: {price} руб.\n"
        f"💰 Назначенная цена: {final_price} руб.\n"
        f"📊 Статус: {status_text}\n"
        f"📅 Создан: {created}\n"
        f"✅ Оплачен: {paid}\n"
    )
    
    if admin_note:
        text += f"📌 Заметка: {admin_note}\n"
    
    await update_message(callback, text, order_detail_keyboard(order_id, status))
    await callback.answer()

# ===================== АДМИН: УДАЛЕНИЕ СТАРЫХ ЗАКАЗОВ =====================
@dp.callback_query(F.data == "admin_delete_old")
async def cb_admin_delete_old(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    text = (
        "🗑️ *Удаление старых заказов*\n\n"
        "Эта команда удаляет все оплаченные и отменённые заказы, "
        "которые старше указанного количества дней.\n\n"
        "Введите количество дней (например, 30):"
    )
    await callback.message.edit_text(text, reply_markup=back_to_main_keyboard())
    await state.set_state(AdminDeleteOldState.waiting_for_days)
    await callback.answer()

@dp.message(AdminDeleteOldState.waiting_for_days)
async def cb_admin_delete_old_process(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Нет доступа.")
        await state.clear()
        return
    
    try:
        days = int(message.text.strip())
        if days <= 0:
            await message.answer("❌ Количество дней должно быть положительным числом. Попробуйте снова:")
            return
        
        deleted_count = delete_old_orders(days)
        add_admin_log(message.from_user.id, "delete_old_orders", f"Удалил {deleted_count} заказов старше {days} дней")
        
        await message.answer(
            f"✅ Удалено *{deleted_count}* заказов, которые были старше *{days}* дней.\n\n"
            f"Удалены только оплаченные и отменённые заказы.",
            parse_mode="Markdown",
            reply_markup=admin_menu_keyboard()
        )
        await state.clear()
        
    except ValueError:
        await message.answer("❌ Введите корректное число. Попробуйте снова:")

# ===================== АДМИН: НАЗНАЧЕНИЕ ЦЕНЫ =====================
@dp.callback_query(F.data.startswith("set_price_"))
async def cb_set_price_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    order_id = int(callback.data.split("_")[2])
    order = get_order(order_id)
    if not order:
        await callback.answer("❌ Заказ не найден", show_alert=True)
        return
    
    await state.update_data(order_id=order_id)
    await callback.message.edit_text(
        f"💰 *Назначение цены для заказа #{order_id}*\n\n"
        f"Текущая цена: {order[3]} руб.\n\n"
        f"Введите новую цену (только число):",
        reply_markup=back_to_main_keyboard()
    )
    await state.set_state(AdminSetPriceState.waiting_for_price)
    await callback.answer()

@dp.message(AdminSetPriceState.waiting_for_price)
async def cb_set_price_process(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Нет доступа.")
        await state.clear()
        return
    
    try:
        new_price = int(message.text.strip())
        if new_price <= 0:
            await message.answer("❌ Цена должна быть положительным числом. Попробуйте снова:")
            return
        
        data = await state.get_data()
        order_id = data.get("order_id")
        
        update_order_price(order_id, new_price, "")
        add_admin_log(message.from_user.id, "set_price", f"Назначил цену {new_price} руб. для заказа #{order_id}")
        
        await message.answer(f"✅ Цена для заказа #{order_id} успешно обновлена на *{new_price} руб.*")
        await state.clear()
        
        # Возвращаемся к заказу
        await cb_order_detail_callback(message, order_id)
        
    except ValueError:
        await message.answer("❌ Введите корректное число. Попробуйте снова:")

async def cb_order_detail_callback(message: Message, order_id: int):
    order = get_order(order_id)
    if not order:
        await message.answer("❌ Заказ не найден")
        return
    
    order_id, user_id, service, price, status, created_at, paid_at, admin_price, admin_note, order_code = order
    status_text = "✅ Оплачен" if status == "paid" else "⏳ Ожидает оплаты" if status == "pending" else "❌ Отменён"
    final_price = admin_price if admin_price > 0 else price
    name = f"ID: {user_id}"
    display_code = order_code or f"#{order_id}"
    
    created = datetime.fromisoformat(created_at).strftime("%d.%m.%Y %H:%M")
    paid = datetime.fromisoformat(paid_at).strftime("%d.%m.%Y %H:%M") if paid_at else "Не оплачен"
    
    text = (
        f"📦 *Информация о заказе {display_code}*\n\n"
        f"👤 Пользователь: {name}\n"
        f"📝 Услуга: {service}\n"
        f"💰 Изначальная цена: {price} руб.\n"
        f"💰 Назначенная цена: {final_price} руб.\n"
        f"📊 Статус: {status_text}\n"
        f"📅 Создан: {created}\n"
        f"✅ Оплачен: {paid}\n"
    )
    
    if admin_note:
        text += f"📌 Заметка: {admin_note}\n"
    
    keyboard = InlineKeyboardBuilder()
    if status == "pending":
        keyboard.button(text="✅ Подтвердить оплату", callback_data=f"confirm_payment_{order_id}")
        keyboard.button(text="💰 Назначить цену", callback_data=f"set_price_{order_id}")
        keyboard.button(text="❌ Удалить заказ", callback_data=f"delete_order_{order_id}")
    keyboard.button(text="🔙 Назад к заказам", callback_data="admin_orders")
    keyboard.adjust(1)
    
    await message.answer(text, reply_markup=keyboard.as_markup())

# ===================== АДМИН: УДАЛЕНИЕ ЗАКАЗА =====================
@dp.callback_query(F.data.startswith("delete_order_"))
async def cb_delete_order(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    order_id = int(callback.data.split("_")[2])
    order = get_order(order_id)
    if not order:
        await callback.answer("❌ Заказ не найден", show_alert=True)
        return
    
    delete_order(order_id)
    add_admin_log(callback.from_user.id, "delete_order", f"Удалил заказ #{order_id}")
    
    await callback.message.edit_text(
        f"✅ Заказ #{order_id} успешно удалён!",
        reply_markup=admin_menu_keyboard()
    )
    await callback.answer()

# ===================== АДМИН: ПОДТВЕРЖДЕНИЕ ОПЛАТЫ =====================
@dp.callback_query(F.data.startswith("confirm_payment_"))
async def cb_confirm_payment(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    order_id = int(callback.data.split("_")[2])
    order = get_order(order_id)
    if not order:
        await callback.answer("❌ Заказ не найден", show_alert=True)
        return
    
    if order[4] != "pending":
        await callback.answer("❌ Заказ уже оплачен или отменён", show_alert=True)
        return
    
    user_id, service, price = order[1], order[2], order[3]
    admin_price = order[7]
    final_price = admin_price if admin_price > 0 else price
    
    update_order_status(order_id, "paid")
    add_admin_log(callback.from_user.id, "confirm_payment", f"Подтвердил оплату заказа #{order_id} ({final_price} руб.)")
    
    try:
        await bot.send_message(
            user_id,
            f"✅ *Оплата подтверждена!*\n\n"
            f"Заказ #{order_id}: {service}\n"
            f"Сумма: {final_price} руб.\n\n"
            f"Спасибо за оплату! Мы свяжемся с вами в ближайшее время.\n"
            f"Диспетчер: {DISPATCHER_USERNAME}"
        )
    except:
        pass
    
    await callback.answer("✅ Оплата подтверждена!", show_alert=True)
    
    # Показываем обновлённый заказ
    await show_order_detail(callback.message, order_id, is_callback=True)

async def show_order_detail(target, order_id: int, is_callback: bool = False):
    """Показывает детали заказа (для администратора)."""
    order = get_order(order_id)
    if not order:
        if is_callback:
            await target.answer("❌ Заказ не найден")
        else:
            await target.answer("❌ Заказ не найден")
        return
    
    order_id, user_id, service, price, status, created_at, paid_at, admin_price, admin_note, order_code = order
    status_text = "✅ Оплачен" if status == "paid" else "⏳ Ожидает оплаты" if status == "pending" else "❌ Отменён"
    final_price = admin_price if admin_price > 0 else price
    name = f"ID: {user_id}"
    display_code = order_code or f"#{order_id}"
    
    created = datetime.fromisoformat(created_at).strftime("%d.%m.%Y %H:%M")
    paid = datetime.fromisoformat(paid_at).strftime("%d.%m.%Y %H:%M") if paid_at else "Не оплачен"
    
    text = (
        f"📦 *Информация о заказе {display_code}*\n\n"
        f"👤 Пользователь: {name}\n"
        f"📝 Услуга: {service}\n"
        f"💰 Изначальная цена: {price} руб.\n"
        f"💰 Назначенная цена: {final_price} руб.\n"
        f"📊 Статус: {status_text}\n"
        f"📅 Создан: {created}\n"
        f"✅ Оплачен: {paid}\n"
    )
    
    if admin_note:
        text += f"📌 Заметка: {admin_note}\n"
    
    if is_callback:
        await target.edit_text(
            text,
            reply_markup=order_detail_keyboard(order_id, status)
        )
    else:
        await target.answer(
            text,
            reply_markup=order_detail_keyboard(order_id, status)
        )

# ===================== ПОЛЬЗОВАТЕЛЬ: ОТМЕНА ЗАКАЗА =====================
@dp.callback_query(F.data.startswith("cancel_order_"))
async def cb_cancel_order(callback: CallbackQuery):
    order_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    
    order = get_order(order_id)
    if not order:
        await callback.answer("❌ Заказ не найден", show_alert=True)
        return
    
    if order[1] != user_id:
        await callback.answer("⛔ Это не ваш заказ", show_alert=True)
        return
    
    if order[4] == "paid":
        await callback.answer("❌ Оплаченный заказ нельзя отменить", show_alert=True)
        return
    
    if order[4] == "cancelled":
        await callback.answer("❌ Заказ уже отменён", show_alert=True)
        return
    
    update_order_status(order_id, "cancelled")
    add_user_log(user_id, "cancel_order", f"Отменил заказ #{order_id}")
    
    await callback.message.edit_text(
        f"✅ Заказ #{order_id} успешно отменён!\n\n"
        f"Если вы передумали, вы можете создать новый заказ.",
        reply_markup=back_to_main_keyboard()
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("refresh_order_"))
async def cb_refresh_order(callback: CallbackQuery):
    order_id = int(callback.data.split("_")[2])
    await cb_user_order_detail(callback)

# ===================== ПОЛЬЗОВАТЕЛЬ: ДЕТАЛИ ЗАКАЗА =====================
@dp.callback_query(F.data.startswith("my_order_"))
async def cb_user_order_detail(callback: CallbackQuery):
    order_id = int(callback.data.split("_")[2])
    user_id = callback.from_user.id
    
    order = get_order(order_id)
    if not order:
        await callback.answer("❌ Заказ не найден", show_alert=True)
        return
    
    if order[1] != user_id:
        await callback.answer("⛔ Это не ваш заказ", show_alert=True)
        return
    
    order_id, user_id, service, price, status, created_at, paid_at, admin_price, admin_note, order_code = order
    status_text = "✅ Оплачен" if status == "paid" else "⏳ Ожидает оплаты" if status == "pending" else "❌ Отменён"
    final_price = admin_price if admin_price > 0 else price
    display_code = order_code or f"#{order_id}"
    
    created = datetime.fromisoformat(created_at).strftime("%d.%m.%Y %H:%M")
    paid = datetime.fromisoformat(paid_at).strftime("%d.%m.%Y %H:%M") if paid_at else "Не оплачен"
    
    text = (
        f"📦 *Заказ {display_code}*\n\n"
        f"📝 Услуга: {service}\n"
        f"💰 Цена: {final_price} руб.\n"
        f"📊 Статус: {status_text}\n"
        f"📅 Создан: {created}\n"
        f"✅ Оплачен: {paid}\n"
    )
    
    if admin_note:
        text += f"📌 Заметка: {admin_note}\n"
    
    await update_message(callback, text, order_user_keyboard(order_id, status))
    await callback.answer()

# ===================== АДМИН: ЛОГИ =====================
@dp.callback_query(F.data == "admin_logs")
async def cb_admin_logs(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    add_admin_log(callback.from_user.id, "view_logs", "Просмотрел логи")
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT admin_id, action, details, timestamp FROM admin_logs ORDER BY timestamp DESC LIMIT 20")
    logs = cur.fetchall()
    conn.close()
    if not logs:
        text = "📋 Логов пока нет."
    else:
        text = "📋 *Последние действия администраторов:*\n\n"
        for admin_id, action, details, timestamp in logs:
            time_str = datetime.fromisoformat(timestamp).strftime("%d.%m %H:%M")
            text += f"• {time_str} - {action} {details}\n"
    await update_message(callback, text, admin_menu_keyboard())
    await callback.answer()

# ===================== ОСТАЛЬНЫЕ CALLBACK =====================
@dp.callback_query(F.data == "main_menu")
async def cb_main_menu(callback: CallbackQuery):
    user_id = callback.from_user.id
    update_user_action(user_id, "main_menu")
    add_user_log(user_id, "main_menu", "Вернулся в главное меню")
    text = "🎵 Sopranidi Corp.\n\nВыберите услугу ниже 👇"
    if callback.message.photo:
        try:
            await callback.message.delete()
        except:
            pass
        await callback.message.answer(text, reply_markup=main_menu_keyboard())
    else:
        await update_message(callback, text, main_menu_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "admin_menu")
async def cb_admin_menu(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа")
        return
    stats = get_stats()
    text = (
        "🔐 *Админ-панель Sopranidi Corp.*\n\n"
        f"👥 Пользователей: *{stats['users']}*\n"
        f"📦 Всего заказов: *{stats['total_orders']}*\n"
        f"✅ Оплаченных: *{stats['paid_orders']}*\n"
        f"⏳ Ожидают оплаты: *{stats['pending_orders']}*\n"
        f"❌ Отменённых: *{stats['cancelled_orders']}*\n"
        f"💰 Доход: *{stats['income']} руб.*\n\n"
        f"📌 Диспетчер: {DISPATCHER_USERNAME}\n"
        f"👤 CEO: {CEO_USERNAME}"
    )
    await update_message(callback, text, admin_menu_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "buy")
async def cb_buy(callback: CallbackQuery):
    user_id = callback.from_user.id
    update_user_action(user_id, "buy")
    add_user_log(user_id, "buy", "Открыл выбор услуг")
    await update_message(callback, "📚 *Выберите тип работы:*", services_keyboard())
    await callback.answer()

@dp.callback_query(F.data.startswith("service_"))
async def cb_service(callback: CallbackQuery):
    user_id = callback.from_user.id

    service_map = {
        "service_coursework": ("Курсовая работа", 2500, "от 2500 ₽"),
        "service_project": ("Школьный проект", 1500, "от 1500 ₽"),
        "service_practice": ("Отчёт по практике", 3000, "от 3000 ₽"),
    }

    service_type, base_price, price_text = service_map.get(callback.data, ("Неизвестно", 0, "0 ₽"))
    if base_price == 0:
        await callback.answer("Ошибка выбора", show_alert=True)
        return

    order_id, order_code = add_order(user_id, service_type, base_price)
    update_user_action(user_id, f"order_{service_type}")
    add_user_log(user_id, "create_order", f"Заказ {order_code}: {service_type} ({price_text})")

    text = (
        f"✅ *Вы выбрали: {service_type}*\n\n"
        f"💰 Базовая стоимость: *{price_text}*\n\n"
        f"📌 *Важно!* Окончательная цена зависит от:\n"
        f"• Тема работы\n"
        f"• Сроки выполнения\n"
        f"• Сложность и объём\n\n"
        f"📞 Для уточнения стоимости и оформления заказа свяжитесь с диспетчером:\n"
        f"{DISPATCHER_USERNAME}\n"
        f"👤 Или с CEO: {CEO_USERNAME}\n\n"
        f"💬 После согласования всех деталей сообщите диспетчеру код заказа: *{order_code}*"
    )

    keyboard = InlineKeyboardBuilder()
    dispatcher_username = DISPATCHER_USERNAME.replace("@", "")
    ceo_username = CEO_USERNAME.replace("@", "")
    keyboard.button(text="📞 Связаться с диспетчером", url=f"https://t.me/{dispatcher_username}")
    keyboard.button(text="👤 Связаться с CEO", url=f"https://t.me/{ceo_username}")
    keyboard.button(text="📋 Мои заказы", callback_data="my_orders")
    keyboard.button(text="🔙 Назад", callback_data="main_menu")
    keyboard.adjust(1)

    await update_message(callback, text, keyboard.as_markup())
    await callback.answer()

@dp.callback_query(F.data == "examples")
async def cb_examples(callback: CallbackQuery):
    user_id = callback.from_user.id
    update_user_action(user_id, "examples")
    add_user_log(user_id, "examples", "Открыл примеры работ")
    builder = InlineKeyboardBuilder()
    builder.button(text="📄 Динамика цен на квартиры", callback_data="example_1")
    builder.button(text="💧 Экономия воды", callback_data="example_2")
    builder.button(text="🎱 План открытия бильярдной", callback_data="example_3")
    builder.button(text="🔙 Назад", callback_data="main_menu")
    builder.adjust(1)
    await update_message(callback, "📂 *Примеры выполненных работ*\n\nВыберите работу:", builder.as_markup())
    await callback.answer()

@dp.callback_query(F.data.startswith("example_"))
async def send_example(callback: CallbackQuery):
    user_id = callback.from_user.id

    example_map = {
        "example_1": ("динамика цен на квартиры 2023-2026годов.pdf", "Динамика цен на квартиры 2023-2026"),
        "example_2": ("экономия воды.pdf", "Экономия воды"),
        "example_3": ("План открытия бильярдной.pdf", "План открытия бильярдной"),
    }

    file_name, title = example_map.get(callback.data, (None, None))
    if not file_name:
        await callback.answer("❌ Пример не найден", show_alert=True)
        return

    add_user_log(user_id, "download_example", f"Скачал: {title}")

    try:
        file_path = f"examples/{file_name}"

        if not os.path.exists(file_path):
            if os.path.exists("examples"):
                pdf_files = [f for f in os.listdir("examples") if f.endswith('.pdf')]
                if pdf_files:
                    file_path = f"examples/{pdf_files[0]}"
                    logging.info(f"Используем файл: {pdf_files[0]}")
                else:
                    await callback.answer("❌ Нет PDF-файлов", show_alert=True)
                    return
            else:
                await callback.answer("❌ Папка examples не найдена", show_alert=True)
                return

        file = FSInputFile(file_path)
        await callback.message.answer_document(
            document=file,
            caption=f"📄 {title}\n\n✅ Файл загружен!"
        )
        await callback.answer("✅ Файл отправлен!")

    except Exception as e:
        logging.error(f"Ошибка отправки: {e}")
        await callback.answer("❌ Ошибка при отправке", show_alert=True)

@dp.callback_query(F.data == "support")
async def cb_support(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    update_user_action(user_id, "support")
    add_user_log(user_id, "support", "Открыл поддержку")
    text = (
        "📞 *Техническая поддержка*\n\n"
        "Напишите ваше сообщение, и я перешлю его автору.\n"
        "Автор ответит вам в этом же чате.\n\n"
        "Также вы можете связаться с диспетчером:\n"
        f"{DISPATCHER_USERNAME}\n"
        f"👤 Или с CEO: {CEO_USERNAME}\n\n"
        "Для выхода из режима поддержки отправьте /cancel."
    )
    await update_message(callback, text, back_to_main_keyboard())
    await state.set_state(SupportState.waiting_for_message)
    await callback.answer()

@dp.callback_query(F.data == "my_orders")
async def cb_my_orders(callback: CallbackQuery):
    user_id = callback.from_user.id
    update_user_action(user_id, "my_orders")
    add_user_log(user_id, "my_orders", "Просмотрел свои заказы")
    
    orders = get_user_orders(user_id)
    if not orders:
        text = "📋 У вас пока нет заказов."
        await update_message(callback, text, back_to_main_keyboard())
        await callback.answer()
        return
    
    text = "📋 *Ваши заказы:*\n\n"
    for order in orders:
        order_id, service, price, status, created_at, admin_price, order_code = order
        status_text = {"pending": "⏳ Ожидает оплаты", "paid": "✅ Оплачен", "cancelled": "❌ Отменён"}.get(status, status)
        final_price = admin_price if admin_price > 0 else price
        created = datetime.fromisoformat(created_at).strftime("%d.%m.%Y")
        display_code = order_code or f"#{order_id}"
        text += f"• {display_code}: {service} - {final_price} руб. ({status_text}) [{created}]\n"
    
    builder = InlineKeyboardBuilder()
    for order in orders:
        order_id, service, price, status, created_at, admin_price, order_code = order
        display_code = order_code or f"#{order_id}"
        builder.button(text=f"📦 {display_code} - {service[:15]}", callback_data=f"my_order_{order_id}")
    builder.button(text="🔙 Назад", callback_data="main_menu")
    builder.adjust(1)
    
    await update_message(callback, text, builder.as_markup())
    await callback.answer()

# ===================== ПОДДЕРЖКА (FSM) =====================
@dp.message(SupportState.waiting_for_message)
async def support_send_message(message: Message, state: FSMContext):
    if message.text and message.text.startswith("/"):
        await state.clear()
        return
    user = message.from_user
    add_user_log(user.id, "support_message", f"Отправил сообщение: {message.text[:50]}")
    text = f"📩 *Сообщение от пользователя* @{user.username or 'без username'} (ID: {user.id})\n\n{message.text}"
    try:
        for admin_id in ADMINS:
            await bot.send_message(admin_id, text)
        if message.photo:
            file_id = message.photo[-1].file_id
            for admin_id in ADMINS:
                await bot.send_photo(admin_id, file_id, caption=f"Фото от @{user.username}")
        elif message.document:
            for admin_id in ADMINS:
                await bot.send_document(admin_id, message.document.file_id, caption=f"Документ от @{user.username}")
        await message.answer("✅ Ваше сообщение отправлено автору. Он ответит вам здесь.", reply_markup=back_to_main_keyboard())
    except Exception as e:
        logging.error(f"Ошибка пересылки: {e}")
        await message.answer("❌ Не удалось отправить сообщение. Попробуйте позже.")
    await state.clear()

@dp.message(StateFilter(SupportState.waiting_for_message), F.text == "/cancel")
async def support_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Режим поддержки отменён.", reply_markup=main_menu_keyboard())

# ===================== РАССЫЛКА (FSM) =====================
@dp.message(AdminBroadcastState.waiting_for_message)
async def broadcast_send(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ У вас нет прав.")
        await state.clear()
        return
    users = get_all_users()
    sent = 0
    for uid in users:
        try:
            await bot.send_message(uid, message.text)
            sent += 1
            await asyncio.sleep(0.1)
        except:
            pass
    add_admin_log(message.from_user.id, "broadcast", f"Отправил рассылку {sent} пользователям")
    await message.answer(f"✅ Рассылка выполнена. Отправлено {sent} пользователям.")
    await state.clear()

# ===================== ЗАПУСК БОТА =====================
async def main():
    init_db()
    logging.info("🚀 Бот Sopranidi Corp. запущен!")
    logging.info(f"📌 Диспетчер: {DISPATCHER_USERNAME}")
    logging.info(f"👤 CEO: {CEO_USERNAME}")
    logging.info(f"👥 Администраторы: {len(ADMINS)}")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
