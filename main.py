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
CHANNEL_LINK = "https://t.me/sopranidi_corporation"
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
    
    # Таблица заказов
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='orders'")
    table_exists = cur.fetchone()
    
    if table_exists:
        cur.execute("PRAGMA table_info(orders)")
        columns = [col[1] for col in cur.fetchall()]
        
        if "order_code" not in columns:
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
            
            cur.execute("""
                INSERT INTO orders_new (order_id, user_id, service, price, status, created_at, paid_at, admin_price, admin_note)
                SELECT order_id, user_id, service, price, status, created_at, paid_at, admin_price, admin_note
                FROM orders
            """)
            
            cur.execute("DROP TABLE orders")
            cur.execute("ALTER TABLE orders_new RENAME TO orders")
            logging.info("✅ Добавлена колонка order_code")
        
        cur.execute("PRAGMA table_info(orders)")
        columns = [col[1] for col in cur.fetchall()]
        if "admin_price" not in columns:
            cur.execute("ALTER TABLE orders ADD COLUMN admin_price INTEGER DEFAULT 0")
        if "admin_note" not in columns:
            cur.execute("ALTER TABLE orders ADD COLUMN admin_note TEXT DEFAULT ''")
        
        # Добавляем колонку для оценки
        if "rating" not in columns:
            cur.execute("ALTER TABLE orders ADD COLUMN rating INTEGER DEFAULT 0")
        if "review" not in columns:
            cur.execute("ALTER TABLE orders ADD COLUMN review TEXT DEFAULT ''")
        if "file_id" not in columns:
            cur.execute("ALTER TABLE orders ADD COLUMN file_id TEXT DEFAULT ''")
            
    else:
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
                rating INTEGER DEFAULT 0,
                review TEXT DEFAULT '',
                file_id TEXT DEFAULT '',
                FOREIGN KEY(user_id) REFERENCES users(user_id)
            )
        """)
        logging.info("✅ Таблица orders создана")
    
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

def update_order_review(order_id: int, rating: int, review: str):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "UPDATE orders SET rating = ?, review = ? WHERE order_id = ?",
        (rating, review, order_id)
    )
    conn.commit()
    conn.close()

def update_order_file(order_id: int, file_id: str):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "UPDATE orders SET file_id = ? WHERE order_id = ?",
        (file_id, order_id)
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
        SELECT order_id, user_id, service, price, status, created_at, paid_at, admin_price, admin_note, order_code, rating, review, file_id
        FROM orders WHERE order_id = ?
    """, (order_id,))
    row = cur.fetchone()
    conn.close()
    return row

def get_user_orders(user_id: int):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "SELECT order_id, service, price, status, created_at, admin_price, order_code, rating, review FROM orders WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,)
    )
    rows = cur.fetchall()
    conn.close()
    return rows

def get_user_stats(user_id: int):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM orders WHERE user_id = ?", (user_id,))
    total_orders = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM orders WHERE user_id = ? AND status='paid'", (user_id,))
    paid_orders = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM orders WHERE user_id = ? AND status='in_progress'", (user_id,))
    in_progress = cur.fetchone()[0]
    cur.execute("SELECT SUM(price) FROM orders WHERE user_id = ? AND status='paid'", (user_id,))
    total_spent = cur.fetchone()[0] or 0
    conn.close()
    return {
        "total_orders": total_orders,
        "paid_orders": paid_orders,
        "in_progress": in_progress,
        "total_spent": total_spent
    }

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
        SELECT o.order_id, o.user_id, u.username, o.service, o.price, o.status, o.created_at, o.paid_at, o.admin_price, o.admin_note, o.order_code, o.rating, o.review
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

