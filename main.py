import telebot
from telebot import types
import json
import os
import shutil
from datetime import datetime
from fastapi import FastAPI, Request, File, UploadFile, Form, HTTPException
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import logging
from typing import Optional
import hashlib

# Logging sozlamalari
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== KONFIGURATSIYA ====================
BOT_TOKEN = "8778358404:AAHmM4e2OnROyXLCsGXERCbXd3arzl7kPS0"
RENDER_EXTERNAL_URL = "https://bottt-02j7.onrender.com"
WEB_APP_URL = f"{RENDER_EXTERNAL_URL}/shop"

ADMIN_IDS = [8735360012]

# Fayllar
PRODUCTS_FILE = "products.json"
ORDERS_FILE = "orders.json"
USERS_FILE = "users.json"
PHOTOS_DIR = "photos"

# Bot va app
bot = telebot.TeleBot(BOT_TOKEN)
app = FastAPI(title="Telegram Shop Bot", version="3.0.0")

# Papkalarni yaratish
os.makedirs(PHOTOS_DIR, exist_ok=True)

# State saqlash
user_states = {}


# ==================== YORDAMCHI FUNKSIYALAR ====================
def load_json(filename, default):
    """JSON faylni yuklash"""
    try:
        if os.path.exists(filename):
            with open(filename, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"Error loading {filename}: {e}")
    return default


def save_json(filename, data):
    """JSON faylni saqlash"""
    try:
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error(f"Error saving {filename}: {e}")
        return False


def get_products():
    return load_json(PRODUCTS_FILE, [])


def get_orders():
    return load_json(ORDERS_FILE, [])


def get_users():
    return load_json(USERS_FILE, {})


def save_products(products):
    return save_json(PRODUCTS_FILE, products)


def save_orders(orders):
    return save_json(ORDERS_FILE, orders)


def save_users(users):
    return save_json(USERS_FILE, users)


def is_admin(user_id):
    return user_id in ADMIN_IDS


def format_price(price):
    """Narxni formatlash"""
    return f"{price:,}".replace(",", " ")


def save_product_photos(product_id, files):
    """Mahsulot rasmlarini saqlash"""
    photos = []
    for i, file in enumerate(files):
        if file and file.filename:
            ext = file.filename.split('.')[-1]
            filename = f"product_{product_id}_{i+1}.{ext}"
            filepath = os.path.join(PHOTOS_DIR, filename)
            with open(filepath, "wb") as f:
                f.write(file.file.read())
            photos.append(f"/photos/{filename}")
    return photos


# ==================== KLAVIATURALAR ====================
def get_main_menu(user_id):
    """Asosiy menyu"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    shop_btn = types.KeyboardButton(
        "🛍️ Do'konni ochish",
        web_app=types.WebAppInfo(url=WEB_APP_URL)
    )
    markup.add(shop_btn)
    
    markup.add(
        types.KeyboardButton("📦 Mening zakazlarim"),
        types.KeyboardButton("📞 Aloqa"),
        types.KeyboardButton("ℹ️ Yordam")
    )
    
    if is_admin(user_id):
        markup.add(types.KeyboardButton("👨‍💼 Admin panel"))
    
    return markup


def get_admin_menu():
    """Admin menyusi"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton("➕ Mahsulot qo'shish"),
        types.KeyboardButton("📋 Mahsulotlar ro'yxati"),
        types.KeyboardButton("📊 Statistika"),
        types.KeyboardButton("📦 Barcha zakazlar")
    )
    markup.add(types.KeyboardButton("🔙 Asosiy menyu"))
    return markup


