import telebot
from telebot import types
import json
import os
from datetime import datetime, timedelta
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
import threading
import time
import random
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============ KONFIGURATSIYA ============
BOT_TOKEN = "8778358404:AAHmM4e2OnROyXLCsGXERCbXd3arzl7kPS0"
RENDER_EXTERNAL_URL = "https://bottt-02j7.onrender.com"
WEB_APP_URL = f"{RENDER_EXTERNAL_URL}/shop"

ADMIN_IDS = [8735360012]

# Fayllar
PRODUCTS_FILE = "products.json"
ORDERS_FILE = "orders.json"
USERS_FILE = "users.json"
ADDRESSES_FILE = "addresses.json"
FAVORITES_FILE = "favorites.json"
PROMO_FILE = "promo.json"
REVIEWS_FILE = "reviews.json"

bot = telebot.TeleBot(BOT_TOKEN)
app = FastAPI()

user_states = {}
order_timers = {}


# ============ YORDAMCHI FUNKSIYALAR ============
def load_json(filename, default):
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            return json.load(f)
    return default


def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_products():
    return load_json(PRODUCTS_FILE, [])


def get_orders():
    return load_json(ORDERS_FILE, [])


def get_users():
    return load_json(USERS_FILE, {})


def get_addresses():
    return load_json(ADDRESSES_FILE, {})


def get_favorites():
    return load_json(FAVORITES_FILE, {})


def get_promos():
    return load_json(PROMO_FILE, [])


def get_reviews():
    return load_json(REVIEWS_FILE, {})


def save_products(p):
    save_json(PRODUCTS_FILE, p)


def save_orders(o):
    save_json(ORDERS_FILE, o)


def save_users(u):
    save_json(USERS_FILE, u)


def save_addresses(a):
    save_json(ADDRESSES_FILE, a)


def save_favorites(f):
    save_json(FAVORITES_FILE, f)


def save_promos(p):
    save_json(PROMO_FILE, p)


def save_reviews(r):
    save_json(REVIEWS_FILE, r)


def is_admin(user_id):
    return user_id in ADMIN_IDS


def format_price(price):
    return f"{price:,}".replace(",", " ")


def format_phone(phone):
    if phone.startswith('+'):
        return phone
    return f"+{phone}"


# ============ KLAVIATURALAR ============
def get_main_menu(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    shop_btn = types.KeyboardButton(
        "🛍️ Do'kon",
        web_app=types.WebAppInfo(url=WEB_APP_URL)
    )
    markup.add(shop_btn)
    
    markup.add(
        types.KeyboardButton("📦 Mening zakazlarim"),
        types.KeyboardButton("❤️ Sevimlilar"),
        types.KeyboardButton("📍 Manzillarim"),
        types.KeyboardButton("🎁 Promo kod"),
        types.KeyboardButton("📞 Aloqa"),
        types.KeyboardButton("ℹ️ Yordam")
    )
    
    if is_admin(user_id):
        markup.add(types.KeyboardButton("👨‍💼 Admin panel"))
    
    return markup


def get_admin_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton("➕ Mahsulot qo'shish"),
        types.KeyboardButton("📋 Mahsulotlar"),
        types.KeyboardButton("📦 Zakazlar"),
        types.KeyboardButton("📊 Statistika"),
        types.KeyboardButton("🎁 Promo yaratish"),
        types.KeyboardButton("📢 Xabar yuborish")
    )
    markup.add(types.KeyboardButton("🔙 Asosiy menyu"))
    return markup


