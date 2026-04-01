import telebot
from telebot import types
import json
import os
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse

# 🔥 HAMMASI ICHIDA
BOT_TOKEN = "8778358404:AAHmM4e2OnROyXLCsGXERCbXd3arzl7kPS0"
RENDER_EXTERNAL_URL = "https://bottt-02j7.onrender.com"

WEB_APP_URL = f"{RENDER_EXTERNAL_URL}/shop"

ADMIN_IDS = [8735360012]

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


def update_webapp_products(products):
    with open("webapp_products.json", "w", encoding="utf-8") as f:
        json.dump(products, f, ensure_ascii=False, indent=2)


bot = telebot.TeleBot(BOT_TOKEN)
app = FastAPI()

user_states = {}


def is_admin(user_id):
    return user_id in ADMIN_IDS


def get_main_menu(user_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)

    btn = types.KeyboardButton(
        "🛍️ Do'konni ochish",
        web_app=types.WebAppInfo(url=WEB_APP_URL)
    )

    markup.add(btn)
    return markup


# ================= BOT =================

@bot.message_handler(commands=["start"])
def start(message):
    bot.send_message(
        message.chat.id,
        "Salom 😎\nDo'konni ochish tugmasini bos",
        reply_markup=get_main_menu(message.from_user.id)
    )


@bot.message_handler(content_types=["web_app_data"])
def web_app_order(message):
    data = json.loads(message.web_app_data.data)

    orders = get_orders()

    new_order = {
        "id": len(orders) + 1,
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


# ================= FASTAPI =================

@app.on_event("startup")
async def startup():
    print("Server ishga tushdi")

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
