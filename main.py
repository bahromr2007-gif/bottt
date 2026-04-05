import telebot
from telebot import types
import json
import os
import logging
from datetime import datetime, timedelta
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import threading
import random
import re
from typing import Dict, List, Optional, Any

# ============================================================
#  KONFIGURATSIYA
# ============================================================
BOT_TOKEN             = "8778358404:AAHmM4e2OnROyXLCsGXERCbXd3arzl7kPS0"
RENDER_EXTERNAL_URL   = "https://bottt-02j7.onrender.com"
WEB_APP_URL           = f"{RENDER_EXTERNAL_URL}/shop"
ADMIN_IDS             = [8735360012]

DELIVERY_FEE          = 15_000
FREE_DELIVERY_AMOUNT  = 100_000
MIN_ORDER_AMOUNT      = 5_000
MAX_ORDER_ITEMS       = 50

DATA_DIR        = "data"
PRODUCTS_FILE   = f"{DATA_DIR}/products.json"
ORDERS_FILE     = f"{DATA_DIR}/orders.json"
USERS_FILE      = f"{DATA_DIR}/users.json"
ADDRESSES_FILE  = f"{DATA_DIR}/addresses.json"
FAVORITES_FILE  = f"{DATA_DIR}/favorites.json"
PROMO_FILE      = f"{DATA_DIR}/promo.json"
REVIEWS_FILE    = f"{DATA_DIR}/reviews.json"
SETTINGS_FILE   = f"{DATA_DIR}/settings.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ============================================================
#  MA'LUMOTLAR BAZASI
# ============================================================
class Database:
    """Lightweight JSON-backed data store."""

    def __init__(self):
        self._ensure_data_dir()
        self._init_files()
        self._lock = threading.Lock()

    # ── helpers ────────────────────────────────────────────
    def _ensure_data_dir(self):
        os.makedirs(DATA_DIR, exist_ok=True)

    def _init_files(self):
        defaults = {
            PRODUCTS_FILE:  [],
            ORDERS_FILE:    [],
            USERS_FILE:     {},
            ADDRESSES_FILE: {},
            FAVORITES_FILE: {},
            PROMO_FILE:     [],
            REVIEWS_FILE:   {},
            SETTINGS_FILE:  {
                "delivery_fee":          DELIVERY_FEE,
                "free_delivery_amount":  FREE_DELIVERY_AMOUNT,
            },
        }
        for path, default in defaults.items():
            if not os.path.exists(path):
                self._save_json(path, default)

    def _load_json(self, path: str) -> Any:
        with self._lock:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                return []

    def _save_json(self, path: str, data: Any):
        with self._lock:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

    # ── Mahsulotlar ────────────────────────────────────────
    def get_products(self, only_available: bool = True) -> List[Dict]:
        products = self._load_json(PRODUCTS_FILE)
        if only_available:
            products = [p for p in products if p.get("available", True)]
        return sorted(products, key=lambda x: x.get("id", 0))

    def get_product(self, product_id: int) -> Optional[Dict]:
        return next((p for p in self.get_products(False) if p["id"] == product_id), None)

    def add_product(self, product: Dict) -> Dict:
        products = self.get_products(False)
        product["id"]         = max([p.get("id", 0) for p in products] + [0]) + 1
        product["created_at"] = datetime.now().isoformat()
        product.setdefault("available", True)
        product.setdefault("rating", 0)
        product.setdefault("reviews_count", 0)
        product.setdefault("sold", 0)
        products.append(product)
        self._save_json(PRODUCTS_FILE, products)
        return product

    def update_product(self, product_id: int, updates: Dict) -> Optional[Dict]:
        products = self.get_products(False)
        for i, p in enumerate(products):
            if p["id"] == product_id:
                products[i].update(updates)
                self._save_json(PRODUCTS_FILE, products)
                return products[i]
        return None

    def delete_product(self, product_id: int) -> bool:
        products = self.get_products(False)
        new = [p for p in products if p["id"] != product_id]
        if len(new) != len(products):
            self._save_json(PRODUCTS_FILE, new)
            return True
        return False

    # ── Zakazlar ───────────────────────────────────────────
    def get_orders(self, user_id: Optional[int] = None,
                   status: Optional[str] = None) -> List[Dict]:
        orders = self._load_json(ORDERS_FILE)
        if user_id:
            orders = [o for o in orders if o.get("user_id") == user_id]
        if status:
            orders = [o for o in orders if o.get("status") == status]
        return sorted(orders, key=lambda x: x.get("created_at", ""), reverse=True)

    def get_order(self, order_id: int) -> Optional[Dict]:
        return next((o for o in self.get_orders() if o["id"] == order_id), None)

    def add_order(self, order: Dict) -> Dict:
        orders = self.get_orders()
        order["id"]         = max([o.get("id", 0) for o in orders] + [1000]) + 1
        order["created_at"] = datetime.now().isoformat()
        orders.append(order)
        self._save_json(ORDERS_FILE, orders)
        return order

    def update_order(self, order_id: int, updates: Dict) -> Optional[Dict]:
        orders = self.get_orders()
        for i, o in enumerate(orders):
            if o["id"] == order_id:
                orders[i].update(updates)
                self._save_json(ORDERS_FILE, orders)
                return orders[i]
        return None

    # ── Foydalanuvchilar ───────────────────────────────────
    def get_users(self) -> Dict[str, Dict]:
        return self._load_json(USERS_FILE)

    def get_user(self, user_id: int) -> Optional[Dict]:
        return self.get_users().get(str(user_id))

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

    # ── Manzillar ──────────────────────────────────────────
    def get_addresses(self, user_id: int) -> List[str]:
        return self._load_json(ADDRESSES_FILE).get(str(user_id), [])

    def add_address(self, user_id: int, address: str) -> List[str]:
        addresses = self._load_json(ADDRESSES_FILE)
        user_addrs = addresses.get(str(user_id), [])
        if address not in user_addrs:
            user_addrs.append(address)
            user_addrs = user_addrs[-10:]
            addresses[str(user_id)] = user_addrs
            self._save_json(ADDRESSES_FILE, addresses)
        return user_addrs

    def delete_address(self, user_id: int, address: str) -> bool:
        addresses = self._load_json(ADDRESSES_FILE)
        user_addrs = addresses.get(str(user_id), [])
        if address in user_addrs:
            user_addrs.remove(address)
            addresses[str(user_id)] = user_addrs
            self._save_json(ADDRESSES_FILE, addresses)
            return True
        return False

    # ── Sevimlilar ─────────────────────────────────────────
    def get_favorites(self, user_id: int) -> List[int]:
        return self._load_json(FAVORITES_FILE).get(str(user_id), [])

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

    # ── Promo kodlar ───────────────────────────────────────
    def get_promos(self) -> List[Dict]:
        return self._load_json(PROMO_FILE)

    def get_promo(self, code: str) -> Optional[Dict]:
        code = code.upper().strip()
        return next(
            (p for p in self.get_promos() if p["code"] == code and p.get("active", True)),
            None,
        )

    def add_promo(self, promo: Dict) -> Dict:
        promos = self.get_promos()
        promo["code"] = promo["code"].upper().strip()
        promos.append(promo)
        self._save_json(PROMO_FILE, promos)
        return promo

    def use_promo(self, code: str) -> bool:
        promos = self.get_promos()
        for p in promos:
            if p["code"] == code.upper().strip():
                p["used_count"] = p.get("used_count", 0) + 1
                if p.get("usage_limit") and p["used_count"] >= p["usage_limit"]:
                    p["active"] = False
                self._save_json(PROMO_FILE, promos)
                return True
        return False

    # ── Baholar ────────────────────────────────────────────
    def get_reviews(self, product_id: Optional[int] = None):
        reviews = self._load_json(REVIEWS_FILE)
        if product_id:
            return reviews.get(str(product_id), [])
        return reviews

    def add_review(self, product_id: int, user_id: int,
                   rating: int, comment: str = "") -> Dict:
        reviews = self._load_json(REVIEWS_FILE)
        product_reviews = reviews.get(str(product_id), [])
        review = {
            "user_id": user_id,
            "rating":  rating,
            "comment": comment,
            "date":    datetime.now().isoformat(),
        }
        product_reviews.append(review)
        reviews[str(product_id)] = product_reviews
        self._save_json(REVIEWS_FILE, reviews)

        product = self.get_product(product_id)
        if product:
            avg = sum(r["rating"] for r in product_reviews) / len(product_reviews)
            self.update_product(product_id, {
                "rating":       round(avg, 1),
                "reviews_count": len(product_reviews),
            })
        return review

    # ── Statistika ─────────────────────────────────────────
    def get_stats(self) -> Dict:
        users    = self.get_users()
        orders   = self.get_orders()
        products = self.get_products(only_available=False)

        today    = datetime.now().strftime("%Y-%m-%d")
        week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

        today_orders = [o for o in orders if o.get("created_at", "").startswith(today)]
        week_orders  = [o for o in orders if o.get("created_at", "") >= week_ago]

        category_stats: Dict[str, int] = {}
        for p in products:
            cat = p.get("category", "Boshqa")
            category_stats[cat] = category_stats.get(cat, 0) + 1

        return {
            "total_users":     len(users),
            "total_products":  len(products),
            "total_orders":    len(orders),
            "total_revenue":   sum(o.get("total", 0) for o in orders),
            "today_orders":    len(today_orders),
            "today_revenue":   sum(o.get("total", 0) for o in today_orders),
            "week_orders":     len(week_orders),
            "week_revenue":    sum(o.get("total", 0) for o in week_orders),
            "category_stats":  category_stats,
            "pending_orders":  len([o for o in orders if o.get("status") in ("new", "accepted", "preparing")]),
        }