def get_cancel_btn():
    """Bekor qilish tugmasi"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("❌ Bekor qilish"))
    return markup


# ==================== BOT HANDLERLAR ====================
@bot.message_handler(commands=["start"])
def start(message):
    """Start komandasi"""
    user_id = message.from_user.id
    users = get_users()
    
    if str(user_id) not in users:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        contact_btn = types.KeyboardButton(
            "📱 Telefon raqamimni yuborish",
            request_contact=True
        )
        markup.add(contact_btn)
        
        bot.send_message(
            message.chat.id,
            f"👋 *Assalomu alaykum, {message.from_user.first_name}!*\n\n"
            "🛍️ *Do'konimizga xush kelibsiz!*\n\n"
            "📝 *Ro'yxatdan o'tish uchun telefon raqamingizni yuboring* 👇",
            parse_mode="Markdown",
            reply_markup=markup
        )
        user_states[user_id] = {"state": "waiting_contact"}
    else:
        bot.send_message(
            message.chat.id,
            "🏠 *Asosiy menyu*",
            parse_mode="Markdown",
            reply_markup=get_main_menu(user_id)
        )


@bot.message_handler(content_types=["contact"])
def handle_contact(message):
    """Telefon raqamni qabul qilish"""
    user_id = message.from_user.id
    state = user_states.get(user_id, {}).get("state")
    
    if state == "waiting_contact":
        users = get_users()
        users[str(user_id)] = {
            "user_id": user_id,
            "first_name": message.from_user.first_name,
            "last_name": message.from_user.last_name or "",
            "username": message.from_user.username or "",
            "phone": message.contact.phone_number,
            "joined": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        save_users(users)
        
        user_states[user_id] = {"state": "idle"}
        
        bot.send_message(
            message.chat.id,
            "✅ *Ro'yxatdan o'tish muvaffaqiyatli!*\n\n"
            "Endi xarid qilishingiz mumkin 🛍️",
            parse_mode="Markdown",
            reply_markup=get_main_menu(user_id)
        )
        
        # Adminlarga xabar
        for admin_id in ADMIN_IDS:
            try:
                bot.send_message(
                    admin_id,
                    f"🆕 *Yangi foydalanuvchi!*\n\n"
                    f"👤 {message.from_user.first_name}\n"
                    f"📞 {message.contact.phone_number}\n"
                    f"🆔 {user_id}\n"
                    f"👤 @{message.from_user.username or 'None'}",
                    parse_mode="Markdown"
                )
            except:
                pass


@bot.message_handler(func=lambda m: m.text == "👨‍💼 Admin panel")
def admin_panel(message):
    """Admin panel"""
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "❌ *Siz admin emassiz!*", parse_mode="Markdown")
        return
    
    bot.send_message(
        message.chat.id,
        "👨‍💼 *Admin panel*\n\n"
        "Quyidagi amallarni bajarishingiz mumkin:",
        parse_mode="Markdown",
        reply_markup=get_admin_menu()
    )


@bot.message_handler(func=lambda m: m.text == "➕ Mahsulot qo'shish")
def add_product_start(message):
    """Mahsulot qo'shish boshlash"""
    if not is_admin(message.from_user.id):
        return
    
    user_states[message.from_user.id] = {"state": "add_name", "temp": {}}
    bot.send_message(
        message.chat.id,
        "📝 *1/6 - Mahsulot nomi*\n\n"
        "Mahsulot nomini kiriting:",
        parse_mode="Markdown",
        reply_markup=get_cancel_btn()
    )


@bot.message_handler(func=lambda m: m.text == "📋 Mahsulotlar ro'yxati")
def list_products(message):
    """Barcha mahsulotlarni ko'rish"""
    if not is_admin(message.from_user.id):
        return
    
    products = get_products()
    if not products:
        bot.send_message(message.chat.id, "📭 *Hozircha mahsulot yo'q*", parse_mode="Markdown")
        return
    
    for p in products:
        text = (
            f"🆔 *ID:* {p['id']}\n"
            f"📌 *Nomi:* {p['name']}\n"
            f"💰 *Narxi:* {format_price(p['price'])} so'm\n"
            f"🏷 *Kategoriya:* {p['category']}\n"
            f"📸 *Rasmlar:* {len(p.get('photos', []))} ta\n"
            f"✅ *Holat:* {'Mavjud' if p.get('available', True) else 'Mavjud emas'}\n"
        )
        
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("🗑 O'chirish", callback_data=f"del_prod_{p['id']}"),
            types.InlineKeyboardButton("📝 Tahrirlash", callback_data=f"edit_prod_{p['id']}")
        )
        
        # Agar rasm bo'lsa, rasm bilan yuborish
        photos = p.get('photos', [])
        if photos and os.path.exists(photos[0][1:] if photos[0].startswith('/') else photos[0]):
            try:
                with open(photos[0][1:] if photos[0].startswith('/') else photos[0], 'rb') as photo:
                    bot.send_photo(
                        message.chat.id,
                        photo,
                        caption=text,
                        parse_mode="Markdown",
                        reply_markup=markup
                    )
            except:
                bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=markup)
        else:
            bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=markup)


