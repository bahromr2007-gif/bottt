import telebot
from telebot import types
import json
import os
from datetime import datetime
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import logging

# Logging sozlamalari
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Konfiguratsiya
BOT_TOKEN = "8778358404:AAHmM4e2OnROyXLCsGXERCbXd3arzl7kPS0"
RENDER_EXTERNAL_URL = "https://bottt-02j7.onrender.com"
WEB_APP_URL = f"{RENDER_EXTERNAL_URL}/shop"

ADMIN_IDS = [8735360012]

# Fayllar
PRODUCTS_FILE = "products.json"
ORDERS_FILE = "orders.json"
USERS_FILE = "users.json"

# Bot va app
bot = telebot.TeleBot(BOT_TOKEN)
app = FastAPI(title="Telegram Shop Bot", version="2.0.0")

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


# ==================== KLAVIATURALAR ====================
def get_main_menu(user_id):
    """Asosiy menyu"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    # Web App tugmasi
    shop_btn = types.KeyboardButton(
        "🛍️ Do'konni ochish",
        web_app=types.WebAppInfo(url=WEB_APP_URL)
    )
    markup.add(shop_btn)
    
    # Boshqa tugmalar
    markup.add(
        types.KeyboardButton("📦 Mening zakazlarim"),
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
        types.KeyboardButton("📋 Barcha mahsulotlar"),
        types.KeyboardButton("📊 Statistika")
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
        # Telefon raqam so'rash
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
            "name": message.from_user.first_name,
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
                    f"🆔 {user_id}",
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
        "📝 *1/4 - Mahsulot nomi*\n\n"
        "Mahsulot nomini kiriting:",
        parse_mode="Markdown",
        reply_markup=get_cancel_btn()
    )


@bot.message_handler(func=lambda m: m.text == "📋 Barcha mahsulotlar")
def list_products(message):
    """Barcha mahsulotlarni ko'rish"""
    if not is_admin(message.from_user.id):
        return
    
    products = get_products()
    if not products:
        bot.send_message(message.chat.id, "📭 *Hozircha mahsulot yo'q*", parse_mode="Markdown")
        return
    
    text = "📋 *Barcha mahsulotlar:*\n\n"
    for p in products:
        text += f"🆔 #{p['id']}\n"
        text += f"📌 {p['name']}\n"
        text += f"💰 {format_price(p['price'])} so'm\n"
        text += f"🏷 {p['category']}\n"
        text += f"✅ {'Mavjud' if p.get('available', True) else 'Mavjud emas'}\n"
        text += "─" * 20 + "\n\n"
    
    # Uzun xabarlarni bo'lib yuborish
    if len(text) > 4000:
        for i in range(0, len(text), 4000):
            bot.send_message(message.chat.id, text[i:i+4000], parse_mode="Markdown")
    else:
        bot.send_message(message.chat.id, text, parse_mode="Markdown")


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
    
    stats_text = (
        f"📊 *Bot statistikasi*\n\n"
        f"👥 Foydalanuvchilar: *{total_users}*\n"
        f"🛍️ Mahsulotlar: *{total_products}*\n"
        f"📦 Zakazlar: *{total_orders}*\n"
        f"💰 Umumiy sotuv: *{format_price(total_sales)} so'm*\n"
        f"📈 O'rtacha zakaz: *{format_price(total_sales // total_orders) if total_orders > 0 else 0} so'm*"
    )
    
    bot.send_message(message.chat.id, stats_text, parse_mode="Markdown")


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
    
    text = "📦 *Sizning zakazlaringiz:*\n\n"
    for order in user_orders[-10:]:  # Oxirgi 10 ta zakaz
        text += f"🆔 #{order['id']}\n"
        text += f"📅 {order['date']}\n"
        text += f"💰 {format_price(order['total'])} so'm\n"
        text += f"📦 {len(order.get('items', []))} ta mahsulot\n"
        text += "─" * 20 + "\n\n"
    
    bot.send_message(message.chat.id, text, parse_mode="Markdown")