# ============ BOT HANDLERLAR ============
@bot.message_handler(commands=["start"])
def start(message):
    user_id = message.from_user.id
    users = get_users()
    
    if str(user_id) not in users:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        contact_btn = types.KeyboardButton("📱 Telefon raqam", request_contact=True)
        location_btn = types.KeyboardButton("📍 Lokatsiya", request_location=True)
        markup.add(contact_btn, location_btn)
        
        bot.send_message(
            message.chat.id,
            f"👋 *Assalomu alaykum {message.from_user.first_name}!*\n\n"
            "🚀 *Do'konimizga xush kelibsiz!*\n\n"
            "📝 Ro'yxatdan o'tish uchun telefon raqamingizni yuboring 👇",
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


@bot.message_handler(content_types=["contact", "location"])
def handle_contact_location(message):
    user_id = message.from_user.id
    
    if user_states.get(user_id, {}).get("state") == "waiting_contact":
        users = get_users()
        
        if message.contact:
            phone = message.contact.phone_number
        else:
            phone = users.get(str(user_id), {}).get("phone", "")
        
        users[str(user_id)] = {
            "user_id": user_id,
            "name": message.from_user.first_name,
            "phone": phone,
            "joined": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        
        if message.location:
            users[str(user_id)]["lat"] = message.location.latitude
            users[str(user_id)]["lon"] = message.location.longitude
        
        save_users(users)
        user_states[user_id] = {"state": "idle"}
        
        bot.send_message(
            message.chat.id,
            "✅ *Ro'yxatdan o'tdingiz!*\n\n"
            "Endi xarid qilishingiz mumkin 🛍️",
            parse_mode="Markdown",
            reply_markup=get_main_menu(user_id)
        )
        
        # Adminga xabar
        for admin_id in ADMIN_IDS:
            try:
                bot.send_message(
                    admin_id,
                    f"🆕 *Yangi foydalanuvchi!*\n\n"
                    f"👤 {message.from_user.first_name}\n"
                    f"📞 {phone}\n"
                    f"🆔 {user_id}",
                    parse_mode="Markdown"
                )
            except:
                pass


@bot.message_handler(func=lambda m: m.text == "📍 Manzillarim")
def my_addresses(message):
    user_id = message.from_user.id
    addresses = get_addresses().get(str(user_id), [])
    
    if not addresses:
        bot.send_message(
            message.chat.id,
            "📍 *Sizning manzillaringiz yo'q*\n\n"
            "Do'kondan zakaz berishda manzil saqlanadi.",
            parse_mode="Markdown"
        )
        return
    
    text = "📍 *Sizning manzillaringiz:*\n\n"
    for i, addr in enumerate(addresses, 1):
        text += f"{i}. {addr}\n"
    
    bot.send_message(message.chat.id, text, parse_mode="Markdown")


@bot.message_handler(func=lambda m: m.text == "❤️ Sevimlilar")
def my_favorites(message):
    user_id = message.from_user.id
    favorites = get_favorites().get(str(user_id), [])
    products = get_products()
    
    if not favorites:
        bot.send_message(
            message.chat.id,
            "❤️ *Sevimli mahsulotlaringiz yo'q*\n\n"
            "Mahsulotlarni yurakcha bosib saqlang.",
            parse_mode="Markdown"
        )
        return
    
    text = "❤️ *Sevimli mahsulotlaringiz:*\n\n"
    for fav_id in favorites:
        product = next((p for p in products if p['id'] == fav_id), None)
        if product:
            text += f"• {product['name']} - {format_price(product['price'])} so'm\n"
    
    bot.send_message(message.chat.id, text, parse_mode="Markdown")


@bot.message_handler(func=lambda m: m.text == "🎁 Promo kod")
def promo_code(message):
    bot.send_message(
        message.chat.id,
        "🎁 *Promo kodlar*\n\n"
        "Promo kodingizni yuboring:\n"
        "Masalan: WELCOME10",
        parse_mode="Markdown"
    )
    user_states[message.from_user.id] = {"state": "waiting_promo"}


@bot.message_handler(func=lambda m: m.text == "📦 Mening zakazlarim")
def my_orders(message):
    user_id = message.from_user.id
    orders = get_orders()
    user_orders = [o for o in orders if o.get("user_id") == user_id][-10:]
    
    if not user_orders:
        bot.send_message(
            message.chat.id,
            "📭 *Zakazlaringiz yo'q*\n\n"
            "Do'konni ochib xarid qiling 🛍️",
            parse_mode="Markdown"
        )
        return
    
    for order in user_orders:
        status_emoji = {
            "new": "🆕",
            "accepted": "✅",
            "preparing": "🔧",
            "courier": "🚚",
            "delivering": "🚛",
            "delivered": "📦",
            "cancelled": "❌"
        }.get(order.get("status", "new"), "🆕")
        
        text = f"""
{status_emoji} *Zakaz #{order['id']}*
📅 {order['date']}
💰 {format_price(order['total'])} so'm
📊 *Holat:* {order.get('status', 'Yangi')}

📦 *Mahsulotlar:*
"""
        for item in order.get("items", []):
            text += f"  • {item['name']} x{item['qty']}\n"
        
        if order.get("eta"):
            text += f"\n⏱ *Yetib borish vaqti:* {order['eta']}"
        
        if order.get("courier_phone"):
            text += f"\n📞 *Kuryer:* {order['courier_phone']}"
        
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🔄 Qayta zakaz", callback_data=f"reorder_{order['id']}"))
        
        if order.get("status") == "delivered":
            markup.add(types.InlineKeyboardButton("⭐ Baholash", callback_data=f"review_{order['id']}"))
        
        bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=markup)


@bot.message_handler(func=lambda m: m.text == "👨‍💼 Admin panel")
def admin_panel(message):
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "❌ Admin emassiz!")
        return
    bot.send_message(message.chat.id, "👨‍💼 *Admin panel*", parse_mode="Markdown", reply_markup=get_admin_menu())


