#!/usr/bin/env python3
"""
🛍️ Do'kon Telegram Boti
Yaratuvchi: Claude (Anthropic)
O'rnatish: pip install pyTelegramBotAPI
Ishga tushirish: python bot.py
"""

import telebot
from telebot import types
import json
import os
from datetime import datetime
from fastapi import FastAPI
app = FastAPI()

# ==================== SOZLAMALAR ====================
BOT_TOKEN = "8778358404:AAHmM4e2OnROyXLCsGXERCbXd3arzl7kPS0"   # @BotFather dan oling
ADMIN_IDS = [8735360012]             # O'z Telegram ID ingizni qo'ying
WEB_APP_URL = "https://YOUR_SITE.com/shop.html"  # shop.html ni joylashtirgan URL

# ==================== MA'LUMOTLAR ====================
# Fayllar (oddiy JSON bazasi)
PRODUCTS_FILE = "products.json"
ORDERS_FILE = "orders.json"
USERS_FILE = "users.json"

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

def save_products(p): save_json(PRODUCTS_FILE, p)
def save_orders(o): save_json(ORDERS_FILE, o)
def save_users(u): save_json(USERS_FILE, u)

# ==================== BOT ====================
bot = telebot.TeleBot(BOT_TOKEN)

# Foydalanuvchi holatlari
user_states = {}
# user_states[user_id] = {
#   "state": "idle" | "add_name" | "add_desc" | "add_price" | "add_photo" | "add_cat",
#   "temp": {}
# }

def is_admin(user_id):
    return user_id in ADMIN_IDS

def get_main_menu(user_id):
    """Asosiy menyu (mijoz uchun)"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    # Web App tugmasi - faqat to'g'ri URL bo'lsa
    if WEB_APP_URL and WEB_APP_URL.startswith("https://") and "YOUR_SITE" not in WEB_APP_URL:
        shop_btn = types.KeyboardButton(
            "🛍️ Do'konni ochish",
            web_app=types.WebAppInfo(url=WEB_APP_URL)
        )
    else:
        shop_btn = types.KeyboardButton("🛍️ Do'konni ochish")
    markup.add(shop_btn)
    markup.add(
        types.KeyboardButton("📦 Mening zakaz larim"),
        types.KeyboardButton("📞 Aloqa")
    )
    markup.add(types.KeyboardButton("ℹ️ Yordam"))
    
    if is_admin(user_id):
        markup.add(types.KeyboardButton("👨‍💼 Admin panel"))
    
    return markup

def get_admin_menu():
    """Admin menyusi"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton("➕ Mahsulot qo'shish"),
        types.KeyboardButton("📋 Barcha mahsulotlar")
    )
    markup.add(
        types.KeyboardButton("📬 Zakaz lar"),
        types.KeyboardButton("📊 Statistika")
    )
    markup.add(types.KeyboardButton("🗑️ Mahsulot o'chirish"))
    markup.add(types.KeyboardButton("🔙 Asosiy menyu"))
    return markup

def get_cancel_btn():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("❌ Bekor qilish"))
    return markup

# ==================== START ====================
@bot.message_handler(commands=["start"])
def start(message):
    user_id = message.from_user.id
    users = get_users()
    
    # Telefon raqam so'rash (yangi foydalanuvchi)
    if str(user_id) not in users:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        contact_btn = types.KeyboardButton(
            "📱 Telefon raqamimni yuborish",
            request_contact=True
        )
        markup.add(contact_btn)
        
        bot.send_message(
            message.chat.id,
            f"👋 Assalomu alaykum, *{message.from_user.first_name}*!\n\n"
            "🛍️ *Bizning do'konimizga xush kelibsiz!*\n\n"
            "Davom etish uchun telefon raqamingizni yuboring 👇",
            parse_mode="Markdown",
            reply_markup=markup
        )
        user_states[user_id] = {"state": "waiting_contact", "temp": {}}
    else:
        # Qaytib kelgan foydalanuvchi
        bot.send_message(
            message.chat.id,
            f"👋 Qaytib keldingiz, *{message.from_user.first_name}*!\n\n"
            "Quyidagi tugmalardan birini tanlang 👇",
            parse_mode="Markdown",
            reply_markup=get_main_menu(user_id)
        )