db = Database()


# ============================================================
#  YORDAMCHI FUNKSIYALAR
# ============================================================
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
    return len(re.sub(r"\D", "", phone)) in (9, 12, 13)

def calculate_delivery_fee(total: int) -> int:
    s = db._load_json(SETTINGS_FILE)
    return 0 if total >= s.get("free_delivery_amount", FREE_DELIVERY_AMOUNT) \
        else s.get("delivery_fee", DELIVERY_FEE)

def calculate_discount(total: int, promo_code: str = "") -> tuple:
    if not promo_code:
        return 0, 0
    promo = db.get_promo(promo_code)
    if not promo or not promo.get("active", True):
        return 0, 0
    if promo.get("discount_type") == "percentage":
        pct = promo.get("discount_value", 0)
        return int(total * pct / 100), pct
    return min(promo.get("discount_value", 0), total), 0

def get_order_status_text(status: str) -> dict:
    statuses = {
        "new":        {"text": "Yangi zakaz",      "emoji": "🆕", "color": "#FF6B35"},
        "accepted":   {"text": "Qabul qilindi",    "emoji": "✅", "color": "#48BB78"},
        "preparing":  {"text": "Tayyorlanmoqda",   "emoji": "🔧", "color": "#F6AD55"},
        "courier":    {"text": "Kuryerga berildi", "emoji": "🚚", "color": "#4299E1"},
        "delivering": {"text": "Yetkazilmoqda",    "emoji": "🚛", "color": "#9F7AEA"},
        "delivered":  {"text": "Yetkazildi",       "emoji": "📦", "color": "#48BB78"},
        "cancelled":  {"text": "Bekor qilindi",    "emoji": "❌", "color": "#F56565"},
    }
    return statuses.get(status, {"text": status, "emoji": "📋", "color": "#718096"})

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def esc(text: str) -> str:
    """Markdown v1 special chars escape."""
    special = r"_*[]()~`>#+-=|{}.!"
    return "".join(f"\\{c}" if c in special else c for c in str(text))


# ============================================================
#  KLAVIATURALAR
# ============================================================
def kb_main(user_id: int) -> types.ReplyKeyboardMarkup:
    m = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    m.add(types.KeyboardButton("🛍️ DO'KON", web_app=types.WebAppInfo(url=WEB_APP_URL)))
    m.add("📦 Mening zakazlarim", "❤️ Sevimlilar")
    m.add("📍 Manzillarim", "🎁 Promo kodlar")
    m.add("📞 Aloqa", "ℹ️ Yordam")
    if is_admin(user_id):
        m.add("👨‍💼 ADMIN PANEL")
    return m

