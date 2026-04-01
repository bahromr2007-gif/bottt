import telebot
from telebot import types
import json
import os
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse

BOT_TOKEN = "8778358404:AAHmM4e2OnROyXLCsGXERCbXd3arzl7kPS0"
RENDER_EXTERNAL_URL = "https://bottt-02j7.onrender.com"
WEB_APP_URL = f"{RENDER_EXTERNAL_URL}/shop"

ADMIN_IDS = [8735360012]

PRODUCTS_FILE = "products.json"
ORDERS_FILE = "orders.json"
USERS_FILE = "users.json"

bot = telebot.TeleBot(BOT_TOKEN)
app = FastAPI()

user_states = {}


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


def update_webapp_products(products):
    with open("webapp_products.json", "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)


def is_admin(user_id):
    return user_id in ADMIN_IDS


def get_main_menu(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)

    shop_btn = types.KeyboardButton(
        "🛍️ Do'konni ochish",
        web_app=types.WebAppInfo(url=WEB_APP_URL)
    )
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
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add(
        types.KeyboardButton("➕ Mahsulot qo'shish"),
        types.KeyboardButton("📋 Barcha mahsulotlar")
    )
    markup.add(types.KeyboardButton("🔙 Asosiy menyu"))
    return markup


def get_cancel_btn():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("❌ Bekor qilish"))
    return markup


@bot.message_handler(commands=["start"])
def start(message):
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
            f"👋 Assalomu alaykum, *{message.from_user.first_name}*!\n\n"
            "🛍️ Do'konimizga xush kelibsiz!\n\n"
            "Davom etish uchun telefon raqamingizni yuboring 👇",
            parse_mode="Markdown",
            reply_markup=markup
        )
        user_states[user_id] = {"state": "waiting_contact", "temp": {}}
    else:
        bot.send_message(
            message.chat.id,
            "Kerakli bo'limni tanlang 👇",
            reply_markup=get_main_menu(user_id)
        )


@bot.message_handler(content_types=["contact"])
def get_contact(message):
    user_id = message.from_user.id
    state = user_states.get(user_id, {}).get("state")

    if state == "waiting_contact":
        users = get_users()
        users[str(user_id)] = {
            "name": message.from_user.first_name,
            "username": message.from_user.username or "",
            "phone": message.contact.phone_number,
            "joined": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "user_id": user_id
        }
        save_users(users)

        user_states[user_id] = {"state": "idle", "temp": {}}

        bot.send_message(
            message.chat.id,
            "✅ Ro'yxatdan o'tdingiz!",
            reply_markup=get_main_menu(user_id)
        )


@bot.message_handler(func=lambda m: m.text == "👨‍💼 Admin panel")
def admin_panel(message):
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "❌ Siz admin emassiz.")
        return

    bot.send_message(
        message.chat.id,
        "👨‍💼 Admin panel",
        reply_markup=get_admin_menu()
    )


@bot.message_handler(func=lambda m: m.text == "🔙 Asosiy menyu")
def back_main(message):
    user_states[message.from_user.id] = {"state": "idle", "temp": {}}
    bot.send_message(
        message.chat.id,
        "🏠 Asosiy menyu",
        reply_markup=get_main_menu(message.from_user.id)
    )


@bot.message_handler(func=lambda m: m.text == "➕ Mahsulot qo'shish")
def add_product_start(message):
    if not is_admin(message.from_user.id):
        return

    user_states[message.from_user.id] = {"state": "add_name", "temp": {}}
    bot.send_message(
        message.chat.id,
        "1️⃣ Mahsulot nomini kiriting:",
        reply_markup=get_cancel_btn()
    )


@bot.message_handler(func=lambda m: m.text == "📋 Barcha mahsulotlar")
def show_products(message):
    if not is_admin(message.from_user.id):
        return

    products = get_products()
    if not products:
        bot.send_message(message.chat.id, "📋 Hali mahsulot yo'q.")
        return

    text = "📋 Barcha mahsulotlar:\n\n"
    for p in products:
        text += f"#{p['id']} {p['name']}\n"
        text += f"💰 {p['price']:,} so'm\n"
        text += f"🏷 {p['category']}\n\n"

    bot.send_message(message.chat.id, text, reply_markup=get_admin_menu())


@bot.message_handler(func=lambda m: m.text == "❌ Bekor qilish")
def cancel_action(message):
    user_states[message.from_user.id] = {"state": "idle", "temp": {}}
    bot.send_message(
        message.chat.id,
        "❌ Bekor qilindi",
        reply_markup=get_admin_menu() if is_admin(message.from_user.id) else get_main_menu(message.from_user.id)
    )


