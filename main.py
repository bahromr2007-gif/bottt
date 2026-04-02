import telebot
from telebot import types
import json
import os
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
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

bot = telebot.TeleBot(BOT_TOKEN)
app = FastAPI()

user_states = {}


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


def save_products(p):
    save_json(PRODUCTS_FILE, p)


def save_orders(o):
    save_json(ORDERS_FILE, o)


def save_users(u):
    save_json(USERS_FILE, u)


def is_admin(user_id):
    return user_id in ADMIN_IDS


def format_price(price):
    return f"{price:,}".replace(",", " ")


# ============ KLAVIATURALAR ============
def get_main_menu(user_id):
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
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton("➕ Mahsulot qo'shish"),
        types.KeyboardButton("📋 Mahsulotlar"),
        types.KeyboardButton("📊 Statistika")
    )
    markup.add(types.KeyboardButton("🔙 Asosiy menyu"))
    return markup


def get_cancel_btn():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("❌ Bekor qilish"))
    return markup


# ============ BOT HANDLERLAR ============
@bot.message_handler(commands=["start"])
def start(message):
    user_id = message.from_user.id
    users = get_users()
    
    if str(user_id) not in users:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        contact_btn = types.KeyboardButton("📱 Telefon raqam", request_contact=True)
        markup.add(contact_btn)
        
        bot.send_message(
            message.chat.id,
            f"👋 Assalomu alaykum {message.from_user.first_name}!\n\n"
            "Ro'yxatdan o'tish uchun telefon raqamingizni yuboring 👇",
            reply_markup=markup
        )
        user_states[user_id] = {"state": "waiting_contact"}
    else:
        bot.send_message(message.chat.id, "🏠 Asosiy menyu", reply_markup=get_main_menu(user_id))


@bot.message_handler(content_types=["contact"])
def handle_contact(message):
    user_id = message.from_user.id
    
    if user_states.get(user_id, {}).get("state") == "waiting_contact":
        users = get_users()
        users[str(user_id)] = {
            "user_id": user_id,
            "name": message.from_user.first_name,
            "phone": message.contact.phone_number,
            "joined": datetime.now().strftime("%Y-%m-%d %H:%M")
        }
        save_users(users)
        user_states[user_id] = {"state": "idle"}
        
        bot.send_message(
            message.chat.id,
            "✅ Ro'yxatdan o'tdingiz!",
            reply_markup=get_main_menu(user_id)
        )
        
        # Adminga xabar
        for admin_id in ADMIN_IDS:
            try:
                bot.send_message(admin_id, f"🆕 Yangi foydalanuvchi!\n👤 {message.from_user.first_name}\n📞 {message.contact.phone_number}")
            except:
                pass


@bot.message_handler(func=lambda m: m.text == "👨‍💼 Admin panel")
def admin_panel(message):
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "❌ Admin emassiz!")
        return
    bot.send_message(message.chat.id, "👨‍💼 Admin panel", reply_markup=get_admin_menu())


@bot.message_handler(func=lambda m: m.text == "🔙 Asosiy menyu")
def back_main(message):
    user_states[message.from_user.id] = {"state": "idle"}
    bot.send_message(message.chat.id, "🏠 Asosiy menyu", reply_markup=get_main_menu(message.from_user.id))


@bot.message_handler(func=lambda m: m.text == "➕ Mahsulot qo'shish")
def add_product(message):
    if not is_admin(message.from_user.id):
        return
    
    user_states[message.from_user.id] = {"state": "add_name", "temp": {}}
    bot.send_message(message.chat.id, "1. Mahsulot nomini kiriting:", reply_markup=get_cancel_btn())


@bot.message_handler(func=lambda m: m.text == "📋 Mahsulotlar")
def list_products(message):
    if not is_admin(message.from_user.id):
        return
    
    products = get_products()
    if not products:
        bot.send_message(message.chat.id, "Mahsulot yo'q")
        return
    
    text = "📋 Mahsulotlar:\n\n"
    for p in products:
        text += f"#{p['id']} {p['name']}\n💰 {format_price(p['price'])} so'm\n🏷 {p['category']}\n\n"
    
    bot.send_message(message.chat.id, text, reply_markup=get_admin_menu())


@bot.message_handler(func=lambda m: m.text == "📊 Statistika")
def show_stats(message):
    if not is_admin(message.from_user.id):
        return
    
    products = get_products()
    orders = get_orders()
    users = get_users()
    
    total_sales = sum(o.get('total', 0) for o in orders)
    
    text = f"📊 Statistika:\n\n"
    text += f"👥 Foydalanuvchilar: {len(users)}\n"
    text += f"🛍️ Mahsulotlar: {len(products)}\n"
    text += f"📦 Zakazlar: {len(orders)}\n"
    text += f"💰 Sotuv: {format_price(total_sales)} so'm"
    
    bot.send_message(message.chat.id, text, reply_markup=get_admin_menu())


@bot.message_handler(func=lambda m: m.text == "❌ Bekor qilish")
def cancel(message):
    user_states[message.from_user.id] = {"state": "idle"}
    markup = get_admin_menu() if is_admin(message.from_user.id) else get_main_menu(message.from_user.id)
    bot.send_message(message.chat.id, "❌ Bekor qilindi", reply_markup=markup)