def kb_admin() -> types.ReplyKeyboardMarkup:
    m = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    m.add("➕ Mahsulot qo'shish", "📋 Mahsulotlar ro'yxati")
    m.add("📦 Zakazlar", "📊 Statistika")
    m.add("🎁 Promo kod yaratish", "📢 Xabar yuborish")
    m.add("👥 Foydalanuvchilar", "⚙️ Sozlamalar")
    m.add("🔙 Asosiy menyu")
    return m

def kb_cancel() -> types.ReplyKeyboardMarkup:
    m = types.ReplyKeyboardMarkup(resize_keyboard=True)
    m.add("❌ Bekor qilish")
    return m

def kb_category() -> types.ReplyKeyboardMarkup:
    m = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    for cat in ["👗 Kiyim", "👟 Poyabzal", "📱 Elektronika",
                "🏠 Uy jihozlari", "🍕 Oziq-ovqat", "🎁 Boshqa"]:
        m.add(types.KeyboardButton(cat))
    m.add("❌ Bekor qilish")
    return m

def kb_order_status(order_id: int) -> types.InlineKeyboardMarkup:
    m = types.InlineKeyboardMarkup(row_width=2)
    for label, status in [
        ("✅ Qabul qilish", "accepted"), ("🔧 Tayyorlash", "preparing"),
        ("🚚 Kuryerga", "courier"),     ("🚛 Yetkazish", "delivering"),
        ("📦 Yetkazildi", "delivered"), ("❌ Bekor qilish", "cancelled"),
    ]:
        m.add(types.InlineKeyboardButton(label, callback_data=f"status_{order_id}_{status}"))
    return m

def kb_order_actions(order_id: int, is_delivered: bool = False) -> types.InlineKeyboardMarkup:
    m = types.InlineKeyboardMarkup()
    m.add(types.InlineKeyboardButton("🔄 Qayta zakaz", callback_data=f"reorder_{order_id}"))
    if is_delivered:
        m.add(types.InlineKeyboardButton("⭐ Baholash", callback_data=f"review_{order_id}"))
    return m


# ============================================================
#  BOT VA FASTAPI INSTANCE
# ============================================================
bot = telebot.TeleBot(BOT_TOKEN)
app = FastAPI(title="Telegram Shop Bot", version="5.0.0")

user_states: Dict[int, Dict] = {}


# ============================================================
#  BOT — ASOSIY HANDLERLAR
# ============================================================
@bot.message_handler(commands=["start"])
def cmd_start(msg: types.Message):
    uid = msg.from_user.id
    if not db.get_user(uid):
        m = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        m.add(types.KeyboardButton("📱 Telefon raqam yuborish", request_contact=True))
        bot.send_message(
            msg.chat.id,
            f"👋 *Assalomu alaykum, {esc(msg.from_user.first_name)}!*\n\n"
            "🚀 *Do'konimizga xush kelibsiz!*\n\n"
            "Ro'yxatdan o'tish uchun telefon raqamingizni yuboring 👇",
            parse_mode="Markdown", reply_markup=m,
        )
        user_states[uid] = {"state": "waiting_contact"}
    else:
        bot.send_message(
            msg.chat.id, "🏠 *Asosiy menyu*",
            parse_mode="Markdown", reply_markup=kb_main(uid),
        )
        user_states[uid] = {"state": "idle"}


@bot.message_handler(content_types=["contact"])
def handle_contact(msg: types.Message):
    uid = msg.from_user.id
    if user_states.get(uid, {}).get("state") != "waiting_contact":
        return

    phone = msg.contact.phone_number if msg.contact else ""
    if not validate_phone(phone):
        bot.send_message(msg.chat.id, "❌ *Noto'g'ri raqam!* Iltimos qaytadan urinib ko'ring.",
                         parse_mode="Markdown")
        return

    db.add_user(uid, {
        "user_id":      uid,
        "name":         msg.from_user.first_name,
        "username":     msg.from_user.username,
        "phone":        format_phone(phone),
        "joined":       datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_orders": 0,
        "total_spent":  0,
        "language":     "uz",
    })
    bot.send_message(
        msg.chat.id,
        "✅ *Ro'yxatdan o'tdingiz!*\n\nEndi xarid qilishingiz mumkin 🛍️",
        parse_mode="Markdown", reply_markup=kb_main(uid),
    )
    user_states[uid] = {"state": "idle"}

    for admin_id in ADMIN_IDS:
        try:
            bot.send_message(
                admin_id,
                f"🆕 *Yangi foydalanuvchi!*\n\n"
                f"👤 {msg.from_user.first_name}\n"
                f"📞 {format_phone(phone)}\n"
                f"🆔 `{uid}`\n"
                f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                parse_mode="Markdown",
            )
        except Exception:
            pass


@bot.message_handler(func=lambda m: m.text == "📦 Mening zakazlarim")
def my_orders(msg: types.Message):
    orders = db.get_orders(msg.from_user.id)
    if not orders:
        bot.send_message(msg.chat.id,
                         "📭 *Zakazlaringiz yo'q*\n\nDo'konni ochib xarid qiling!",
                         parse_mode="Markdown")
        return

    for order in orders[:10]:
        si = get_order_status_text(order.get("status", "new"))
        items_text = "\n".join(
            f"  • {i.get('name')} x{i.get('quantity', 1)} = "
            f"{format_price(i.get('price', 0) * i.get('quantity', 1))} so'm"
            for i in order.get("items", [])
        )
        text = (
            f"{si['emoji']} *Zakaz #{order['id']}*\n"
            f"📅 {order.get('created_at', '—')[:16]}\n"
            f"💰 {format_price(order.get('total', 0))} so'm\n"
            f"📊 *Holat:* {si['text']}\n\n"
            f"📦 *Mahsulotlar:*\n{items_text}\n\n"
            f"📍 *Manzil:* {esc(order.get('address', '—'))}"
        )
        if order.get("eta"):
            text += f"\n⏱ *ETA:* {order['eta']}"
        if order.get("courier_phone"):
            text += f"\n📞 *Kuryer:* {order['courier_phone']}"

        bot.send_message(
            msg.chat.id, text, parse_mode="Markdown",
            reply_markup=kb_order_actions(order["id"], order.get("status") == "delivered"),
        )