def get_all_reviews():
    """Возвращает все отзывы с информацией о пользователях."""
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT o.order_code, o.service, o.rating, o.review, u.username, u.first_name, o.created_at
        FROM orders o
        LEFT JOIN users u ON o.user_id = u.user_id
        WHERE o.rating > 0 AND o.review != ''
        ORDER BY o.created_at DESC
    """)
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
    cur.execute("SELECT COUNT(*) FROM orders WHERE status='in_progress'")
    in_progress = cur.fetchone()[0]
    cur.execute("SELECT AVG(rating) FROM orders WHERE rating > 0")
    avg_rating = cur.fetchone()[0] or 0
    conn.close()
    return {
        "users": user_count,
        "total_orders": total_orders,
        "paid_orders": paid_orders,
        "pending_orders": pending_orders,
        "cancelled_orders": cancelled_orders,
        "in_progress": in_progress,
        "income": total_income,
        "avg_rating": round(avg_rating, 1)
    }

# ===================== КЛАВИАТУРЫ =====================
def main_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📚 Заказать работу", callback_data="buy")
    builder.button(text="📂 Примеры работ", callback_data="examples")
    builder.button(text="📞 Поддержка", callback_data="support")
    builder.button(text="📋 Мои заказы", callback_data="my_orders")
    builder.button(text="👤 Профиль", callback_data="profile")
    builder.button(text="⭐ Отзывы", callback_data="view_reviews")
    builder.button(text="ℹ️ О нас", callback_data="about")
    builder.adjust(2, 2, 2, 1)
    return builder.as_markup()

def admin_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Статистика", callback_data="admin_stats")
    builder.button(text="👥 Пользователи", callback_data="admin_users")
    builder.button(text="📦 Заказы", callback_data="admin_orders")
    builder.button(text="⭐ Управление отзывами", callback_data="admin_reviews")
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
    builder.button(text="📄 Доклад (от 500₽)", callback_data="service_report")
    builder.button(text="📽️ Презентация (от 300₽)", callback_data="service_presentation")
    builder.button(text="🗣️ Защитное слово (от 100₽)", callback_data="service_defense")
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
        order_id, user_id, username, service, price, status, _, _, admin_price, _, order_code, rating, _ = order
        status_emoji = "✅" if status == "paid" else "⏳" if status == "pending" else "🔧" if status == "in_progress" else "❌"
        final_price = admin_price if admin_price > 0 else price
        display_code = order_code or f"#{order_id}"
        display_name = username or f"ID:{user_id}"
        rating_str = f"⭐{rating}" if rating > 0 else ""
        builder.button(
            text=f"{status_emoji} {display_code} - {display_name} ({final_price}₽) {rating_str}",
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

def reviews_keyboard(reviews: list, page: int = 0) -> InlineKeyboardMarkup:
    """Клавиатура для списка отзывов (для админа)."""
    builder = InlineKeyboardBuilder()
    start = page * 10
    end = start + 10
    page_reviews = reviews[start:end]
    for review in page_reviews:
        order_code, service, rating, review_text, username, first_name, created_at = review
        name = username or first_name or "Аноним"
        display_text = f"{order_code} - {service[:10]} ⭐{rating} - {name[:10]}"
        builder.button(
            text=display_text,
            callback_data=f"review_detail_{order_code}"
        )
    nav_buttons = []
    if page > 0:
        nav_buttons.append(("◀️ Назад", f"reviews_page_{page-1}"))
    if end < len(reviews):
        nav_buttons.append(("Вперед ▶️", f"reviews_page_{page+1}"))
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
        builder.button(text="🔧 В работу", callback_data=f"start_work_{order_id}")
        builder.button(text="❌ Удалить заказ", callback_data=f"delete_order_{order_id}")
    elif status == "in_progress":
        builder.button(text="✅ Завершить работу", callback_data=f"complete_work_{order_id}")
        builder.button(text="❌ Удалить заказ", callback_data=f"delete_order_{order_id}")
    elif status == "paid":
        builder.button(text="📎 Прикрепить файл", callback_data=f"attach_file_{order_id}")
        builder.button(text="❌ Удалить заказ", callback_data=f"delete_order_{order_id}")
    
    builder.button(text="🔙 Назад к заказам", callback_data="admin_orders")
    builder.adjust(1)
    return builder.as_markup()

def order_user_keyboard(order_id: int, status: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    if status == "pending":
        builder.button(text="❌ Отменить заказ", callback_data=f"cancel_order_{order_id}")
    
    if status == "paid":
        builder.button(text="⭐ Оставить отзыв", callback_data=f"review_order_{order_id}")
    
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

class ReviewState(StatesGroup):
    waiting_for_rating = State()
    waiting_for_review = State()

class AttachFileState(StatesGroup):
    waiting_for_file = State()

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
        "🎵 Добро пожаловать в Sopranidi Corporation!\n\n"
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
        "/my_orders - мои заказы\n"
        "/profile - мой профиль\n\n"
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
        "🔐 *Админ-панель Sopranidi Corporation*\n\n"
        f"👥 Пользователей: *{stats['users']}*\n"
        f"📦 Всего заказов: *{stats['total_orders']}*\n"
        f"✅ Оплаченных: *{stats['paid_orders']}*\n"
        f"⏳ Ожидают оплаты: *{stats['pending_orders']}*\n"
        f"🔧 В работе: *{stats['in_progress']}*\n"
        f"❌ Отменённых: *{stats['cancelled_orders']}*\n"
        f"💰 Доход: *{stats['income']} руб.*\n"
        f"⭐ Средняя оценка: *{stats['avg_rating']}*\n\n"
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
        f"🔧 В работе: *{stats['in_progress']}*\n"
        f"❌ Отменено: *{stats['cancelled_orders']}*\n"
        f"💰 Доход: *{stats['income']} руб.*\n"
        f"⭐ Средняя оценка: *{stats['avg_rating']}*"
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

# ===================== ПРОСМОТР ОТЗЫВОВ =====================
@dp.callback_query(F.data == "view_reviews")
async def cb_view_reviews(callback: CallbackQuery):
    user_id = callback.from_user.id
    update_user_action(user_id, "view_reviews")
    add_user_log(user_id, "view_reviews", "Просмотрел отзывы")
    
    reviews = get_all_reviews()
    if not reviews:
        text = "⭐ *Отзывы*\n\nПока нет ни одного отзыва. Будьте первым!"
        await update_message(callback, text, back_to_main_keyboard())
        await callback.answer()
        return
    
    text = "⭐ *Отзывы наших клиентов:*\n\n"
    for review in reviews[:10]:
        order_code, service, rating, review_text, username, first_name, created_at = review
        name = username or first_name or "Аноним"
        created = datetime.fromisoformat(created_at).strftime("%d.%m.%Y")
        stars = "⭐" * rating + "☆" * (5 - rating)
        text += f"📌 *{order_code}* - {service}\n"
        text += f"👤 {name}\n"
        text += f"{stars} {rating}/5\n"
        if review_text:
            text += f"📝 \"{review_text[:100]}{'...' if len(review_text) > 100 else ''}\"\n"
        text += f"📅 {created}\n\n"
    
    if len(reviews) > 10:
        text += f"📌 *Показано 10 из {len(reviews)} отзывов*"
    
    await update_message(callback, text, back_to_main_keyboard())
    await callback.answer()

# ===================== ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ =====================
@dp.callback_query(F.data == "profile")
async def cb_profile(callback: CallbackQuery):
    user_id = callback.from_user.id
    update_user_action(user_id, "profile")
    add_user_log(user_id, "profile", "Просмотрел профиль")
    
    stats = get_user_stats(user_id)
    
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT username, first_name, last_name, reg_date FROM users WHERE user_id = ?", (user_id,))
    user_data = cur.fetchone()
    conn.close()
    
    if user_data:
        username, first_name, last_name, reg_date = user_data
        name = f"{first_name} {last_name or ''}".strip() or "Пользователь"
        username_str = f"@{username}" if username else "Не указан"
        reg_date_str = datetime.fromisoformat(reg_date).strftime("%d.%m.%Y")
        
        text = (
            f"👤 *Ваш профиль*\n\n"
            f"👤 Имя: {name}\n"
            f"📌 Username: {username_str}\n"
            f"📅 Регистрация: {reg_date_str}\n\n"
            f"📊 *Статистика:*\n"
            f"📦 Всего заказов: {stats['total_orders']}\n"
            f"✅ Оплачено: {stats['paid_orders']}\n"
            f"🔧 В работе: {stats['in_progress']}\n"
            f"💰 Всего потрачено: {stats['total_spent']} руб."
        )
    else:
        text = "❌ Профиль не найден."
    
    await update_message(callback, text, back_to_main_keyboard())
    await callback.answer()

# ===================== О КОМПАНИИ =====================
@dp.callback_query(F.data == "about")
async def cb_about(callback: CallbackQuery):
    user_id = callback.from_user.id
    update_user_action(user_id, "about")
    add_user_log(user_id, "about", "Открыл информацию о компании")
    
    text = (
        "ℹ️ *О компании Sopranidi Corporation*\n\n"
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
        f"🔧 В работе: *{stats['in_progress']}*\n"
        f"❌ Отменённых: *{stats['cancelled_orders']}*\n"
        f"💰 Доход: *{stats['income']} руб.*\n"
        f"⭐ Средняя оценка: *{stats['avg_rating']}*"
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

# ===================== АДМИН: УПРАВЛЕНИЕ ОТЗЫВАМИ =====================
@dp.callback_query(F.data == "admin_reviews")
async def cb_admin_reviews(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    reviews = get_all_reviews()
    add_admin_log(callback.from_user.id, "view_reviews", "Просмотрел список отзывов")
    
    if not reviews:
        await update_message(callback, "⭐ Отзывов пока нет.", admin_menu_keyboard())
        await callback.answer()
        return
    
    await update_message(callback, "⭐ *Управление отзывами*\n\nВыберите отзыв для управления:", reviews_keyboard(reviews, 0))
    await callback.answer()

@dp.callback_query(F.data.startswith("reviews_page_"))
async def cb_reviews_page(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    page = int(callback.data.split("_")[2])
    reviews = get_all_reviews()
    await callback.message.edit_reply_markup(reply_markup=reviews_keyboard(reviews, page))
    await callback.answer()

@dp.callback_query(F.data.startswith("review_detail_"))
async def cb_review_detail(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    order_code = callback.data.split("_")[2]
    
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT o.order_code, o.service, o.rating, o.review, u.username, u.first_name, o.created_at, o.order_id
        FROM orders o
        LEFT JOIN users u ON o.user_id = u.user_id
        WHERE o.order_code = ? AND o.rating > 0
    """, (order_code,))
    review = cur.fetchone()
    conn.close()
    
    if not review:
        await callback.answer("❌ Отзыв не найден", show_alert=True)
        return
    
    order_code, service, rating, review_text, username, first_name, created_at, order_id = review
    name = username or first_name or "Аноним"
    created = datetime.fromisoformat(created_at).strftime("%d.%m.%Y %H:%M")
    stars = "⭐" * rating + "☆" * (5 - rating)
    
    text = (
        f"⭐ *Детали отзыва*\n\n"
        f"📌 Заказ: *{order_code}*\n"
        f"📝 Услуга: {service}\n"
        f"👤 Автор: {name}\n"
        f"{stars} {rating}/5\n"
        f"📝 Отзыв: {review_text or 'Без текста'}\n"
        f"📅 Дата: {created}\n"
    )
    
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="❌ Удалить отзыв", callback_data=f"delete_review_{order_code}")
    keyboard.button(text="🔙 Назад", callback_data="admin_reviews")
    keyboard.adjust(1)
    
    await update_message(callback, text, keyboard.as_markup())
    await callback.answer()

