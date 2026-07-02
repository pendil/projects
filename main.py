# main.py
# -*- coding: utf-8 -*-

import asyncio
import logging
import sqlite3
import os
from datetime import datetime

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message, CallbackQuery, LabeledPrice, PreCheckoutQuery,
    InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.client.telegram import TelegramAPIServer

# ===================== НАСТРОЙКИ =====================
BOT_TOKEN = "8886790065:AAGdMQdY0UXRFH1ZhQ7TtdS72nP2V5UmZO8"
PROVIDER_TOKEN = "ВАШ_ПРОВАЙДЕР_ТОКЕН"
ADMIN_ID = 1244835178

# ===================== НАСТРОЙКА ПРОКСИ =====================
TELEGRAM_SERVER = TelegramAPIServer.from_base("https://td.telegram.org:443")

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# ===================== СОЗДАНИЕ ДИСПЕТЧЕРА И БОТА =====================
dp = Dispatcher()
bot = Bot(token=BOT_TOKEN, server=TELEGRAM_SERVER)

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
            reg_date TEXT
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
            payload TEXT,
            FOREIGN KEY(user_id) REFERENCES users(user_id)
        )
    """)
    conn.commit()
    conn.close()

def add_user(user_id: int, username: str, first_name: str, last_name: str = ""):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "INSERT OR IGNORE INTO users (user_id, username, first_name, last_name, reg_date) VALUES (?, ?, ?, ?, ?)",
        (user_id, username, first_name, last_name, datetime.now().isoformat())
    )
    conn.commit()
    conn.close()

def add_order(user_id: int, service: str, price: int, payload: str) -> int:
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO orders (user_id, service, price, status, created_at, payload) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, service, price, "pending", datetime.now().isoformat(), payload)
    )
    order_id = cur.lastrowid
    conn.commit()
    conn.close()
    return order_id

def update_order_status(order_id: int, status: str, paid_at: str = None):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    if paid_at:
        cur.execute(
            "UPDATE orders SET status = ?, paid_at = ? WHERE order_id = ?",
            (status, paid_at, order_id)
        )
    else:
        cur.execute(
            "UPDATE orders SET status = ? WHERE order_id = ?",
            (status, order_id)
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
    cur.execute("SELECT user_id FROM users")
    rows = cur.fetchall()
    conn.close()
    return [row[0] for row in rows]

# ===================== КЛАВИАТУРЫ =====================
def main_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📚 Заказать работу", callback_data="buy")
    builder.button(text="📂 Примеры работ", callback_data="examples")
    builder.button(text="📞 Поддержка", callback_data="support")
    builder.button(text="📋 Мои заказы", callback_data="my_orders")
    builder.adjust(2, 2)
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

# ===================== МАШИНЫ СОСТОЯНИЙ (FSM) =====================
class SupportState(StatesGroup):
    waiting_for_message = State()

# ===================== УТИЛИТЫ =====================
async def safe_edit_text(callback: CallbackQuery, text: str, reply_markup=None, parse_mode="Markdown"):
    """Безопасно редактирует сообщение. Если не получается, отправляет новое."""
    try:
        await callback.message.edit_text(
            text,
            parse_mode=parse_mode,
            reply_markup=reply_markup
        )
    except Exception as e:
        logging.warning(f"Не удалось отредактировать: {e}")
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
        "Если у вас возникли вопросы, просто напишите мне, и я перенаправлю ваше сообщение автору.",
        parse_mode="Markdown"
    )

# ===================== ОБРАБОТЧИКИ CALLBACK =====================
@dp.callback_query(F.data == "main_menu")
async def cb_main_menu(callback: CallbackQuery):
    """Возврат в главное меню (сообщение НЕ удаляется)."""
    text = (
        "🎵 *Sopranidi Corp.*\n\n"
        "Мы создаём *индивидуальные* проекты, курсовые и отчёты "
        "с учётом всех ваших требований. Каждая работа уникальна, "
        "проверена на антиплагиат и сдаётся строго в срок.\n\n"
        "Выберите услугу ниже 👇"
    )
    
    try:
        # Пробуем отредактировать с фото
        photo = FSInputFile("logo.jpg")
        await callback.message.delete()
        await callback.message.answer_photo(
            photo=photo,
            caption=text,
            parse_mode="Markdown",
            reply_markup=main_menu_keyboard()
        )
    except FileNotFoundError:
        # Если нет фото, просто редактируем текст
        await safe_edit_text(callback, text, main_menu_keyboard())
    except Exception as e:
        logging.error(f"Ошибка в главном меню: {e}")
        await safe_edit_text(callback, text, main_menu_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "buy")
async def cb_buy(callback: CallbackQuery):
    """Выбор услуги."""
    text = "📚 *Выберите тип работы:*"
    await safe_edit_text(callback, text, services_keyboard())
    await callback.answer()

@dp.callback_query(F.data.startswith("service_"))
async def cb_service(callback: CallbackQuery):
    """Обработка выбора услуги."""
    service_map = {
        "service_coursework": ("Курсовая работа", 3500),
        "service_project": ("Школьный проект", 1500),
        "service_practice": ("Отчёт по практике", 3000),
    }
    service_type, price = service_map.get(callback.data, ("Неизвестно", 0))
    if price == 0:
        await callback.answer("Ошибка выбора", show_alert=True)
        return

    user_id = callback.from_user.id
    payload = f"order_{user_id}_{datetime.now().timestamp()}"
    order_id = add_order(user_id, service_type, price, payload)

    try:
        await bot.send_invoice(
            chat_id=user_id,
            title=service_type,
            description=f"Заказ №{order_id} – {service_type}",
            payload=payload,
            provider_token=PROVIDER_TOKEN,
            currency="RUB",
            prices=[LabeledPrice(label=service_type, amount=price * 100)],
            start_parameter="buy_work",
            need_name=True,
            need_phone_number=True,
            need_email=True,
            need_shipping_address=False,
            is_flexible=False,
        )
        text = f"✅ Счёт на сумму {price} руб. отправлен.\nОплатите его в этом же чате."
        await safe_edit_text(callback, text, back_to_main_keyboard())
    except Exception as e:
        logging.error(f"Ошибка отправки счёта: {e}")
        text = "❌ Не удалось создать платёж. Попробуйте позже."
        await safe_edit_text(callback, text, back_to_main_keyboard())
    await callback.answer()

@dp.callback_query(F.data == "examples")
async def cb_examples(callback: CallbackQuery):
    """Список примеров работ."""
    builder = InlineKeyboardBuilder()
    builder.button(text="📄 Динамика цен на квартиры", callback_data="example_1")
    builder.button(text="💧 Сбережение воды", callback_data="example_2")
    builder.button(text="🎱 План открытия бильярдной", callback_data="example_3")
    builder.button(text="🔙 Назад", callback_data="main_menu")
    builder.adjust(1)
    
    text = "📂 *Примеры выполненных работ*\n\nВыберите работу, чтобы скачать её:"
    await safe_edit_text(callback, text, builder.as_markup())
    await callback.answer()

@dp.callback_query(F.data == "example_1")
async def send_example_1(callback: CallbackQuery):
    """Пример: Динамика цен на квартиры."""
    try:
        file = FSInputFile("examples/динамика_цен_на_квартиры.pdf")
        await callback.message.answer_document(
            document=file,
            caption="📄 *Динамика цен на квартиры*\n\n"
                   "Тема: 'Анализ рынка недвижимости'\n"
                   "Объём: 30 страниц\n"
                   "Оценка: Отлично"
        )
        await callback.answer("Файл отправлен! ✅")
    except Exception as e:
        logging.error(f"Ошибка отправки файла: {e}")
        await callback.answer("❌ Файл временно недоступен", show_alert=True)

@dp.callback_query(F.data == "example_2")
async def send_example_2(callback: CallbackQuery):
    """Пример: Сбережение воды."""
    try:
        file = FSInputFile("examples/сбережение_воды.pdf")
        await callback.message.answer_document(
            document=file,
            caption="💧 *Сбережение воды*\n\n"
                   "Тема: 'Экологические технологии'\n"
                   "Объём: 25 страниц\n"
                   "Оценка: Отлично"
        )
        await callback.answer("Файл отправлен! ✅")
    except Exception as e:
        logging.error(f"Ошибка отправки файла: {e}")
        await callback.answer("❌ Файл временно недоступен", show_alert=True)

@dp.callback_query(F.data == "example_3")
async def send_example_3(callback: CallbackQuery):
    """Пример: План открытия бильярдной."""
    try:
        file = FSInputFile("examples/план_бильярдной.pdf")
        await callback.message.answer_document(
            document=file,
            caption="🎱 *План открытия бильярдной*\n\n"
                   "Тема: 'Бизнес-план'\n"
                   "Объём: 40 страниц\n"
                   "Оценка: Отлично"
        )
        await callback.answer("Файл отправлен! ✅")
    except Exception as e:
        logging.error(f"Ошибка отправки файла: {e}")
        await callback.answer("❌ Файл временно недоступен", show_alert=True)

@dp.callback_query(F.data == "support")
async def cb_support(callback: CallbackQuery, state: FSMContext):
    """Поддержка."""
    text = (
        "📞 *Техническая поддержка*\n\n"
        "Напишите ваше сообщение, и я перешлю его автору.\n"
        "Автор ответит вам в этом же чате.\n\n"
        "Для выхода из режима поддержки отправьте /cancel."
    )
    await safe_edit_text(callback, text, back_to_main_keyboard())
    await state.set_state(SupportState.waiting_for_message)
    await callback.answer()

@dp.callback_query(F.data == "my_orders")
async def cb_my_orders(callback: CallbackQuery):
    """История заказов."""
    user_id = callback.from_user.id
    orders = get_user_orders(user_id)
    if not orders:
        text = "📋 У вас пока нет заказов."
    else:
        text = "📋 *Ваши заказы:*\n\n"
        for order in orders:
            order_id, service, price, status, created_at = order
            status_text = {
                "pending": "⏳ Ожидает оплаты",
                "paid": "✅ Оплачен (автор свяжется)",
                "completed": "🎉 Выполнен",
                "cancelled": "❌ Отменён"
            }.get(status, status)
            text += f"• Заказ #{order_id}: {service} – {price} руб. ({status_text})\n"
    await safe_edit_text(callback, text, back_to_main_keyboard())
    await callback.answer()

# ===================== ОБРАБОТКА ПЛАТЕЖЕЙ =====================
@dp.pre_checkout_query(lambda query: True)
async def pre_checkout_query_handler(query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(query.id, ok=True)

@dp.message(F.successful_payment)
async def successful_payment_handler(message: Message):
    payment = message.successful_payment
    user_id = message.from_user.id
    payload = payment.invoice_payload

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "SELECT order_id FROM orders WHERE payload = ? AND status = 'pending'",
        (payload,)
    )
    row = cur.fetchone()
    conn.close()

    if row:
        order_id = row[0]
        update_order_status(order_id, "paid", datetime.now().isoformat())
        await bot.send_message(
            ADMIN_ID,
            f"💰 *Новая оплата!*\n"
            f"Пользователь: @{message.from_user.username or 'без username'} (ID: {user_id})\n"
            f"Заказ №{order_id}\n"
            f"Сумма: {payment.total_amount / 100} руб.\n"
            f"Телефон: {payment.order_info.phone_number if payment.order_info else 'не указан'}\n",
            parse_mode="Markdown"
        )
        await message.answer(
            "✅ Спасибо за оплату! Мы свяжемся с вами в ближайшее время.\n"
            "Вы можете вернуться в главное меню.",
            reply_markup=back_to_main_keyboard()
        )
    else:
        await message.answer("⚠️ Что-то пошло не так. Пожалуйста, свяжитесь с поддержкой.")

# ===================== ОБРАБОТЧИКИ СОСТОЯНИЙ (FSM) =====================
@dp.message(SupportState.waiting_for_message)
async def support_send_message(message: Message, state: FSMContext):
    user = message.from_user
    text = f"📩 *Сообщение от пользователя* @{user.username or 'без username'} (ID: {user.id})\n\n{message.text}"
    try:
        await bot.send_message(ADMIN_ID, text, parse_mode="Markdown")
        if message.photo:
            file_id = message.photo[-1].file_id
            await bot.send_photo(ADMIN_ID, file_id, caption=f"Фото от @{user.username}")
        elif message.document:
            await bot.send_document(ADMIN_ID, message.document.file_id, caption=f"Документ от @{user.username}")
        await message.answer(
            "✅ Ваше сообщение отправлено автору. Он ответит вам здесь.\n"
            "Можете вернуться в главное меню.",
            reply_markup=back_to_main_keyboard()
        )
    except Exception as e:
        logging.error(f"Ошибка пересылки: {e}")
        await message.answer("❌ Не удалось отправить сообщение. Попробуйте позже.")
    await state.clear()

@dp.message(StateFilter(SupportState.waiting_for_message), F.text == "/cancel")
async def support_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Режим поддержки отменён.", reply_markup=main_menu_keyboard())

# ===================== АДМИНСКИЕ КОМАНДЫ =====================
@dp.message(Command("stats"))
async def cmd_stats(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("У вас нет прав.")
        return
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    user_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM orders WHERE status='paid'")
    paid_count = cur.fetchone()[0]
    cur.execute("SELECT SUM(price) FROM orders WHERE status='paid'")
    total_income = cur.fetchone()[0] or 0
    conn.close()
    await message.answer(
        f"📊 *Статистика Sopranidi Corp.*\n\n"
        f"Пользователей: {user_count}\n"
        f"Оплаченных заказов: {paid_count}\n"
        f"Общий доход: {total_income} руб.",
        parse_mode="Markdown"
    )

@dp.message(Command("broadcast"))
async def cmd_broadcast(message: Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("У вас нет прав.")
        return
    text = message.text.replace("/broadcast", "", 1).strip()
    if not text:
        await message.answer("Напишите текст рассылки после команды. Пример: /broadcast Привет всем!")
        return
    users = get_all_users()
    sent = 0
    for uid in users:
        try:
            await bot.send_message(uid, text)
            sent += 1
            await asyncio.sleep(0.05)
        except:
            pass
    await message.answer(f"Рассылка выполнена. Отправлено {sent} пользователям.")

# ===================== ЗАПУСК БОТА =====================
async def main():
    init_db()
    logging.info("🚀 Бот Sopranidi Corp. запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