@bot.message_handler(func=lambda m: m.text == "❤️ Sevimlilar")
def my_favorites(msg: types.Message):
    uid       = msg.from_user.id
    favorites = db.get_favorites(uid)
    if not favorites:
        bot.send_message(msg.chat.id,
                         "❤️ *Sevimli mahsulotlaringiz yo'q*\n\nMahsulotni ❤️ bosib saqlang!",
                         parse_mode="Markdown")
        return

    fav_products = [p for p in db.get_products() if p["id"] in favorites]
    if not fav_products:
        bot.send_message(msg.chat.id, "❤️ Topilmadi.")
        return

    text = "❤️ *Sevimli mahsulotlaringiz:*\n\n"
    for p in fav_products:
        text += f"• {esc(p['name'])} — {format_price(p['price'])} so'm\n"

    m = types.InlineKeyboardMarkup()
    m.add(types.InlineKeyboardButton("🗑 Barchasini tozalash", callback_data="clear_favorites"))
    bot.send_message(msg.chat.id, text, parse_mode="Markdown", reply_markup=m)


@bot.message_handler(func=lambda m: m.text == "📍 Manzillarim")
def my_addresses(msg: types.Message):
    addresses = db.get_addresses(msg.from_user.id)
    if not addresses:
        bot.send_message(msg.chat.id,
                         "📍 *Manzillaringiz yo'q*\n\nZakaz berishda manzil avtomatik saqlanadi.",
                         parse_mode="Markdown")
        return

    text = "📍 *Sizning manzillaringiz:*\n\n" + "\n".join(
        f"{i}. {esc(a)}" for i, a in enumerate(addresses, 1)
    )
    m = types.InlineKeyboardMarkup()
    m.add(types.InlineKeyboardButton("🗑 Manzil o'chirish", callback_data="delete_address"))
    bot.send_message(msg.chat.id, text, parse_mode="Markdown", reply_markup=m)


@bot.message_handler(func=lambda m: m.text == "🎁 Promo kodlar")
def promo_info(msg: types.Message):
    bot.send_message(
        msg.chat.id,
        "🎁 *Promo kodlar*\n\n"
        "Zakaz berishda quyidagi promo kodlarni kiriting:\n\n"
        "• `WELCOME10` — 10% chegirma\n"
        "• `WELCOME20` — 20% chegirma\n\n"
        "📌 Har bir kod bir marta ishlatiladi!",
        parse_mode="Markdown",
    )


@bot.message_handler(func=lambda m: m.text == "📞 Aloqa")
def contact_info(msg: types.Message):
    bot.send_message(
        msg.chat.id,
        "📞 *Aloqa ma'lumotlari*\n\n"
        "📱 Telefon: +998 90 123 45 67\n"
        "📧 Email: support@shop.uz\n\n"
        "🕐 Ish vaqti: 09:00 — 21:00\n"
        "📢 Telegram: @shop\\_support",
        parse_mode="Markdown",
    )


@bot.message_handler(func=lambda m: m.text == "ℹ️ Yordam")
def help_info(msg: types.Message):
    bot.send_message(
        msg.chat.id,
        "ℹ️ *Yordam*\n\n"
        "🛍️ *Do'kon* — mahsulotlarni ko'rish va xarid qilish\n"
        "📦 *Zakazlarim* — zakazlarni kuzatish\n"
        "❤️ *Sevimlilar* — saqlangan mahsulotlar\n"
        "📍 *Manzillarim* — saqlangan manzillar\n"
        "🎁 *Promo kod* — chegirma kodlarini qo'llash\n\n"
        "*To'lov usullari:*\n"
        "• Naqd pul (yetkazib berishda)\n"
        "• Click / Payme (online)",
        parse_mode="Markdown",
    )


@bot.message_handler(func=lambda m: m.text == "👨‍💼 ADMIN PANEL")
def admin_panel(msg: types.Message):
    if not is_admin(msg.from_user.id):
        return
    stats = db.get_stats()
    bot.send_message(
        msg.chat.id,
        f"👨‍💼 *ADMIN PANEL*\n\n"
        f"👥 Foydalanuvchilar: *{stats['total_users']}*\n"
        f"🛍️ Mahsulotlar: *{stats['total_products']}*\n"
        f"📦 Zakazlar: *{stats['total_orders']}*\n"
        f"💰 Umumiy sotuv: *{format_price(stats['total_revenue'])} so'm*\n"
        f"⏳ Kutilayotgan: *{stats['pending_orders']}*\n\n"
        f"📅 *Bugun:* {stats['today_orders']} zakaz — {format_price(stats['today_revenue'])} so'm\n"
        f"📊 *7 kun:* {stats['week_orders']} zakaz — {format_price(stats['week_revenue'])} so'm",
        parse_mode="Markdown",
        reply_markup=kb_admin(),
    )


@bot.message_handler(func=lambda m: m.text == "🔙 Asosiy menyu")
def back_main(msg: types.Message):
    uid = msg.from_user.id
    user_states[uid] = {"state": "idle"}
    bot.send_message(msg.chat.id, "🏠 *Asosiy menyu*",
                     parse_mode="Markdown", reply_markup=kb_main(uid))


# ============================================================
#  ADMIN — MAHSULOT QO'SHISH
# ============================================================
@bot.message_handler(func=lambda m: m.text == "➕ Mahsulot qo'shish")
def admin_add_start(msg: types.Message):
    if not is_admin(msg.from_user.id):
        return
    user_states[msg.from_user.id] = {"state": "add_product", "step": "name", "data": {}}
    bot.send_message(msg.chat.id,
                     "➕ *Mahsulot qo'shish*\n\n1️⃣ Mahsulot nomini kiriting:",
                     parse_mode="Markdown", reply_markup=kb_cancel())