@bot.message_handler(func=lambda m: m.text == "🔙 Asosiy menyu")
def back_main(message):
    user_states[message.from_user.id] = {"state": "idle"}
    bot.send_message(
        message.chat.id,
        "🏠 *Asosiy menyu*",
        parse_mode="Markdown",
        reply_markup=get_main_menu(message.from_user.id)
    )


@bot.message_handler(func=lambda m: m.text == "➕ Mahsulot qo'shish")
def add_product(message):
    if not is_admin(message.from_user.id):
        return
    
    user_states[message.from_user.id] = {"state": "add_name", "temp": {}}
    bot.send_message(
        message.chat.id,
        "1️⃣ *Mahsulot nomi:*",
        parse_mode="Markdown",
        reply_markup=get_cancel_btn()
    )


@bot.message_handler(func=lambda m: m.text == "📋 Mahsulotlar")
def list_products_admin(message):
    if not is_admin(message.from_user.id):
        return
    
    products = get_products()
    if not products:
        bot.send_message(message.chat.id, "📭 Mahsulot yo'q")
        return
    
    for p in products:
        text = f"""
🆔 #{p['id']}
📌 *{p['name']}*
💰 {format_price(p['price'])} so'm
🏷 {p['category']}
⭐ Reyting: {p.get('rating', 0)}
"""
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("🗑 O'chirish", callback_data=f"del_prod_{p['id']}"),
            types.InlineKeyboardButton("✏️ Tahrirlash", callback_data=f"edit_prod_{p['id']}")
        )
        bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=markup)


@bot.message_handler(func=lambda m: m.text == "📦 Zakazlar")
def list_orders_admin(message):
    if not is_admin(message.from_user.id):
        return
    
    orders = get_orders()
    if not orders:
        bot.send_message(message.chat.id, "📭 Zakaz yo'q")
        return
    
    for order in orders[-20:]:
        text = f"""
🆔 *Zakaz #{order['id']}*
👤 {order.get('user_name', 'Noma\'lum')}
📞 {order.get('user_phone', 'Noma\'lum')}
📍 {order.get('address', 'Noma\'lum')}
💰 {format_price(order['total'])} so'm
📅 {order['date']}
📊 Holat: {order.get('status', 'new')}
"""
        markup = types.InlineKeyboardMarkup(row_width=2)
        markup.add(
            types.InlineKeyboardButton("✅ Qabul", callback_data=f"status_{order['id']}_accepted"),
            types.InlineKeyboardButton("🔧 Tayyor", callback_data=f"status_{order['id']}_preparing"),
            types.InlineKeyboardButton("🚚 Kuryerda", callback_data=f"status_{order['id']}_courier"),
            types.InlineKeyboardButton("🚛 Yetkazish", callback_data=f"status_{order['id']}_delivering"),
            types.InlineKeyboardButton("📦 Yetkazildi", callback_data=f"status_{order['id']}_delivered"),
            types.InlineKeyboardButton("❌ Bekor", callback_data=f"status_{order['id']}_cancelled")
        )
        bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=markup)


