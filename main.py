# main.py
# -*- coding: utf-8 -*-

import asyncio
import logging
import sqlite3
import os
import time
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

# ===================== ЮMONEY =====================
from yoomoney import Quickpay, Client

# ===================== НАСТРОЙКИ =====================
BOT_TOKEN = "8886790065:AAGdMQdY0UXRFH1ZhQ7TtdS72nP2V5UmZO8"
ADMIN_ID = 1244835178

# Настройки ЮMoney
YOOMONEY_TOKEN = "ВАШ_ТОКЕН_ОТ_ЮMONEY"  # Получить в настройках кошелька
YOOMONEY_RECEIVER = "410011234567890"   # Номер вашего кошелька (без пробелов)

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
            payment_id TEXT,
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

def add_order(user_id: int, service: str, price: int, payment_id: str) -> int:
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO orders (user_id, service, price, status, created_at, payment_id) VALUES (?, ?, ?, ?, ?, ?)",
        (user_id, service, price, "pending", datetime.now().isoformat(), payment_id)
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

def get_order(order_id: int):
    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()
    cur.execute(
        "SELECT order_id, user_id, service, price, status, payment_id FROM orders WHERE order_id = ?",
        (order_id,)
    )
    row = cur.fetchone()
    conn.close()
    return row

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

# ===================== ЮMONEY ФУНКЦИИ =====================
def create_yoomoney_payment(amount: int, description: str, order_id: int) -> str:
    """
    Создаёт платёж в ЮMoney и возвращает ссылку для оплаты.
    """
    try:
        quickpay = Quickpay(
            receiver=YOOMONEY_RECEIVER,
            quickpay_form="shop",
            targets=description,
            paymentType="SB",
            sum=amount,
            label=str(order_id),
            successURL="https://t.me/sopranidi_bot"
        )
        return quickpay.redirected_url
    except Exception as e:
        logging.error(f"Ошибка создания платежа ЮMoney: {e}")
        return None

def check_payment_status(payment_id: str) -> str:
    """
    Проверяет статус платежа в ЮMoney.
    Возвращает 'success', 'pending', 'error' или None.
    """
    try:
        client = Client(YOOMONEY_TOKEN)
        history = client.operation_history(label=payment_id)
        
        for operation in history.operations:
            if operation.label == payment_id:
                if operation.status == "success":
                    return "success"
                elif operation.status == "pending":
                    return "pending"
                else:
                    return "error"
        return "not_found"
    except Exception as e:
        logging.error(f"Ошибка проверки платежа: {e}")
        return None

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

# ===================== УНИВЕРСАЛЬНАЯ ФУНКЦИЯ ДЛЯ ОБНОВЛЕНИЯ =====================
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
    
    text = (
        "🎵 *Добро пожаловать в Sopranidi Corp.!*\n\n"
        "Мы — команда профессионалов, помогающая студентам и школьникам "
        "создавать уникальные проекты, курсовые и отчёты. "
        "Каждая работа разрабатывается *индивидуально* под ваши требования, "
        "с учётом всех пожеланий и стандартов. "
        "Мы гарантируем *высокое качество*, *оригинальность* и *соблюдение сроков*.\n\n"
        "Оплата через ЮMoney на карту.\n"
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
        "Оплата производится через ЮMoney. После оплаты заказ автоматически подтверждается.",
        parse_mode="Markdown"
    )

# ===================== ОБРАБОТЧИКИ CALLBACK =====================
@dp.callback_query(F.data == "main_menu")
async def cb_main_menu(callback: CallbackQuery):
    text = (
        "🎵 *Sopranidi Corp.*\n\n"
        "Мы создаём *индивидуальные* проекты, курсовые и отчёты "
        "с учётом всех ваших требований. Каждая работа уникальна, "
        "проверена на антиплагиат и сдаётся строго в срок.\n\n"
        "Оплата через ЮMoney на карту.\n"
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

@dp.callback_query(F.data == "buy")
async def cb_buy(callback: CallbackQuery):
    text = "📚 *Выберите тип работы:*"
    await update_message(callback, text, services_keyboard())
    await callback.answer()

@dp.callback_query(F.data.startswith("service_"))
async def cb_service(callback: CallbackQuery):
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
    
    payment_id = f"order_{user_id}_{int(time.time())}"
    order_id = add_order(user_id, service_type, price, payment_id)

    payment_url = create_yoomoney_payment(
        amount=price,
        description=f"{service_type} (заказ #{order_id})",
        order_id=order_id
    )

    if not payment_url:
        await callback.answer("❌ Ошибка создания платежа", show_alert=True)
        return

    text = (
        f"💳 *{service_type}*\n\n"
        f"Сумма к оплате: *{price} ₽*\n\n"
        f"Для оплаты перейдите по ссылке ниже:\n"
        f"{payment_url}\n\n"
        f"⚠️ После оплаты заказ будет автоматически подтверждён.\n"
        f"Это может занять до 1-2 минут."
    )
    
    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="💳 Оплатить", url=payment_url)
    keyboard.button(text="🔄 Проверить оплату", callback_data=f"check_{order_id}")
    keyboard.button(text="🔙 Назад", callback_data="main_menu")
    keyboard.adjust(1)
    
    await update_message(callback, text, keyboard.as_markup())
    await callback.answer()