@dp.callback_query(F.data.startswith("delete_review_"))
async def cb_delete_review_confirm(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    order_code = callback.data.split("_")[2]
    
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT order_id, service, rating, review FROM orders WHERE order_code = ?", (order_code,))
    review = cur.fetchone()
    conn.close()
    
    if not review:
        await callback.answer("❌ Отзыв не найден", show_alert=True)
        return
    
    order_id, service, rating, review_text = review
    
    text = (
        f"⚠️ *Вы уверены, что хотите удалить этот отзыв?*\n\n"
        f"📌 Заказ: *{order_code}*\n"
        f"📝 Услуга: {service}\n"
        f"⭐ Оценка: {rating}/5\n"
        f"📝 Отзыв: {review_text or 'Без текста'}\n\n"
        f"Это действие невозможно отменить!"
    )
    
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="✅ Да, удалить", callback_data=f"confirm_delete_review_{order_code}")
    keyboard.button(text="❌ Отмена", callback_data=f"review_detail_{order_code}")
    keyboard.adjust(1)
    
    await update_message(callback, text, keyboard.as_markup())
    await callback.answer()

@dp.callback_query(F.data.startswith("confirm_delete_review_"))
async def cb_confirm_delete_review(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    # Исправлено: было [2], стало [3]
    order_code = callback.data.split("_")[3]
    
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("UPDATE orders SET rating = 0, review = '' WHERE order_code = ?", (order_code,))
    conn.commit()
    conn.close()
    
    add_admin_log(callback.from_user.id, "delete_review", f"Удалил отзыв к заказу {order_code}")
    
    await callback.message.edit_text(
        f"✅ Отзыв к заказу *{order_code}* успешно удалён!",
        parse_mode="Markdown",
        reply_markup=admin_menu_keyboard()
    )
    await callback.answer()

# ===================== СНАЧАЛА БОЛЕЕ КОНКРЕТНЫЙ ОБРАБОТЧИК (user_orders_) =====================
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
            order_id, service, price, status, created_at, admin_price, order_code, rating, _ = order
            status_text = "✅ Оплачен" if status == "paid" else "⏳ Ожидает" if status == "pending" else "🔧 В работе" if status == "in_progress" else "❌ Отменён"
            final_price = admin_price if admin_price > 0 else price
            created = datetime.fromisoformat(created_at).strftime("%d.%m.%Y")
            display_code = order_code or f"#{order_id}"
            rating_str = f"⭐{rating}" if rating > 0 else ""
            text += f"• {display_code}: {service} - {final_price} руб. ({status_text}) [{created}] {rating_str}\n"
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🔙 Назад", callback_data=f"user_{user_id}")
    keyboard.adjust(1)
    await update_message(callback, text, keyboard.as_markup())
    await callback.answer()

# ===================== ПОТОМ БОЛЕЕ ОБЩИЙ ОБРАБОТЧИК (user_) =====================
@dp.callback_query(F.data.startswith("user_"))
async def cb_user_detail(callback: CallbackQuery):
    # Пропускаем user_orders_ (они обрабатываются выше)
    if callback.data.startswith("user_orders_"):
        return
    
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    try:
        user_id = int(callback.data.split("_")[1])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка", show_alert=True)
        return
    
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
    user_stats = get_user_stats(user_id)
    text = (
        f"👤 *Информация о пользователе*\n\n"
        f"🆔 ID: `{user_id}`\n"
        f"👤 Имя: {first_name} {last_name or ''}\n"
        f"📌 Username: @{username or 'Не указан'}\n"
        f"📅 Регистрация: {reg_date[:10]}\n"
        f"📌 Последнее действие: {last_action or 'Нет'}\n\n"
        f"📦 Заказов: {user_stats['total_orders']}\n"
        f"✅ Оплачено: {user_stats['paid_orders']}\n"
        f"🔧 В работе: {user_stats['in_progress']}\n"
        f"💰 Потрачено: {user_stats['total_spent']} руб.\n\n"
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
    
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT username, first_name FROM users WHERE user_id = ?", (order[1],))
    user_data = cur.fetchone()
    conn.close()
    
    order_id, user_id, service, price, status, created_at, paid_at, admin_price, admin_note, order_code, rating, review, file_id = order
    status_text = "✅ Оплачен" if status == "paid" else "⏳ Ожидает оплаты" if status == "pending" else "🔧 В работе" if status == "in_progress" else "❌ Отменён"
    final_price = admin_price if admin_price > 0 else price
    
    if user_data:
        username, first_name = user_data
        if username:
            user_display = f"@{username}"
        else:
            user_display = first_name or str(user_id)
    else:
        user_display = f"ID: {user_id}"
    
    display_code = order_code or f"#{order_id}"
    
    created = datetime.fromisoformat(created_at).strftime("%d.%m.%Y %H:%M")
    paid = datetime.fromisoformat(paid_at).strftime("%d.%m.%Y %H:%M") if paid_at else "Не оплачен"
    
    text = (
        f"📦 *Информация о заказе {display_code}*\n\n"
        f"👤 Пользователь: {user_display} (ID: {user_id})\n"
        f"📝 Услуга: {service}\n"
        f"💰 Изначальная цена: {price} руб.\n"
        f"💰 Назначенная цена: {final_price} руб.\n"
        f"📊 Статус: {status_text}\n"
        f"📅 Создан: {created}\n"
        f"✅ Оплачен: {paid}\n"
    )
    
    if rating > 0:
        text += f"⭐ Оценка: {rating}/5\n"
        if review:
            text += f"📝 Отзыв: {review}\n"
    
    if file_id:
        text += f"📎 Прикреплён файл: ✅\n"
    
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
        f"💰 *Назначение цены для заказа {order[9] or f'#{order_id}'}*\n\n"
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
        
        order = get_order(order_id)
        order_code = order[9] if order else f"#{order_id}"
        
        update_order_price(order_id, new_price, "")
        add_admin_log(message.from_user.id, "set_price", f"Назначил цену {new_price} руб. для заказа {order_code}")
        
        await message.answer(f"✅ Цена для заказа {order_code} успешно обновлена на *{new_price} руб.*", parse_mode="Markdown")
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
    
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT username, first_name FROM users WHERE user_id = ?", (order[1],))
    user_data = cur.fetchone()
    conn.close()
    
    order_id, user_id, service, price, status, created_at, paid_at, admin_price, admin_note, order_code, rating, review, file_id = order
    status_text = "✅ Оплачен" if status == "paid" else "⏳ Ожидает оплаты" if status == "pending" else "🔧 В работе" if status == "in_progress" else "❌ Отменён"
    final_price = admin_price if admin_price > 0 else price
    
    if user_data:
        username, first_name = user_data
        if username:
            user_display = f"@{username}"
        else:
            user_display = first_name or str(user_id)
    else:
        user_display = f"ID: {user_id}"
    
    display_code = order_code or f"#{order_id}"
    
    created = datetime.fromisoformat(created_at).strftime("%d.%m.%Y %H:%M")
    paid = datetime.fromisoformat(paid_at).strftime("%d.%m.%Y %H:%M") if paid_at else "Не оплачен"
    
    text = (
        f"📦 *Информация о заказе {display_code}*\n\n"
        f"👤 Пользователь: {user_display} (ID: {user_id})\n"
        f"📝 Услуга: {service}\n"
        f"💰 Изначальная цена: {price} руб.\n"
        f"💰 Назначенная цена: {final_price} руб.\n"
        f"📊 Статус: {status_text}\n"
        f"📅 Создан: {created}\n"
        f"✅ Оплачен: {paid}\n"
    )
    
    if rating > 0:
        text += f"⭐ Оценка: {rating}/5\n"
        if review:
            text += f"📝 Отзыв: {review}\n"
    
    if file_id:
        text += f"📎 Прикреплён файл: ✅\n"
    
    if admin_note:
        text += f"📌 Заметка: {admin_note}\n"
    
    keyboard = InlineKeyboardBuilder()
    if status == "pending":
        keyboard.button(text="✅ Подтвердить оплату", callback_data=f"confirm_payment_{order_id}")
        keyboard.button(text="💰 Назначить цену", callback_data=f"set_price_{order_id}")
        keyboard.button(text="🔧 В работу", callback_data=f"start_work_{order_id}")
        keyboard.button(text="❌ Удалить заказ", callback_data=f"delete_order_{order_id}")
    elif status == "in_progress":
        keyboard.button(text="✅ Завершить работу", callback_data=f"complete_work_{order_id}")
        keyboard.button(text="❌ Удалить заказ", callback_data=f"delete_order_{order_id}")
    elif status == "paid":
        keyboard.button(text="📎 Прикрепить файл", callback_data=f"attach_file_{order_id}")
        keyboard.button(text="❌ Удалить заказ", callback_data=f"delete_order_{order_id}")
    keyboard.button(text="🔙 Назад к заказам", callback_data="admin_orders")
    keyboard.adjust(1)
    
    await message.answer(text, reply_markup=keyboard.as_markup())

# ===================== АДМИН: В РАБОТУ =====================
@dp.callback_query(F.data.startswith("start_work_"))
async def cb_start_work(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    order_id = int(callback.data.split("_")[2])
    order = get_order(order_id)
    if not order:
        await callback.answer("❌ Заказ не найден", show_alert=True)
        return
    
    if order[4] != "pending":
        await callback.answer("❌ Заказ не ожидает оплаты", show_alert=True)
        return
    
    order_code = order[9] or f"#{order_id}"
    
    update_order_status(order_id, "in_progress")
    add_admin_log(callback.from_user.id, "start_work", f"Начал работу над заказом {order_code}")
    
    await callback.answer("✅ Заказ переведён в статус 'В работе'!", show_alert=True)
    
    try:
        await bot.send_message(
            order[1],
            f"🔧 *Статус заказа обновлён!*\n\n"
            f"Заказ {order_code}: {order[2]}\n"
            f"Статус: *В работе*\n\n"
            f"Наша команда уже работает над вашим заказом!"
        )
    except:
        pass
    
    await cb_order_detail_callback(callback.message, order_id)

# ===================== АДМИН: ЗАВЕРШИТЬ РАБОТУ =====================
@dp.callback_query(F.data.startswith("complete_work_"))
async def cb_complete_work(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    order_id = int(callback.data.split("_")[2])
    order = get_order(order_id)
    if not order:
        await callback.answer("❌ Заказ не найден", show_alert=True)
        return
    
    if order[4] != "in_progress":
        await callback.answer("❌ Заказ не в работе", show_alert=True)
        return
    
    order_code = order[9] or f"#{order_id}"
    
    update_order_status(order_id, "paid")
    add_admin_log(callback.from_user.id, "complete_work", f"Завершил работу над заказом {order_code}")
    
    await callback.answer("✅ Заказ переведён в статус 'Выполнен'!", show_alert=True)
    
    try:
        await bot.send_message(
            order[1],
            f"✅ *Заказ выполнен!*\n\n"
            f"Заказ {order_code}: {order[2]}\n"
            f"Статус: *Выполнен*\n\n"
            f"Спасибо за ожидание! Вы можете оставить отзыв о нашей работе."
        )
    except:
        pass
    
    await cb_order_detail_callback(callback.message, order_id)

# ===================== АДМИН: УДАЛЕНИЕ ЗАКАЗА (С ПОДТВЕРЖДЕНИЕМ) =====================
@dp.callback_query(F.data.startswith("delete_order_"))
async def cb_delete_order(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    try:
        order_id = int(callback.data.split("_")[2])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка: неверный формат данных", show_alert=True)
        return
    
    order = get_order(order_id)
    if not order:
        await callback.answer("❌ Заказ не найден", show_alert=True)
        return
    
    order_code = order[9] or f"#{order_id}"
    
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="✅ Да, удалить", callback_data=f"confirm_delete_order_{order_id}")
    keyboard.button(text="❌ Отмена", callback_data=f"order_{order_id}")
    keyboard.adjust(1)
    
    await callback.message.edit_text(
        f"⚠️ *Вы уверены, что хотите удалить заказ {order_code}?*\n\n"
        f"📝 Услуга: {order[2]}\n"
        f"💰 Цена: {order[3]} руб.\n"
        f"📊 Статус: {order[4]}\n\n"
        f"Это действие невозможно отменить!",
        reply_markup=keyboard.as_markup()
    )
    await callback.answer()

@dp.callback_query(F.data.startswith("confirm_delete_order_"))
async def cb_confirm_delete_order(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    # Исправлено: было [2], стало [3]
    try:
        order_id = int(callback.data.split("_")[3])
    except (ValueError, IndexError):
        await callback.answer("❌ Ошибка: неверный формат данных", show_alert=True)
        return
    
    order = get_order(order_id)
    if not order:
        await callback.answer("❌ Заказ не найден", show_alert=True)
        return
    
    order_code = order[9] or f"#{order_id}"
    
    delete_order(order_id)
    add_admin_log(callback.from_user.id, "delete_order", f"Удалил заказ {order_code}")
    
    await callback.message.edit_text(
        f"✅ Заказ {order_code} успешно удалён!",
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
    
    order_code = order[9] or f"#{order_id}"
    user_id, service, price = order[1], order[2], order[3]
    admin_price = order[7]
    final_price = admin_price if admin_price > 0 else price
    
    update_order_status(order_id, "paid")
    add_admin_log(callback.from_user.id, "confirm_payment", f"Подтвердил оплату заказа {order_code} ({final_price} руб.)")
    
    try:
        await bot.send_message(
            user_id,
            f"✅ *Оплата подтверждена!*\n\n"
            f"Заказ {order_code}: {service}\n"
            f"Сумма: {final_price} руб.\n\n"
            f"Спасибо за оплату! Мы свяжемся с вами в ближайшее время.\n"
            f"Диспетчер: {DISPATCHER_USERNAME}"
        )
    except:
        pass
    
    await callback.answer("✅ Оплата подтверждена!", show_alert=True)
    
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
    
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT username, first_name FROM users WHERE user_id = ?", (order[1],))
    user_data = cur.fetchone()
    conn.close()
    
    order_id, user_id, service, price, status, created_at, paid_at, admin_price, admin_note, order_code, rating, review, file_id = order
    status_text = "✅ Оплачен" if status == "paid" else "⏳ Ожидает оплаты" if status == "pending" else "🔧 В работе" if status == "in_progress" else "❌ Отменён"
    final_price = admin_price if admin_price > 0 else price
    
    if user_data:
        username, first_name = user_data
        if username:
            user_display = f"@{username}"
        else:
            user_display = first_name or str(user_id)
    else:
        user_display = f"ID: {user_id}"
    
    display_code = order_code or f"#{order_id}"
    
    created = datetime.fromisoformat(created_at).strftime("%d.%m.%Y %H:%M")
    paid = datetime.fromisoformat(paid_at).strftime("%d.%m.%Y %H:%M") if paid_at else "Не оплачен"
    
    text = (
        f"📦 *Информация о заказе {display_code}*\n\n"
        f"👤 Пользователь: {user_display} (ID: {user_id})\n"
        f"📝 Услуга: {service}\n"
        f"💰 Изначальная цена: {price} руб.\n"
        f"💰 Назначенная цена: {final_price} руб.\n"
        f"📊 Статус: {status_text}\n"
        f"📅 Создан: {created}\n"
        f"✅ Оплачен: {paid}\n"
    )
    
    if rating > 0:
        text += f"⭐ Оценка: {rating}/5\n"
        if review:
            text += f"📝 Отзыв: {review}\n"
    
    if file_id:
        text += f"📎 Прикреплён файл: ✅\n"
    
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

# ===================== АДМИН: ПРИКРЕПИТЬ ФАЙЛ =====================
@dp.callback_query(F.data.startswith("attach_file_"))
async def cb_attach_file_start(callback: CallbackQuery, state: FSMContext):
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
        f"📎 *Прикрепить файл к заказу {order[9] or f'#{order_id}'}*\n\n"
        f"Отправьте файл (PDF, DOC, DOCX, TXT, ZIP, JPG, PNG):",
        reply_markup=back_to_main_keyboard()
    )
    await state.set_state(AttachFileState.waiting_for_file)
    await callback.answer()

@dp.message(AttachFileState.waiting_for_file)
async def cb_attach_file_process(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Нет доступа.")
        await state.clear()
        return
    
    data = await state.get_data()
    order_id = data.get("order_id")
    
    if not order_id:
        await message.answer("❌ Ошибка: заказ не найден.")
        await state.clear()
        return
    
    order = get_order(order_id)
    order_code = order[9] if order else f"#{order_id}"
    
    if message.document:
        file_id = message.document.file_id
        file_name = message.document.file_name or "файл"
    elif message.photo:
        file_id = message.photo[-1].file_id
        file_name = "фото.jpg"
    else:
        await message.answer("❌ Пожалуйста, отправьте файл (PDF, DOC, DOCX, TXT, ZIP, JPG, PNG).")
        return
    
    update_order_file(order_id, file_id)
    add_admin_log(message.from_user.id, "attach_file", f"Прикрепил файл к заказу {order_code}")
    
    await message.answer(
        f"✅ Файл *{file_name}* успешно прикреплён к заказу {order_code}!",
        parse_mode="Markdown",
        reply_markup=admin_menu_keyboard()
    )
    await state.clear()
    
    if order:
        try:
            await bot.send_message(
                order[1],
                f"📎 *К вашему заказу прикреплён файл!*\n\n"
                f"Заказ {order_code}: {order[2]}\n"
                f"Файл: {file_name}\n\n"
                f"Вы можете скачать его в разделе 'Мои заказы'."
            )
        except:
            pass

# ===================== ОТЗЫВЫ =====================
@dp.callback_query(F.data.startswith("review_order_"))
async def cb_review_start(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    order_id = int(callback.data.split("_")[2])
    
    order = get_order(order_id)
    if not order:
        await callback.answer("❌ Заказ не найден", show_alert=True)
        return
    
    if order[1] != user_id:
        await callback.answer("⛔ Это не ваш заказ", show_alert=True)
        return
    
    if order[4] != "paid":
        await callback.answer("❌ Оставить отзыв можно только для выполненного заказа", show_alert=True)
        return
    
    if order[10] > 0:
        await callback.answer("❌ Вы уже оставили отзыв на этот заказ", show_alert=True)
        return
    
    await state.update_data(order_id=order_id)
    
    keyboard = InlineKeyboardBuilder()
    for i in range(1, 6):
        keyboard.button(text=f"⭐ {i}", callback_data=f"rating_{i}")
    keyboard.button(text="❌ Отмена", callback_data="my_orders")
    keyboard.adjust(5, 1)
    
    await callback.message.edit_text(
        f"⭐ *Оцените работу над заказом {order[9] or f'#{order_id}'}*\n\n"
        f"Выберите оценку от 1 до 5:",
        reply_markup=keyboard.as_markup()
    )
    await state.set_state(ReviewState.waiting_for_rating)
    await callback.answer()

@dp.callback_query(F.data.startswith("rating_"))
async def cb_review_rating(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    rating = int(callback.data.split("_")[1])
    
    await state.update_data(rating=rating)
    await callback.message.edit_text(
        f"⭐ *Оставьте отзыв*\n\n"
        f"Вы выбрали оценку: {rating}/5\n\n"
        f"Напишите текст отзыва (или отправьте /skip, чтобы пропустить):"
    )
    await state.set_state(ReviewState.waiting_for_review)
    await callback.answer()

@dp.message(ReviewState.waiting_for_review)
async def cb_review_process(message: Message, state: FSMContext):
    if message.text and message.text == "/skip":
        review_text = ""
    else:
        review_text = message.text
    
    data = await state.get_data()
    order_id = data.get("order_id")
    rating = data.get("rating")
    
    if not order_id:
        await message.answer("❌ Ошибка: заказ не найден.")
        await state.clear()
        return
    
    order = get_order(order_id)
    order_code = order[9] if order else f"#{order_id}"
    
    update_order_review(order_id, rating, review_text)
    add_user_log(message.from_user.id, "review", f"Оставил отзыв на заказ {order_code}: {rating}/5")
    
    await message.answer(
        f"✅ Спасибо за ваш отзыв!\n\n"
        f"⭐ Оценка: {rating}/5\n"
        f"📝 Отзыв: {review_text or 'Без текста'}\n\n"
        f"Мы ценим ваше мнение!",
        reply_markup=back_to_main_keyboard()
    )
    await state.clear()

@dp.message(StateFilter(ReviewState.waiting_for_review), F.text == "/cancel")
async def cb_review_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Отзыв отменён.", reply_markup=main_menu_keyboard())

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
    
    if order[4] == "in_progress":
        await callback.answer("❌ Заказ уже в работе, отмена невозможна", show_alert=True)
        return
    
    order_code = order[9] or f"#{order_id}"
    
    update_order_status(order_id, "cancelled")
    add_user_log(user_id, "cancel_order", f"Отменил заказ {order_code}")
    
    await callback.message.edit_text(
        f"✅ Заказ {order_code} успешно отменён!\n\n"
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
    
    order_id, user_id, service, price, status, created_at, paid_at, admin_price, admin_note, order_code, rating, review, file_id = order
    status_text = "✅ Оплачен" if status == "paid" else "⏳ Ожидает оплаты" if status == "pending" else "🔧 В работе" if status == "in_progress" else "❌ Отменён"
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
    
    if rating > 0:
        text += f"⭐ Оценка: {rating}/5\n"
        if review:
            text += f"📝 Отзыв: {review}\n"
    
    if file_id:
        text += f"\n📎 *Файл прикреплён!*\n"
        keyboard = InlineKeyboardBuilder()
        keyboard.button(text="📥 Скачать файл", callback_data=f"download_file_{order_id}")
        keyboard.button(text="🔙 Назад", callback_data="my_orders")
        keyboard.adjust(1)
        await update_message(callback, text, keyboard.as_markup())
        await callback.answer()
        return
    
    if admin_note:
        text += f"\n📌 Заметка: {admin_note}\n"
    
    await update_message(callback, text, order_user_keyboard(order_id, status))
    await callback.answer()

# ===================== СКАЧИВАНИЕ ФАЙЛА =====================
@dp.callback_query(F.data.startswith("download_file_"))
async def cb_download_file(callback: CallbackQuery):
    user_id = callback.from_user.id
    order_id = int(callback.data.split("_")[2])
    
    order = get_order(order_id)
    if not order:
        await callback.answer("❌ Заказ не найден", show_alert=True)
        return
    
    if order[1] != user_id and not is_admin(user_id):
        await callback.answer("⛔ Нет доступа", show_alert=True)
        return
    
    file_id = order[12]
    if not file_id:
        await callback.answer("❌ Файл не найден", show_alert=True)
        return
    
    try:
        await bot.send_document(
            user_id,
            file_id,
            caption=f"📎 Файл к заказу {order[9] or f'#{order_id}'}\nУслуга: {order[2]}"
        )
        await callback.answer("✅ Файл отправлен!")
    except Exception as e:
        logging.error(f"Ошибка отправки файла: {e}")
        await callback.answer("❌ Ошибка при отправке файла", show_alert=True)

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
        f"🔧 В работе: *{stats['in_progress']}*\n"
        f"❌ Отменённых: *{stats['cancelled_orders']}*\n"
        f"💰 Доход: *{stats['income']} руб.*\n"
        f"⭐ Средняя оценка: *{stats['avg_rating']}*\n\n"
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

# ===================== ВЫБОР УСЛУГИ С ПОДТВЕРЖДЕНИЕМ =====================
@dp.callback_query(F.data.startswith("service_"))
async def cb_service(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id

    service_map = {
        "service_coursework": ("Курсовая работа", 2500, "от 2500 ₽", 
            "📝 *Курсовая работа*\n\n"
            "Мы поможем вам написать качественную курсовую работу по любой теме.\n"
            "• Глубокий анализ темы\n"
            "• Оформление по ГОСТ\n"
            "• Уникальность от 70%\n"
            "• Сроки от 4 часов (зависит от загрузки)"),
        "service_project": ("Школьный проект", 1500, "от 1500 ₽",
            "🎓 *Школьный проект*\n\n"
            "Создадим уникальный проект для школы.\n"
            "• Индивидуальная тема\n"
            "• Практическая часть\n"
            "• Красочное оформление\n"
            "• Сроки от 4 часов (зависит от загрузки)"),
        "service_practice": ("Отчёт по практике", 3000, "от 3000 ₽",
            "📊 *Отчёт по практике*\n\n"
            "Поможем оформить отчёт по производственной практике.\n"
            "• Дневник практики\n"
            "• Характеристика\n"
            "• Аналитическая часть\n"
            "• Сроки от 4 часов (зависит от загрузки)"),
        "service_report": ("Доклад", 500, "от 500 ₽",
            "📄 *Доклад*\n\n"
            "Подготовим качественный доклад на любую тему.\n"
            "• Объём от 5 страниц\n"
            "• Чёткая структура\n"
            "• Актуальная информация\n"
            "• Сроки от 4 часов (зависит от загрузки)"),
        "service_presentation": ("Презентация", 300, "от 300 ₽",
            "📽️ *Презентация*\n\n"
            "Создадим стильную и информативную презентацию.\n"
            "• От 10 слайдов\n"
            "• Качественный дизайн\n"
            "• Инфографика\n"
            "• Сроки от 10 минут (в редких случаях до 3 часов)"),
        "service_defense": ("Защитное слово", 100, "от 100 ₽",
            "🗣️ *Защитное слово*\n\n"
            "Составим защитное слово для успешной защиты проекта.\n"
            "• Индивидуальный подход\n"
            "• Структурированный текст\n"
            "• Убедительная аргументация\n"
            "• Сроки от 10 минут (в редких случаях до 3 часов)"),
    }

    service_data = service_map.get(callback.data)
    if not service_data:
        await callback.answer("Ошибка выбора", show_alert=True)
        return
    
    service_type, base_price, price_text, description = service_data
    
    await state.update_data(
        service_type=service_type,
        base_price=base_price,
        price_text=price_text,
        description=description
    )

    text = (
        f"📋 *Вы выбрали: {service_type}*\n\n"
        f"{description}\n\n"
        f"💰 Базовая стоимость: *{price_text}*\n\n"
        f"📌 *Важно!* Окончательная цена и сроки зависят от:\n"
        f"• Тема работы\n"
        f"• Сложность и объём\n"
        f"• Текущая загрузка команды\n\n"
        f"✅ Подтвердите создание заказа или вернитесь к выбору:"
    )

    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="✅ Подтвердить заказ", callback_data=f"confirm_order_{callback.data.split('_')[1]}")
    keyboard.button(text="❌ Отмена", callback_data="buy")
    keyboard.adjust(1)

    await update_message(callback, text, keyboard.as_markup())
    await callback.answer()

# ===================== ПОДТВЕРЖДЕНИЕ СОЗДАНИЯ ЗАКАЗА С УВЕДОМЛЕНИЕМ =====================
@dp.callback_query(F.data.startswith("confirm_order_"))
async def cb_confirm_order(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    
    data = await state.get_data()
    service_type = data.get("service_type")
    base_price = data.get("base_price")
    price_text = data.get("price_text")
    description = data.get("description")
    
    if not service_type:
        await callback.answer("❌ Ошибка: выберите услугу заново", show_alert=True)
        await state.clear()
        return
    
    order_id, order_code = add_order(user_id, service_type, base_price)
    update_user_action(user_id, f"order_{service_type}")
    add_user_log(user_id, "create_order", f"Заказ {order_code}: {service_type} ({price_text})")
    
    await state.clear()
    
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT username, first_name FROM users WHERE user_id = ?", (user_id,))
    user_data = cur.fetchone()
    conn.close()
    
    username = user_data[0] if user_data else None
    user_name = user_data[1] if user_data else "Пользователь"
    
    text = (
        f"✅ *Заказ успешно создан!*\n\n"
        f"📋 Услуга: *{service_type}*\n"
        f"💰 Базовая стоимость: *{price_text}*\n"
        f"🏷️ Код заказа: *{order_code}*\n\n"
        f"📌 *Важно!* Окончательная цена и сроки зависят от:\n"
        f"• Тема работы\n"
        f"• Сложность и объём\n"
        f"• Текущая загрузка команды\n\n"
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
    keyboard.button(text="🔙 На главную", callback_data="main_menu")
    keyboard.adjust(1)

    await update_message(callback, text, keyboard.as_markup())
    await callback.answer()
    
    for admin_id in ADMINS:
        try:
            await bot.send_message(
                admin_id,
                f"🆕 *НОВЫЙ ЗАКАЗ!*\n\n"
                f"📋 Услуга: *{service_type}*\n"
                f"🏷️ Код: *{order_code}*\n"
                f"👤 Пользователь: @{username or 'без username'} ({user_name})\n"
                f"💰 Цена: {price_text}\n\n"
                f"📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n"
                f"🆔 ID заказа: `{order_id}`",
                parse_mode="Markdown"
            )
        except Exception as e:
            logging.error(f"Ошибка отправки уведомления админу {admin_id}: {e}")

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
        order_id, service, price, status, created_at, admin_price, order_code, rating, review = order
        status_text = {"pending": "⏳ Ожидает оплаты", "paid": "✅ Оплачен", "in_progress": "🔧 В работе", "cancelled": "❌ Отменён"}.get(status, status)
        final_price = admin_price if admin_price > 0 else price
        created = datetime.fromisoformat(created_at).strftime("%d.%m.%Y")
        display_code = order_code or f"#{order_id}"
        rating_str = f"⭐{rating}" if rating > 0 else ""
        text += f"• {display_code}: {service} - {final_price} руб. ({status_text}) [{created}] {rating_str}\n"
    
    builder = InlineKeyboardBuilder()
    for order in orders:
        order_id, service, price, status, created_at, admin_price, order_code, rating, _ = order
        display_code = order_code or f"#{order_id}"
        status_emoji = "✅" if status == "paid" else "⏳" if status == "pending" else "🔧" if status == "in_progress" else "❌"
        builder.button(text=f"{status_emoji} {display_code} - {service[:15]}", callback_data=f"my_order_{order_id}")
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
    
    sent_to = 0
    for admin_id in ADMINS:
        try:
            await bot.send_message(admin_id, text)
            sent_to += 1
            if message.photo:
                file_id = message.photo[-1].file_id
                await bot.send_photo(admin_id, file_id, caption=f"Фото от @{user.username}")
            elif message.document:
                await bot.send_document(admin_id, message.document.file_id, caption=f"Документ от @{user.username}")
        except Exception as e:
            logging.warning(f"Не удалось отправить сообщение админу {admin_id}: {e}")
    
    if sent_to > 0:
        await message.answer("✅ Ваше сообщение отправлено автору. Он ответит вам здесь.", reply_markup=back_to_main_keyboard())
    else:
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
