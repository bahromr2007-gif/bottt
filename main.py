import telebot
from telebot import types
import json
import os
import logging
from datetime import datetime, timedelta
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
import uvicorn
import threading
import random
import re
from typing import Dict, List, Optional, Any

# ============ KONFIGURATSIYA ============
# Eslatma:
# Pastdagi qiymatlarni o'zingiznikiga almashtiring.
BOT_TOKEN = os.getenv("BOT_TOKEN", "8778358404:AAHmM4e2OnROyXLCsGXERCbXd3arzl7kPS0")
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL", "https://bottt-02j7.onrender.com")
WEB_APP_URL = f"{RENDER_EXTERNAL_URL}/shop"
ADMIN_IDS = [8735360012]

# Yetkazib berish sozlamalari
DELIVERY_FEE = 15000
FREE_DELIVERY_AMOUNT = 100000
MIN_ORDER_AMOUNT = 5000
MAX_ORDER_ITEMS = 50

# Fayllar
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
TEMPLATE_DIR = os.path.join(BASE_DIR, "templates")

PRODUCTS_FILE = os.path.join(DATA_DIR, "products.json")
ORDERS_FILE = os.path.join(DATA_DIR, "orders.json")
USERS_FILE = os.path.join(DATA_DIR, "users.json")
ADDRESSES_FILE = os.path.join(DATA_DIR, "addresses.json")
FAVORITES_FILE = os.path.join(DATA_DIR, "favorites.json")
PROMO_FILE = os.path.join(DATA_DIR, "promo.json")
REVIEWS_FILE = os.path.join(DATA_DIR, "reviews.json")
SETTINGS_FILE = os.path.join(DATA_DIR, "settings.json")