@bot.message_handler(func=lambda m: user_states.get(m.from_user.id, {}).get("state") == "add_product")
def handle_add_product(msg: types.Message):
    uid   = msg.from_user.id
    state = user_states[uid]
    step  = state["step"]

    if msg.text == "❌ Bekor qilish":
        del user_states[uid]
        bot.send_message(msg.chat.id, "❌ Bekor qilindi!", reply_markup=kb_admin())
        return

    if step == "name":
        state["data"]["name"] = msg.text
        state["step"]         = "price"
        bot.send_message(msg.chat.id, "2️⃣ Narxini kiriting (so'mda):", parse_mode="Markdown")

    elif step == "price":
        try:
            price = int(msg.text.replace(" ", "").replace(",", ""))
            assert price > 0
            state["data"]["price"] = price
            state["step"]          = "category"
            bot.send_message(msg.chat.id, "3️⃣ Kategoriyani tanlang:",
                             reply_markup=kb_category())
        except Exception:
            bot.send_message(msg.chat.id, "❌ Noto'g'ri narx! Raqam kiriting:")

    elif step == "category":
        state["data"]["category"] = msg.text
        state["step"]             = "description"
        bot.send_message(msg.chat.id,
                         "4️⃣ Tavsif kiriting (ixtiyoriy), yoki '❌ Bekor qilish':",
                         reply_markup=kb_cancel())

    elif step == "description":
        state["data"]["description"] = "" if msg.text == "❌ Bekor qilish" else msg.text
        product = db.add_product(state["data"])
        bot.send_message(
            msg.chat.id,
            f"✅ *Mahsulot qo'shildi!*\n\n"
            f"📌 {esc(product['name'])}\n"
            f"💰 {format_price(product['price'])} so'm\n"
            f"🏷 {product['category']}\n"
            f"🆔 #{product['id']}",
            parse_mode="Markdown", reply_markup=kb_admin(),
        )
        del user_states[uid]


# ============================================================
#  ADMIN — MAHSULOTLAR RO'YXATI
# ============================================================
@bot.message_handler(func=lambda m: m.text == "📋 Mahsulotlar ro'yxati")
def admin_list_products(msg: types.Message):
    if not is_admin(msg.from_user.id):
        return
    products = db.get_products(only_available=False)
    if not products:
        bot.send_message(msg.chat.id, "📭 Mahsulotlar mavjud emas!")
        return

    for p in products[:20]:
        status = "✅ Aktiv" if p.get("available", True) else "❌ Aktiv emas"
        text = (
            f"🆔 #{p['id']}\n"
            f"📌 *{esc(p['name'])}*\n"
            f"💰 {format_price(p['price'])} so'm\n"
            f"🏷 {p.get('category', '—')}\n"
            f"⭐ {p.get('rating', 0)} ({p.get('reviews_count', 0)} ta)\n"
            f"📦 Stok: {p.get('stock', '♾️')}\n"
            f"{status}"
        )
        m = types.InlineKeyboardMarkup()
        m.add(
            types.InlineKeyboardButton("🗑 O'chirish",       callback_data=f"del_prod_{p['id']}"),
            types.InlineKeyboardButton("🔄 Aktiv/inaktiv",   callback_data=f"toggle_prod_{p['id']}"),
        )
        bot.send_message(msg.chat.id, text, parse_mode="Markdown", reply_markup=m)


# ============================================================
#  ADMIN — ZAKAZLAR
# ============================================================
@bot.message_handler(func=lambda m: m.text == "📦 Zakazlar")
def admin_list_orders(msg: types.Message):
    if not is_admin(msg.from_user.id):
        return
    orders = db.get_orders()
    if not orders:
        bot.send_message(msg.chat.id, "📭 Zakazlar mavjud emas!")
        return

    for order in orders[:20]:
        si   = get_order_status_text(order.get("status", "new"))
        text = (
            f"{si['emoji']} *Zakaz #{order['id']}*\n"
            f"👤 {esc(order.get('user_name', '—'))}\n"
            f"📞 {order.get('user_phone', '—')}\n"
            f"📍 {esc(order.get('address', '—'))}\n"
            f"💰 {format_price(order.get('total', 0))} so'm\n"
            f"📅 {order.get('created_at', '—')[:16]}\n"
            f"📊 Holat: {si['text']}"
        )
        bot.send_message(msg.chat.id, text, parse_mode="Markdown",
                         reply_markup=kb_order_status(order["id"]))


# ============================================================
#  ADMIN — STATISTIKA
# ============================================================
@bot.message_handler(func=lambda m: m.text == "📊 Statistika")
def admin_stats(msg: types.Message):
    if not is_admin(msg.from_user.id):
        return
    stats  = db.get_stats()
    orders = db.get_orders()

    product_sales: Dict[str, int] = {}
    for o in orders:
        for item in o.get("items", []):
            name = item.get("name")
            if name:
                product_sales[name] = product_sales.get(name, 0) + item.get("quantity", 1)

    top = sorted(product_sales.items(), key=lambda x: x[1], reverse=True)[:10]
    top_text  = "\n".join(f"{i+1}. {esc(n)} — {q} ta" for i, (n, q) in enumerate(top)) or "Ma'lumot yo'q"
    cat_text  = "\n".join(f"• {c}: {n} ta" for c, n in stats.get("category_stats", {}).items())

    status_counts: Dict[str, int] = {}
    for o in orders:
        s = o.get("status", "new")
        status_counts[s] = status_counts.get(s, 0) + 1
    status_text = "\n".join(
        f"{get_order_status_text(s)['emoji']} {get_order_status_text(s)['text']}: {n}"
        for s, n in status_counts.items()
    )

    bot.send_message(
        msg.chat.id,
        f"📊 *STATISTIKA*\n\n"
        f"👥 Foydalanuvchilar: {stats['total_users']}\n"
        f"🛍️ Mahsulotlar: {stats['total_products']}\n"
        f"📦 Jami zakazlar: {stats['total_orders']}\n"
        f"💰 Umumiy sotuv: {format_price(stats['total_revenue'])} so'm\n\n"
        f"📅 *BUGUN:*\n{stats['today_orders']} zakaz — {format_price(stats['today_revenue'])} so'm\n\n"
        f"📊 *7 KUN:*\n{stats['week_orders']} zakaz — {format_price(stats['week_revenue'])} so'm\n\n"
        f"📋 *HOLATLAR:*\n{status_text}\n\n"
        f"🏆 *TOP 10:*\n{top_text}\n\n"
        f"📂 *KATEGORIYALAR:*\n{cat_text}",
        parse_mode="Markdown",
    )