@bot.message_handler(func=lambda m: m.text == "📊 Statistika")
def show_stats(message):
    """Statistika ko'rish"""
    if not is_admin(message.from_user.id):
        return
    
    products = get_products()
    orders = get_orders()
    users = get_users()
    
    total_sales = sum(o.get('total', 0) for o in orders)
    total_orders = len(orders)
    total_users = len(users)
    total_products = len(products)
    
    # Kunlik, oylik statistikalar
    today = datetime.now().strftime("%Y-%m-%d")
    today_orders = [o for o in orders if o.get('date', '').startswith(today)]
    today_sales = sum(o.get('total', 0) for o in today_orders)
    
    stats_text = (
        f"📊 *Bot statistikasi*\n\n"
        f"👥 *Foydalanuvchilar:* {total_users}\n"
        f"🛍️ *Mahsulotlar:* {total_products}\n"
        f"📦 *Jami zakazlar:* {total_orders}\n"
        f"💰 *Umumiy sotuv:* {format_price(total_sales)} so'm\n"
        f"📈 *O'rtacha zakaz:* {format_price(total_sales // total_orders) if total_orders > 0 else 0} so'm\n\n"
        f"📅 *Bugungi statistik:*\n"
        f"📦 Zakazlar: {len(today_orders)}\n"
        f"💰 Sotuv: {format_price(today_sales)} so'm"
    )
    
    bot.send_message(message.chat.id, stats_text, parse_mode="Markdown")


@bot.message_handler(func=lambda m: m.text == "📦 Barcha zakazlar")
def list_all_orders(message):
    """Barcha zakazlarni ko'rish"""
    if not is_admin(message.from_user.id):
        return
    
    orders = get_orders()
    if not orders:
        bot.send_message(message.chat.id, "📭 *Hozircha zakaz yo'q*", parse_mode="Markdown")
        return
    
    for order in orders[-20:]:  # Oxirgi 20 ta zakaz
        user = get_users().get(str(order.get('user_id')), {})
        text = (
            f"🆔 *Zakaz #{order['id']}*\n"
            f"📅 *Sana:* {order['date']}\n"
            f"👤 *Mijoz:* {order.get('user_name', 'Noma\'lum')}\n"
            f"📞 *Telefon:* {order.get('user_phone', 'Noma\'lum')}\n"
            f"📍 *Manzil:* {order.get('address', 'Noma\'lum')}\n"
            f"💰 *Jami:* {format_price(order['total'])} so'm\n"
            f"📦 *Mahsulotlar:*\n"
        )
        
        for item in order.get('items', []):
            text += f"  • {item.get('name')} x{item.get('qty', 1)} = {format_price(item.get('price', 0) * item.get('qty', 1))} so'm\n"
        
        if order.get('note'):
            text += f"💬 *Izoh:* {order['note']}\n"
        
        text += f"✅ *Holat:* {'Yangi' if order.get('status') == 'new' else order.get('status')}"
        
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("✅ Qabul qilindi", callback_data=f"order_status_{order['id']}_accepted"),
            types.InlineKeyboardButton("🚚 Yetkazilmoqda", callback_data=f"order_status_{order['id']}_delivering"),
            types.InlineKeyboardButton("✅ Yetkazildi", callback_data=f"order_status_{order['id']}_delivered")
        )
        
        bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=markup)