@dp.callback_query(F.data.startswith("check_"))
async def cb_check_payment(callback: CallbackQuery):
    """Проверка статуса оплаты."""
    order_id = int(callback.data.split("_")[1])
    
    order = get_order(order_id)
    if not order:
        await callback.answer("❌ Заказ не найден", show_alert=True)
        return
    
    _, user_id, service, price, status, payment_id = order
    
    if status == "paid":
        await callback.answer("✅ Заказ уже оплачен!", show_alert=True)
        return
    
    # Проверяем статус в ЮMoney
    payment_status = check_payment_status(payment_id)
    
    if payment_status == "success":
        # Оплата прошла!
        update_order_status(order_id, "paid", datetime.now().isoformat())
        
        await callback.message.edit_text(
            f"✅ *Оплата подтверждена!*\n\n"
            f"Заказ #{order_id}: {service}\n"
            f"Сумма: {price} ₽\n\n"
            f"Спасибо за оплату! Мы свяжемся с вами в ближайшее время.",
            parse_mode="Markdown",
            reply_markup=back_to_main_keyboard()
        )
        
        # Уведомление админу
        await bot.send_message(
            ADMIN_ID,
            f"💰 *Новая оплата!*\n"
            f"Пользователь: @{callback.from_user.username or 'без username'} (ID: {user_id})\n"
            f"Заказ #{order_id}: {service}\n"
            f"Сумма: {price} ₽\n"
            f"Свяжитесь с клиентом как можно скорее.",
            parse_mode="Markdown"
        )
        
        await callback.answer("✅ Оплата подтверждена!", show_alert=True)
        
    elif payment_status == "pending":
        await callback.answer("⏳ Платёж ещё не прошёл. Попробуйте позже.", show_alert=True)
    else:
        await callback.answer("❌ Платёж не найден. Проверьте, оплатили ли вы.", show_alert=True)

@dp.callback_query(F.data == "examples")
async def cb_examples(callback: CallbackQuery):
    builder = InlineKeyboardBuilder()
    builder.button(text="📄 Динамика цен на квартиры", callback_data="example_1")
    builder.button(text="💧 Сбережение воды", callback_data="example_2")
    builder.button(text="🎱 План открытия бильярдной", callback_data="example_3")
    builder.button(text="🔙 Назад", callback_data="main_menu")
    builder.adjust(1)
    
    text = "📂 *Примеры выполненных работ*\n\nВыберите работу, чтобы скачать её:"
    await update_message(callback, text, builder.as_markup())
    await callback.answer()

@dp.callback_query(F.data == "example_1")
async def send_example_1(callback: CallbackQuery):
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
    text = (
        "📞 *Техническая поддержка*\n\n"
        "Напишите ваше сообщение, и я перешлю его автору.\n"
        "Автор ответит вам в этом же чате.\n\n"
        "Для выхода из режима поддержки отправьте /cancel."
    )
    await update_message(callback, text, back_to_main_keyboard())
    await state.set_state(SupportState.waiting_for_message)
    await callback.answer()

@dp.callback_query(F.data == "my_orders")
async def cb_my_orders(callback: CallbackQuery):
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
            text += f"• Заказ #{order_id}: {service} – {price} ₽ ({status_text})\n"
    await update_message(callback, text, back_to_main_keyboard())
    await callback.answer()

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
        f"Общий доход: {total_income} ₽",
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

# ===================== ФОНТОВАЯ ПРОВЕРКА ПЛАТЕЖЕЙ =====================
async def check_payments_periodically():
    """
    Фоновый процесс для автоматической проверки статуса платежей.
    Запускается вместе с ботом.
    """
    while True:
        try:
            pending_orders = get_pending_orders()
            for order_id, payment_id, price in pending_orders:
                status = check_payment_status(payment_id)
                if status == "success":
                    # Получаем данные заказа
                    order = get_order(order_id)
                    if order:
                        _, user_id, service, _, _, _ = order
                        update_order_status(order_id, "paid", datetime.now().isoformat())
                        
                        # Уведомляем пользователя
                        try:
                            await bot.send_message(
                                user_id,
                                f"✅ *Оплата подтверждена!*\n\n"
                                f"Заказ #{order_id}: {service}\n"
                                f"Сумма: {price} ₽\n\n"
                                f"Спасибо! Мы свяжемся с вами в ближайшее время.",
                                parse_mode="Markdown"
                            )
                            # Уведомляем админа
                            await bot.send_message(
                                ADMIN_ID,
                                f"💰 *Новая оплата!*\n"
                                f"Заказ #{order_id}: {service}\n"
                                f"Сумма: {price} ₽\n"
                                f"Пользователь ID: {user_id}",
                                parse_mode="Markdown"
                            )
                        except Exception as e:
                            logging.error(f"Ошибка уведомления: {e}")
            
            await asyncio.sleep(30)  # Проверяем каждые 30 секунд
        except Exception as e:
            logging.error(f"Ошибка в фоновой проверке: {e}")
            await asyncio.sleep(60)

# ===================== ЗАПУСК БОТА =====================
async def main():
    init_db()
    logging.info("🚀 Бот Sopranidi Corp. запущен!")
    
    # Запускаем фоновую проверку платежей
    asyncio.create_task(check_payments_periodically())
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