# ============================================================
#  ADMIN — PROMO KOD YARATISH
# ============================================================
@bot.message_handler(func=lambda m: m.text == "🎁 Promo kod yaratish")
def admin_promo_start(msg: types.Message):
    if not is_admin(msg.from_user.id):
        return
    user_states[msg.from_user.id] = {"state": "create_promo", "step": "code", "data": {}}
    bot.send_message(msg.chat.id,
                     "🎁 *Promo kod yaratish*\n\n1️⃣ Kod nomini kiriting (masalan: SUMMER20):",
                     parse_mode="Markdown", reply_markup=kb_cancel())


@bot.message_handler(func=lambda m: user_states.get(m.from_user.id, {}).get("state") == "create_promo")
def handle_create_promo(msg: types.Message):
    uid   = msg.from_user.id
    state = user_states[uid]
    step  = state["step"]

    if msg.text == "❌ Bekor qilish":
        del user_states[uid]
        bot.send_message(msg.chat.id, "❌ Bekor qilindi!", reply_markup=kb_admin())
        return

    if step == "code":
        state["data"]["code"] = msg.text.upper().strip()
        state["step"]         = "discount_type"
        m = types.ReplyKeyboardMarkup(resize_keyboard=True)
        m.add("📊 Foiz (%)", "💰 Belgilangan summa")
        m.add("❌ Bekor qilish")
        bot.send_message(msg.chat.id, "2️⃣ Chegirma turini tanlang:", reply_markup=m)

    elif step == "discount_type":
        state["data"]["discount_type"] = "percentage" if "Foiz" in msg.text else "fixed"
        state["step"]                  = "discount_value"
        hint = "foiz (masalan: 10)" if state["data"]["discount_type"] == "percentage" else "summa so'mda"
        bot.send_message(msg.chat.id, f"3️⃣ Chegirma {hint}ni kiriting:")

    elif step == "discount_value":
        try:
            v = int(msg.text.replace(" ", "").replace(",", ""))
            assert v > 0
            state["data"]["discount_value"] = v
            state["step"]                   = "expiry"
            bot.send_message(msg.chat.id, "4️⃣ Amal qilish muddati (kun, 0 = cheksiz):")
        except Exception:
            bot.send_message(msg.chat.id, "❌ Noto'g'ri qiymat! Raqam kiriting:")

    elif step == "expiry":
        try:
            days   = int(msg.text)
            expiry = datetime.now() + timedelta(days=days if days > 0 else 365)
            promo  = {
                "code":           state["data"]["code"],
                "discount_type":  state["data"]["discount_type"],
                "discount_value": state["data"]["discount_value"],
                "expires_at":     expiry.isoformat(),
                "usage_limit":    100,
                "used_count":     0,
                "active":         True,
            }
            db.add_promo(promo)
            v    = promo["discount_value"]
            desc = f"{v}%" if promo["discount_type"] == "percentage" else f"{format_price(v)} so'm"
            bot.send_message(
                msg.chat.id,
                f"✅ *Promo kod yaratildi!*\n\n"
                f"🎁 Kod: `{promo['code']}`\n"
                f"📊 Chegirma: {desc}\n"
                f"📅 Muddati: {expiry.strftime('%Y-%m-%d')}",
                parse_mode="Markdown", reply_markup=kb_admin(),
            )
            del user_states[uid]
        except Exception:
            bot.send_message(msg.chat.id, "❌ Noto'g'ri! Raqam kiriting:")


# ============================================================
#  ADMIN — BROADCAST
# ============================================================
@bot.message_handler(func=lambda m: m.text == "📢 Xabar yuborish")
def admin_broadcast_start(msg: types.Message):
    if not is_admin(msg.from_user.id):
        return
    user_states[msg.from_user.id] = {"state": "broadcast", "step": "message"}
    bot.send_message(msg.chat.id,
                     "📢 *Xabar yuborish*\n\nXabaringizni yozing yoki rasm/video yuboring:",
                     parse_mode="Markdown", reply_markup=kb_cancel())


@bot.message_handler(func=lambda m: user_states.get(m.from_user.id, {}).get("state") == "broadcast")
def handle_broadcast(msg: types.Message):
    uid = msg.from_user.id
    if msg.text == "❌ Bekor qilish":
        del user_states[uid]
        bot.send_message(msg.chat.id, "❌ Bekor qilindi!", reply_markup=kb_admin())
        return

    users   = db.get_all_users()
    success = failed = 0
    status  = bot.send_message(msg.chat.id, "📢 Yuborilmoqda... ⏳")

    for user in users:
        try:
            if msg.photo:
                bot.send_photo(user["user_id"], msg.photo[-1].file_id, caption=msg.caption)
            elif msg.video:
                bot.send_video(user["user_id"], msg.video.file_id, caption=msg.caption)
            else:
                bot.send_message(user["user_id"], f"📢 *Xabar*\n\n{msg.text}", parse_mode="Markdown")
            success += 1
        except Exception:
            failed += 1

    bot.edit_message_text(
        f"✅ *Yakunlandi!*\n\n✅ {success} ta yuborildi\n❌ {failed} ta yuborilmadi",
        msg.chat.id, status.message_id, parse_mode="Markdown",
    )
    del user_states[uid]


# ============================================================
#  ADMIN — FOYDALANUVCHILAR
# ============================================================
@bot.message_handler(func=lambda m: m.text == "👥 Foydalanuvchilar")
def admin_users(msg: types.Message):
    if not is_admin(msg.from_user.id):
        return
    users = db.get_all_users()
    if not users:
        bot.send_message(msg.chat.id, "📭 Foydalanuvchilar mavjud emas!")
        return

    text = f"👥 *Foydalanuvchilar ({len(users)} ta):*\n\n"
    for u in users[:20]:
        text += (
            f"• {esc(u.get('name', '—'))}\n"
            f"  📞 {u.get('phone', '—')}\n"
            f"  💰 {format_price(u.get('total_spent', 0))} so'm\n\n"
        )
    bot.send_message(msg.chat.id, text, parse_mode="Markdown")