@bot.message_handler(func=lambda m: m.text == "📊 Statistika")
def show_stats(message):
    if not is_admin(message.from_user.id):
        return
    
    products = get_products()
    orders = get_orders()
    users = get_users()
    
    total_sales = sum(o.get('total', 0) for o in orders)
    today = datetime.now().strftime("%Y-%m-%d")
    today_orders = [o for o in orders if o.get('date', '').startswith(today)]
    
    # Eng ko'p sotilgan
    product_sales = {}
    for order in orders:
        for item in order.get('items', []):
            name = item.get('name')
            if name:
                product_sales[name] = product_sales.get(name, 0) + item.get('qty', 0)
    
    top_products = sorted(product_sales.items(), key=lambda x: x[1], reverse=True)[:5]
    
    text = f"""
📊 *STATISTIKA*

👥 Foydalanuvchilar: {len(users)}
🛍️ Mahsulotlar: {len(products)}
📦 Jami zakazlar: {len(orders)}
💰 Umumiy sotuv: {format_price(total_sales)} so'm

📅 *Bugungi:*
Zakazlar: {len(today_orders)}
Sotuv: {format_price(sum(o.get('total', 0) for o in today_orders))} so'm

🏆 *Eng ko'p sotilgan:*
"""
    for i, (name, qty) in enumerate(top_products, 1):
        text += f"{i}. {name} - {qty} ta\n"
    
    bot.send_message(message.chat.id, text, parse_mode="Markdown")


@bot.message_handler(func=lambda m: m.text == "🎁 Promo yaratish")
def create_promo(message):
    if not is_admin(message.from_user.id):
        return
    
    user_states[message.from_user.id] = {"state": "promo_code", "temp": {}}
    bot.send_message(
        message.chat.id,
        "🎁 *Promo kod yaratish*\n\n"
        "1. Promo kod nomini kiriting (masalan: WELCOME10):",
        parse_mode="Markdown"
    )


@bot.message_handler(func=lambda m: m.text == "📢 Xabar yuborish")
def broadcast_message(message):
    if not is_admin(message.from_user.id):
        return
    
    user_states[message.from_user.id] = {"state": "broadcast"}
    bot.send_message(
        message.chat.id,
        "📢 *Xabar yuborish*\n\n"
        "Yubormoqchi bo'lgan xabaringizni yozing:",
        parse_mode="Markdown"
    )