@bot.message_handler(func=lambda m: m.text == "📦 Mening zakaz larim")
def my_orders(message):
    user_id = message.from_user.id
    orders = get_orders()
    user_orders = [o for o in orders if o.get("user_id") == user_id]

    if not user_orders:
        bot.send_message(message.chat.id, "📦 Hozircha zakaz laringiz yo'q.")
        return

    text = "📦 Sizning zakaz laringiz:\n\n"
    for o in user_orders[-5:]:
        text += f"📦 Zakaz #{o['id']}\n"
        text += f"📅 {o['date']}\n"
        text += f"💰 {o['total']:,} so'm\n\n"

    bot.send_message(message.chat.id, text)


@bot.message_handler(func=lambda m: m.text == "📞 Aloqa")
def contact_info(message):
    bot.send_message(message.chat.id, "📞 Admin: @admin_username")


@bot.message_handler(func=lambda m: m.text == "ℹ️ Yordam")
def help_info(message):
    bot.send_message(message.chat.id, "ℹ️ Do'konni ochib mahsulot tanlang.")


@bot.message_handler(content_types=["web_app_data"])
def web_app_order(message):
    try:
        data = json.loads(message.web_app_data.data)
        orders = get_orders()

        new_order = {
            "id": len(orders) + 1,
            "user_id": message.from_user.id,
            "user": message.from_user.first_name,
            "items": data.get("items", []),
            "total": data.get("total", 0),
            "date": datetime.now().strftime("%Y-%m-%d %H:%M")
        }

        orders.append(new_order)
        save_orders(orders)

        bot.send_message(
            message.chat.id,
            f"✅ Zakaz qabul qilindi!\nJami: {new_order['total']} so'm"
        )
    except Exception as e:
        print("web_app_order error:", e)
        bot.send_message(message.chat.id, "❌ Xatolik yuz berdi.")


@bot.message_handler(content_types=["text"])
def handle_states(message):
    user_id = message.from_user.id
    state_data = user_states.get(user_id, {"state": "idle", "temp": {}})
    state = state_data.get("state", "idle")

    if state == "add_name":
        user_states[user_id]["temp"]["name"] = message.text
        user_states[user_id]["state"] = "add_desc"
        bot.send_message(message.chat.id, "2️⃣ Tavsif kiriting:")

    elif state == "add_desc":
        user_states[user_id]["temp"]["description"] = message.text
        user_states[user_id]["state"] = "add_price"
        bot.send_message(message.chat.id, "3️⃣ Narx kiriting: masalan 50000")

    elif state == "add_price":
        try:
            price = int(message.text.replace(" ", "").replace(",", ""))
            user_states[user_id]["temp"]["price"] = price
            user_states[user_id]["state"] = "add_category"

            markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
            markup.add("👗 Kiyim", "👟 Poyabzal", "💄 Kosmetika", "📱 Elektronika")
            markup.add("🏠 Uy jihozlari", "🍕 Oziq-ovqat", "🎁 Boshqa")
            markup.add("❌ Bekor qilish")

            bot.send_message(message.chat.id, "4️⃣ Kategoriyani tanlang:", reply_markup=markup)
        except:
            bot.send_message(message.chat.id, "❌ Narxni raqam bilan kiriting.")

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
            "photo": None,
            "available": True,
            "added": datetime.now().strftime("%Y-%m-%d %H:%M")
        }

        products.append(new_product)
        save_products(products)
        update_webapp_products(products)

        user_states[user_id] = {"state": "idle", "temp": {}}

        bot.send_message(
            message.chat.id,
            f"✅ Mahsulot qo'shildi:\n\n"
            f"📌 {new_product['name']}\n"
            f"💰 {new_product['price']:,} so'm\n"
            f"🏷 {new_product['category']}",
            reply_markup=get_admin_menu()
        )


@app.on_event("startup")
async def startup():
    if not os.path.exists(PRODUCTS_FILE):
        sample_products = [
            {
                "id": 1,
                "name": "Misol Mahsulot 1",
                "description": "Bu test mahsulot",
                "price": 50000,
                "category": "🎁 Boshqa",
                "photo": None,
                "available": True,
                "added": "2026-04-02"
            }
        ]
        save_products(sample_products)
        update_webapp_products(sample_products)

    webhook_url = f"{RENDER_EXTERNAL_URL}/bot"
    bot.remove_webhook()
    bot.set_webhook(url=webhook_url)
    print("Webhook:", webhook_url)


@app.get("/")
def home():
    return {"status": "ishlayapti"}


@app.get("/shop")
def shop():
    return FileResponse("index.html")


@app.get("/webapp_products.json")
def products():
    return JSONResponse(get_products())


@app.post("/bot")
async def webhook(req: Request):
    data = await req.json()
    update = telebot.types.Update.de_json(data)
    bot.process_new_updates([update])
    return {"ok": True}