# ============================================================
#  ADMIN — SOZLAMALAR
# ============================================================
@bot.message_handler(func=lambda m: m.text == "⚙️ Sozlamalar")
def admin_settings(msg: types.Message):
    if not is_admin(msg.from_user.id):
        return
    s = db._load_json(SETTINGS_FILE)
    bot.send_message(
        msg.chat.id,
        f"⚙️ *Sozlamalar*\n\n"
        f"🚚 Yetkazib berish narxi: {format_price(s.get('delivery_fee', DELIVERY_FEE))} so'm\n"
        f"✅ Bepul yetkazish: {format_price(s.get('free_delivery_amount', FREE_DELIVERY_AMOUNT))} so'm dan\n"
        f"💳 Minimal zakaz: {format_price(MIN_ORDER_AMOUNT)} so'm\n"
        f"📦 Maks. mahsulotlar: {MAX_ORDER_ITEMS} ta",
        parse_mode="Markdown",
    )


# ============================================================
#  WEB APP — ZAKAZ QABUL QILISH
# ============================================================
@bot.message_handler(content_types=["web_app_data"])
def handle_web_app_order(msg: types.Message):
    try:
        data       = json.loads(msg.web_app_data.data)
        uid        = msg.from_user.id
        user       = db.get_user(uid)
        if not user:
            bot.send_message(msg.chat.id, "❌ Iltimos, /start bosing!")
            return

        items      = data.get("items", [])
        address    = data.get("address", "").strip()
        note       = data.get("note", "")
        promo_code = data.get("promo_code", "")

        if not items:
            bot.send_message(msg.chat.id, "❌ Savat bo'sh!")
            return
        if not address:
            bot.send_message(msg.chat.id, "❌ Manzil kiritilmagan!")
            return

        subtotal        = sum(i.get("price", 0) * i.get("quantity", 1) for i in items)
        discount, dpct  = calculate_discount(subtotal, promo_code)
        delivery_fee    = calculate_delivery_fee(subtotal - discount)
        total           = subtotal - discount + delivery_fee

        if total < MIN_ORDER_AMOUNT:
            bot.send_message(msg.chat.id,
                             f"❌ Minimal zakaz: {format_price(MIN_ORDER_AMOUNT)} so'm!")
            return

        order = db.add_order({
            "user_id":          uid,
            "user_name":        msg.from_user.first_name,
            "user_username":    msg.from_user.username,
            "user_phone":       user.get("phone", ""),
            "items":            items,
            "subtotal":         subtotal,
            "discount":         discount,
            "discount_percent": dpct,
            "delivery_fee":     delivery_fee,
            "total":            total,
            "address":          address,
            "note":             note,
            "promo_code":       promo_code,
            "status":           "new",
        })

        db.add_address(uid, address)
        if promo_code:
            db.use_promo(promo_code)
        db.update_user(uid, {
            "total_orders": user.get("total_orders", 0) + 1,
            "total_spent":  user.get("total_spent", 0) + total,
        })

        items_text = "\n".join(
            f"  • {i.get('name')} x{i.get('quantity', 1)} = "
            f"{format_price(i.get('price', 0) * i.get('quantity', 1))} so'm"
            for i in items
        )

        user_text = (
            f"✅ *Zakaz #{order['id']} qabul qilindi!*\n\n"
            f"📦 *Mahsulotlar:*\n{items_text}\n\n"
            f"💰 Mahsulotlar: {format_price(subtotal)} so'm\n"
        )
        if discount:
            user_text += f"🎁 Chegirma: -{format_price(discount)} so'm ({dpct}%)\n"
        user_text += (
            f"🚚 Yetkazib berish: {format_price(delivery_fee)} so'm\n"
            f"📊 *JAMI: {format_price(total)} so'm*\n\n"
            f"📍 *Manzil:* {esc(address)}\n"
        )
        if note:
            user_text += f"💬 Izoh: {esc(note)}\n"
        user_text += "\n📦 Zakazni «Mening zakazlarim» bo'limidan kuzating!"

        bot.send_message(msg.chat.id, user_text, parse_mode="Markdown")

        admin_text = (
            f"🆕 *YANGI ZAKAZ #{order['id']}*\n\n"
            f"👤 {msg.from_user.first_name}\n"
            f"📞 {user.get('phone', '—')}\n"
            f"📍 {esc(address)}\n\n"
            f"📦 *Mahsulotlar:*\n{items_text}\n\n"
            f"💰 *Jami:* {format_price(total)} so'm\n"
        )
        if promo_code:
            admin_text += f"🎁 Promo: {promo_code}\n"
        if note:
            admin_text += f"💬 Izoh: {esc(note)}\n"
        admin_text += f"\n📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}"

        for admin_id in ADMIN_IDS:
            try:
                bot.send_message(admin_id, admin_text, parse_mode="Markdown",
                                 reply_markup=kb_order_status(order["id"]))
            except Exception:
                pass

    except Exception as e:
        logger.error(f"Web App order error: {e}", exc_info=True)
        bot.send_message(msg.chat.id, "❌ Xatolik! Iltimos qaytadan urinib ko'ring.")