@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    # Status o'zgartirish
    if call.data.startswith("status_"):
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "Admin emassiz!")
            return
        
        parts = call.data.split("_")
        order_id = int(parts[1])
        status = parts[2]
        
        orders = get_orders()
        for order in orders:
            if order['id'] == order_id:
                order['status'] = status
                order['status_updated'] = datetime.now().strftime("%Y-%m-%d %H:%M")
                
                # ETA qo'shish
                if status == "delivering":
                    eta_minutes = random.randint(15, 45)
                    order['eta'] = f"{eta_minutes} daqiqa"
                
                # Kuryer telefoni
                if status == "courier":
                    order['courier_phone'] = "+998 XX XXX XX XX"
                
                save_orders(orders)
                
                # Foydalanuvchiga xabar
                status_text = {
                    "accepted": "✅ Qabul qilindi",
                    "preparing": "🔧 Tayyorlanmoqda",
                    "courier": "🚚 Kuryerga berildi",
                    "delivering": "🚛 Yetkazilmoqda",
                    "delivered": "📦 Yetkazildi",
                    "cancelled": "❌ Bekor qilindi"
                }.get(status, status)
                
                try:
                    bot.send_message(
                        order['user_id'],
                        f"🔄 *Zakaz #{order_id} holati:* {status_text}\n\n"
                        f"📅 {datetime.now().strftime('%H:%M')}\n"
                        f"{'⏱ Yetib borish vaqti: ' + order['eta'] if order.get('eta') else ''}\n"
                        f"{'📞 Kuryer: ' + order.get('courier_phone', '') if order.get('courier_phone') else ''}",
                        parse_mode="Markdown"
                    )
                except:
                    pass
                
                bot.answer_callback_query(call.id, f"Holat: {status_text}")
                break
    
    # Mahsulot o'chirish
    elif call.data.startswith("del_prod_"):
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "Admin emassiz!")
            return
        
        product_id = int(call.data.split("_")[2])
        products = get_products()
        products = [p for p in products if p['id'] != product_id]
        save_products(products)
        bot.answer_callback_query(call.id, "Mahsulot o'chirildi!")
    
    # Qayta zakaz
    elif call.data.startswith("reorder_"):
        order_id = int(call.data.split("_")[1])
        orders = get_orders()
        order = next((o for o in orders if o['id'] == order_id), None)
        
        if order:
            addresses = get_addresses().get(str(call.from_user.id), [])
            if addresses:
                last_address = addresses[-1]
            else:
                last_address = order.get('address', '')
            
            # Yangi zakaz yaratish
            new_order = {
                "id": len(orders) + 1,
                "user_id": call.from_user.id,
                "user_name": order.get('user_name'),
                "user_phone": order.get('user_phone'),
                "items": order.get('items', []),
                "total": order.get('total', 0),
                "address": last_address,
                "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
                "status": "new"
            }
            
            orders.append(new_order)
            save_orders(orders)
            
            bot.answer_callback_query(call.id, "Zakaz qayta berildi!")
            bot.send_message(
                call.message.chat.id,
                f"✅ *Zakaz #{new_order['id']} qayta berildi!*\n"
                f"💰 {format_price(new_order['total'])} so'm",
                parse_mode="Markdown"
            )
    
    # Baholash
    elif call.data.startswith("review_"):
        user_states[call.from_user.id] = {"state": "waiting_review", "temp": {"order_id": int(call.data.split("_")[1])}}
        bot.send_message(
            call.message.chat.id,
            "⭐ *Mahsulotni baholang!*\n\n"
            "1 dan 5 gacha baho bering:",
            parse_mode="Markdown"
        )
    
    bot.answer_callback_query(call.id)