# Telefon raqam qabul qilish
@bot.message_handler(content_types=["contact"])
def get_contact(message):
    user_id = message.from_user.id
    state = user_states.get(user_id, {}).get("state")
    
    if state == "waiting_contact":
        contact = message.contact
        users = get_users()
        users[str(user_id)] = {
            "name": message.from_user.first_name,
            "username": message.from_user.username or "",
            "phone": contact.phone_number,
            "joined": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "user_id": user_id
        }
        save_users(users)
        user_states[user_id] = {"state": "idle", "temp": {}}
        
        bot.send_message(
            message.chat.id,
            f"✅ *Ro'yxatdan o'tdingiz!*\n\n"
            f"📱 Telefon: `{contact.phone_number}`\n\n"
            "Endi do'konimizdan xarid qilishingiz mumkin! 🛒",
            parse_mode="Markdown",
            reply_markup=get_main_menu(user_id)
        )

# ==================== ASOSIY MENYU HANDLE ====================
@bot.message_handler(func=lambda m: m.text == "📦 Mening zakaz larim")
def my_orders(message):
    user_id = message.from_user.id
    orders = get_orders()
    user_orders = [o for o in orders if o.get("user_id") == user_id]
    
    if not user_orders:
        bot.send_message(message.chat.id, "📦 Hozircha zakaz laringiz yo'q.\n\n🛍️ Do'konni oching va birinchi xaridingizni qiling!")
        return
    
    text = "📦 *Sizning zakaz laringiz:*\n\n"
    for o in user_orders[-5:]:  # Oxirgi 5 ta
        status_emoji = {"yangi": "🆕", "qabul": "✅", "yetkazish": "🚚", "bajarildi": "✔️"}.get(o.get("status", "yangi"), "🆕")
        text += f"{status_emoji} *Zakaz #{o['id']}*\n"
        text += f"   📅 {o['date']}\n"
        text += f"   💰 {o['total']:,} so'm\n"
        text += f"   📌 Holat: {o.get('status', 'Yangi')}\n\n"
    
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "📞 Aloqa")
def contact_info(message):
    bot.send_message(
        message.chat.id,
        "📞 *Biz bilan bog'laning:*\n\n"
        "📱 Telefon: +998 XX XXX XX XX\n"
        "💬 Telegram: @admin_username\n"
        "🕐 Ish vaqti: 9:00 - 21:00\n\n"
        "Savol va takliflaringiz bo'lsa yozishingiz mumkin!",
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda m: m.text == "ℹ️ Yordam")
def help_info(message):
    bot.send_message(
        message.chat.id,
        "ℹ️ *Yordam*\n\n"
        "🛍️ *Do'konni ochish* — Barcha mahsulotlarni ko'rish, savatchaga qo'shish va zakaz berish\n\n"
        "📦 *Mening zakazlarim* — Zakaz laringiz holati\n\n"
        "📞 *Aloqa* — Biz bilan bog'lanish\n\n"
        "_Muammo bo'lsa admin bilan bog'laning!_",
        parse_mode="Markdown"
    )

# ==================== ADMIN PANEL ====================
@bot.message_handler(func=lambda m: m.text == "👨‍💼 Admin panel")
def admin_panel(message):
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "❌ Sizda ruxsat yo'q!")
        return
    
    products = get_products()
    orders = get_orders()
    users = get_users()
    
    new_orders = len([o for o in orders if o.get("status") == "yangi"])
    
    bot.send_message(
        message.chat.id,
        f"👨‍💼 *Admin Panel*\n\n"
        f"📦 Mahsulotlar: {len(products)} ta\n"
        f"🛒 Jami zakaz lar: {len(orders)} ta\n"
        f"🆕 Yangi zakaz lar: {new_orders} ta\n"
        f"👥 Foydalanuvchilar: {len(users)} ta\n\n"
        f"Kerakli bo'limni tanlang 👇",
        parse_mode="Markdown",
        reply_markup=get_admin_menu()
    )

@bot.message_handler(func=lambda m: m.text == "🔙 Asosiy menyu")
def back_to_main(message):
    user_states[message.from_user.id] = {"state": "idle", "temp": {}}
    bot.send_message(
        message.chat.id,
        "🏠 Asosiy menyu",
        reply_markup=get_main_menu(message.from_user.id)
    )