# ============================================================
#  CALLBACK HANDLERLAR
# ============================================================
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call: types.CallbackQuery):
    data = call.data

    # ── Zakaz holati o'zgartirish ──────────────────────────
    if data.startswith("status_"):
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Admin emassiz!")
            return
        _, order_id_str, status = data.split("_", 2)
        order_id = int(order_id_str)
        order    = db.update_order(order_id, {"status": status})
        if order:
            si = get_order_status_text(status)
            bot.answer_callback_query(call.id, f"{si['emoji']} {si['text']}")
            try:
                user_text = f"🔄 *Zakaz #{order_id} holati:* {si['text']}"
                if status == "delivering":
                    eta = random.randint(15, 60)
                    user_text += f"\n⏱ Taxminiy vaqt: {eta} daqiqa"
                    db.update_order(order_id, {"eta": f"{eta} daqiqa"})
                if status == "courier":
                    cph = "+998 90 123 45 67"
                    user_text += f"\n📞 Kuryer: {cph}"
                    db.update_order(order_id, {"courier_phone": cph})
                bot.send_message(order["user_id"], user_text, parse_mode="Markdown")
            except Exception:
                pass

    # ── Mahsulot o'chirish ─────────────────────────────────
    elif data.startswith("del_prod_"):
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌")
            return
        pid = int(data.split("_")[2])
        db.delete_product(pid)
        bot.answer_callback_query(call.id, "✅ O'chirildi!")
        bot.delete_message(call.message.chat.id, call.message.message_id)

    # ── Aktiv/inaktiv toggle ───────────────────────────────
    elif data.startswith("toggle_prod_"):
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌")
            return
        pid     = int(data.split("_")[2])
        product = db.get_product(pid)
        if product:
            new_status = not product.get("available", True)
            db.update_product(pid, {"available": new_status})
            bot.answer_callback_query(call.id, "aktiv ✅" if new_status else "inaktiv ❌")

    # ── Qayta zakaz ────────────────────────────────────────
    elif data.startswith("reorder_"):
        bot.answer_callback_query(call.id, "Do'konni oching!")
        bot.send_message(
            call.message.chat.id,
            "🔄 Qayta zakaz uchun do'konni oching:",
            reply_markup=types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton(
                    "🛍️ Do'kon", web_app=types.WebAppInfo(url=WEB_APP_URL),
                )
            ),
        )

    # ── Baholash ───────────────────────────────────────────
    elif data.startswith("review_"):
        order_id = int(data.split("_")[1])
        order    = db.get_order(order_id)
        if order and order.get("status") == "delivered":
            bot.answer_callback_query(call.id)
            bot.send_message(call.message.chat.id,
                             "⭐ *1 dan 5 gacha baho bering:*", parse_mode="Markdown")
            bot.register_next_step_handler(call.message, save_review, order_id)
        else:
            bot.answer_callback_query(call.id, "❌ Faqat yetkazilgan zakazlarni baholash mumkin!")

    # ── Sevimlilarni tozalash ──────────────────────────────
    elif data == "clear_favorites":
        uid = call.from_user.id
        for fid in db.get_favorites(uid)[:]:
            db.remove_favorite(uid, fid)
        bot.answer_callback_query(call.id, "✅ Tozalandi!")
        bot.delete_message(call.message.chat.id, call.message.message_id)

    else:
        bot.answer_callback_query(call.id)


def save_review(msg: types.Message, order_id: int):
    try:
        rating = int(msg.text)
        assert 1 <= rating <= 5
        order = db.get_order(order_id)
        if order:
            for item in order.get("items", []):
                pid = item.get("id")
                if pid:
                    db.add_review(pid, msg.from_user.id, rating)
            bot.send_message(msg.chat.id,
                             f"⭐ *Rahmat!* Bahoingiz: {rating}/5", parse_mode="Markdown")
    except Exception:
        bot.send_message(msg.chat.id, "❌ 1—5 oralig'ida son kiriting!")


# ============================================================
#  FASTAPI ROUTES
# ============================================================
@app.get("/")
async def root():
    return {"status": "online", "version": "5.0.0", "bot": "Telegram Shop Bot"}


@app.get("/shop", response_class=HTMLResponse)
async def shop_page():
    with open("shop.html", "r", encoding="utf-8") as f:
        return f.read()


@app.get("/api/products")
async def api_products():
    return JSONResponse(db.get_products())


@app.get("/api/addresses/{user_id}")
async def api_addresses(user_id: int):
    return JSONResponse(db.get_addresses(user_id))


@app.post("/webhook")
async def webhook(request: Request):
    try:
        data   = await request.json()
        update = types.Update.de_json(data)
        bot.process_new_updates([update])
        return {"ok": True}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================
#  STARTUP
# ============================================================
@app.on_event("startup")
async def startup():
    # Webhook
    webhook_url = f"{RENDER_EXTERNAL_URL}/webhook"
    bot.remove_webhook()
    bot.set_webhook(url=webhook_url)
    logger.info(f"✅ Webhook: {webhook_url}")

    # Default mahsulotlar
    if not db.get_products():
        for p in [
            {"name": "Classic T-Shirt",    "price": 89_000,    "category": "👗 Kiyim",        "description": "Sifatli paxta T-shirt"},
            {"name": "Sport Krossovkalar", "price": 299_000,   "category": "👟 Poyabzal",      "description": "Qulay sport poyabzali"},
            {"name": "Smartfon Pro",        "price": 2_499_000, "category": "📱 Elektronika",   "description": "6.5\" ekran, 128GB"},
            {"name": "LED Lampochka",       "price": 25_000,    "category": "🏠 Uy jihozlari",  "description": "Energiya tejamkor"},
            {"name": "Tandir Non",          "price": 5_000,     "category": "🍕 Oziq-ovqat",    "description": "Tandirda pishirilgan"},
            {"name": "Jersi Short",         "price": 59_000,    "category": "👗 Kiyim",         "description": "Yozgi sport shorti"},
            {"name": "Power Bank 10000",    "price": 129_000,   "category": "📱 Elektronika",   "description": "10 000 mAh, tez zaryadlash"},
        ]:
            db.add_product(p)
        logger.info("✅ Default mahsulotlar qo'shildi")

    # Default promo kodlar
    if not db.get_promos():
        for promo in [
            {"code": "WELCOME10", "discount_type": "percentage", "discount_value": 10,
             "expires_at": (datetime.now() + timedelta(days=30)).isoformat(), "active": True},
            {"code": "WELCOME20", "discount_type": "percentage", "discount_value": 20,
             "expires_at": (datetime.now() + timedelta(days=30)).isoformat(), "active": True},
        ]:
            db.add_promo(promo)
        logger.info("✅ Default promo kodlar qo'shildi")

    logger.info(f"🚀 Bot ishga tushdi! Admin IDs: {ADMIN_IDS}")


if __name__ == "__main__":
    uvicorn.run("bot:app", host="0.0.0.0", port=8000, reload=False)