@bot.message_handler(func=lambda m: m.text == "📞 Aloqa")
def contact_info(message):
    """Aloqa ma'lumotlari"""
    text = (
        "📞 *Bog'lanish ma'lumotlari*\n\n"
        "👨‍💼 Admin: @admin_username\n"
        "📱 Telefon: +998 XX XXX XX XX\n"
        "📧 Email: admin@example.com\n\n"
        "⚠️ *Ish vaqti:* 9:00 - 21:00"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")


@bot.message_handler(func=lambda m: m.text == "ℹ️ Yordam")
def help_info(message):
    """Yordam ma'lumotlari"""
    text = (
        "ℹ️ *Yordam* \n\n"
        "🛍️ *Do'konni ochish* - Mahsulotlarni ko'rish va xarid qilish\n"
        "📦 *Mening zakazlarim* - Tarixni ko'rish\n"
        "📞 *Aloqa* - Admin bilan bog'lanish\n\n"
        "❓ *Savollaringiz bo'lsa, @admin_username ga yozing*"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")


@bot.message_handler(content_types=["web_app_data"])
def handle_webapp_order(message):
    """Web App dan zakaz qabul qilish"""
    try:
        data = json.loads(message.web_app_data.data)
        logger.info(f"New order from {message.from_user.id}: {data}")
        
        orders = get_orders()
        
        # Yangi zakaz
        new_order = {
            "id": len(orders) + 1,
            "user_id": message.from_user.id,
            "user_name": message.from_user.first_name,
            "user_phone": get_users().get(str(message.from_user.id), {}).get("phone", ""),
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
        bot.send_message(
            message.chat.id,
            f"✅ *Zakaz qabul qilindi!*\n\n"
            f"🆔 #{new_order['id']}\n"
            f"💰 {format_price(new_order['total'])} so'm\n\n"
            f"📦 *Mahsulotlar:*\n" +
            "\n".join([f"• {item.get('name', '')} x{item.get('qty', 1)}" for item in new_order['items']]) +
            f"\n\n📍 *Manzil:* {new_order['address']}\n"
            f"💬 *Izoh:* {new_order['note'] or 'Yo‘q'}\n\n"
            f"Tez orada admin siz bilan bog'lanadi! ☎️",
            parse_mode="Markdown"
        )
        
        # Adminlarga xabar
        for admin_id in ADMIN_IDS:
            try:
                items_text = "\n".join([
                    f"  • {item.get('name', '')} x{item.get('qty', 1)} = {format_price(item.get('price', 0) * item.get('qty', 1))} so'm"
                    for item in new_order['items']
                ])
                
                bot.send_message(
                    admin_id,
                    f"🆕 *Yangi zakaz!*\n\n"
                    f"🆔 #{new_order['id']}\n"
                    f"👤 {new_order['user_name']}\n"
                    f"📞 {new_order['user_phone']}\n"
                    f"📦 *Mahsulotlar:*\n{items_text}\n"
                    f"💰 *Jami:* {format_price(new_order['total'])} so'm\n"
                    f"📍 *Manzil:* {new_order['address']}\n"
                    f"💬 *Izoh:* {new_order['note'] or 'Yo‘q'}\n"
                    f"📅 *Vaqt:* {new_order['date']}",
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Error sending to admin: {e}")
        
    except Exception as e:
        logger.error(f"WebApp order error: {e}")
        bot.send_message(
            message.chat.id,
            "❌ *Xatolik yuz berdi!*\n\n"
            "Iltimos, qaytadan urinib ko'ring.",
            parse_mode="Markdown"
        )


@bot.message_handler(content_types=["text"])
def handle_states(message):
    """State larni boshqarish"""
    user_id = message.from_user.id
    state_data = user_states.get(user_id, {"state": "idle"})
    state = state_data.get("state", "idle")
    
    # Mahsulot qo'shish state lari
    if state == "add_name":
        user_states[user_id]["temp"]["name"] = message.text
        user_states[user_id]["state"] = "add_desc"
        bot.send_message(
            message.chat.id,
            "📝 *2/4 - Tavsif*\n\n"
            "Mahsulot tavsifini kiriting:",
            parse_mode="Markdown"
        )
    
    elif state == "add_desc":
        user_states[user_id]["temp"]["description"] = message.text
        user_states[user_id]["state"] = "add_price"
        bot.send_message(
            message.chat.id,
            "💰 *3/4 - Narx*\n\n"
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
                "🏷️ *4/4 - Kategoriya*\n\n"
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
        temp = user_states[user_id]["temp"]
        temp["category"] = message.text
        
        products = get_products()
        new_product = {
            "id": len(products) + 1,
            "name": temp["name"],
            "description": temp["description"],
            "price": temp["price"],
            "category": temp["category"],
            "available": True,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        products.append(new_product)
        save_products(products)
        
        # State ni tozalash
        user_states[user_id] = {"state": "idle"}
        
        bot.send_message(
            message.chat.id,
            f"✅ *Mahsulot muvaffaqiyatli qo'shildi!*\n\n"
            f"📌 {new_product['name']}\n"
            f"💰 {format_price(new_product['price'])} so'm\n"
            f"🏷 {new_product['category']}\n\n"
            f"Endi uni do'konda ko'rishingiz mumkin 🛍️",
            parse_mode="Markdown",
            reply_markup=get_admin_menu()
        )


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
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                margin: 0;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
            }
            .container {
                text-align: center;
                padding: 2rem;
            }
            h1 {
                font-size: 3rem;
                margin-bottom: 1rem;
            }
            p {
                font-size: 1.2rem;
                opacity: 0.9;
            }
            .status {
                background: rgba(255,255,255,0.2);
                padding: 1rem;
                border-radius: 1rem;
                margin-top: 2rem;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🛍️ Telegram Shop Bot</h1>
            <p>Bot ishlayapti ✅</p>
            <div class="status">
                <strong>📊 Statistika</strong><br>
                <span id="stats">Yuklanmoqda...</span>
            </div>
        </div>
        <script>
            fetch('/stats')
                .then(res => res.json())
                .then(data => {
                    document.getElementById('stats').innerHTML = `
                        👥 Foydalanuvchilar: ${data.users}<br>
                        🛍️ Mahsulotlar: ${data.products}<br>
                        📦 Zakazlar: ${data.orders}
                    `;
                });
        </script>
    </body>
    </html>
    """)


@app.get("/shop")
async def shop_page():
    """Web App sahifasi"""
    html_content = get_webapp_html()
    return HTMLResponse(content=html_content)


@app.get("/webapp_products.json")
async def get_products_json():
    """Mahsulotlar API"""
    products = get_products()
    # Web App uchun mos format
    webapp_products = []
    for p in products:
        if p.get('available', True):
            webapp_products.append({
                "id": p['id'],
                "name": p['name'],
                "description": p.get('description', ''),
                "price": p['price'],
                "category": p.get('category', '🎁 Boshqa'),
                "available": True
            })
    return JSONResponse(webapp_products)


@app.get("/stats")
async def get_stats():
    """Statistika API"""
    return {
        "users": len(get_users()),
        "products": len(get_products()),
        "orders": len(get_orders())
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
                "available": True,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            },
            {
                "id": 2,
                "name": "Premium Mahsulot",
                "description": "Yuqori sifatli mahsulot",
                "price": 150000,
                "category": "🎁 Boshqa",
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


def get_webapp_html():
    """Web App HTML kodi"""
    return '''<!DOCTYPE html>
<html lang="uz">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>🛍️ Do'konim</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  
  :root {
    --primary: #FF6B35;
    --primary-dark: #e55a26;
    --bg: #F7F8FC;
    --card: #FFFFFF;
    --text: #1A202C;
    --muted: #718096;
    --border: #E2E8F0;
    --shadow: 0 2px 8px rgba(0,0,0,0.05);
    --radius: 12px;
  }
  
  body {
    font-family: 'Inter', sans-serif;
    background: var(--bg);
    color: var(--text);
    padding-bottom: 70px;
  }
  
  /* Header */
  .header {
    background: var(--card);
    padding: 16px;
    position: sticky;
    top: 0;
    z-index: 100;
    box-shadow: var(--shadow);
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  
  .logo {
    font-size: 20px;
    font-weight: 800;
    background: linear-gradient(135deg, var(--primary), #FF8C42);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
  }
  
  .cart-icon {
    position: relative;
    cursor: pointer;
    background: var(--bg);
    padding: 8px 12px;
    border-radius: 50px;
    font-weight: 600;
  }
  
  .cart-count {
    position: absolute;
    top: -5px;
    right: -5px;
    background: var(--primary);
    color: white;
    border-radius: 50%;
    width: 18px;
    height: 18px;
    font-size: 11px;
    display: flex;
    align-items: center;
    justify-content: center;
  }
  
  /* Search */
  .search-box {
    padding: 12px 16px;
  }
  
  .search-input {
    width: 100%;
    padding: 12px 16px;
    border: 1px solid var(--border);
    border-radius: 50px;
    font-size: 14px;
    outline: none;
    background: var(--card);
  }
  
  /* Categories */
  .categories {
    padding: 8px 16px;
    overflow-x: auto;
    white-space: nowrap;
    scrollbar-width: none;
  }
  
  .category-btn {
    display: inline-block;
    padding: 8px 20px;
    margin-right: 8px;
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 50px;
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s;
  }
  
  .category-btn.active {
    background: var(--primary);
    color: white;
    border-color: var(--primary);
  }
  
  /* Products */
  .products {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: 12px;
    padding: 12px;
  }
  
  .product-card {
    background: var(--card);
    border-radius: var(--radius);
    overflow: hidden;
    box-shadow: var(--shadow);
  }
  
  .product-image {
    width: 100%;
    aspect-ratio: 1;
    background: linear-gradient(135deg, #f5f5f5, #e5e5e5);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 48px;
  }
  
  .product-info {
    padding: 12px;
  }
  
  .product-name {
    font-size: 14px;
    font-weight: 700;
    margin-bottom: 4px;
  }
  
  .product-price {
    font-size: 16px;
    font-weight: 800;
    color: var(--primary);
    margin-bottom: 8px;
  }
  
  .add-btn {
    width: 100%;
    padding: 8px;
    background: var(--primary);
    color: white;
    border: none;
    border-radius: 8px;
    font-weight: 600;
    cursor: pointer;
  }
  
  /* Cart Modal */
  .modal {
    display: none;
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    background: var(--card);
    border-radius: 20px 20px 0 0;
    max-height: 80vh;
    overflow-y: auto;
    z-index: 1000;
    box-shadow: 0 -2px 20px rgba(0,0,0,0.1);
  }
  
  .modal.show {
    display: block;
  }
  
  .modal-header {
    padding: 16px;
    border-bottom: 1px solid var(--border);
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  
  .cart-item {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 16px;
    border-bottom: 1px solid var(--border);
  }
  
  .checkout-btn {
    width: 100%;
    padding: 16px;
    background: var(--primary);
    color: white;
    border: none;
    font-size: 16px;
    font-weight: 700;
    cursor: pointer;
  }
  
  .overlay {
    display: none;
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0,0,0,0.5);
    z-index: 999;
  }
  
  .overlay.show {
    display: block;
  }
</style>
</head>
<body>
<div class="header">
    <div class="logo">🛍️ DO'KON</div>
    <div class="cart-icon" onclick="openCart()">
        🛒
        <span class="cart-count" id="cartCount">0</span>
    </div>
</div>

<div class="search-box">
    <input type="text" class="search-input" placeholder="🔍 Qidirish..." id="searchInput" oninput="filterProducts()">
</div>

<div class="categories" id="categories"></div>

<div class="products" id="products"></div>

<div class="overlay" id="overlay" onclick="closeCart()"></div>
<div class="modal" id="cartModal">
    <div class="modal-header">
        <h3>🛒 Savatcha</h3>
        <button onclick="closeCart()" style="background:none;border:none;font-size:24px;">&times;</button>
    </div>
    <div id="cartItems"></div>
    <div style="padding:16px;border-top:1px solid var(--border)">
        <div style="display:flex;justify-content:space-between;margin-bottom:16px">
            <strong>Jami:</strong>
            <strong id="cartTotal">0 so'm</strong>
        </div>
        <button class="checkout-btn" onclick="checkout()">✅ Zakaz berish</button>
    </div>
</div>

<script>
const tg = window.Telegram.WebApp;
tg.ready();
tg.expand();

let products = [];
let cart = {};
let currentCategory = 'all';

async function loadProducts() {
    try {
        const response = await fetch('/webapp_products.json?' + Date.now());
        products = await response.json();
        renderCategories();
        renderProducts();
    } catch (error) {
        console.error('Error loading products:', error);
    }
}

function renderCategories() {
    const categories = ['all', ...new Set(products.map(p => p.category))];
    const container = document.getElementById('categories');
    container.innerHTML = categories.map(cat => `
        <button class="category-btn ${cat === currentCategory ? 'active' : ''}" onclick="filterByCategory('${cat}')">
            ${cat === 'all' ? '🌟 Barchasi' : cat}
        </button>
    `).join('');
}

function filterByCategory(category) {
    currentCategory = category;
    renderCategories();
    renderProducts();
}

function filterProducts() {
    renderProducts();
}

function renderProducts() {
    const search = document.getElementById('searchInput').value.toLowerCase();
    let filtered = products;
    
    if (currentCategory !== 'all') {
        filtered = filtered.filter(p => p.category === currentCategory);
    }
    
    if (search) {
        filtered = filtered.filter(p => p.name.toLowerCase().includes(search));
    }
    
    const container = document.getElementById('products');
    if (filtered.length === 0) {
        container.innerHTML = '<div style="text-align:center;padding:40px">📭 Mahsulot topilmadi</div>';
        return;
    }
    
    container.innerHTML = filtered.map(product => {
        const qty = cart[product.id] || 0;
        return `
            <div class="product-card">
                <div class="product-image">${getCategoryIcon(product.category)}</div>
                <div class="product-info">
                    <div class="product-name">${escapeHtml(product.name)}</div>
                    <div class="product-price">${formatPrice(product.price)} so'm</div>
                    ${qty === 0 ? 
                        `<button class="add-btn" onclick="addToCart(${product.id})">➕ Savatga</button>` :
                        `<div style="display:flex;gap:8px;align-items:center;justify-content:space-between">
                            <button class="add-btn" onclick="updateQuantity(${product.id}, -1)" style="width:40px">-</button>
                            <span style="font-weight:700">${qty}</span>
                            <button class="add-btn" onclick="updateQuantity(${product.id}, 1)" style="width:40px">+</button>
                        </div>`
                    }
                </div>
            </div>
        `;
    }).join('');
}

function getCategoryIcon(category) {
    const icons = {
        '👗 Kiyim': '👗', '👟 Poyabzal': '👟', '💄 Kosmetika': '💄',
        '📱 Elektronika': '📱', '🏠 Uy jihozlari': '🏠', '🍕 Oziq-ovqat': '🍕'
    };
    return icons[category] || '🛍️';
}

function formatPrice(price) {
    return price.toString().replace(/\\B(?=(\\d{3})+(?!\\d))/g, ' ');
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function addToCart(productId) {
    cart[productId] = (cart[productId] || 0) + 1;
    updateCartUI();
    renderProducts();
    if (tg.HapticFeedback) tg.HapticFeedback.impactOccurred('light');
}

function updateQuantity(productId, delta) {
    const newQty = (cart[productId] || 0) + delta;
    if (newQty <= 0) {
        delete cart[productId];
    } else {
        cart[productId] = newQty;
    }
    updateCartUI();
    renderProducts();
}

function updateCartUI() {
    const total = Object.values(cart).reduce((a,b) => a+b, 0);
    document.getElementById('cartCount').textContent = total;
    
    let cartTotal = 0;
    const cartItemsHtml = Object.entries(cart).map(([id, qty]) => {
        const product = products.find(p => p.id == id);
        if (!product) return '';
        const subtotal = product.price * qty;
        cartTotal += subtotal;
        return `
            <div class="cart-item">
                <div>
                    <div style="font-weight:600">${product.name}</div>
                    <div style="font-size:12px;color:var(--muted)">${qty} x ${formatPrice(product.price)} so'm</div>
                </div>
                <div style="font-weight:700">${formatPrice(subtotal)} so'm</div>
            </div>
        `;
    }).join('');
    
    document.getElementById('cartItems').innerHTML = cartItemsHtml || '<div style="padding:20px;text-align:center">Savat bo\'sh</div>';
    document.getElementById('cartTotal').textContent = formatPrice(cartTotal) + ' so\'m';
}

function openCart() {
    if (Object.keys(cart).length === 0) {
        tg.showPopup({ message: 'Savat bo\'sh!' });
        return;
    }
    document.getElementById('overlay').classList.add('show');
    document.getElementById('cartModal').classList.add('show');
}

function closeCart() {
    document.getElementById('overlay').classList.remove('show');
    document.getElementById('cartModal').classList.remove('show');
}

function checkout() {
    if (Object.keys(cart).length === 0) {
        tg.showPopup({ message: 'Savat bo\'sh!' });
        return;
    }
    
    tg.showPopup({
        title: 'Zakaz rasmiylashtirish',
        message: 'Manzilingizni kiriting',
        buttons: [{type: 'default', text: 'OK'}]
    }, (buttonId) => {
        tg.showPrompt({
            title: 'Manzil',
            message: 'Yetkazib berish manzili:',
            placeholder: 'Toshkent, Yunusobod...'
        }, (address) => {
            if (address) {
                const items = Object.entries(cart).map(([id, qty]) => {
                    const p = products.find(p => p.id == id);
                    return {id: p.id, name: p.name, price: p.price, qty};
                });
                
                const orderData = {
                    items: items,
                    total: Object.entries(cart).reduce((sum, [id, qty]) => {
                        const p = products.find(p => p.id == id);
                        return sum + (p ? p.price * qty : 0);
                    }, 0),
                    address: address
                };
                
                tg.sendData(JSON.stringify(orderData));
                cart = {};
                updateCartUI();
                renderProducts();
                closeCart();
                
                tg.showPopup({
                    message: '✅ Zakaz qabul qilindi!\\nTez orada bog\'lanamiz.',
                    buttons: [{type: 'ok'}]
                });
            }
        });
    });
}

loadProducts();
</script>
</body>
</html>'''


# ==================== MAIN ====================
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