# ==================== MAHSULOT QO'SHISH ====================
@bot.message_handler(func=lambda m: m.text == "➕ Mahsulot qo'shish")
def add_product_start(message):
    if not is_admin(message.from_user.id):
        return
    user_states[message.from_user.id] = {"state": "add_name", "temp": {}}
    bot.send_message(
        message.chat.id,
        "➕ *Yangi mahsulot qo'shish*\n\n"
        "1️⃣ Mahsulot nomini kiriting:",
        parse_mode="Markdown",
        reply_markup=get_cancel_btn()
    )

@bot.message_handler(func=lambda m: m.text == "❌ Bekor qilish")
def cancel_action(message):
    user_id = message.from_user.id
    user_states[user_id] = {"state": "idle", "temp": {}}
    markup = get_admin_menu() if is_admin(user_id) else get_main_menu(user_id)
    bot.send_message(message.chat.id, "❌ Bekor qilindi.", reply_markup=markup)

# Mahsulot qo'shish jarayoni - text handler
@bot.message_handler(content_types=["text", "photo"])
def handle_states(message):
    user_id = message.from_user.id
    state_data = user_states.get(user_id, {"state": "idle", "temp": {}})
    state = state_data.get("state", "idle")
    
    # ===== MAHSULOT QO'SHISH =====
    if state == "add_name":
        user_states[user_id]["temp"]["name"] = message.text
        user_states[user_id]["state"] = "add_desc"
        bot.send_message(message.chat.id, "2️⃣ Mahsulot tavsifini kiriting:")
    
    elif state == "add_desc":
        user_states[user_id]["temp"]["description"] = message.text
        user_states[user_id]["state"] = "add_price"
        bot.send_message(message.chat.id, "3️⃣ Narxini kiriting (faqat raqam, so'mda):\nMasalan: 50000")
    
    elif state == "add_price":
        try:
            price = int(message.text.replace(" ", "").replace(",", ""))
            user_states[user_id]["temp"]["price"] = price
            user_states[user_id]["state"] = "add_category"
            
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
            markup.add("👗 Kiyim", "👟 Poyabzal", "💄 Kosmetika", "🏠 Uy jihozlari")
            markup.add("📱 Elektronika", "🍕 Oziq-ovqat", "🎁 Boshqa")
            bot.send_message(message.chat.id, "4️⃣ Kategoriyani tanlang:", reply_markup=markup)
        except:
            bot.send_message(message.chat.id, "❌ Faqat raqam kiriting! Masalan: 50000")
    
    elif state == "add_category":
        user_states[user_id]["temp"]["category"] = message.text
        user_states[user_id]["state"] = "add_photo"
        bot.send_message(
            message.chat.id,
            "5️⃣ Mahsulot rasmini yuboring:\n_(Rasm bo'lmasa /skip yozing)_",
            parse_mode="Markdown",
            reply_markup=get_cancel_btn()
        )
    
    elif state == "add_photo":
        if message.content_type == "photo":
            photo_id = message.photo[-1].file_id
            user_states[user_id]["temp"]["photo"] = photo_id
        else:
            user_states[user_id]["temp"]["photo"] = None
        
        # Mahsulotni saqlash
        products = get_products()
        temp = user_states[user_id]["temp"]
        new_product = {
            "id": len(products) + 1,
            "name": temp["name"],
            "description": temp["description"],
            "price": temp["price"],
            "category": temp["category"],
            "photo": temp.get("photo"),
            "available": True,
            "added": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        products.append(new_product)
        save_products(products)
        user_states[user_id] = {"state": "idle", "temp": {}}
        
        bot.send_message(
            message.chat.id,
            f"✅ *Mahsulot qo'shildi!*\n\n"
            f"📌 Nom: {temp['name']}\n"
            f"💰 Narx: {temp['price']:,} so'm\n"
            f"🏷️ Kategoriya: {temp['category']}",
            parse_mode="Markdown",
            reply_markup=get_admin_menu()
        )
        
        # Web App ni yangilash uchun JSON faylni qayta yozish
        update_webapp_products(products)
    
    # ===== ADMIN MENYUSI =====
    elif message.text == "📋 Barcha mahsulotlar" and is_admin(user_id):
        products = get_products()
        if not products:
            bot.send_message(message.chat.id, "📋 Hali mahsulot yo'q.")
            return
        
        text = "📋 *Barcha mahsulotlar:*\n\n"
        for p in products:
            avail = "✅" if p.get("available", True) else "❌"
            text += f"{avail} *#{p['id']}* {p['name']}\n"
            text += f"   💰 {p['price']:,} so'm | {p['category']}\n\n"
        
        bot.send_message(message.chat.id, text, parse_mode="Markdown")
    
    elif message.text == "📬 Zakaz lar" and is_admin(user_id):
        show_orders_admin(message)
    
    elif message.text == "📊 Statistika" and is_admin(user_id):
        show_statistics(message)
    
    elif message.text == "🗑️ Mahsulot o'chirish" and is_admin(user_id):
        delete_product_start(message)
    
    elif state == "delete_product":
        delete_product_confirm(message)

def show_orders_admin(message):
    """Admin: zakaz larni ko'rish"""
    orders = get_orders()
    if not orders:
        bot.send_message(message.chat.id, "📬 Hali zakaz yo'q.")
        return
    
    # Oxirgi 10 ta zakaz
    recent = orders[-10:][::-1]
    for o in recent:
        status_emoji = {"yangi": "🆕", "qabul": "✅", "yetkazish": "🚚", "bajarildi": "✔️"}.get(o.get("status", "yangi"), "🆕")
        
        items_text = ""
        for item in o.get("items", []):
            items_text += f"  • {item['name']} x{item['qty']} = {item['price'] * item['qty']:,} so'm\n"
        
        text = (
            f"{status_emoji} *Zakaz #{o['id']}*\n"
            f"👤 {o.get('user_name', 'Noma\'lum')}\n"
            f"📱 {o.get('phone', '-')}\n"
            f"📅 {o['date']}\n"
            f"📍 {o.get('address', '-')}\n\n"
            f"🛒 *Mahsulotlar:*\n{items_text}\n"
            f"💰 *Jami: {o['total']:,} so'm*\n"
            f"📌 Holat: {o.get('status', 'Yangi')}"
        )
        
        # Holat o'zgartirish inline button
        markup = types.InlineKeyboardMarkup()
        markup.row(
            types.InlineKeyboardButton("✅ Qabul", callback_data=f"status_{o['id']}_qabul"),
            types.InlineKeyboardButton("🚚 Yetkazish", callback_data=f"status_{o['id']}_yetkazish"),
            types.InlineKeyboardButton("✔️ Bajarildi", callback_data=f"status_{o['id']}_bajarildi")
        )
        
        bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("status_"))