@bot.message_handler(content_types=["text"])
def handle_states(message):
    user_id = message.from_user.id
    state_data = user_states.get(user_id, {})
    state = state_data.get("state", "idle")
    
    # Mahsulot qo'shish
    if state == "add_name":
        user_states[user_id]["temp"]["name"] = message.text
        user_states[user_id]["state"] = "add_price"
        bot.send_message(message.chat.id, "2️⃣ *Narxi (so'mda):*", parse_mode="Markdown")
    
    elif state == "add_price":
        try:
            price = int(message.text.replace(" ", ""))
            user_states[user_id]["temp"]["price"] = price
            user_states[user_id]["state"] = "add_category"
            
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
            for cat in ["👗 Kiyim", "👟 Poyabzal", "📱 Elektronika", "🏠 Uy jihozlari", "🍕 Oziq-ovqat", "🎁 Boshqa"]:
                markup.add(types.KeyboardButton(cat))
            markup.add(types.KeyboardButton("❌ Bekor qilish"))
            
            bot.send_message(message.chat.id, "3️⃣ *Kategoriyani tanlang:*", parse_mode="Markdown", reply_markup=markup)
        except:
            bot.send_message(message.chat.id, "❌ Son kiriting!")
    
    elif state == "add_category":
        temp = user_states[user_id]["temp"]
        temp["category"] = message.text
        
        products = get_products()
        new_product = {
            "id": len(products) + 1,
            "name": temp["name"],
            "price": temp["price"],
            "category": temp["category"],
            "description": "",
            "rating": 0,
            "reviews_count": 0,
            "available": True
        }
        
        products.append(new_product)
        save_products(products)
        user_states[user_id] = {"state": "idle"}
        
        bot.send_message(
            message.chat.id,
            f"✅ *Mahsulot qo'shildi!*\n\n"
            f"📌 {new_product['name']}\n"
            f"💰 {format_price(new_product['price'])} so'm",
            parse_mode="Markdown",
            reply_markup=get_admin_menu()
        )
    
    # Promo kod
    elif state == "waiting_promo":
        promos = get_promos()
        promo = next((p for p in promos if p['code'] == message.text.upper()), None)
        
        if promo and promo.get('active', True):
            user_states[user_id] = {"state": "idle"}
            bot.send_message(
                message.chat.id,
                f"✅ *Promo kod aktiv!\n🎁 {promo['discount']}% chegirma*",
                parse_mode="Markdown"
            )
        else:
            bot.send_message(message.chat.id, "❌ Promo kod topilmadi yoki muddati o'tgan!")
            user_states[user_id] = {"state": "idle"}
    
    # Broadcast
    elif state == "broadcast":
        if not is_admin(user_id):
            return
        
        users = get_users()
        success = 0
        fail = 0
        
        bot.send_message(message.chat.id, "📢 Xabar yuborilmoqda...")
        
        for user_id_str, user in users.items():
            try:
                bot.send_message(int(user_id_str), f"📢 *Xabar*\n\n{message.text}", parse_mode="Markdown")
                success += 1
            except:
                fail += 1
        
        bot.send_message(
            message.chat.id,
            f"✅ Xabar yuborildi!\n\n"
            f"✅ Yuborildi: {success}\n"
            f"❌ Yuborilmadi: {fail}",
            reply_markup=get_admin_menu()
        )
        user_states[user_id] = {"state": "idle"}
    
    # Baholash
    elif state == "waiting_review":
        try:
            rating = int(message.text)
            if 1 <= rating <= 5:
                order_id = state_data["temp"]["order_id"]
                orders = get_orders()
                order = next((o for o in orders if o['id'] == order_id), None)
                
                if order:
                    reviews = get_reviews()
                    if str(order_id) not in reviews:
                        reviews[str(order_id)] = {
                            "user_id": user_id,
                            "rating": rating,
                            "date": datetime.now().strftime("%Y-%m-%d %H:%M")
                        }
                        save_reviews(reviews)
                        
                        # Mahsulot reytingini yangilash
                        products = get_products()
                        for item in order.get('items', []):
                            product = next((p for p in products if p['name'] == item['name']), None)
                            if product:
                                old_rating = product.get('rating', 0)
                                old_count = product.get('reviews_count', 0)
                                new_count = old_count + 1
                                new_rating = (old_rating * old_count + rating) / new_count
                                product['rating'] = round(new_rating, 1)
                                product['reviews_count'] = new_count
                        
                        save_products(products)
                        
                        bot.send_message(
                            message.chat.id,
                            f"⭐ *Rahmat!* Sizning bahoingiz: {rating}/5",
                            parse_mode="Markdown"
                        )
            else:
                bot.send_message(message.chat.id, "❌ 1 dan 5 gacha son kiriting!")
        except:
            bot.send_message(message.chat.id, "❌ Son kiriting!")
        
        user_states[user_id] = {"state": "idle"}