# Logging sozlamalari
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ============ MA'LUMOTLAR BAZASI ============
class Database:
    """JSON asosidagi ma'lumotlar bazasi"""

    def __init__(self):
        self._lock = threading.Lock()
        self._ensure_data_dir()
        self._init_files()

    def _ensure_data_dir(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        os.makedirs(TEMPLATE_DIR, exist_ok=True)

    def _default_for_file(self, file_path: str) -> Any:
        if file_path == USERS_FILE:
            return {}
        if file_path == ADDRESSES_FILE:
            return {}
        if file_path == FAVORITES_FILE:
            return {}
        if file_path == REVIEWS_FILE:
            return {}
        if file_path == SETTINGS_FILE:
            return {
                "delivery_fee": DELIVERY_FEE,
                "free_delivery_amount": FREE_DELIVERY_AMOUNT
            }
        return []

    def _init_files(self):
        files = [
            PRODUCTS_FILE,
            ORDERS_FILE,
            USERS_FILE,
            ADDRESSES_FILE,
            FAVORITES_FILE,
            PROMO_FILE,
            REVIEWS_FILE,
            SETTINGS_FILE
        ]
        for file_path in files:
            if not os.path.exists(file_path):
                self._save_json(file_path, self._default_for_file(file_path))

    def _load_json(self, file_path: str) -> Any:
        with self._lock:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    default = self._default_for_file(file_path)
                    if isinstance(default, dict) and not isinstance(data, dict):
                        return default
                    if isinstance(default, list) and not isinstance(data, list):
                        return default
                    return data
            except (FileNotFoundError, json.JSONDecodeError):
                return self._default_for_file(file_path)

    def _save_json(self, file_path: str, data: Any):
        with self._lock:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

    # Mahsulotlar
    def get_products(self, only_available: bool = True) -> List[Dict]:
        products = self._load_json(PRODUCTS_FILE)
        if only_available:
            products = [p for p in products if p.get("available", True)]
        return sorted(products, key=lambda x: x.get("id", 0))

    def get_product(self, product_id: int) -> Optional[Dict]:
        products = self.get_products(only_available=False)
        return next((p for p in products if p.get("id") == product_id), None)

    def add_product(self, product: Dict) -> Dict:
        products = self.get_products(only_available=False)
        product["id"] = max([p.get("id", 0) for p in products] + [0]) + 1
        product["created_at"] = datetime.now().isoformat()
        product.setdefault("available", True)
        product.setdefault("rating", 0)
        product.setdefault("reviews_count", 0)
        products.append(product)
        self._save_json(PRODUCTS_FILE, products)
        return product

    def update_product(self, product_id: int, updates: Dict) -> Optional[Dict]:
        products = self.get_products(only_available=False)
        for i, p in enumerate(products):
            if p.get("id") == product_id:
                products[i].update(updates)
                self._save_json(PRODUCTS_FILE, products)
                return products[i]
        return None

    def delete_product(self, product_id: int) -> bool:
        products = self.get_products(only_available=False)
        new_products = [p for p in products if p.get("id") != product_id]
        if len(new_products) != len(products):
            self._save_json(PRODUCTS_FILE, new_products)
            return True
        return False

    # Zakazlar
    def get_orders(self, user_id: Optional[int] = None, status: Optional[str] = None) -> List[Dict]:
        orders = self._load_json(ORDERS_FILE)
        if user_id is not None:
            orders = [o for o in orders if o.get("user_id") == user_id]
        if status:
            orders = [o for o in orders if o.get("status") == status]
        return sorted(orders, key=lambda x: x.get("date", ""), reverse=True)

    def get_order(self, order_id: int) -> Optional[Dict]:
        orders = self.get_orders()
        return next((o for o in orders if o.get("id") == order_id), None)

    def add_order(self, order: Dict) -> Dict:
        orders = self.get_orders()
        order["id"] = max([o.get("id", 0) for o in orders] + [1000]) + 1
        order["created_at"] = datetime.now().isoformat()
        orders.append(order)
        self._save_json(ORDERS_FILE, orders)
        return order

    def update_order(self, order_id: int, updates: Dict) -> Optional[Dict]:
        orders = self.get_orders()
        for i, o in enumerate(orders):
            if o.get("id") == order_id:
                orders[i].update(updates)
                self._save_json(ORDERS_FILE, orders)
                return orders[i]
        return None

    # Foydalanuvchilar
    def get_users(self) -> Dict[str, Dict]:
        return self._load_json(USERS_FILE)

    def get_user(self, user_id: int) -> Optional[Dict]:
        users = self.get_users()
        return users.get(str(user_id))

    def add_user(self, user_id: int, user_data: Dict) -> Dict:
        users = self.get_users()
        users[str(user_id)] = user_data
        self._save_json(USERS_FILE, users)
        return user_data

    def update_user(self, user_id: int, updates: Dict) -> Optional[Dict]:
        users = self.get_users()
        if str(user_id) in users:
            users[str(user_id)].update(updates)
            self._save_json(USERS_FILE, users)
            return users[str(user_id)]
        return None

    def get_all_users(self) -> List[Dict]:
        return list(self.get_users().values())

    # Manzillar
    def get_addresses(self, user_id: int) -> List[str]:
        addresses = self._load_json(ADDRESSES_FILE)
        return addresses.get(str(user_id), [])

    def add_address(self, user_id: int, address: str) -> List[str]:
        addresses = self._load_json(ADDRESSES_FILE)
        user_addresses = addresses.get(str(user_id), [])
        if address not in user_addresses:
            user_addresses.append(address)
            if len(user_addresses) > 10:
                user_addresses = user_addresses[-10:]
            addresses[str(user_id)] = user_addresses
            self._save_json(ADDRESSES_FILE, addresses)
        return user_addresses

    def delete_address(self, user_id: int, address: str) -> bool:
        addresses = self._load_json(ADDRESSES_FILE)
        user_addresses = addresses.get(str(user_id), [])
        if address in user_addresses:
            user_addresses.remove(address)
            addresses[str(user_id)] = user_addresses
            self._save_json(ADDRESSES_FILE, addresses)
            return True
        return False

    # Sevimlilar
    def get_favorites(self, user_id: int) -> List[int]:
        favorites = self._load_json(FAVORITES_FILE)
        return favorites.get(str(user_id), [])

    def add_favorite(self, user_id: int, product_id: int) -> bool:
        favorites = self._load_json(FAVORITES_FILE)
        user_favs = favorites.get(str(user_id), [])
        if product_id not in user_favs:
            user_favs.append(product_id)
            favorites[str(user_id)] = user_favs
            self._save_json(FAVORITES_FILE, favorites)
            return True
        return False

    def remove_favorite(self, user_id: int, product_id: int) -> bool:
        favorites = self._load_json(FAVORITES_FILE)
        user_favs = favorites.get(str(user_id), [])
        if product_id in user_favs:
            user_favs.remove(product_id)
            favorites[str(user_id)] = user_favs
            self._save_json(FAVORITES_FILE, favorites)
            return True
        return False

    # Promo kodlar
    def get_promos(self) -> List[Dict]:
        return self._load_json(PROMO_FILE)

    def get_promo(self, code: str) -> Optional[Dict]:
        promos = self.get_promos()
        code = code.upper().strip()
        for p in promos:
            if p.get("code") == code and p.get("active", True):
                expires_at = p.get("expires_at")
                if expires_at:
                    try:
                        if datetime.fromisoformat(expires_at) < datetime.now():
                            continue
                    except ValueError:
                        pass
                return p
        return None

    def add_promo(self, promo: Dict) -> Dict:
        promos = self.get_promos()
        promo["code"] = promo["code"].upper().strip()
        promos.append(promo)
        self._save_json(PROMO_FILE, promos)
        return promo

    def use_promo(self, code: str) -> bool:
        promos = self.get_promos()
        changed = False
        for p in promos:
            if p.get("code") == code.upper().strip():
                p["used_count"] = p.get("used_count", 0) + 1
                if p.get("usage_limit") and p["used_count"] >= p["usage_limit"]:
                    p["active"] = False
                changed = True
                break
        if changed:
            self._save_json(PROMO_FILE, promos)
        return changed

    # Baholar
    def get_reviews(self, product_id: Optional[int] = None):
        reviews = self._load_json(REVIEWS_FILE)
        if product_id is not None:
            return reviews.get(str(product_id), [])
        return reviews

    def add_review(self, product_id: int, user_id: int, rating: int, comment: str = "") -> Dict:
        reviews = self._load_json(REVIEWS_FILE)
        product_reviews = reviews.get(str(product_id), [])
        review = {
            "user_id": user_id,
            "rating": rating,
            "comment": comment,
            "date": datetime.now().isoformat()
        }
        product_reviews.append(review)
        reviews[str(product_id)] = product_reviews
        self._save_json(REVIEWS_FILE, reviews)

        product = self.get_product(product_id)
        if product:
            avg_rating = sum(r["rating"] for r in product_reviews) / len(product_reviews)
            self.update_product(
                product_id,
                {
                    "rating": round(avg_rating, 1),
                    "reviews_count": len(product_reviews)
                }
            )
        return review

    # Statistika
    def get_stats(self) -> Dict:
        users = self.get_users()
        orders = self.get_orders()
        products = self.get_products(only_available=False)

        today = datetime.now().strftime("%Y-%m-%d")
        week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

        today_orders = [o for o in orders if str(o.get("date", "")).startswith(today)]
        week_orders = [o for o in orders if str(o.get("date", "")) >= week_ago]

        category_stats = {}
        for product in products:
            cat = product.get("category", "Boshqa")
            category_stats[cat] = category_stats.get(cat, 0) + 1

        return {
            "total_users": len(users),
            "total_products": len(products),
            "total_orders": len(orders),
            "total_revenue": sum(o.get("total", 0) for o in orders),
            "today_orders": len(today_orders),
            "today_revenue": sum(o.get("total", 0) for o in today_orders),
            "week_orders": len(week_orders),
            "week_revenue": sum(o.get("total", 0) for o in week_orders),
            "category_stats": category_stats,
            "pending_orders": len([o for o in orders if o.get("status") in ["new", "accepted", "preparing"]])
        }


db = Database()


# ============ YORDAMCHI FUNKSIYALAR ============
def format_price(price: int) -> str:
    return f"{price:,}".replace(",", " ")


def format_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone)
    if len(digits) == 9:
        return f"+998 {digits[:2]} {digits[2:5]} {digits[5:7]} {digits[7:]}"
    if len(digits) == 12 and digits.startswith("998"):
        return f"+{digits[:3]} {digits[3:5]} {digits[5:8]} {digits[8:10]} {digits[10:]}"
    return phone


def validate_phone(phone: str) -> bool:
    digits = re.sub(r"\D", "", phone)
    return len(digits) in [9, 12, 13]