@bot.callback_query_handler(func=lambda call: call.data.startswith('order_status_'))
def handle_order_status(call):
    """Zakaz holatini o'zgartirish"""
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Siz admin emassiz!", show_alert=True)
        return
    
    parts = call.data.split('_')
    order_id = int(parts[2])
    status = parts[3]
    
    orders = get_orders()
    for order in orders:
        if order['id'] == order_id:
            order['status'] = status
            save_orders(orders)
            
            # Mijozga xabar
            try:
                status_text = {
                    'accepted': '✅ Qabul qilindi',
                    'delivering': '🚚 Yetkazilmoqda',
                    'delivered': '✅ Yetkazildi'
                }.get(status, status)
                
                bot.send_message(
                    order['user_id'],
                    f"📦 *Zakaz #{order_id} holati:* {status_text}\n\n"
                    f"Tez orada siz bilan bog'lanamiz! ☎️",
                    parse_mode="Markdown"
                )
            except:
                pass
            
            bot.answer_callback_query(call.id, f"Holat o'zgartirildi: {status_text}")
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
            break


@bot.callback_query_handler(func=lambda call: call.data.startswith('del_prod_'))
def delete_product(call):
    """Mahsulotni o'chirish"""
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "Siz admin emassiz!", show_alert=True)
        return
    
    product_id = int(call.data.split('_')[2])
    products = get_products()
    products = [p for p in products if p['id'] != product_id]
    save_products(products)
    
    bot.answer_callback_query(call.id, "Mahsulot o'chirildi!")
    bot.edit_message_caption(
        call.message.chat.id,
        call.message.message_id,
        caption="✅ Mahsulot o'chirildi"
    )


@bot.message_handler(func=lambda m: m.text == "🔙 Asosiy menyu")
def back_to_main(message):
    """Asosiy menyuga qaytish"""
    user_states[message.from_user.id] = {"state": "idle"}
    bot.send_message(
        message.chat.id,
        "🏠 *Asosiy menyu*",
        parse_mode="Markdown",
        reply_markup=get_main_menu(message.from_user.id)
    )


@bot.message_handler(func=lambda m: m.text == "❌ Bekor qilish")
def cancel_action(message):
    """Amalni bekor qilish"""
    user_states[message.from_user.id] = {"state": "idle"}
    markup = get_admin_menu() if is_admin(message.from_user.id) else get_main_menu(message.from_user.id)
    bot.send_message(
        message.chat.id,
        "❌ *Amal bekor qilindi*",
        parse_mode="Markdown",
        reply_markup=markup
    )


@bot.message_handler(func=lambda m: m.text == "📦 Mening zakazlarim")
def my_orders(message):
    """Foydalanuvchi zakazlari"""
    user_id = message.from_user.id
    orders = get_orders()
    user_orders = [o for o in orders if o.get("user_id") == user_id]
    
    if not user_orders:
        bot.send_message(
            message.chat.id,
            "📭 *Sizning zakazlaringiz yo'q*\n\n"
            "Do'konni ochib xarid qilishingiz mumkin 🛍️",
            parse_mode="Markdown"
        )
        return
    
    for order in user_orders[-10:]:
        status_text = {
            'new': '🆕 Yangi',
            'accepted': '✅ Qabul qilingan',
            'delivering': '🚚 Yetkazilmoqda',
            'delivered': '✅ Yetkazilgan'
        }.get(order.get('status', 'new'), '🆕 Yangi')
        
        text = (
            f"📦 *Zakaz #{order['id']}*\n"
            f"📅 {order['date']}\n"
            f"💰 {format_price(order['total'])} so'm\n"
            f"📦 {len(order.get('items', []))} ta mahsulot\n"
            f"✅ *Holat:* {status_text}\n"
            f"─" * 20 + "\n"
        )
        bot.send_message(message.chat.id, text, parse_mode="Markdown")