@bot.message_handler(content_types=["web_app_data"])
def handle_order(message):
    try:
        data = json.loads(message.web_app_data.data)
        orders = get_orders()
        users = get_users()
        user = users.get(str(message.from_user.id), {})
        
        # Manzilni saqlash
        addresses = get_addresses()
        user_addresses = addresses.get(str(message.from_user.id), [])
        address = data.get("address", "")
        if address and address not in user_addresses:
            user_addresses.append(address)
            addresses[str(message.from_user.id)] = user_addresses[-5:]  # Oxirgi 5 ta manzil
            save_addresses(addresses)
        
        new_order = {
            "id": len(orders) + 1,
            "user_id": message.from_user.id,
            "user_name": message.from_user.first_name,
            "user_phone": user.get("phone", "Noma'lum"),
            "items": data.get("items", []),
            "total": data.get("total", 0),
            "address": address,
            "note": data.get("note", ""),
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "status": "new"
        }
        
        orders.append(new_order)
        save_orders(orders)
        
        # Foydalanuvchiga xabar
        bot.send_message(
            message.chat.id,
            f"✅ *Zakaz #{new_order['id']} qabul qilindi!*\n\n"
            f"💰 {format_price(new_order['total'])} so'm\n"
            f"📍 {address}\n\n"
            f"Holatni \"Mening zakazlarim\" bo'limidan kuzatishingiz mumkin.",
            parse_mode="Markdown"
        )
        
        # Adminga xabar
        items_text = ""
        for item in new_order['items']:
            items_text += f"• {item['name']} x{item['qty']} = {format_price(item['price'] * item['qty'])} so'm\n"
        
        admin_text = f"""
🆕 *YANGI ZAKAZ #{new_order['id']}*

👤 {new_order['user_name']}
📞 {new_order['user_phone']}
📍 {new_order['address']}

📦 *Mahsulotlar:*
{items_text}
💰 *Jami:* {format_price(new_order['total'])} so'm
💬 *Izoh:* {new_order['note'] or 'Yo\'q'}

📅 {new_order['date']}
"""
        for admin_id in ADMIN_IDS:
            try:
                bot.send_message(admin_id, admin_text, parse_mode="Markdown")
            except:
                pass
        
        # Abandoned cart eslatmasi uchun timer
        def remind_user():
            try:
                bot.send_message(
                    message.from_user.id,
                    "🛒 *Savatda mahsulotlaringiz qoldi!*\n\n"
                    "Zakaz berishni davom ettiring yoki do'konni oching.",
                    parse_mode="Markdown"
                )
            except:
                pass
        
        timer = threading.Timer(1800, remind_user)  # 30 daqiqa
        order_timers[new_order['id']] = timer
        
    except Exception as e:
        logger.error(f"Order error: {e}")
        bot.send_message(message.chat.id, "❌ Xatolik yuz berdi!")


def get_cancel_btn():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("❌ Bekor qilish"))
    return markup


# ============ FASTAPI ============
@app.get("/")
def home():
    return {"status": "Bot ishlayapti", "version": "3.0"}


@app.get("/shop")
def shop():
    html = open("index.html", "r", encoding="utf-8").read()
    return HTMLResponse(content=html)


@app.get("/webapp_products.json")
def products_json():
    products = []
    for p in get_products():
        if p.get("available", True):
            products.append({
                "id": p["id"],
                "name": p["name"],
                "price": p["price"],
                "category": p["category"],
                "description": p.get("description", ""),
                "rating": p.get("rating", 0)
            })
    return JSONResponse(products)


@app.get("/user_data/{user_id}")
def user_data(user_id: int):
    users = get_users()
    addresses = get_addresses()
    favorites = get_favorites()
    
    return {
        "phone": users.get(str(user_id), {}).get("phone", ""),
        "addresses": addresses.get(str(user_id), []),
        "favorites": favorites.get(str(user_id), [])
    }


@app.post("/bot")
async def webhook(request: Request):
    try:
        data = await request.json()
        update = telebot.types.Update.de_json(data)
        bot.process_new_updates([update])
        return {"ok": True}
    except Exception as e:
        return {"ok": False}


@app.on_event("startup")
async def startup():
    if not os.path.exists(PRODUCTS_FILE):
        save_products([
            {"id": 1, "name": "Namuna Mahsulot", "price": 50000, "category": "🎁 Boshqa", "description": "", "rating": 0, "available": True}
        ])
    
    if not os.path.exists(PROMO_FILE):
        save_promos([
            {"code": "WELCOME10", "discount": 10, "active": True, "expires": "2025-12-31"}
        ])
    
    webhook_url = f"{RENDER_EXTERNAL_URL}/bot"
    bot.remove_webhook()
    bot.set_webhook(url=webhook_url)
    print(f"✅ Webhook: {webhook_url}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
