# main.py
# -*- coding: utf-8 -*-

import asyncio
import logging
import sqlite3
import os
from datetime import datetime

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, FSInputFile
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

# ===================== НАСТРОЙКИ =====================
BOT_TOKEN = "8886790065:AAGdMQdY0UXRFH1ZhQ7TtdS72nP2V5UmZO8"
ADMIN_ID = 1244835178

# Контакты диспетчера
DISPATCHER_USERNAME = "@ваш_юзернейм"  # Укажите юзернейм диспетчера
DISPATCHER_PHONE = "+7 (999) 123-45-67"  # Или телефон

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# ===================== СОЗДАНИЕ ДИСПЕТЧЕРА И БОТА =====================
dp = Dispatcher()
bot = Bot(token=BOT_TOKEN)

# ===================== РАБОТА С БАЗОЙ ДАННЫХ =====================
DB_NAME = "shop_bot.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    
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
    
    cur.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            order_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            service TEXT,
            price INTEGER,
            status TEXT,
            created_at TEXT,
            paid_at TEXT,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    """)
    
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

# ===================== ФУНКЦИИ БАЗЫ ДАННЫХ =====================
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

def add_order(user_id: int, service: str, price: int) -> int:
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO orders (user_id, service, price, status, created_at) VALUES (?, ?, ?, ?, ?)",
        (user_id, service, price, "pending", datetime.now().isoformat())
    )
    order_id = cur.lastrowid
    conn.commit()
    conn.close()
    return order_id

def update_order_status(order_id: int, status: str):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "UPDATE orders SET status = ?, paid_at = ? WHERE order_id = ?",
        (status, datetime.now().isoformat(), order_id)
    )
    conn.commit()
    conn.close()

def get_user_orders(user_id: int):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "SELECT order_id, service, price, status, created_at FROM orders WHERE user_id = ? ORDER BY created_at DESC",
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
        SELECT o.order_id, o.user_id, u.username, o.service, o.price, o.status, o.created_at, o.paid_at 
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
    conn.close()
    return {
        "users": user_count,
        "total_orders": total_orders,
        "paid_orders": paid_orders,
        "pending_orders": pending_orders,
        "income": total_income
    }

# ===================== КЛАВИАТУРЫ =====================
def main_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📚 Заказать работу", callback_data="buy")
    builder.button(text="📂 Примеры работ", callback_data="examples")
    builder.button(text="📞 Поддержка", callback_data="support")
    builder.button(text="📋 Мои заказы", callback_data="my_orders")
    builder.adjust(2, 2)
    return builder.as_markup()

def admin_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Статистика", callback_data="admin_stats")
    builder.button(text="👥 Пользователи", callback_data="admin_users")
    builder.button(text="📦 Заказы", callback_data="admin_orders")
    builder.button(text="📋 Логи", callback_data="admin_logs")
    builder.button(text="🔙 В главное меню", callback_data="main_menu")
    builder.adjust(2, 2, 1)
    return builder.as_markup()

def services_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Курсовая работа (3500₽)", callback_data="service_coursework")
    builder.button(text="🎓 Школьный проект (1500₽)", callback_data="service_project")
    builder.button(text="📊 Отчёт по практике (3000₽)", callback_data="service_practice")
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
        order_id, user_id, username, service, price, status, _, _ = order
        status_emoji = "✅" if status == "paid" else "⏳"
        builder.button(
            text=f"{status_emoji} #{order_id} - {service[:12]}",
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

# ===================== МАШИНЫ СОСТОЯНИЙ (FSM) =====================
class SupportState(StatesGroup):
    waiting_for_message = State()

class AdminBroadcastState(StatesGroup):
    waiting_for_message = State()

# ===================== УНИВЕРСАЛЬНАЯ ФУНКЦИЯ =====================
async def update_message(callback: CallbackQuery, text: str, reply_markup=None, parse_mode="Markdown"):
    try:
        await callback.message.edit_text(
            text,
            parse_mode=parse_mode,
            reply_markup=reply_markup
        )
    except Exception as e:
        if "there is no text" in str(e):
            try:
                await callback.message.delete()
            except:
                pass
            await callback.message.answer(
                text,
                parse_mode=parse_mode,
                reply_markup=reply_markup
            )
        else:
            logging.error(f"Ошибка обновления: {e}")
            await callback.message.answer(
                text,
                parse_mode=parse_mode,
                reply_markup=reply_markup
            )

# ===================== ОБРАБОТЧИКИ КОМАНД =====================
@dp.message(Command("start"))
async def cmd_start(message: Message):
    user = message.from_user
    add_user(user.id, user.username, user.first_name, user.last_name or "")
    update_user_action(user.id, "start")
    add_user_log(user.id, "start", "Запустил бота")
    
    text = (
        "🎵 *Добро пожаловать в Sopranidi Corp.!*\n\n"
        "Мы — команда профессионалов, помогающая студентам и школьникам "
        "создавать уникальные проекты, курсовые и отчёты. "
        "Каждая работа разрабатывается *индивидуально* под ваши требования, "
        "с учётом всех пожеланий и стандартов. "
        "Мы гарантируем *высокое качество*, *оригинальность* и *соблюдение сроков*.\n\n"
        "Выберите нужную услугу в меню ниже 👇"
    )
    
    try:
        photo = FSInputFile("logo.jpg")
        await message.answer_photo(
            photo=photo,
            caption=text,
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )
    except Exception as e:
        logging.warning(f"Фото не найдено: {e}")
        await message.answer(
            text,
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )

@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "📖 *Помощь*\n\n"
        "• /start – показать главное меню\n"
        "• /buy – перейти к выбору услуги\n"
        "• /examples – посмотреть примеры работ\n"
        "• /support – связаться с поддержкой\n"
        "• /my_orders – посмотреть историю заказов\n\n"
        "Для администратора:\n"
        "• /admin – открыть админ-панель",
        parse_mode="Markdown"
    )

@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ У вас нет доступа к админ-панели.")
        return
    
    add_admin_log(message.from_user.id, "admin_panel", "Открыл админ-панель")
    
    stats = get_stats()
    text = (
        "🔐 *Админ-панель Sopranidi Corp.*\n\n"
        f"👥 Пользователей: {stats['users']}\n"
        f"📦 Всего заказов: {stats['total_orders']}\n"
        f"✅ Оплаченных: {stats['paid_orders']}\n"
        f"⏳ Ожидают оплаты: {stats['pending_orders']}\n"
        f"💰 Доход: {stats['income']} ₽\n\n"
        f"📌 Диспетчер: {DISPATCHER_USERNAME}\n"
        f"📱 Телефон: {DISPATCHER_PHONE}\n\n"
        "Выберите действие:"
    )
    
    await message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=admin_menu_keyboard()
    )

# ===================== ОБРАБОТЧИКИ CALLBACK =====================
@dp.callback_query(F.data == "main_menu")
async def cb_main_menu(callback: CallbackQuery):
    user_id = callback.from_user.id
    update_user_action(user_id, "main_menu")
    add_user_log(user_id, "main_menu", "Вернулся в главное меню")
    
    text = (
        "🎵 *Sopranidi Corp.*\n\n"
        "Мы создаём *индивидуальные* проекты, курсовые и отчёты "
        "с учётом всех ваших требований. Каждая работа уникальна, "
        "проверена на антиплагиат и сдаётся строго в срок.\n\n"
        "Выберите услугу ниже 👇"
    )
    
    if callback.message.photo:
        try:
            await callback.message.delete()
        except:
            pass
        await callback.message.answer(
            text,
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )
    else:
        await update_message(callback, text, main_menu_keyboard())
    
    await callback.answer()

@dp.callback_query(F.data == "admin_menu")
async def cb_admin_menu(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Нет доступа")
        return
    
    stats = get_stats()
    text = (
        "🔐 *Админ-панель Sopranidi Corp.*\n\n"
        f"👥 Пользователей: {stats['users']}\n"
        f"📦 Всего заказов: {stats['total_orders']}\n"
        f"✅ Оплаченных: {stats['paid_orders']}\n"
        f"⏳ Ожидают оплаты: {stats['pending_orders']}\n"
        f"💰 Доход: {stats['income']} ₽\n\n"
        f"📌 Диспетчер: {DISPATCHER_USERNAME}\n"
        f"📱 Телефон: {DISPATCHER_PHONE}\n\n"
        "Выберите действие:"
    )
    
    await update_message(callback, text, admin_menu_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "buy")
async def cb_buy(callback: CallbackQuery):
    user_id = callback.from_user.id
    update_user_action(user_id, "buy")
    add_user_log(user_id, "buy", "Открыл выбор услуг")
    
    text = "📚 *Выберите тип работы:*"
    await update_message(callback, text, services_keyboard())
    await callback.answer()

@dp.callback_query(F.data.startswith("service_"))
async def cb_service(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    service_map = {
        "service_coursework": ("Курсовая работа", 3500),
        "service_project": ("Школьный проект", 1500),
        "service_practice": ("Отчёт по практике", 3000),
    }
    service_type, price = service_map.get(callback.data, ("Неизвестно", 0))
    if price == 0:
        await callback.answer("Ошибка выбора", show_alert=True)
        return

    order_id = add_order(user_id, service_type, price)
    update_user_action(user_id, f"order_{service_type}")
    add_user_log(user_id, "create_order", f"Заказ #{order_id}: {service_type} ({price}₽)")

    text = (
        f"✅ *Вы выбрали: {service_type}*\n\n"
        f"💰 Стоимость: *{price} ₽*\n\n"
        f"📌 *Для оформления заказа свяжитесь с диспетчером:*\n"
        f"{DISPATCHER_USERNAME}\n"
        f"📱 Или позвоните: {DISPATCHER_PHONE}\n\n"
        f"💬 После оплаты напишите диспетчеру и сообщите номер заказа: *#{order_id}*\n\n"
        f"Диспетчер свяжется с вами для уточнения деталей."
    )
    
    keyboard = InlineKeyboardBuilder()
    dispatcher_username = DISPATCHER_USERNAME.replace("@", "")
    keyboard.button(text="📞 Связаться с диспетчером", url=f"https://t.me/{dispatcher_username}")
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
    builder.button(text="💧 Сбережение воды", callback_data="example_2")
    builder.button(text="🎱 План открытия бильярдной", callback_data="example_3")
    builder.button(text="🔙 Назад", callback_data="main_menu")
    builder.adjust(1)
    
    text = "📂 *Примеры выполненных работ*\n\nВыберите работу, чтобы скачать её:"
    await update_message(callback, text, builder.as_markup())
    await callback.answer()

@dp.callback_query(F.data.startswith("example_"))
async def send_example(callback: CallbackQuery):
    user_id = callback.from_user.id
    
    example_map = {
        "example_1": ("examples/динамика_цен_на_квартиры.pdf", "Динамика цен на квартиры"),
        "example_2": ("examples/сбережение_воды.pdf", "Сбережение воды"),
        "example_3": ("examples/план_бильярдной.pdf", "План открытия бильярдной"),
    }
    
    file_name, title = example_map.get(callback.data, (None, None))
    if not file_name:
        await callback.answer("❌ Пример не найден", show_alert=True)
        return
    
    add_user_log(user_id, "download_example", f"Скачал: {title}")
    
    try:
        # Проверяем существование файла
        file_path = f"examples/{file_name}"
        if os.path.exists(file_path):
            file = FSInputFile(file_path)
            await callback.message.answer_document(
                document=file,
                caption=f"📄 *{title}*\n\n"
                       f"Пример выполненной работы"
            )
            await callback.answer("Файл отправлен! ✅")
        else:
            logging.warning(f"Файл не найден: {file_path}")
            await callback.answer("❌ Файл временно недоступен", show_alert=True)
    except Exception as e:
        logging.error(f"Ошибка отправки файла: {e}")
        await callback.answer("❌ Ошибка при отправке файла", show_alert=True)

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
        f"📱 {DISPATCHER_PHONE}\n\n"
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
    else:
        text = "📋 *Ваши заказы:*\n\n"
        for order in orders:
            order_id, service, price, status, created_at = order
            status_text = {
                "pending": "⏳ Ожидает оплаты",
                "paid": "✅ Оплачен"
            }.get(status, status)
            created = datetime.fromisoformat(created_at).strftime("%d.%m.%Y")
            text += f"• #{order_id}: {service} – {price}₽ ({status_text}) [{created}]\n"
    
    await update_message(callback, text, back_to_main_keyboard())
    await callback.answer()

# ===================== АДМИН-ПАНЕЛЬ =====================
@dp.callback_query(F.data == "admin_stats")
async def cb_admin_stats(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Нет доступа")
        return
    
    stats = get_stats()
    add_admin_log(callback.from_user.id, "view_stats", "Просмотрел статистику")
    
    text = (
        "📊 *Статистика Sopranidi Corp.*\n\n"
        f"👥 *Пользователи:* {stats['users']}\n"
        f"📦 *Всего заказов:* {stats['total_orders']}\n"
        f"✅ *Оплаченных:* {stats['paid_orders']}\n"
        f"⏳ *Ожидают оплаты:* {stats['pending_orders']}\n"
        f"💰 *Доход:* {stats['income']} ₽\n\n"
        f"📌 *Диспетчер:* {DISPATCHER_USERNAME}\n"
        f"📱 *Телефон:* {DISPATCHER_PHONE}"
    )
    
    await update_message(callback, text, admin_menu_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "admin_users")
async def cb_admin_users(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Нет доступа")
        return
    
    users = get_all_users()
    add_admin_log(callback.from_user.id, "view_users", f"Просмотрел список пользователей ({len(users)})")
    
    if not users:
        text = "👥 Пользователей пока нет."
        await update_message(callback, text, admin_menu_keyboard())
        await callback.answer()
        return
    
    await update_message(callback, "👥 *Список пользователей:*", users_keyboard(users, 0))
    await callback.answer()

@dp.callback_query(F.data.startswith("users_page_"))
async def cb_users_page(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Нет доступа")
        return
    
    page = int(callback.data.split("_")[2])
    users = get_all_users()
    
    await callback.message.edit_reply_markup(reply_markup=users_keyboard(users, page))
    await callback.answer()

@dp.callback_query(F.data.startswith("user_"))
async def cb_user_detail(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Нет доступа")
        return
    
    user_id = int(callback.data.split("_")[1])
    
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "SELECT user_id, username, first_name, last_name, reg_date, last_action, action_date FROM users WHERE user_id = ?",
        (user_id,)
    )
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
        f"ID: {user_id}\n"
        f"Имя: {first_name} {last_name or ''}\n"
        f"Username: @{username or 'Не указан'}\n"
        f"Дата регистрации: {reg_date[:10]}\n"
        f"Последнее действие: {last_action or 'Нет'}\n\n"
        f"📦 Заказов: {len(orders)}\n"
        f"Оплачено: {len([o for o in orders if o[3] == 'paid'])}\n\n"
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
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Нет доступа")
        return
    
    user_id = int(callback.data.split("_")[2])
    orders = get_user_orders(user_id)
    
    if not orders:
        text = "📦 У пользователя нет заказов."
    else:
        text = f"📦 *Заказы пользователя (ID: {user_id}):*\n\n"
        for order in orders:
            order_id, service, price, status, created_at = order
            status_text = "✅ Оплачен" if status == "paid" else "⏳ Ожидает"
            created = datetime.fromisoformat(created_at).strftime("%d.%m.%Y")
            text += f"• #{order_id}: {service} – {price}₽ ({status_text}) [{created}]\n"
    
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="🔙 Назад", callback_data=f"user_{user_id}")
    keyboard.adjust(1)
    
    await update_message(callback, text, keyboard.as_markup())
    await callback.answer()

@dp.callback_query(F.data == "admin_orders")
async def cb_admin_orders(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Нет доступа")
        return
    
    orders = get_all_orders()
    add_admin_log(callback.from_user.id, "view_orders", f"Просмотрел список заказов ({len(orders)})")
    
    if not orders:
        text = "📦 Заказов пока нет."
        await update_message(callback, text, admin_menu_keyboard())
        await callback.answer()
        return
    
    await update_message(callback, "📦 *Список заказов:*", orders_keyboard(orders, 0))
    await callback.answer()

@dp.callback_query(F.data.startswith("orders_page_"))
async def cb_orders_page(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Нет доступа")
        return
    
    page = int(callback.data.split("_")[2])
    orders = get_all_orders()
    
    await callback.message.edit_reply_markup(reply_markup=orders_keyboard(orders, page))
    await callback.answer()

@dp.callback_query(F.data.startswith("order_"))
async def cb_order_detail(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Нет доступа")
        return
    
    order_id = int(callback.data.split("_")[1])
    
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("""
        SELECT o.order_id, o.user_id, u.username, u.first_name, o.service, o.price, o.status, o.created_at, o.paid_at 
        FROM orders o
        LEFT JOIN users u ON o.user_id = u.user_id
        WHERE o.order_id = ?
    """, (order_id,))
    order = cur.fetchone()
    conn.close()
    
    if not order:
        await callback.answer("❌ Заказ не найден", show_alert=True)
        return
    
    _, user_id, username, first_name, service, price, status, created_at, paid_at = order
    
    status_text = "✅ Оплачен" if status == "paid" else "⏳ Ожидает оплаты"
    name = username or first_name or str(user_id)
    created = datetime.fromisoformat(created_at).strftime("%d.%m.%Y %H:%M")
    paid = datetime.fromisoformat(paid_at).strftime("%d.%m.%Y %H:%M") if paid_at else "Не оплачен"
    
    text = (
        f"📦 *Информация о заказе #{order_id}*\n\n"
        f"👤 Пользователь: {name} (ID: {user_id})\n"
        f"📝 Услуга: {service}\n"
        f"💰 Стоимость: {price} ₽\n"
        f"📊 Статус: {status_text}\n"
        f"📅 Создан: {created}\n"
        f"✅ Оплачен: {paid}\n"
    )
    
    keyboard = InlineKeyboardBuilder()
    if status == "pending":
        keyboard.button(text="✅ Подтвердить оплату", callback_data=f"confirm_payment_{order_id}")
    keyboard.button(text="🔙 Назад", callback_data="admin_orders")
    keyboard.adjust(1)
    
    await update_message(callback, text, keyboard.as_markup())
    await callback.answer()

@dp.callback_query(F.data.startswith("confirm_payment_"))
async def cb_confirm_payment(callback: CallbackQuery):
    if callback.from_user.id != ADMIN_ID:
        await callback.answer("⛔ Нет доступа")
        return
    
    order_id = int(callback.data.split("_")[2])
    
    conn = sqlite3.connect