def change_order_status(call):
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, "❌ Ruxsat yo'q!")
        return
    
    _, order_id, new_status = call.data.split("_")
    order_id = int(order_id)
    
    orders = get_orders()
    for o in orders:
        if o["id"] == order_id:
            o["status"] = new_status
            # Mijozga xabar
            try:
                status_text = {"qabul": "✅ Qabul qilindi", "yetkazish": "🚚 Yetkazilmoqda", "bajarildi": "✔️ Bajarildi"}.get(new_status, new_status)
                bot.send_message(
                    o["user_id"],
                    f"📦 *Zakaz #{order_id} holati o'zgardi!*\n\n"
                    f"📌 Yangi holat: {status_text}",
                    parse_mode="Markdown"
                )
            except:
                pass
            break
    
    save_orders(orders)
    bot.answer_callback_query(call.id, f"✅ Holat: {new_status}")
    bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id)

def show_statistics(message):
    products = get_products()
    orders = get_orders()
    users = get_users()
    
    total_revenue = sum(o["total"] for o in orders if o.get("status") == "bajarildi")
    
    bot.send_message(
        message.chat.id,
        f"📊 *Statistika*\n\n"
        f"👥 Foydalanuvchilar: {len(users)} ta\n"
        f"📦 Mahsulotlar: {len(products)} ta\n"
        f"🛒 Jami zakaz: {len(orders)} ta\n"
        f"🆕 Yangi: {len([o for o in orders if o.get('status') == 'yangi'])} ta\n"
        f"✔️ Bajarilgan: {len([o for o in orders if o.get('status') == 'bajarildi'])} ta\n"
        f"💰 Daromad: {total_revenue:,} so'm",
        parse_mode="Markdown"
    )

def delete_product_start(message):
    products = get_products()
    if not products:
        bot.send_message(message.chat.id, "❌ O'chiriladigan mahsulot yo'q.")
        return
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    for p in products:
        markup.add(types.KeyboardButton(f"#{p['id']} {p['name']}"))
    markup.add(types.KeyboardButton("❌ Bekor qilish"))
    
    user_states[message.from_user.id] = {"state": "delete_product", "temp": {}}
    bot.send_message(message.chat.id, "🗑️ O'chiriladigan mahsulotni tanlang:", reply_markup=markup)