@bot.message_handler(func=lambda m: m.text == "📦 Mening zakazlarim")
def my_orders(message):
    user_id = message.from_user.id
    orders = get_orders()
    user_orders = [o for o in orders if o.get("user_id") == user_id]
    
    if not user_orders:
        bot.send_message(message.chat.id, "Zakazlaringiz yo'q")
        return
    
    text = "📦 Zakazlaringiz:\n\n"
    for o in user_orders[-5:]:
        text += f"#{o['id']} | {o['date']}\n💰 {format_price(o['total'])} so'm\n\n"
    
    bot.send_message(message.chat.id, text)


@bot.message_handler(func=lambda m: m.text == "📞 Aloqa")
def contact(message):
    bot.send_message(message.chat.id, "📞 Admin: @admin_username")


@bot.message_handler(func=lambda m: m.text == "ℹ️ Yordam")
def help_msg(message):
    bot.send_message(message.chat.id, "🛍️ Do'konni ochib mahsulot tanlang")


@bot.message_handler(content_types=["web_app_data"])
def handle_order(message):
    try:
        data = json.loads(message.web_app_data.data)
        orders = get_orders()
        users = get_users()
        user = users.get(str(message.from_user.id), {})
        
        new_order = {
            "id": len(orders) + 1,
            "user_id": message.from_user.id,
            "user_name": message.from_user.first_name,
            "user_phone": user.get("phone", "Noma'lum"),
            "items": data.get("items", []),
            "total": data.get("total", 0),
            "address": data.get("address", ""),
            "note": data.get("note", ""),
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "status": "new"
        }
        
        orders.append(new_order)
        save_orders(orders)
        
        # Foydalanuvchiga xabar
        bot.send_message(
            message.chat.id,
            f"✅ Zakaz #{new_order['id']} qabul qilindi!\n💰 {format_price(new_order['total'])} so'm"
        )
        
        # Adminga to'liq xabar
        items_text = ""
        for item in new_order['items']:
            items_text += f"• {item['name']} x{item['qty']} = {format_price(item['price'] * item['qty'])} so'm\n"
        
        admin_text = f"""
🆕 YANGI ZAKAZ #{new_order['id']}

👤 Mijoz: {new_order['user_name']}
📞 Telefon: {new_order['user_phone']}
🆔 User ID: {new_order['user_id']}
📍 Manzil: {new_order['address']}

📦 Mahsulotlar:
{items_text}
💰 Jami: {format_price(new_order['total'])} so'm
💬 Izoh: {new_order['note'] or 'Yo\'q'}
📅 Vaqt: {new_order['date']}
"""
        
        for admin_id in ADMIN_IDS:
            try:
                bot.send_message(admin_id, admin_text)
            except:
                pass
                
    except Exception as e:
        logger.error(f"Order error: {e}")
        bot.send_message(message.chat.id, "❌ Xatolik yuz berdi")


@bot.message_handler(content_types=["text"])
def handle_states(message):
    user_id = message.from_user.id
    state = user_states.get(user_id, {}).get("state", "idle")
    
    if state == "add_name":
        user_states[user_id]["temp"]["name"] = message.text
        user_states[user_id]["state"] = "add_price"
        bot.send_message(message.chat.id, "2. Narxini kiriting (so'm):")
    
    elif state == "add_price":
        try:
            price = int(message.text.replace(" ", ""))
            user_states[user_id]["temp"]["price"] = price
            user_states[user_id]["state"] = "add_category"
            
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
            for cat in ["👗 Kiyim", "👟 Poyabzal", "📱 Elektronika", "🏠 Uy jihozlari", "🍕 Oziq-ovqat", "🎁 Boshqa"]:
                markup.add(types.KeyboardButton(cat))
            markup.add(types.KeyboardButton("❌ Bekor qilish"))
            
            bot.send_message(message.chat.id, "3. Kategoriyani tanlang:", reply_markup=markup)
        except:
            bot.send_message(message.chat.id, "❌ Faqat son kiriting!")
    
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
            "available": True
        }
        
        products.append(new_product)
        save_products(products)
        
        user_states[user_id] = {"state": "idle"}
        
        bot.send_message(
            message.chat.id,
            f"✅ Mahsulot qo'shildi!\n\n📌 {new_product['name']}\n💰 {format_price(new_product['price'])} so'm\n🏷 {new_product['category']}",
            reply_markup=get_admin_menu()
        )


# ============ FASTAPI ============
@app.get("/")
def home():
    return {"status": "Bot ishlayapti"}


@app.get("/shop")
def shop():
    with open("index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(content=f.read())


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
                "description": p.get("description", "")
            })
    return JSONResponse(products)


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
            {"id": 1, "name": "Namuna Mahsulot", "price": 50000, "category": "🎁 Boshqa", "description": "", "available": True}
        ])
    
    webhook_url = f"{RENDER_EXTERNAL_URL}/bot"
    bot.remove_webhook()
    bot.set_webhook(url=webhook_url)
    print(f"Webhook: {webhook_url}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