def calculate_delivery_fee(total: int) -> int:
    settings = db._load_json(SETTINGS_FILE)
    free_amount = settings.get("free_delivery_amount", FREE_DELIVERY_AMOUNT)
    return 0 if total >= free_amount else settings.get("delivery_fee", DELIVERY_FEE)


def calculate_discount(total: int, promo_code: str = None) -> tuple:
    discount_amount = 0
    discount_percent = 0

    if promo_code:
        promo = db.get_promo(promo_code)
        if promo and promo.get("active", True):
            if promo.get("discount_type") == "percentage":
                discount_percent = promo.get("discount_value", 0)
                discount_amount = int(total * discount_percent / 100)
            else:
                discount_amount = min(promo.get("discount_value", 0), total)

    return discount_amount, discount_percent


def get_order_status_text(status: str) -> dict:
    statuses = {
        "new": {"text": "Yangi zakaz", "emoji": "🆕", "color": "#FF6B35"},
        "accepted": {"text": "Qabul qilindi", "emoji": "✅", "color": "#48BB78"},
        "preparing": {"text": "Tayyorlanmoqda", "emoji": "🔧", "color": "#F6AD55"},
        "courier": {"text": "Kuryerga berildi", "emoji": "🚚", "color": "#4299E1"},
        "delivering": {"text": "Yetkazilmoqda", "emoji": "🚛", "color": "#9F7AEA"},
        "delivered": {"text": "Yetkazildi", "emoji": "📦", "color": "#48BB78"},
        "cancelled": {"text": "Bekor qilindi", "emoji": "❌", "color": "#F56565"}
    }
    return statuses.get(status, {"text": status, "emoji": "📋", "color": "#718096"})


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def escape_markdown(text: str) -> str:
    special_chars = r'_*[]()~`>#+-=|{}.!'
    return "".join(f"\\{c}" if c in special_chars else c for c in str(text))


def read_shop_template() -> str:
    template_path = os.path.join(TEMPLATE_DIR, "shop.html")
    with open(template_path, "r", encoding="utf-8") as f:
        return f.read()


# ============ KLAVIATURALAR ============
def get_main_keyboard(user_id: int) -> types.ReplyKeyboardMarkup:
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)

    shop_btn = types.KeyboardButton(
        "🛍️ DO'KON",
        web_app=types.WebAppInfo(url=WEB_APP_URL)
    )
    markup.add(shop_btn)

    buttons = [
        "📦 Mening zakazlarim",
        "❤️ Sevimlilar",
        "📍 Manzillarim",
        "🎁 Promo kodlar",
        "📞 Aloqa",
        "ℹ️ Yordam"
    ]
    markup.add(*buttons)

    if is_admin(user_id):
        markup.add("👨‍💼 ADMIN PANEL")

    return markup


def get_admin_keyboard() -> types.ReplyKeyboardMarkup:
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    buttons = [
        "➕ Mahsulot qo'shish",
        "📋 Mahsulotlar ro'yxati",
        "📦 Zakazlar",
        "📊 Statistika",
        "🎁 Promo kod yaratish",
        "📢 Xabar yuborish",
        "👥 Foydalanuvchilar",
        "⚙️ Sozlamalar"
    ]
    markup.add(*buttons)
    markup.add("🔙 Asosiy menyu")
    return markup


def get_cancel_keyboard() -> types.ReplyKeyboardMarkup:
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("❌ Bekor qilish")
    return markup


def get_category_keyboard() -> types.ReplyKeyboardMarkup:
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    categories = [
        "👗 Kiyim",
        "👟 Poyabzal",
        "📱 Elektronika",
        "🏠 Uy jihozlari",
        "🍕 Oziq-ovqat",
        "🎁 Boshqa"
    ]
    for cat in categories:
        markup.add(types.KeyboardButton(cat))
    markup.add("❌ Bekor qilish")
    return markup


def get_order_status_keyboard(order_id: int) -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup(row_width=2)
    statuses = [
        ("✅ Qabul qilish", "accepted"),
        ("🔧 Tayyorlash", "preparing"),
        ("🚚 Kuryerga", "courier"),
        ("🚛 Yetkazish", "delivering"),
        ("📦 Yetkazildi", "delivered"),
        ("❌ Bekor qilish", "cancelled")
    ]
    for label, status in statuses:
        markup.add(types.InlineKeyboardButton(label, callback_data=f"status_{order_id}_{status}"))
    return markup


def get_order_actions_keyboard(order_id: int, is_delivered: bool = False) -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔄 Qayta zakaz", callback_data=f"reorder_{order_id}"))
    if is_delivered:
        markup.add(types.InlineKeyboardButton("⭐ Baholash", callback_data=f"review_{order_id}"))
    return markup


# ============ BOT VA FASTAPI ============
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="Markdown")
app = FastAPI(title="Telegram Shop Bot", version="4.0.0")
user_states: Dict[int, Dict] = {}


# ============ BOT HANDLERLAR ============
@bot.message_handler(commands=["start"])
def start_command(message: types.Message):
    user_id = message.from_user.id
    user = db.get_user(user_id)

    if not user:
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        contact_btn = types.KeyboardButton("📱 Telefon raqam yuborish", request_contact=True)
        markup.add(contact_btn)

        bot.send_message(
            message.chat.id,
            f"👋 *Assalomu alaykum {escape_markdown(message.from_user.first_name)}!*\n\n"
            "🚀 *Do'konimizga xush kelibsiz!*\n\n"
            "📝 Ro'yxatdan o'tish uchun telefon raqamingizni yuboring 👇",
            reply_markup=markup
        )
        user_states[user_id] = {"state": "waiting_contact"}
    else:
        bot.send_message(
            message.chat.id,
            "🏠 *Asosiy menyu*",
            reply_markup=get_main_keyboard(user_id)
        )
        user_states[user_id] = {"state": "idle"}