def delete_product_confirm(message):
    user_id = message.from_user.id
    text = message.text
    if text.startswith("#"):
        try:
            prod_id = int(text.split(" ")[0][1:])
            products = get_products()
            products = [p for p in products if p["id"] != prod_id]
            save_products(products)
            update_webapp_products(products)
            user_states[user_id] = {"state": "idle", "temp": {}}
            bot.send_message(message.chat.id, f"✅ Mahsulot #{prod_id} o'chirildi.", reply_markup=get_admin_menu())
        except:
            bot.send_message(message.chat.id, "❌ Xato. Qaytadan urinib ko'ring.")

# ==================== WEB APP dan ZAKAZ ====================
@bot.message_handler(content_types=["web_app_data"])
def web_app_order(message):
    """Web App dan kelgan zakaz"""
    user_id = message.from_user.id
    users = get_users()
    
    try:
        data = json.loads(message.web_app_data.data)
        
        if data.get("type") == "order":
            orders = get_orders()
            new_order = {
                "id": len(orders) + 1,
                "user_id": user_id,
                "user_name": message.from_user.first_name,
                "phone": users.get(str(user_id), {}).get("phone", "-"),
                "items": data.get("items", []),
                "total": data.get("total", 0),
                "address": data.get("address", "-"),
                "note": data.get("note", ""),
                "status": "yangi",
                "date": datetime.now().strftime("%Y-%m-%d %H:%M")
            }
            orders.append(new_order)
            save_orders(orders)
            
            # Mijozga tasdiqlash
            items_text = "\n".join([f"• {i['name']} x{i['qty']}" for i in new_order["items"]])
            bot.send_message(
                message.chat.id,
                f"✅ *Zakazingiz qabul qilindi!*\n\n"
                f"📦 Zakaz #{new_order['id']}\n\n"
                f"🛒 *Mahsulotlar:*\n{items_text}\n\n"
                f"💰 Jami: *{new_order['total']:,} so'm*\n\n"
                f"📍 Manzil: {new_order['address']}\n\n"
                f"⏰ Tez orada siz bilan bog'lanamiz!",
                parse_mode="Markdown",
                reply_markup=get_main_menu(user_id)
            )
            
            # Adminlarga xabar
            for admin_id in ADMIN_IDS:
                try:
                    markup = types.InlineKeyboardMarkup()
                    markup.row(
                        types.InlineKeyboardButton("✅ Qabul", callback_data=f"status_{new_order['id']}_qabul"),
                        types.InlineKeyboardButton("🚚 Yetkazish", callback_data=f"status_{new_order['id']}_yetkazish")
                    )
                    bot.send_message(
                        admin_id,
                        f"🆕 *YANGI ZAKAZ #{new_order['id']}!*\n\n"
                        f"👤 {new_order['user_name']}\n"
                        f"📱 {new_order['phone']}\n"
                        f"📍 {new_order['address']}\n\n"
                        f"🛒 {items_text}\n\n"
                        f"💰 *Jami: {new_order['total']:,} so'm*",
                        parse_mode="Markdown",
                        reply_markup=markup
                    )
                except:
                    pass
    except Exception as e:
        bot.send_message(message.chat.id, "❌ Xatolik yuz berdi. Qaytadan urinib ko'ring.")
        print(f"Error: {e}")

def update_webapp_products(products):
    """Web App uchun mahsulotlar JSON faylini yangilash"""
    try:
        with open("webapp_products.json", "w", encoding="utf-8") as f:
            json.dump(products, f, ensure_ascii=False, indent=2)
    except:
        pass

# ==================== ISHGA TUSHIRISH ====================
if __name__ == "__main__":
    print("🛍️ Do'kon boti ishga tushdi...")
    print(f"👨‍💼 Admin IDs: {ADMIN_IDS}")
    
    # Boshlang'ich mahsulotlar (test uchun)
    if not os.path.exists(PRODUCTS_FILE):
        sample_products = [
            {"id": 1, "name": "Misol Mahsulot 1", "description": "Bu test mahsulot", "price": 50000, "category": "🎁 Boshqa", "photo": None, "available": True, "added": "2024-01-01"},
        ]
        save_products(sample_products)
        update_webapp_products(sample_products)
    
    bot.infinity_polling(timeout=20, long_polling_timeout=20)