@bot.message_handler(func=lambda m: m.text == "📞 Aloqa")
def contact_info(message):
    """Aloqa ma'lumotlari"""
    text = (
        "📞 *Bog'lanish ma'lumotlari*\n\n"
        "👨‍💼 *Admin:* @admin_username\n"
        "📱 *Telefon:* +998 XX XXX XX XX\n"
        "📧 *Email:* admin@example.com\n\n"
        "⚠️ *Ish vaqti:* 9:00 - 21:00\n"
        "📅 *Dam olish kuni:* Yakshanba"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")


@bot.message_handler(func=lambda m: m.text == "ℹ️ Yordam")
def help_info(message):
    """Yordam ma'lumotlari"""
    text = (
        "ℹ️ *Yordam bo'limi*\n\n"
        "🛍️ *Do'konni ochish* - Mahsulotlarni ko'rish va xarid qilish\n"
        "📦 *Mening zakazlarim* - Zakaz tarixini ko'rish\n"
        "📞 *Aloqa* - Admin bilan bog'lanish\n\n"
        "❓ *Savollaringiz bo'lsa:* @admin_username\n\n"
        "📝 *Zakaz berish tartibi:*\n"
        "1. Do'konni oching\n"
        "2. Mahsulotlarni tanlang\n"
        "3. Savatga qo'shing\n"
        "4. Manzilni kiriting\n"
        "5. Zakazni tasdiqlang"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")


@bot.message_handler(content_types=["web_app_data"])
def handle_webapp_order(message):
    """Web App dan zakaz qabul qilish"""
    try:
        data = json.loads(message.web_app_data.data)
        logger.info(f"New order from {message.from_user.id}: {data}")
        
        orders = get_orders()
        users = get_users()
        user_info = users.get(str(message.from_user.id), {})
        
        # Yangi zakaz
        new_order = {
            "id": len(orders) + 1,
            "user_id": message.from_user.id,
            "user_name": user_info.get('first_name', message.from_user.first_name),
            "user_phone": user_info.get('phone', 'Noma\'lum'),
            "items": data.get("items", []),
            "total": data.get("total", 0),
            "address": data.get("address", ""),
            "note": data.get("note", ""),
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "new"
        }
        
        orders.append(new_order)
        save_orders(orders)
        
        # Foydalanuvchiga xabar
        items_text = "\n".join([
            f"• {item.get('name', '')} x{item.get('qty', 1)} = {format_price(item.get('price', 0) * item.get('qty', 1))} so'm"
            for item in new_order['items']
        ])
        
        bot.send_message(
            message.chat.id,
            f"✅ *Zakaz qabul qilindi!*\n\n"
            f"🆔 *Zakaz #:* {new_order['id']}\n"
            f"💰 *Jami:* {format_price(new_order['total'])} so'm\n\n"
            f"📦 *Mahsulotlar:*\n{items_text}\n\n"
            f"📍 *Manzil:* {new_order['address']}\n"
            f"💬 *Izoh:* {new_order['note'] or 'Yo‘q'}\n\n"
            f"Tez orada admin siz bilan bog'lanadi! ☎️\n"
            f"Zakaz holatini \"Mening zakazlarim\" bo'limidan kuzatishingiz mumkin.",
            parse_mode="Markdown"
        )
        
        # Adminlarga to'liq ma'lumot bilan xabar
        for admin_id in ADMIN_IDS:
            try:
                admin_text = (
                    f"🆕 *YANGI ZAKAZ!* 🆕\n\n"
                    f"📋 *Zakaz ma'lumotlari:*\n"
                    f"🆔 Zakaz ID: #{new_order['id']}\n"
                    f"📅 Sana: {new_order['date']}\n\n"
                    f"👤 *Mijoz ma'lumotlari:*\n"
                    f"Ismi: {new_order['user_name']}\n"
                    f"Telefon: {new_order['user_phone']}\n"
                    f"Telegram ID: {new_order['user_id']}\n"
                    f"Username: @{user_info.get('username', 'None')}\n\n"
                    f"📍 *Yetkazib berish manzili:*\n{new_order['address']}\n\n"
                    f"📦 *Zakaz tarkibi:*\n"
                )
                
                for item in new_order['items']:
                    admin_text += f"  • {item.get('name')} x{item.get('qty', 1)} = {format_price(item.get('price', 0) * item.get('qty', 1))} so'm\n"
                
                admin_text += f"\n💰 *Jami summa:* {format_price(new_order['total'])} so'm\n"
                
                if new_order.get('note'):
                    admin_text += f"\n💬 *Mijoz izohi:*\n{new_order['note']}\n"
                
                admin_text += f"\n🔄 *Holat:* Yangi\n"
                admin_text += f"─" * 30 + "\n"
                admin_text += f"📊 /stats - Statistika ko'rish\n"
                admin_text += f"📦 /orders - Barcha zakazlar"
                
                markup = types.InlineKeyboardMarkup()
                markup.add(
                    types.InlineKeyboardButton("✅ Qabul qilish", callback_data=f"order_status_{new_order['id']}_accepted"),
                    types.InlineKeyboardButton("🚚 Yetkazish", callback_data=f"order_status_{new_order['id']}_delivering"),
                    types.InlineKeyboardButton("👤 Mijoz bilan bog'lanish", url=f"tg://user?id={new_order['user_id']}")
                )
                
                bot.send_message(
                    admin_id,
                    admin_text,
                    parse_mode="Markdown",
                    reply_markup=markup
                )
            except Exception as e:
                logger.error(f"Error sending to admin: {e}")
        
    except Exception as e:
        logger.error(f"WebApp order error: {e}")
        bot.send_message(
            message.chat.id,
            "❌ *Xatolik yuz berdi!*\n\n"
            "Iltimos, qaytadan urinib ko'ring.\n"
            "Agar xatolik takrorlansa, admin bilan bog'lang.",
            parse_mode="Markdown"
        )


@bot.message_handler(content_types=["text"])
def handle_states(message):
    """State larni boshqarish (Mahsulot qo'shish)"""
    user_id = message.from_user.id
    state_data = user_states.get(user_id, {"state": "idle"})
    state = state_data.get("state", "idle")
    
    # Mahsulot qo'shish state lari
    if state == "add_name":
        user_states[user_id]["temp"]["name"] = message.text
        user_states[user_id]["state"] = "add_desc"
        bot.send_message(
            message.chat.id,
            "📝 *2/6 - Tavsif*\n\n"
            "Mahsulot tavsifini kiriting:",
            parse_mode="Markdown"
        )
    
    elif state == "add_desc":
        user_states[user_id]["temp"]["description"] = message.text
        user_states[user_id]["state"] = "add_price"
        bot.send_message(
            message.chat.id,
            "💰 *3/6 - Narx*\n\n"
            "Mahsulot narxini kiriting (so'mda):\n"
            "Masalan: 50000",
            parse_mode="Markdown"
        )
    
    elif state == "add_price":
        try:
            price = int(message.text.replace(" ", "").replace(",", ""))
            if price <= 0:
                raise ValueError
                
            user_states[user_id]["temp"]["price"] = price
            user_states[user_id]["state"] = "add_category"
            
            # Kategoriya tanlash
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
            categories = ["👗 Kiyim", "👟 Poyabzal", "💄 Kosmetika", "📱 Elektronika", 
                         "🏠 Uy jihozlari", "🍕 Oziq-ovqat", "🎁 Boshqa"]
            for cat in categories:
                markup.add(types.KeyboardButton(cat))
            markup.add(types.KeyboardButton("❌ Bekor qilish"))
            
            bot.send_message(
                message.chat.id,
                "🏷️ *4/6 - Kategoriya*\n\n"
                "Mahsulot kategoriyasini tanlang:",
                parse_mode="Markdown",
                reply_markup=markup
            )
        except:
            bot.send_message(
                message.chat.id,
                "❌ *Xato!*\n\n"
                "Iltimos, to'g'ri narx kiriting (faqat raqam):\n"
                "Masalan: 50000",
                parse_mode="Markdown"
            )
    
    elif state == "add_category":
        user_states[user_id]["temp"]["category"] = message.text
        user_states[user_id]["state"] = "add_photos"
        bot.send_message(
            message.chat.id,
            "📸 *5/6 - Rasmlar*\n\n"
            "Endi mahsulot rasmlarini yuboring.\n"
            "Bir vaqtning o'zida 5 tagacha rasm yuborishingiz mumkin.\n\n"
            "Rasmlarni yuboring yoki 'Keyingi' tugmasini bosing:",
            parse_mode="Markdown",
            reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add(
                types.KeyboardButton("⏭️ Keyingi"),
                types.KeyboardButton("❌ Bekor qilish")
            )
        )
        user_states[user_id]["temp"]["photos"] = []
    
    elif state == "add_photos":
        user_states[user_id]["state"] = "add_available"
        
        # Mahsulotni saqlash
        temp = user_states[user_id]["temp"]
        products = get_products()
        
        new_product = {
            "id": len(products) + 1,
            "name": temp["name"],
            "description": temp["description"],
            "price": temp["price"],
            "category": temp["category"],
            "photos": temp.get("photos", []),
            "available": True,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        products.append(new_product)
        save_products(products)
        
        # State ni tozalash
        user_states[user_id] = {"state": "idle"}
        
        # Natijani ko'rsatish
        result_text = (
            f"✅ *Mahsulot muvaffaqiyatli qo'shildi!*\n\n"
            f"📌 *Nomi:* {new_product['name']}\n"
            f"💰 *Narxi:* {format_price(new_product['price'])} so'm\n"
            f"🏷 *Kategoriya:* {new_product['category']}\n"
            f"📸 *Rasmlar:* {len(new_product['photos'])} ta\n\n"
            f"Endi uni do'konda ko'rishingiz mumkin 🛍️"
        )
        
        # Agar rasm bo'lsa, rasm bilan yuborish
        if new_product['photos'] and os.path.exists(new_product['photos'][0][1:]):
            try:
                with open(new_product['photos'][0][1:], 'rb') as photo:
                    bot.send_photo(
                        message.chat.id,
                        photo,
                        caption=result_text,
                        parse_mode="Markdown",
                        reply_markup=get_admin_menu()
                    )
            except:
                bot.send_message(message.chat.id, result_text, parse_mode="Markdown", reply_markup=get_admin_menu())
        else:
            bot.send_message(message.chat.id, result_text, parse_mode="Markdown", reply_markup=get_admin_menu())


@bot.message_handler(content_types=["photo"])
def handle_photos(message):
    """Rasmlarni qabul qilish"""
    user_id = message.from_user.id
    state_data = user_states.get(user_id, {})
    
    if state_data.get("state") == "add_photos":
        temp = state_data.get("temp", {})
        photos = temp.get("photos", [])
        
        if len(photos) >= 5:
            bot.send_message(message.chat.id, "❌ Maksimum 5 ta rasm yuborishingiz mumkin!")
            return
        
        # Rasmni saqlash
        try:
            file_id = message.photo[-1].file_id
            file_info = bot.get_file(file_id)
            downloaded_file = bot.download_file(file_info.file_path)
            
            # Rasm nomi
            filename = f"product_{user_id}_{datetime.now().timestamp()}_{len(photos)+1}.jpg"
            filepath = os.path.join(PHOTOS_DIR, filename)
            
            with open(filepath, 'wb') as f:
                f.write(downloaded_file)
            
            photos.append(f"/{filepath}")
            user_states[user_id]["temp"]["photos"] = photos
            
            remaining = 5 - len(photos)
            bot.send_message(
                message.chat.id,
                f"✅ Rasm qabul qilindi! ({len(photos)}/5)\n"
                f"Yana {remaining} ta rasm yuborishingiz mumkin.\n\n"
                f"Rasmlar tugagach '⏭️ Keyingi' tugmasini bosing.",
                reply_markup=types.ReplyKeyboardMarkup(resize_keyboard=True).add(
                    types.KeyboardButton("⏭️ Keyingi"),
                    types.KeyboardButton("❌ Bekor qilish")
                )
            )
        except Exception as e:
            logger.error(f"Photo save error: {e}")
            bot.send_message(message.chat.id, "❌ Rasm saqlashda xatolik! Qaytadan urinib ko'ring.")


# ==================== FASTAPI ENDPOINTS ====================
@app.get("/")
async def home():
    """Bosh sahifa"""
    return HTMLResponse("""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Telegram Shop Bot</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                justify-content: center;
                align-items: center;
                padding: 20px;
            }
            .container {
                background: white;
                border-radius: 24px;
                padding: 40px;
                max-width: 500px;
                width: 100%;
                box-shadow: 0 20px 60px rgba(0,0,0,0.3);
                text-align: center;
            }
            h1 {
                color: #333;
                margin-bottom: 10px;
                font-size: 32px;
            }
            .status {
                background: #4CAF50;
                color: white;
                padding: 12px;
                border-radius: 12px;
                margin: 20px 0;
                font-weight: bold;
            }
            .stats {
                display: grid;
                grid-template-columns: repeat(2, 1fr);
                gap: 16px;
                margin: 20px 0;
            }
            .stat-card {
                background: #f5f5f5;
                padding: 16px;
                border-radius: 12px;
            }
            .stat-number {
                font-size: 28px;
                font-weight: bold;
                color: #667eea;
            }
            .stat-label {
                color: #666;
                margin-top: 5px;
            }
            .btn {
                display: inline-block;
                background: #667eea;
                color: white;
                padding: 12px 24px;
                text-decoration: none;
                border-radius: 12px;
                margin-top: 20px;
                font-weight: bold;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🛍️ Telegram Shop Bot</h1>
            <div class="status">✅ Bot ishlayapti</div>
            <div class="stats" id="stats">
                <div class="stat-card">
                    <div class="stat-number" id="users">-</div>
                    <div class="stat-label">Foydalanuvchilar</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="products">-</div>
                    <div class="stat-label">Mahsulotlar</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="orders">-</div>
                    <div class="stat-label">Zakazlar</div>
                </div>
                <div class="stat-card">
                    <div class="stat-number" id="sales">-</div>
                    <div class="stat-label">Sotuv (so'm)</div>
                </div>
            </div>
            <a href="/shop" class="btn">🛍️ Do'konni ochish</a>
        </div>
        <script>
            async function loadStats() {
                try {
                    const response = await fetch('/stats');
                    const data = await response.json();
                    document.getElementById('users').textContent = data.users;
                    document.getElementById('products').textContent = data.products;
                    document.getElementById('orders').textContent = data.orders;
                    document.getElementById('sales').textContent = (data.sales / 1000000).toFixed(1) + 'M';
                } catch(e) {
                    console.error('Error loading stats:', e);
                }
            }
            loadStats();
            setInterval(loadStats, 30000);
        </script>
    </body>
    </html>
    """)


@app.get("/shop")
async def shop_page():
    """Web App sahifasi"""
    with open("index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


@app.get("/webapp_products.json")
async def get_products_json():
    """Mahsulotlar API"""
    products = get_products()
    webapp_products = []
    for p in products:
        if p.get('available', True):
            webapp_products.append({
                "id": p['id'],
                "name": p['name'],
                "description": p.get('description', ''),
                "price": p['price'],
                "category": p.get('category', '🎁 Boshqa'),
                "photos": p.get('photos', []),
                "available": True
            })
    return JSONResponse(webapp_products)


@app.get("/stats")
async def get_stats():
    """Statistika API"""
    orders = get_orders()
    total_sales = sum(o.get('total', 0) for o in orders)
    return {
        "users": len(get_users()),
        "products": len(get_products()),
        "orders": len(orders),
        "sales": total_sales
    }


@app.post("/bot")
async def bot_webhook(request: Request):
    """Telegram webhook"""
    try:
        data = await request.json()
        update = telebot.types.Update.de_json(data)
        bot.process_new_updates([update])
        return {"ok": True}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return {"ok": False, "error": str(e)}


@app.on_event("startup")
async def startup_event():
    """Bot ishga tushganda"""
    logger.info("Starting bot...")
    
    # Namuna mahsulotlar
    if not os.path.exists(PRODUCTS_FILE):
        sample_products = [
            {
                "id": 1,
                "name": "Namuna Mahsulot",
                "description": "Bu test mahsulot. Admin tomonidan o'zgartirilishi mumkin.",
                "price": 50000,
                "category": "🎁 Boshqa",
                "photos": [],
                "available": True,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        ]
        save_products(sample_products)
        logger.info("Sample products created")
    
    # Webhook o'rnatish
    webhook_url = f"{RENDER_EXTERNAL_URL}/bot"
    try:
        bot.remove_webhook()
        bot.set_webhook(url=webhook_url)
        logger.info(f"✅ Webhook set: {webhook_url}")
    except Exception as e:
        logger.error(f"Webhook setup failed: {e}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