@bot.message_handler(content_types=["contact"])
def handle_contact(message: types.Message):
    user_id = message.from_user.id

    if user_states.get(user_id, {}).get("state") != "waiting_contact":
        return

    if message.contact:
        phone = message.contact.phone_number
    else:
        bot.send_message(message.chat.id, "❌ Iltimos, telefon raqam tugmasini bosing!")
        return

    if not validate_phone(phone):
        bot.send_message(
            message.chat.id,
            "❌ *Noto'g'ri telefon raqam!*\n\nIltimos, to'g'ri raqam yuboring."
        )
        return

    user_data = {
        "user_id": user_id,
        "name": message.from_user.first_name,
        "username": message.from_user.username,
        "phone": format_phone(phone),
        "joined": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_orders": 0,
        "total_spent": 0,
        "language": "uz"
    }
    db.add_user(user_id, user_data)

    bot.send_message(
        message.chat.id,
        "✅ *Ro'yxatdan o'tdingiz!*\n\nEndi xarid qilishingiz mumkin 🛍️",
        reply_markup=get_main_keyboard(user_id)
    )
    user_states[user_id] = {"state": "idle"}

    for admin_id in ADMIN_IDS:
        try:
            bot.send_message(
                admin_id,
                f"🆕 *Yangi foydalanuvchi!*\n\n"
                f"👤 {message.from_user.first_name}\n"
                f"📞 {format_phone(phone)}\n"
                f"🆔 {user_id}\n"
                f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )
        except Exception:
            pass


@bot.message_handler(func=lambda m: m.text == "🛍️ DO'KON")
def shop_button(message: types.Message):
    pass


@bot.message_handler(func=lambda m: m.text == "📦 Mening zakazlarim")
def my_orders(message: types.Message):
    user_id = message.from_user.id
    orders = db.get_orders(user_id)

    if not orders:
        bot.send_message(
            message.chat.id,
            "📭 *Zakazlaringiz yo'q*\n\n🛍️ Do'konni ochib xarid qiling!"
        )
        return

    for order in orders[:10]:
        status_info = get_order_status_text(order.get("status", "new"))
        items_text = "\n".join([
            f"  • {name} x{qty} = {format_price(price * qty)} so'm"
            for item in order.get("items", [])
            for name in [item.get('name', "Noma'lum")]
            for qty in [item.get('quantity', 1)]
            for price in [item.get('price', 0)]
        ])

        text = f"""
{status_info['emoji']} *Zakaz #{order['id']}*
📅 {order.get('date', "Noma'lum")}
💰 {format_price(order.get('total', 0))} so'm
📊 *Holat:* {status_info['text']}

📦 *Mahsulotlar:*
{items_text}

📍 *Manzil:* {order.get('address', "Noma'lum")}
"""
        if order.get("eta"):
            text += f"\n⏱ *Yetib borish vaqti:* {order['eta']}"
        if order.get("courier_phone"):
            text += f"\n📞 *Kuryer:* {order['courier_phone']}"

        markup = get_order_actions_keyboard(order["id"], order.get("status") == "delivered")
        bot.send_message(message.chat.id, text, reply_markup=markup)


@bot.message_handler(func=lambda m: m.text == "❤️ Sevimlilar")
def my_favorites(message: types.Message):
    user_id = message.from_user.id
    favorites = db.get_favorites(user_id)
    products = db.get_products()

    if not favorites:
        bot.send_message(
            message.chat.id,
            "❤️ *Sevimli mahsulotlaringiz yo'q*\n\nMahsulotlarni ❤️ bosib saqlang!"
        )
        return

    fav_products = [p for p in products if p.get("id") in favorites]
    if not fav_products:
        bot.send_message(message.chat.id, "❤️ Sevimli mahsulotlar topilmadi!")
        return

    text = "❤️ *Sevimli mahsulotlaringiz:*\n\n"
    for p in fav_products:
        text += f"• {escape_markdown(p['name'])} - {format_price(p['price'])} so'm\n"

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🗑 Barchasini tozalash", callback_data="clear_favorites"))
    bot.send_message(message.chat.id, text, reply_markup=markup)


@bot.message_handler(func=lambda m: m.text == "📍 Manzillarim")
def my_addresses(message: types.Message):
    user_id = message.from_user.id
    addresses = db.get_addresses(user_id)

    if not addresses:
        bot.send_message(
            message.chat.id,
            "📍 *Sizning manzillaringiz yo'q*\n\nZakaz berishda manzil avtomatik saqlanadi."
        )
        return

    text = "📍 *Sizning manzillaringiz:*\n\n"
    for i, addr in enumerate(addresses, 1):
        text += f"{i}. {escape_markdown(addr)}\n"

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🗑 Manzil o'chirish", callback_data="delete_address"))
    bot.send_message(message.chat.id, text, reply_markup=markup)


@bot.message_handler(func=lambda m: m.text == "🎁 Promo kodlar")
def promo_codes(message: types.Message):
    text = """
🎁 *Promo kodlar*

Aktiv promo kodlarni kiriting va chegirma oling!

*Qanday ishlatiladi?*
1. Savatchaga mahsulotlarni qo'shing
2. Zakaz berishda promo kodni kiriting
3. Chegirma avtomatik qo'llanadi

*Aktiv promo kodlar:*
• WELCOME10 - 10% chegirma
• WELCOME20 - 20% chegirma

📌 *Eslatma:* Har bir promo kod bir marta ishlatiladi!
"""
    bot.send_message(message.chat.id, text)


@bot.message_handler(func=lambda m: m.text == "📞 Aloqa")
def contact_info(message: types.Message):
    text = """
📞 *Aloqa ma'lumotlari*

📱 *Telefon:* +998 90 123 45 67
📧 *Email:* support@shop.uz
🌐 *Website:* https://shop.uz

🕐 *Ish vaqti:* 09:00 - 21:00 (Dushanba - Shanba)

📢 *Ijtimoiy tarmoqlar:*
• Telegram: @shop_support
• Instagram: @shop_uz
• Facebook: @shop_uz
"""
    bot.send_message(message.chat.id, text)


@bot.message_handler(func=lambda m: m.text == "ℹ️ Yordam")
def help_info(message: types.Message):
    text = """
ℹ️ *Yordam markazi*

🛍️ *Do'kon* - Mahsulotlarni ko'rish va xarid qilish
📦 *Zakazlarim* - Zakazlaringizni kuzatish
❤️ *Sevimlilar* - Saqlangan mahsulotlar
📍 *Manzillarim* - Saqlangan manzillar
🎁 *Promo kod* - Chegirma kodlarini qo'llash

*To'lov usullari:*
• Naqd pul
• Click
• Payme
"""
    bot.send_message(message.chat.id, text)


@bot.message_handler(func=lambda m: m.text == "👨‍💼 ADMIN PANEL")
def admin_panel(message: types.Message):
    if not is_admin(message.from_user.id):
        bot.send_message(message.chat.id, "❌ Siz admin emassiz!")
        return

    stats = db.get_stats()
    text = f"""
👨‍💼 *ADMIN PANEL*

👥 Foydalanuvchilar: {stats['total_users']}
🛍️ Mahsulotlar: {stats['total_products']}
📦 Zakazlar: {stats['total_orders']}
💰 Umumiy sotuv: {format_price(stats['total_revenue'])} so'm
⏳ Kutilayotgan zakazlar: {stats['pending_orders']}

📅 *Bugun:*
Zakazlar: {stats['today_orders']}
Sotuv: {format_price(stats['today_revenue'])} so'm

📊 *So'nggi 7 kun:*
Zakazlar: {stats['week_orders']}
Sotuv: {format_price(stats['week_revenue'])} so'm
"""
    bot.send_message(message.chat.id, text, reply_markup=get_admin_keyboard())


@bot.message_handler(func=lambda m: m.text == "🔙 Asosiy menyu")
def back_to_main(message: types.Message):
    user_id = message.from_user.id
    user_states[user_id] = {"state": "idle"}
    bot.send_message(
        message.chat.id,
        "🏠 *Asosiy menyu*",
        reply_markup=get_main_keyboard(user_id)
    )


@bot.message_handler(func=lambda m: m.text == "➕ Mahsulot qo'shish")
def admin_add_product_start(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    user_states[message.from_user.id] = {"state": "add_product", "step": "name", "data": {}}
    bot.send_message(
        message.chat.id,
        "➕ *Mahsulot qo'shish*\n\n1️⃣ *Mahsulot nomini kiriting:*",
        reply_markup=get_cancel_keyboard()
    )


@bot.message_handler(func=lambda m: m.text == "📋 Mahsulotlar ro'yxati")
def admin_list_products(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    products = db.get_products(only_available=False)
    if not products:
        bot.send_message(message.chat.id, "📭 Mahsulotlar mavjud emas!")
        return

    for product in products[:20]:
        status = "✅ Aktiv" if product.get("available", True) else "❌ Aktiv emas"
        text = f"""
🆔 #{product['id']}
📌 *{escape_markdown(product['name'])}*
💰 {format_price(product['price'])} so'm
🏷 {product.get('category', 'Boshqa')}
⭐ Reyting: {product.get('rating', 0)} ({product.get('reviews_count', 0)} ta)
📦 Stok: {product.get('stock', 'Cheksiz')}
{status}
"""
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("🗑 O'chirish", callback_data=f"del_prod_{product['id']}"),
            types.InlineKeyboardButton("✏️ Tahrirlash", callback_data=f"edit_prod_{product['id']}"),
            types.InlineKeyboardButton("🔄 Aktiv/inaktiv", callback_data=f"toggle_prod_{product['id']}")
        )
        bot.send_message(message.chat.id, text, reply_markup=markup)


@bot.message_handler(func=lambda m: m.text == "📦 Zakazlar")
def admin_list_orders(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    orders = db.get_orders()
    if not orders:
        bot.send_message(message.chat.id, "📭 Zakazlar mavjud emas!")
        return

    for order in orders[:20]:
        status_info = get_order_status_text(order.get("status", "new"))
        text = f"""
{status_info['emoji']} *Zakaz #{order['id']}*
👤 {escape_markdown(order.get('user_name', "Noma'lum"))}
📞 {order.get('user_phone', "Noma'lum")}
📍 {order.get('address', "Noma'lum")}
💰 {format_price(order.get('total', 0))} so'm
📅 {order.get('date', "Noma'lum")}
📊 Holat: {status_info['text']}
"""
        bot.send_message(message.chat.id, text, reply_markup=get_order_status_keyboard(order["id"]))


@bot.message_handler(func=lambda m: m.text == "📊 Statistika")
def admin_stats(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    stats = db.get_stats()
    orders = db.get_orders()

    product_sales = {}
    for order in orders:
        for item in order.get("items", []):
            name = item.get("name")
            if name:
                product_sales[name] = product_sales.get(name, 0) + item.get("quantity", 1)

    top_products = sorted(product_sales.items(), key=lambda x: x[1], reverse=True)[:10]
    top_text = "\n".join(
        [f"{i+1}. {escape_markdown(name)} - {qty} ta" for i, (name, qty) in enumerate(top_products)]
    ) if top_products else "Ma'lumot yo'q"

    status_stats = {}
    for order in orders:
        status = order.get("status", "new")
        status_stats[status] = status_stats.get(status, 0) + 1

    status_text = "\n".join(
        [f"{get_order_status_text(s)['emoji']} {get_order_status_text(s)['text']}: {count}" for s, count in status_stats.items()]
    )

    text = f"""
📊 *TO'LIQ STATISTIKA*

👥 *Foydalanuvchilar:* {stats['total_users']}
🛍️ *Mahsulotlar:* {stats['total_products']}
📦 *Jami zakazlar:* {stats['total_orders']}
💰 *Umumiy sotuv:* {format_price(stats['total_revenue'])} so'm

📅 *BUGUN:*
Zakazlar: {stats['today_orders']}
Sotuv: {format_price(stats['today_revenue'])} so'm

📊 *SO'NGGI 7 KUN:*
Zakazlar: {stats['week_orders']}
Sotuv: {format_price(stats['week_revenue'])} so'm

📋 *HOLATLAR BO'YICHA:*
{status_text or "Ma'lumot yo'q"}

🏆 *ENG KO'P SOTILGAN (TOP 10):*
{top_text}

📂 *KATEGORIYALAR BO'YICHA:*
{chr(10).join([f"• {cat}: {count} ta" for cat, count in stats.get('category_stats', {}).items()])}
"""
    bot.send_message(message.chat.id, text)


@bot.message_handler(func=lambda m: m.text == "🎁 Promo kod yaratish")
def admin_create_promo_start(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    user_states[message.from_user.id] = {"state": "create_promo", "step": "code", "data": {}}
    bot.send_message(
        message.chat.id,
        "🎁 *Promo kod yaratish*\n\n1️⃣ *Promo kod nomini kiriting:*\nMasalan: WELCOME10 yoki SUMMER50",
        reply_markup=get_cancel_keyboard()
    )


@bot.message_handler(func=lambda m: m.text == "📢 Xabar yuborish")
def admin_broadcast_start(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    user_states[message.from_user.id] = {"state": "broadcast", "step": "message"}
    bot.send_message(
        message.chat.id,
        "📢 *Xabar yuborish*\n\nYubormoqchi bo'lgan xabaringizni yozing yoki rasm/video yuboring:",
        reply_markup=get_cancel_keyboard()
    )


@bot.message_handler(func=lambda m: m.text == "👥 Foydalanuvchilar")
def admin_users_list(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    users = db.get_all_users()
    if not users:
        bot.send_message(message.chat.id, "📭 Foydalanuvchilar mavjud emas!")
        return

    text = "👥 *Foydalanuvchilar ro'yxati:*\n\n"
    for user in users[:20]:
        text += f"• {escape_markdown(user.get('name', "Noma'lum"))}\n"
        text += f"  📞 {user.get('phone', "Noma'lum")}\n"
        text += f"  🆔 {user.get('user_id')}\n"
        text += f"  📅 {user.get('joined', "Noma'lum")}\n"
        text += f"  💰 {format_price(user.get('total_spent', 0))} so'm\n\n"
    bot.send_message(message.chat.id, text)


@bot.message_handler(func=lambda m: m.text == "⚙️ Sozlamalar")
def admin_settings(message: types.Message):
    if not is_admin(message.from_user.id):
        return

    settings = db._load_json(SETTINGS_FILE)
    text = f"""
⚙️ *Sozlamalar*

🚚 *Yetkazib berish:*
• Narxi: {format_price(settings.get('delivery_fee', DELIVERY_FEE))} so'm
• Bepul yetkazish: {format_price(settings.get('free_delivery_amount', FREE_DELIVERY_AMOUNT))} so'm dan

💳 *Minimal zakaz:* {format_price(MIN_ORDER_AMOUNT)} so'm
📦 *Maksimal mahsulotlar:* {MAX_ORDER_ITEMS} ta
"""
    bot.send_message(message.chat.id, text)


# ============ STATE HANDLERLAR ============
@bot.message_handler(func=lambda m: user_states.get(m.from_user.id, {}).get("state") == "add_product")
def handle_add_product(message: types.Message):
    user_id = message.from_user.id
    state = user_states[user_id]
    step = state.get("step")

    if message.text == "❌ Bekor qilish":
        del user_states[user_id]
        bot.send_message(message.chat.id, "❌ Bekor qilindi!", reply_markup=get_admin_keyboard())
        return

    if step == "name":
        state["data"]["name"] = message.text
        state["step"] = "price"
        bot.send_message(message.chat.id, "2️⃣ *Mahsulot narxini kiriting (so'mda):*\nMasalan: 50000")

    elif step == "price":
        try:
            price = int(message.text.replace(" ", "").replace(",", ""))
            if price <= 0:
                raise ValueError
            state["data"]["price"] = price
            state["step"] = "category"
            bot.send_message(message.chat.id, "3️⃣ *Kategoriyani tanlang:*", reply_markup=get_category_keyboard())
        except Exception:
            bot.send_message(message.chat.id, "❌ Noto'g'ri narx! Iltimos, son kiriting:")

    elif step == "category":
        state["data"]["category"] = message.text
        state["step"] = "description"
        bot.send_message(
            message.chat.id,
            "4️⃣ *Mahsulot tavsifi (ixtiyoriy):*\nTavsif kiriting yoki '❌ Bekor qilish' bosing",
            reply_markup=get_cancel_keyboard()
        )

    elif step == "description":
        state["data"]["description"] = "" if message.text == "❌ Bekor qilish" else message.text
        product = db.add_product(state["data"])

        bot.send_message(
            message.chat.id,
            f"✅ *Mahsulot qo'shildi!*\n\n"
            f"📌 {escape_markdown(product['name'])}\n"
            f"💰 {format_price(product['price'])} so'm\n"
            f"🏷 {product['category']}\n"
            f"🆔 #{product['id']}",
            reply_markup=get_admin_keyboard()
        )
        del user_states[user_id]


@bot.message_handler(func=lambda m: user_states.get(m.from_user.id, {}).get("state") == "create_promo")
def handle_create_promo(message: types.Message):
    user_id = message.from_user.id
    state = user_states[user_id]
    step = state.get("step")

    if message.text == "❌ Bekor qilish":
        del user_states[user_id]
        bot.send_message(message.chat.id, "❌ Bekor qilindi!", reply_markup=get_admin_keyboard())
        return

    if step == "code":
        state["data"]["code"] = message.text.upper().strip()
        state["step"] = "discount_type"

        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("📊 Foiz (%)", "💰 Belgilangan summa")
        markup.add("❌ Bekor qilish")

        bot.send_message(message.chat.id, "2️⃣ *Chegirma turini tanlang:*", reply_markup=markup)

    elif step == "discount_type":
        if "Foiz" in message.text:
            state["data"]["discount_type"] = "percentage"
            state["step"] = "discount_value"
            bot.send_message(message.chat.id, "3️⃣ *Chegirma foizini kiriting:*\nMasalan: 10")
        else:
            state["data"]["discount_type"] = "fixed"
            state["step"] = "discount_value"
            bot.send_message(message.chat.id, "3️⃣ *Chegirma summasini kiriting (so'mda):*\nMasalan: 10000")

    elif step == "discount_value":
        try:
            value = int(message.text.replace(" ", "").replace(",", ""))
            if value <= 0:
                raise ValueError
            state["data"]["discount_value"] = value
            state["step"] = "expiry"
            bot.send_message(
                message.chat.id,
                "4️⃣ *Amal qilish muddati (kunlarda):*\nMasalan: 30\nYoki '0' cheksiz uchun"
            )
        except Exception:
            bot.send_message(message.chat.id, "❌ Noto'g'ri qiymat! Iltimos, son kiriting:")

    elif step == "expiry":
        try:
            days = int(message.text)
            expiry_date = (datetime.now() + timedelta(days=days)) if days > 0 else datetime.now() + timedelta(days=365)

            promo = {
                "code": state["data"]["code"],
                "discount_type": state["data"]["discount_type"],
                "discount_value": state["data"]["discount_value"],
                "expires_at": expiry_date.isoformat(),
                "usage_limit": 100,
                "used_count": 0,
                "active": True
            }

            db.add_promo(promo)

            discount_text = f"📊 Chegirma: {promo['discount_value']}%" if promo['discount_type'] == 'percentage' else f"💰 Chegirma: {format_price(promo['discount_value'])} so'm"
            bot.send_message(
                message.chat.id,
                f"✅ *Promo kod yaratildi!*\n\n"
                f"🎁 *Kod:* {promo['code']}\n"
                f"{discount_text}\n"
                f"📅 Muddati: {expiry_date.strftime('%Y-%m-%d')}",
                reply_markup=get_admin_keyboard()
            )
            del user_states[user_id]
        except Exception:
            bot.send_message(message.chat.id, "❌ Noto'g'ri kun! Iltimos, son kiriting:")


@bot.message_handler(func=lambda m: user_states.get(m.from_user.id, {}).get("state") == "broadcast", content_types=["text", "photo", "video"])
def handle_broadcast(message: types.Message):
    user_id = message.from_user.id

    if getattr(message, "text", None) == "❌ Bekor qilish":
        del user_states[user_id]
        bot.send_message(message.chat.id, "❌ Bekor qilindi!", reply_markup=get_admin_keyboard())
        return

    users = db.get_all_users()
    success = 0
    failed = 0

    status_msg = bot.send_message(message.chat.id, "📢 Xabar yuborilmoqda... ⏳")

    for user in users:
        try:
            if message.content_type == "photo":
                bot.send_photo(user["user_id"], message.photo[-1].file_id, caption=message.caption)
            elif message.content_type == "video":
                bot.send_video(user["user_id"], message.video.file_id, caption=message.caption)
            else:
                bot.send_message(user["user_id"], f"📢 *Xabar*\n\n{message.text}")
            success += 1
        except Exception:
            failed += 1

    bot.edit_message_text(
        f"✅ *Xabar yuborish yakunlandi!*\n\n"
        f"✅ Yuborildi: {success}\n"
        f"❌ Yuborilmadi: {failed}\n"
        f"📊 Jami: {len(users)} ta foydalanuvchi",
        message.chat.id,
        status_msg.message_id
    )
    del user_states[user_id]


@bot.message_handler(content_types=["web_app_data"])
def handle_web_app_order(message: types.Message):
    try:
        data = json.loads(message.web_app_data.data)
        user_id = message.from_user.id
        user = db.get_user(user_id)

        if not user:
            bot.send_message(message.chat.id, "❌ Iltimos, /start buyrug'ini bosing!")
            return

        items = data.get("items", [])
        address = data.get("address", "")
        note = data.get("note", "")
        promo_code = data.get("promo_code", "")

        if not items:
            bot.send_message(message.chat.id, "❌ Savat bo'sh!")
            return
        if not address:
            bot.send_message(message.chat.id, "❌ Manzil kiritilmagan!")
            return

        subtotal = sum(item.get("price", 0) * item.get("quantity", 1) for item in items)
        discount_amount, discount_percent = calculate_discount(subtotal, promo_code)
        delivery_fee = calculate_delivery_fee(subtotal - discount_amount)
        total = subtotal - discount_amount + delivery_fee

        if total < MIN_ORDER_AMOUNT:
            bot.send_message(
                message.chat.id,
                f"❌ *Minimal zakaz miqdori {format_price(MIN_ORDER_AMOUNT)} so'm!*\n\n"
                f"Sizning zakazingiz: {format_price(total)} so'm\n"
                f"Qo'shimcha {format_price(MIN_ORDER_AMOUNT - total)} so'm mahsulot qo'shing."
            )
            return

        order = {
            "user_id": user_id,
            "user_name": message.from_user.first_name,
            "user_username": message.from_user.username,
            "user_phone": user.get("phone", ""),
            "items": items,
            "subtotal": subtotal,
            "discount": discount_amount,
            "discount_percent": discount_percent,
            "delivery_fee": delivery_fee,
            "total": total,
            "address": address,
            "note": note,
            "promo_code": promo_code,
            "status": "new",
            "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        saved_order = db.add_order(order)
        db.add_address(user_id, address)
        if promo_code:
            db.use_promo(promo_code)

        current_user = db.get_user(user_id)
        db.update_user(user_id, {
            "total_orders": current_user.get("total_orders", 0) + 1,
            "total_spent": current_user.get("total_spent", 0) + total
        })

        items_text = "\n".join([
            f"  • {item.get('name')} x{item.get('quantity')} = {format_price(item.get('price') * item.get('quantity'))} so'm"
            for item in items
        ])

        discount_line = f'🎁 Chegirma: -{format_price(discount_amount)} so\'m ({discount_percent}%)' if discount_amount else ''

        text = f"""
✅ *Zakaz #{saved_order['id']} qabul qilindi!*

📦 *Mahsulotlar:*
{items_text}

💰 *Hisob:*
Mahsulotlar: {format_price(subtotal)} so'm
{discount_line}
🚚 Yetkazib berish: {format_price(delivery_fee)} so'm

📊 *JAMI: {format_price(total)} so'm*

📍 *Manzil:* {address}
{'💬 Izoh: ' + note if note else ''}

📅 Sana: {datetime.now().strftime('%H:%M, %d.%m.%Y')}
"""
        bot.send_message(message.chat.id, text)

        admin_text = f"""
🆕 *YANGI ZAKAZ #{saved_order['id']}*

👤 {message.from_user.first_name}
📞 {user.get('phone', "Noma'lum")}
📍 {address}

📦 *Mahsulotlar:*
{items_text}

💰 *Jami:* {format_price(total)} so'm
{'🎁 Promo kod: ' + promo_code if promo_code else ''}
{'💬 Izoh: ' + note if note else ''}

📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
        for admin_id in ADMIN_IDS:
            try:
                bot.send_message(admin_id, admin_text)
            except Exception:
                pass

    except Exception as e:
        logger.error(f"Web App zakaz xatolik: {e}")
        bot.send_message(message.chat.id, "❌ Xatolik yuz berdi! Iltimos, qaytadan urinib ko'ring.")


def save_review(message: types.Message, order_id: int):
    try:
        rating = int(message.text)
        if rating < 1 or rating > 5:
            raise ValueError

        order = db.get_order(order_id)
        if not order:
            bot.send_message(message.chat.id, "❌ Zakaz topilmadi.")
            return

        for item in order.get("items", []):
            product_id = item.get("id")
            if product_id:
                db.add_review(product_id, message.from_user.id, rating, "Zakaz orqali baholandi")

        bot.send_message(message.chat.id, f"✅ Rahmat! Siz {rating} baho berdingiz.")
    except Exception:
        bot.send_message(message.chat.id, "❌ 1 dan 5 gacha son yuboring.")


@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    if call.data.startswith("status_"):
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Admin emassiz!")
            return

        parts = call.data.split("_")
        order_id = int(parts[1])
        status = parts[2]

        order = db.update_order(order_id, {"status": status})
        if order:
            status_info = get_order_status_text(status)
            bot.answer_callback_query(call.id, f"Holat: {status_info['text']}")

            try:
                user_text = f"🔄 *Zakaz #{order_id} holati:* {status_info['text']}\n\n📅 {datetime.now().strftime('%H:%M')}"
                if status == "delivering":
                    eta = random.randint(15, 60)
                    user_text += f"\n⏱ Yetib borish vaqti: {eta} daqiqa"
                    db.update_order(order_id, {"eta": f"{eta} daqiqa"})
                if status == "courier":
                    courier_phone = "+998 90 123 45 67"
                    user_text += f"\n📞 Kuryer: {courier_phone}"
                    db.update_order(order_id, {"courier_phone": courier_phone})
                bot.send_message(order["user_id"], user_text)
            except Exception:
                pass

    elif call.data.startswith("del_prod_"):
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Admin emassiz!")
            return
        product_id = int(call.data.split("_")[2])
        db.delete_product(product_id)
        bot.answer_callback_query(call.id, "✅ Mahsulot o'chirildi!")
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass

    elif call.data.startswith("toggle_prod_"):
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Admin emassiz!")
            return
        product_id = int(call.data.split("_")[2])
        product = db.get_product(product_id)
        if product:
            new_status = not product.get("available", True)
            db.update_product(product_id, {"available": new_status})
            bot.answer_callback_query(call.id, f"✅ Mahsulot {'aktiv' if new_status else 'inaktiv'} qilindi!")

    elif call.data.startswith("reorder_"):
        bot.send_message(
            call.message.chat.id,
            "🔄 Qayta zakaz berish uchun do'konni oching 👇",
            reply_markup=types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton("🛍️ Do'kon", web_app=types.WebAppInfo(url=WEB_APP_URL))
            )
        )
        bot.answer_callback_query(call.id, "✅ Do'kon ochildi!")

    elif call.data.startswith("review_"):
        order_id = int(call.data.split("_")[1])
        order = db.get_order(order_id)
        if order and order.get("status") == "delivered":
            bot.answer_callback_query(call.id)
            msg = bot.send_message(
                call.message.chat.id,
                "⭐ *Mahsulotni baholang!*\n\n1 dan 5 gacha baho yuboring:"
            )
            bot.register_next_step_handler(msg, save_review, order_id)

    elif call.data == "clear_favorites":
        favorites = db._load_json(FAVORITES_FILE)
        favorites[str(call.from_user.id)] = []
        db._save_json(FAVORITES_FILE, favorites)
        bot.answer_callback_query(call.id, "✅ Sevimlilar tozalandi!")

    elif call.data == "delete_address":
        addresses = db.get_addresses(call.from_user.id)
        if addresses:
            db.delete_address(call.from_user.id, addresses[-1])
            bot.answer_callback_query(call.id, "✅ Oxirgi manzil o'chirildi!")
        else:
            bot.answer_callback_query(call.id, "📭 Manzil topilmadi.")


# ============ FASTAPI ROUTELAR ============
@app.get("/")
async def home():
    return {
        "status": "online",
        "bot_name": "Telegram Shop Bot",
        "version": "4.0.0",
        "web_app_url": WEB_APP_URL
    }


@app.get("/shop")
async def shop_page():
    return HTMLResponse(content=read_shop_template())


@app.get("/api/products")
async def get_products_api():
    return JSONResponse(db.get_products())


@app.get("/api/settings")
async def get_settings_api():
    return JSONResponse(db._load_json(SETTINGS_FILE))


@app.get("/api/promos")
async def get_promos_api():
    return JSONResponse(db.get_promos())


@app.post("/webhook")
async def webhook(request: Request):
    try:
        data = await request.json()
        update = types.Update.de_json(data)
        bot.process_new_updates([update])
        return {"ok": True}
    except Exception as e:
        logger.exception("Webhook xatolik")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/set_webhook")
async def set_webhook():
    webhook_url = f"{RENDER_EXTERNAL_URL}/webhook"
    ok = bot.set_webhook(url=webhook_url)
    return {"ok": ok, "webhook_url": webhook_url}


@app.post("/delete_webhook")
async def delete_webhook():
    ok = bot.delete_webhook()
    return {"ok": ok}


def ensure_demo_products():
    products = db.get_products(only_available=False)
    if products:
        return
    demo_products = [
        {
            "name": "AirPods Pro 2",
            "price": 1890000,
            "category": "📱 Elektronika",
            "description": "ANC, MagSafe, original dizayn",
            "image": "🎧",
            "available": True,
            "stock": 12,
            "rating": 4.9,
            "reviews_count": 27
        },
        {
            "name": "Nike Air Max",
            "price": 990000,
            "category": "👟 Poyabzal",
            "description": "Kundalik va sport uchun qulay model",
            "image": "👟",
            "available": True,
            "stock": 20,
            "rating": 4.8,
            "reviews_count": 14
        },
        {
            "name": "Oversize Hoodie",
            "price": 320000,
            "category": "👗 Kiyim",
            "description": "Yumshoq mato, zamonaviy fason",
            "image": "🧥",
            "available": True,
            "stock": 16,
            "rating": 4.7,
            "reviews_count": 18
        },
        {
            "name": "Smart Watch X",
            "price": 740000,
            "category": "📱 Elektronika",
            "description": "Yurak urishi, qadam, bildirishnomalar",
            "image": "⌚",
            "available": True,
            "stock": 8,
            "rating": 4.6,
            "reviews_count": 11
        }
    ]
    for item in demo_products:
        db.add_product(item)


ensure_demo_products()


def start_telegram_polling():
    try:
        bot.remove_webhook()
    except Exception:
        pass
    bot.infinity_polling(skip_pending=True)


if __name__ == "__main__":
    threading.Thread(target=start_telegram_polling, daemon=True).start()
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8000")), reload=True)
