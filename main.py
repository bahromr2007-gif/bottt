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
from dataclasses import dataclass, asdict
from functools import wraps

# ============ KONFIGURATSIYA ============
BOT_TOKEN = "8778358404:AAHmM4e2OnROyXLCsGXERCbXd3arzl7kPS0"
RENDER_EXTERNAL_URL = "https://bottt-02j7.onrender.com"
WEB_APP_URL = f"{RENDER_EXTERNAL_URL}/shop"
ADMIN_IDS = [8735360012]

# Yetkazib berish sozlamalari
DELIVERY_FEE = 15000
FREE_DELIVERY_AMOUNT = 100000
MIN_ORDER_AMOUNT = 5000
MAX_ORDER_ITEMS = 50

# Fayllar
DATA_DIR = "data"
PRODUCTS_FILE = f"{DATA_DIR}/products.json"
ORDERS_FILE = f"{DATA_DIR}/orders.json"
USERS_FILE = f"{DATA_DIR}/users.json"
ADDRESSES_FILE = f"{DATA_DIR}/addresses.json"
FAVORITES_FILE = f"{DATA_DIR}/favorites.json"
PROMO_FILE = f"{DATA_DIR}/promo.json"
REVIEWS_FILE = f"{DATA_DIR}/reviews.json"
SETTINGS_FILE = f"{DATA_DIR}/settings.json"

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
        self._ensure_data_dir()
        self._init_files()
        self._lock = threading.Lock()
    
    def _ensure_data_dir(self):
        if not os.path.exists(DATA_DIR):
            os.makedirs(DATA_DIR)
    
    def _init_files(self):
        files = {
            PRODUCTS_FILE: [],
            ORDERS_FILE: [],
            USERS_FILE: {},
            ADDRESSES_FILE: {},
            FAVORITES_FILE: {},
            PROMO_FILE: [],
            REVIEWS_FILE: {},
            SETTINGS_FILE: {"delivery_fee": DELIVERY_FEE, "free_delivery_amount": FREE_DELIVERY_AMOUNT}
        }
        for file_path, default in files.items():
            if not os.path.exists(file_path):
                self._save_json(file_path, default)
    
    def _load_json(self, file_path: str) -> Any:
        with self._lock:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                return []
    
    def _save_json(self, file_path: str, data: Any):
        with self._lock:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
    
    # Mahsulotlar
    def get_products(self, only_available: bool = True) -> List[Dict]:
        products = self._load_json(PRODUCTS_FILE)
        if only_available:
            products = [p for p in products if p.get('available', True)]
        return sorted(products, key=lambda x: x.get('id', 0))
    
    def get_product(self, product_id: int) -> Optional[Dict]:
        products = self.get_products(only_available=False)
        return next((p for p in products if p['id'] == product_id), None)
    
    def add_product(self, product: Dict) -> Dict:
        products = self.get_products(only_available=False)
        product['id'] = max([p.get('id', 0) for p in products] + [0]) + 1
        product['created_at'] = datetime.now().isoformat()
        products.append(product)
        self._save_json(PRODUCTS_FILE, products)
        return product
    
    def update_product(self, product_id: int, updates: Dict) -> Optional[Dict]:
        products = self.get_products(only_available=False)
        for i, p in enumerate(products):
            if p['id'] == product_id:
                products[i].update(updates)
                self._save_json(PRODUCTS_FILE, products)
                return products[i]
        return None
    
    def delete_product(self, product_id: int) -> bool:
        products = self.get_products(only_available=False)
        new_products = [p for p in products if p['id'] != product_id]
        if len(new_products) != len(products):
            self._save_json(PRODUCTS_FILE, new_products)
            return True
        return False
    
    # Zakazlar
    def get_orders(self, user_id: Optional[int] = None, status: Optional[str] = None) -> List[Dict]:
        orders = self._load_json(ORDERS_FILE)
        if user_id:
            orders = [o for o in orders if o.get('user_id') == user_id]
        if status:
            orders = [o for o in orders if o.get('status') == status]
        return sorted(orders, key=lambda x: x.get('date', ''), reverse=True)
    
    def get_order(self, order_id: int) -> Optional[Dict]:
        orders = self.get_orders()
        return next((o for o in orders if o['id'] == order_id), None)
    
    def add_order(self, order: Dict) -> Dict:
        orders = self.get_orders()
        order['id'] = max([o.get('id', 0) for o in orders] + [1000]) + 1
        order['created_at'] = datetime.now().isoformat()
        orders.append(order)
        self._save_json(ORDERS_FILE, orders)
        return order
    
    def update_order(self, order_id: int, updates: Dict) -> Optional[Dict]:
        orders = self.get_orders()
        for i, o in enumerate(orders):
            if o['id'] == order_id:
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
        users = self.get_users()
        return list(users.values())
    
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
        return next((p for p in promos if p['code'] == code and p.get('active', True)), None)
    
    def add_promo(self, promo: Dict) -> Dict:
        promos = self.get_promos()
        promo['code'] = promo['code'].upper().strip()
        promos.append(promo)
        self._save_json(PROMO_FILE, promos)
        return promo
    
    def use_promo(self, code: str) -> bool:
        promos = self.get_promos()
        for p in promos:
            if p['code'] == code.upper().strip():
                p['used_count'] = p.get('used_count', 0) + 1
                if p.get('usage_limit') and p['used_count'] >= p['usage_limit']:
                    p['active'] = False
                self._save_json(PROMO_FILE, promos)
                return True
        return False
    
    # Baholar
    def get_reviews(self, product_id: Optional[int] = None) -> Dict:
        reviews = self._load_json(REVIEWS_FILE)
        if product_id:
            return reviews.get(str(product_id), [])
        return reviews
    
    def add_review(self, product_id: int, user_id: int, rating: int, comment: str = "") -> Dict:
        reviews = self._load_json(REVIEWS_FILE)
        product_reviews = reviews.get(str(product_id), [])
        review = {
            'user_id': user_id,
            'rating': rating,
            'comment': comment,
            'date': datetime.now().isoformat()
        }
        product_reviews.append(review)
        reviews[str(product_id)] = product_reviews
        self._save_json(REVIEWS_FILE, reviews)
        
        # Mahsulot reytingini yangilash
        product = self.get_product(product_id)
        if product:
            avg_rating = sum(r['rating'] for r in product_reviews) / len(product_reviews)
            self.update_product(product_id, {'rating': round(avg_rating, 1), 'reviews_count': len(product_reviews)})
        
        return review
    
    # Statistika
    def get_stats(self) -> Dict:
        users = self.get_users()
        orders = self.get_orders()
        products = self.get_products(only_available=False)
        
        today = datetime.now().strftime("%Y-%m-%d")
        week_ago = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
        
        today_orders = [o for o in orders if o.get('date', '').startswith(today)]
        week_orders = [o for o in orders if o.get('date', '') >= week_ago]
        
        # Kategoriyalar bo'yicha statistika
        category_stats = {}
        for product in products:
            cat = product.get('category', 'Boshqa')
            category_stats[cat] = category_stats.get(cat, 0) + 1
        
        return {
            'total_users': len(users),
            'total_products': len(products),
            'total_orders': len(orders),
            'total_revenue': sum(o.get('total', 0) for o in orders),
            'today_orders': len(today_orders),
            'today_revenue': sum(o.get('total', 0) for o in today_orders),
            'week_orders': len(week_orders),
            'week_revenue': sum(o.get('total', 0) for o in week_orders),
            'category_stats': category_stats,
            'pending_orders': len([o for o in orders if o.get('status') in ['new', 'accepted', 'preparing']])
        }

db = Database()

# ============ YORDAMCHI FUNKSIYALAR ============
def format_price(price: int) -> str:
    """Narxni formatlash (1 234 567 so'm)"""
    return f"{price:,}".replace(",", " ")

def format_phone(phone: str) -> str:
    """Telefon raqamni formatlash"""
    digits = re.sub(r'\D', '', phone)
    if len(digits) == 9:
        return f"+998 {digits[:2]} {digits[2:5]} {digits[5:7]} {digits[7:]}"
    elif len(digits) == 12 and digits.startswith("998"):
        return f"+{digits[:3]} {digits[3:5]} {digits[5:8]} {digits[8:10]} {digits[10:]}"
    return phone

def validate_phone(phone: str) -> bool:
    """Telefon raqamni tekshirish"""
    digits = re.sub(r'\D', '', phone)
    return len(digits) in [9, 12, 13]

def calculate_delivery_fee(total: int) -> int:
    """Yetkazib berish narxini hisoblash"""
    settings = db._load_json(SETTINGS_FILE)
    free_amount = settings.get('free_delivery_amount', FREE_DELIVERY_AMOUNT)
    return 0 if total >= free_amount else settings.get('delivery_fee', DELIVERY_FEE)

def calculate_discount(total: int, promo_code: str = None) -> tuple:
    """Chegirmani hisoblash"""
    discount_amount = 0
    discount_percent = 0
    
    if promo_code:
        promo = db.get_promo(promo_code)
        if promo and promo.get('active', True):
            if promo.get('discount_type') == 'percentage':
                discount_percent = promo.get('discount_value', 0)
                discount_amount = int(total * discount_percent / 100)
            else:
                discount_amount = min(promo.get('discount_value', 0), total)
    
    return discount_amount, discount_percent

def get_order_status_text(status: str) -> dict:
    """Zakaz holati matni va emojisi"""
    statuses = {
        'new': {'text': 'Yangi zakaz', 'emoji': '🆕', 'color': '#FF6B35'},
        'accepted': {'text': 'Qabul qilindi', 'emoji': '✅', 'color': '#48BB78'},
        'preparing': {'text': 'Tayyorlanmoqda', 'emoji': '🔧', 'color': '#F6AD55'},
        'courier': {'text': 'Kuryerga berildi', 'emoji': '🚚', 'color': '#4299E1'},
        'delivering': {'text': 'Yetkazilmoqda', 'emoji': '🚛', 'color': '#9F7AEA'},
        'delivered': {'text': 'Yetkazildi', 'emoji': '📦', 'color': '#48BB78'},
        'cancelled': {'text': 'Bekor qilindi', 'emoji': '❌', 'color': '#F56565'}
    }
    return statuses.get(status, {'text': status, 'emoji': '📋', 'color': '#718096'})

def is_admin(user_id: int) -> bool:
    """Adminlikni tekshirish"""
    return user_id in ADMIN_IDS

def escape_markdown(text: str) -> str:
    """Markdown special belgilarni escape qilish"""
    special_chars = r'_*[]()~`>#+-=|{}.!'
    return ''.join(f'\\{c}' if c in special_chars else c for c in str(text))

# ============ KLAVIATURALAR ============
def get_main_keyboard(user_id: int) -> types.ReplyKeyboardMarkup:
    """Asosiy menyu klaviaturasi"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    
    # Do'kon tugmasi (Web App)
    shop_btn = types.KeyboardButton(
        "🛍️ DO'KON",
        web_app=types.WebAppInfo(url=WEB_APP_URL)
    )
    markup.add(shop_btn)
    
    # Asosiy tugmalar
    buttons = [
        "📦 Mening zakazlarim",
        "❤️ Sevimlilar",
        "📍 Manzillarim",
        "🎁 Promo kodlar",
        "📞 Aloqa",
        "ℹ️ Yordam"
    ]
    markup.add(*buttons)
    
    # Admin tugmasi
    if is_admin(user_id):
        markup.add("👨‍💼 ADMIN PANEL")
    
    return markup

def get_admin_keyboard() -> types.ReplyKeyboardMarkup:
    """Admin panel klaviaturasi"""
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
    """Bekor qilish klaviaturasi"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("❌ Bekor qilish")
    return markup

def get_category_keyboard() -> types.ReplyKeyboardMarkup:
    """Kategoriya tanlash klaviaturasi"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    categories = ["👗 Kiyim", "👟 Poyabzal", "📱 Elektronika", "🏠 Uy jihozlari", "🍕 Oziq-ovqat", "🎁 Boshqa"]
    for cat in categories:
        markup.add(types.KeyboardButton(cat))
    markup.add("❌ Bekor qilish")
    return markup

def get_order_status_keyboard(order_id: int) -> types.InlineKeyboardMarkup:
    """Zakaz holatini o'zgartirish tugmalari"""
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
    """Zakaz uchun amallar"""
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔄 Qayta zakaz", callback_data=f"reorder_{order_id}"))
    if is_delivered:
        markup.add(types.InlineKeyboardButton("⭐ Baholash", callback_data=f"review_{order_id}"))
    return markup

def get_pagination_keyboard(page: int, total_pages: int, prefix: str) -> types.InlineKeyboardMarkup:
    """Sahifalash tugmalari"""
    markup = types.InlineKeyboardMarkup(row_width=3)
    buttons = []
    
    if page > 1:
        buttons.append(types.InlineKeyboardButton("◀️", callback_data=f"{prefix}_page_{page-1}"))
    
    buttons.append(types.InlineKeyboardButton(f"📄 {page}/{total_pages}", callback_data="ignore"))
    
    if page < total_pages:
        buttons.append(types.InlineKeyboardButton("▶️", callback_data=f"{prefix}_page_{page+1}"))
    
    markup.add(*buttons)
    return markup

# ============ BOT VA FASTAPI ============
bot = telebot.TeleBot(BOT_TOKEN)
app = FastAPI(title="Telegram Shop Bot", version="4.0.0")

# Foydalanuvchi holatlari
user_states = {}

# ============ BOT HANDLERLAR ============
@bot.message_handler(commands=['start'])
def start_command(message: types.Message):
    """/start komandasi"""
    user_id = message.from_user.id
    user = db.get_user(user_id)
    
    if not user:
        # Ro'yxatdan o'tmagan foydalanuvchi
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        contact_btn = types.KeyboardButton("📱 Telefon raqam yuborish", request_contact=True)
        markup.add(contact_btn)
        
        bot.send_message(
            message.chat.id,
            f"👋 *Assalomu alaykum {escape_markdown(message.from_user.first_name)}!*\n\n"
            "🚀 *Do'konimizga xush kelibsiz!*\n\n"
            "📝 Ro'yxatdan o'tish uchun telefon raqamingizni yuboring 👇",
            parse_mode="Markdown",
            reply_markup=markup
        )
        user_states[user_id] = {'state': 'waiting_contact'}
    else:
        # Ro'yxatdan o'tgan foydalanuvchi
        bot.send_message(
            message.chat.id,
            "🏠 *Asosiy menyu*",
            parse_mode="Markdown",
            reply_markup=get_main_keyboard(user_id)
        )
        user_states[user_id] = {'state': 'idle'}

@bot.message_handler(content_types=['contact'])
def handle_contact(message: types.Message):
    """Telefon raqamni qabul qilish"""
    user_id = message.from_user.id
    
    if user_states.get(user_id, {}).get('state') != 'waiting_contact':
        return
    
    if message.contact:
        phone = message.contact.phone_number
    else:
        bot.send_message(message.chat.id, "❌ Iltimos, telefon raqam tugmasini bosing!")
        return
    
    if not validate_phone(phone):
        bot.send_message(
            message.chat.id,
            "❌ *Noto'g'ri telefon raqam!*\n\nIltimos, to'g'ri raqam yuboring.",
            parse_mode="Markdown"
        )
        return
    
    # Foydalanuvchini saqlash
    user_data = {
        'user_id': user_id,
        'name': message.from_user.first_name,
        'username': message.from_user.username,
        'phone': format_phone(phone),
        'joined': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'total_orders': 0,
        'total_spent': 0,
        'language': 'uz'
    }
    db.add_user(user_id, user_data)
    
    bot.send_message(
        message.chat.id,
        "✅ *Ro'yxatdan o'tdingiz!*\n\n"
        "Endi xarid qilishingiz mumkin 🛍️",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard(user_id)
    )
    user_states[user_id] = {'state': 'idle'}
    
    # Adminlarga xabar
    for admin_id in ADMIN_IDS:
        try:
            bot.send_message(
                admin_id,
                f"🆕 *Yangi foydalanuvchi!*\n\n"
                f"👤 {message.from_user.first_name}\n"
                f"📞 {format_phone(phone)}\n"
                f"🆔 {user_id}\n"
                f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                parse_mode="Markdown"
            )
        except:
            pass

@bot.message_handler(func=lambda m: m.text == "🛍️ DO'KON")
def shop_button(message: types.Message):
    """Do'kon tugmasi - Web App ochiladi"""
    # Web App avtomatik ochiladi, qo'shimcha xabar kerak emas
    pass

@bot.message_handler(func=lambda m: m.text == "📦 Mening zakazlarim")
def my_orders(message: types.Message):
    """Foydalanuvchi zakazlari"""
    user_id = message.from_user.id
    orders = db.get_orders(user_id)
    
    if not orders:
        bot.send_message(
            message.chat.id,
            "📭 *Zakazlaringiz yo'q*\n\n"
            "🛍️ Do'konni ochib xarid qiling!",
            parse_mode="Markdown"
        )
        return
    
    # Oxirgi 10 ta zakazni ko'rsatish
    for order in orders[:10]:
        status_info = get_order_status_text(order.get('status', 'new'))
        
        items_text = "\n".join([
            f"  • {item.get('name', 'Noma\'lum')} x{item.get('quantity', 1)} = {format_price(item.get('price', 0) * item.get('quantity', 1))} so'm"
            for item in order.get('items', [])
        ])
        
        text = f"""
{status_info['emoji']} *Zakaz #{order['id']}*
📅 {order.get('date', 'Noma\'lum')}
💰 {format_price(order.get('total', 0))} so'm
📊 *Holat:* {status_info['text']}

📦 *Mahsulotlar:*
{items_text}

📍 *Manzil:* {order.get('address', 'Noma\'lum')}
"""
        
        if order.get('eta'):
            text += f"\n⏱ *Yetib borish vaqti:* {order['eta']}"
        
        if order.get('courier_phone'):
            text += f"\n📞 *Kuryer:* {order['courier_phone']}"
        
        is_delivered = order.get('status') == 'delivered'
        markup = get_order_actions_keyboard(order['id'], is_delivered)
        
        bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "❤️ Sevimlilar")
def my_favorites(message: types.Message):
    """Sevimli mahsulotlar"""
    user_id = message.from_user.id
    favorites = db.get_favorites(user_id)
    products = db.get_products()
    
    if not favorites:
        bot.send_message(
            message.chat.id,
            "❤️ *Sevimli mahsulotlaringiz yo'q*\n\n"
            "Mahsulotlarni ❤️ bosib saqlang!",
            parse_mode="Markdown"
        )
        return
    
    fav_products = [p for p in products if p['id'] in favorites]
    
    if not fav_products:
        bot.send_message(message.chat.id, "❤️ Sevimli mahsulotlar topilmadi!")
        return
    
    text = "❤️ *Sevimli mahsulotlaringiz:*\n\n"
    for p in fav_products:
        text += f"• {escape_markdown(p['name'])} - {format_price(p['price'])} so'm\n"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🗑 Barchasini tozalash", callback_data="clear_favorites"))
    
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "📍 Manzillarim")
def my_addresses(message: types.Message):
    """Foydalanuvchi manzillari"""
    user_id = message.from_user.id
    addresses = db.get_addresses(user_id)
    
    if not addresses:
        bot.send_message(
            message.chat.id,
            "📍 *Sizning manzillaringiz yo'q*\n\n"
            "Zakaz berishda manzil avtomatik saqlanadi.",
            parse_mode="Markdown"
        )
        return
    
    text = "📍 *Sizning manzillaringiz:*\n\n"
    for i, addr in enumerate(addresses, 1):
        text += f"{i}. {escape_markdown(addr)}\n"
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🗑 Manzil o'chirish", callback_data="delete_address"))
    
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "🎁 Promo kodlar")
def promo_codes(message: types.Message):
    """Promo kodlar haqida ma'lumot"""
    text = """
🎁 *Promo kodlar*

Aktiv promo kodlarni kiriting va chegirma oling!

*Qanday ishlatiladi?*
1. Savatchaga mahsulotlarni qo'shing
2. Zakaz berishda promo kodni kiriting
3. Chegirma avtomatik qo'llanadi

*Aktiv promo kodlar:*
• WELCOME10 - 10% chegirma (birinchi zakaz uchun)
• WELCOME20 - 20% chegirma

📌 *Eslatma:* Har bir promo kod bir marta ishlatiladi!
"""
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "📞 Aloqa")
def contact_info(message: types.Message):
    """Aloqa ma'lumotlari"""
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

💬 *Savollaringiz bo'lsa, yozing!*
"""
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "ℹ️ Yordam")
def help_info(message: types.Message):
    """Yordam ma'lumotlari"""
    text = """
ℹ️ *Yordam markazi*

🛍️ *Do'kon* - Mahsulotlarni ko'rish va xarid qilish
📦 *Zakazlarim* - Zakazlaringizni kuzatish
❤️ *Sevimlilar* - Saqlangan mahsulotlar
📍 *Manzillarim* - Saqlangan manzillar
🎁 *Promo kod* - Chegirma kodlarini qo'llash

*Zakaz berish jarayoni:*
1. Do'kon orqali mahsulotlarni tanlang
2. Savatga qo'shing
3. Manzil va promo kodni kiriting
4. Zakazni tasdiqlang

*To'lov usullari:*
• Naqd pul (yetkazib berishda)
• Click (online to'lov)
• Payme (online to'lov)

💡 *Maslahat:* Aniq manzil va telefon raqam kiriting!
"""
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "👨‍💼 ADMIN PANEL")
def admin_panel(message: types.Message):
    """Admin panel"""
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
    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=get_admin_keyboard())

@bot.message_handler(func=lambda m: m.text == "🔙 Asosiy menyu")
def back_to_main(message: types.Message):
    """Asosiy menyuga qaytish"""
    user_id = message.from_user.id
    user_states[user_id] = {'state': 'idle'}
    bot.send_message(
        message.chat.id,
        "🏠 *Asosiy menyu*",
        parse_mode="Markdown",
        reply_markup=get_main_keyboard(user_id)
    )

# ============ ADMIN HANDLERLAR ============
@bot.message_handler(func=lambda m: m.text == "➕ Mahsulot qo'shish")
def admin_add_product_start(message: types.Message):
    """Mahsulot qo'shish boshlash"""
    if not is_admin(message.from_user.id):
        return
    
    user_states[message.from_user.id] = {'state': 'add_product', 'step': 'name', 'data': {}}
    bot.send_message(
        message.chat.id,
        "➕ *Mahsulot qo'shish*\n\n"
        "1️⃣ *Mahsulot nomini kiriting:*",
        parse_mode="Markdown",
        reply_markup=get_cancel_keyboard()
    )

@bot.message_handler(func=lambda m: m.text == "📋 Mahsulotlar ro'yxati")
def admin_list_products(message: types.Message):
    """Mahsulotlar ro'yxati"""
    if not is_admin(message.from_user.id):
        return
    
    products = db.get_products(only_available=False)
    
    if not products:
        bot.send_message(message.chat.id, "📭 Mahsulotlar mavjud emas!")
        return
    
    for product in products[:20]:
        status = "✅ Aktiv" if product.get('available', True) else "❌ Aktiv emas"
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
        bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "📦 Zakazlar")
def admin_list_orders(message: types.Message):
    """Barcha zakazlar"""
    if not is_admin(message.from_user.id):
        return
    
    orders = db.get_orders()
    
    if not orders:
        bot.send_message(message.chat.id, "📭 Zakazlar mavjud emas!")
        return
    
    for order in orders[:20]:
        status_info = get_order_status_text(order.get('status', 'new'))
        
        text = f"""
{status_info['emoji']} *Zakaz #{order['id']}*
👤 {escape_markdown(order.get('user_name', 'Noma\'lum'))}
📞 {order.get('user_phone', 'Noma\'lum')}
📍 {order.get('address', 'Noma\'lum')}
💰 {format_price(order.get('total', 0))} so'm
📅 {order.get('date', 'Noma\'lum')}
📊 Holat: {status_info['text']}
"""
        markup = get_order_status_keyboard(order['id'])
        bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "📊 Statistika")
def admin_stats(message: types.Message):
    """To'liq statistika"""
    if not is_admin(message.from_user.id):
        return
    
    stats = db.get_stats()
    orders = db.get_orders()
    
    # Eng ko'p sotilgan mahsulotlar
    product_sales = {}
    for order in orders:
        for item in order.get('items', []):
            name = item.get('name')
            if name:
                product_sales[name] = product_sales.get(name, 0) + item.get('quantity', 1)
    
    top_products = sorted(product_sales.items(), key=lambda x: x[1], reverse=True)[:10]
    top_text = "\n".join([f"{i+1}. {escape_markdown(name)} - {qty} ta" for i, (name, qty) in enumerate(top_products)]) if top_products else "Ma'lumot yo'q"
    
    # Holatlar bo'yicha statistika
    status_stats = {}
    for order in orders:
        status = order.get('status', 'new')
        status_stats[status] = status_stats.get(status, 0) + 1
    
    status_text = "\n".join([f"{get_order_status_text(s)['emoji']} {get_order_status_text(s)['text']}: {count}" for s, count in status_stats.items()])
    
    text = f"""
📊 *TO'LIQ STATISTIKA*

👥 *Foydalanuvchilar:* {stats['total_users']}
🛍️ *Mahsulotlar:* {stats['total_products']}
📦 *Jami zakazlar:* {stats['total_orders']}
💰 *Umumiy sotuv:* {format_price(stats['total_revenue'])} so'm

📅 *BUGUN:*
Zakazlar: {stats['today_orders']}
Sotuv: {format_price(stats['today_revenue'])} so'm

📊 *SO'NGI 7 KUN:*
Zakazlar: {stats['week_orders']}
Sotuv: {format_price(stats['week_revenue'])} so'm

📋 *HOLATLAR BO'YICHA:*
{status_text}

🏆 *ENG KO'P SOTILGAN (TOP 10):*
{top_text}

📂 *KATEGORIYALAR BO'YICHA:*
{chr(10).join([f"• {cat}: {count} ta" for cat, count in stats.get('category_stats', {}).items()])}
"""
    
    # Sahifalash uchun
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "🎁 Promo kod yaratish")
def admin_create_promo_start(message: types.Message):
    """Promo kod yaratish boshlash"""
    if not is_admin(message.from_user.id):
        return
    
    user_states[message.from_user.id] = {'state': 'create_promo', 'step': 'code', 'data': {}}
    bot.send_message(
        message.chat.id,
        "🎁 *Promo kod yaratish*\n\n"
        "1️⃣ *Promo kod nomini kiriting:*\n"
        "Masalan: WELCOME10 yoki SUMMER50",
        parse_mode="Markdown",
        reply_markup=get_cancel_keyboard()
    )

@bot.message_handler(func=lambda m: m.text == "📢 Xabar yuborish")
def admin_broadcast_start(message: types.Message):
    """Xabar yuborish boshlash"""
    if not is_admin(message.from_user.id):
        return
    
    user_states[message.from_user.id] = {'state': 'broadcast', 'step': 'message'}
    bot.send_message(
        message.chat.id,
        "📢 *Xabar yuborish*\n\n"
        "Yubormoqchi bo'lgan xabaringizni yozing yoki rasm/Video yuboring:\n\n"
        "💡 *Maslahat:* Xabar barcha foydalanuvchilarga yuboriladi!",
        parse_mode="Markdown",
        reply_markup=get_cancel_keyboard()
    )

@bot.message_handler(func=lambda m: m.text == "👥 Foydalanuvchilar")
def admin_users_list(message: types.Message):
    """Foydalanuvchilar ro'yxati"""
    if not is_admin(message.from_user.id):
        return
    
    users = db.get_all_users()
    
    if not users:
        bot.send_message(message.chat.id, "📭 Foydalanuvchilar mavjud emas!")
        return
    
    text = "👥 *Foydalanuvchilar ro'yxati:*\n\n"
    for user in users[:20]:
        text += f"• {escape_markdown(user.get('name', 'Noma\'lum'))}\n"
        text += f"  📞 {user.get('phone', 'Noma\'lum')}\n"
        text += f"  🆔 {user.get('user_id')}\n"
        text += f"  📅 {user.get('joined', 'Noma\'lum')}\n"
        text += f"  💰 {format_price(user.get('total_spent', 0))} so'm\n\n"
    
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.text == "⚙️ Sozlamalar")
def admin_settings(message: types.Message):
    """Admin sozlamalari"""
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

🔄 Sozlamalarni o'zgartirish uchun admin bilan bog'laning.
"""
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

# ============ STATE HANDLERLAR ============
@bot.message_handler(func=lambda m: user_states.get(m.from_user.id, {}).get('state') == 'add_product')
def handle_add_product(message: types.Message):
    """Mahsulot qo'shish jarayoni"""
    user_id = message.from_user.id
    state = user_states[user_id]
    step = state.get('step')
    
    if message.text == "❌ Bekor qilish":
        del user_states[user_id]
        bot.send_message(message.chat.id, "❌ Bekor qilindi!", reply_markup=get_admin_keyboard())
        return
    
    if step == 'name':
        state['data']['name'] = message.text
        state['step'] = 'price'
        bot.send_message(message.chat.id, "2️⃣ *Mahsulot narxini kiriting (so'mda):*\nMasalan: 50000", parse_mode="Markdown")
    
    elif step == 'price':
        try:
            price = int(message.text.replace(' ', '').replace(',', ''))
            if price <= 0:
                raise ValueError
            state['data']['price'] = price
            state['step'] = 'category'
            bot.send_message(message.chat.id, "3️⃣ *Kategoriyani tanlang:*", parse_mode="Markdown", reply_markup=get_category_keyboard())
        except:
            bot.send_message(message.chat.id, "❌ Noto'g'ri narx! Iltimos, son kiriting:", parse_mode="Markdown")
    
    elif step == 'category':
        state['data']['category'] = message.text
        state['step'] = 'description'
        bot.send_message(message.chat.id, "4️⃣ *Mahsulot tavsifi (ixtiyoriy):*\nTavsif kiriting yoki '❌ Bekor qilish' bosing", parse_mode="Markdown", reply_markup=get_cancel_keyboard())
    
    elif step == 'description':
        description = "" if message.text == "❌ Bekor qilish" else message.text
        state['data']['description'] = description
        
        # Mahsulotni saqlash
        product = db.add_product(state['data'])
        
        bot.send_message(
            message.chat.id,
            f"✅ *Mahsulot qo'shildi!*\n\n"
            f"📌 {escape_markdown(product['name'])}\n"
            f"💰 {format_price(product['price'])} so'm\n"
            f"🏷 {product['category']}\n"
            f"🆔 #{product['id']}",
            parse_mode="Markdown",
            reply_markup=get_admin_keyboard()
        )
        
        del user_states[user_id]

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id, {}).get('state') == 'create_promo')
def handle_create_promo(message: types.Message):
    """Promo kod yaratish jarayoni"""
    user_id = message.from_user.id
    state = user_states[user_id]
    step = state.get('step')
    
    if message.text == "❌ Bekor qilish":
        del user_states[user_id]
        bot.send_message(message.chat.id, "❌ Bekor qilindi!", reply_markup=get_admin_keyboard())
        return
    
    if step == 'code':
        state['data']['code'] = message.text.upper().strip()
        state['step'] = 'discount_type'
        
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("📊 Foiz (%)", "💰 Belgilangan summa")
        markup.add("❌ Bekor qilish")
        
        bot.send_message(message.chat.id, "2️⃣ *Chegirma turini tanlang:*", parse_mode="Markdown", reply_markup=markup)
    
    elif step == 'discount_type':
        if 'Foiz' in message.text:
            state['data']['discount_type'] = 'percentage'
            state['step'] = 'discount_value'
            bot.send_message(message.chat.id, "3️⃣ *Chegirma foizini kiriting:*\nMasalan: 10 (10% uchun)", parse_mode="Markdown")
        else:
            state['data']['discount_type'] = 'fixed'
            state['step'] = 'discount_value'
            bot.send_message(message.chat.id, "3️⃣ *Chegirma summasini kiriting (so'mda):*\nMasalan: 10000", parse_mode="Markdown")
    
    elif step == 'discount_value':
        try:
            value = int(message.text.replace(' ', '').replace(',', ''))
            if value <= 0:
                raise ValueError
            state['data']['discount_value'] = value
            state['step'] = 'expiry'
            bot.send_message(
                message.chat.id,
                "4️⃣ *Amal qilish muddati (kunlarda):*\n"
                "Masalan: 30 (30 kun)\n"
                "Yoki '0' cheksiz uchun",
                parse_mode="Markdown"
            )
        except:
            bot.send_message(message.chat.id, "❌ Noto'g'ri qiymat! Iltimos, son kiriting:", parse_mode="Markdown")
    
    elif step == 'expiry':
        try:
            days = int(message.text)
            expiry_date = (datetime.now() + timedelta(days=days)) if days > 0 else datetime.now() + timedelta(days=365)
            
            promo = {
                'code': state['data']['code'],
                'discount_type': state['data']['discount_type'],
                'discount_value': state['data']['discount_value'],
                'expires_at': expiry_date.isoformat(),
                'usage_limit': 100,
                'used_count': 0,
                'active': True
            }
            
            db.add_promo(promo)
            
            bot.send_message(
                message.chat.id,
                f"✅ *Promo kod yaratildi!*\n\n"
                f"🎁 *Kod:* {promo['code']}\n"
                f"{'📊 Chegirma: ' + str(promo['discount_value']) + '%' if promo['discount_type'] == 'percentage' else '💰 Chegirma: ' + format_price(promo['discount_value']) + ' so'm'}\n"
                f"📅 Muddati: {expiry_date.strftime('%Y-%m-%d')}",
                parse_mode="Markdown",
                reply_markup=get_admin_keyboard()
            )
            
            del user_states[user_id]
        except:
            bot.send_message(message.chat.id, "❌ Noto'g'ri kun! Iltimos, son kiriting:", parse_mode="Markdown")

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id, {}).get('state') == 'broadcast')
def handle_broadcast(message: types.Message):
    """Xabar yuborish jarayoni"""
    user_id = message.from_user.id
    
    if message.text == "❌ Bekor qilish":
        del user_states[user_id]
        bot.send_message(message.chat.id, "❌ Bekor qilindi!", reply_markup=get_admin_keyboard())
        return
    
    users = db.get_all_users()
    success = 0
    failed = 0
    
    status_msg = bot.send_message(message.chat.id, "📢 Xabar yuborilmoqda... ⏳")
    
    for user in users:
        try:
            # Xabar turiga qarab yuborish
            if message.photo:
                bot.send_photo(user['user_id'], message.photo[-1].file_id, caption=message.caption)
            elif message.video:
                bot.send_video(user['user_id'], message.video.file_id, caption=message.caption)
            else:
                bot.send_message(user['user_id'], f"📢 *Xabar*\n\n{message.text}", parse_mode="Markdown")
            success += 1
        except:
            failed += 1
    
    bot.edit_message_text(
        f"✅ *Xabar yuborish yakunlandi!*\n\n"
        f"✅ Yuborildi: {success}\n"
        f"❌ Yuborilmadi: {failed}\n"
        f"📊 Jami: {len(users)} ta foydalanuvchi",
        message.chat.id,
        status_msg.message_id,
        parse_mode="Markdown",
        reply_markup=get_admin_keyboard()
    )
    
    del user_states[user_id]

# ============ WEB APP HANDLER ============
@bot.message_handler(content_types=['web_app_data'])
def handle_web_app_order(message: types.Message):
    """Web App dan zakaz qabul qilish"""
    try:
        data = json.loads(message.web_app_data.data)
        user_id = message.from_user.id
        user = db.get_user(user_id)
        
        if not user:
            bot.send_message(message.chat.id, "❌ Iltimos, /start buyrug'ini bosing!")
            return
        
        items = data.get('items', [])
        address = data.get('address', '')
        note = data.get('note', '')
        promo_code = data.get('promo_code', '')
        
        if not items:
            bot.send_message(message.chat.id, "❌ Savat bo'sh!")
            return
        
        if not address:
            bot.send_message(message.chat.id, "❌ Manzil kiritilmagan!")
            return
        
        # Hisoblashlar
        subtotal = sum(item.get('price', 0) * item.get('quantity', 1) for item in items)
        discount_amount, discount_percent = calculate_discount(subtotal, promo_code)
        delivery_fee = calculate_delivery_fee(subtotal - discount_amount)
        total = subtotal - discount_amount + delivery_fee
        
        if total < MIN_ORDER_AMOUNT:
            bot.send_message(
                message.chat.id,
                f"❌ *Minimal zakaz miqdori {format_price(MIN_ORDER_AMOUNT)} so'm!*\n\n"
                f"Sizning zakazingiz: {format_price(total)} so'm\n"
                f"Qo'shimcha {format_price(MIN_ORDER_AMOUNT - total)} so'm mahsulot qo'shing.",
                parse_mode="Markdown"
            )
            return
        
        # Zakaz yaratish
        order = {
            'user_id': user_id,
            'user_name': message.from_user.first_name,
            'user_username': message.from_user.username,
            'user_phone': user.get('phone', ''),
            'items': items,
            'subtotal': subtotal,
            'discount': discount_amount,
            'discount_percent': discount_percent,
            'delivery_fee': delivery_fee,
            'total': total,
            'address': address,
            'note': note,
            'promo_code': promo_code,
            'status': 'new',
            'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        saved_order = db.add_order(order)
        
        # Manzilni saqlash
        db.add_address(user_id, address)
        
        # Promo kodni ishlatilgan deb belgilash
        if promo_code:
            db.use_promo(promo_code)
        
        # Foydalanuvchi statistikasini yangilash
        user = db.get_user(user_id)
        db.update_user(user_id, {
            'total_orders': user.get('total_orders', 0) + 1,
            'total_spent': user.get('total_spent', 0) + total
        })
        
        # Foydalanuvchiga xabar
        items_text = "\n".join([
            f"  • {item.get('name')} x{item.get('quantity')} = {format_price(item.get('price') * item.get('quantity'))} so'm"
            for item in items
        ])
        
        text = f"""
✅ *Zakaz #{saved_order['id']} qabul qilindi!*

📦 *Mahsulotlar:*
{items_text}

💰 *Hisob:*
Mahsulotlar: {format_price(subtotal)} so'm
{f'🎁 Chegirma: -{format_price(discount_amount)} so'm ({discount_percent}%)' if discount_amount else ''}
🚚 Yetkazib berish: {format_price(delivery_fee)} so'm

📊 *JAMI: {format_price(total)} so'm*

📍 *Manzil:* {address}
{'💬 Izoh: ' + note if note else ''}

📅 Sana: {datetime.now().strftime('%H:%M, %d.%m.%Y')}

Holatni "📦 Mening zakazlarim" bo'limidan kuzating!
"""
        
        bot.send_message(message.chat.id, text, parse_mode="Markdown")
        
        # Adminlarga xabar
        admin_text = f"""
🆕 *YANGI ZAKAZ #{saved_order['id']}*

👤 {message.from_user.first_name}
📞 {user.get('phone', 'Noma\'lum')}
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
                bot.send_message(admin_id, admin_text, parse_mode="Markdown")
            except:
                pass
        
    except Exception as e:
        logger.error(f"Web App zakaz xatolik: {e}")
        bot.send_message(message.chat.id, "❌ Xatolik yuz berdi! Iltimos, qaytadan urinib ko'ring.")

# ============ CALLBACK HANDLERLAR ============
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    """Callback query larni qayta ishlash"""
    
    # Zakaz holatini o'zgartirish
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
            
            # Foydalanuvchiga xabar
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
                
                bot.send_message(order['user_id'], user_text, parse_mode="Markdown")
            except:
                pass
            
            # Admin xabarini yangilash
            status_info = get_order_status_text(status)
            new_text = call.message.text
            new_text = re.sub(r'📊 Holat:.*', f'📊 Holat: {status_info["emoji"]} {status_info["text"]}', new_text)
            bot.edit_message_text(new_text, call.message.chat.id, call.message.message_id, parse_mode="Markdown")
    
    # Mahsulot o'chirish
    elif call.data.startswith("del_prod_"):
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Admin emassiz!")
            return
        
        product_id = int(call.data.split("_")[2])
        db.delete_product(product_id)
        bot.answer_callback_query(call.id, "✅ Mahsulot o'chirildi!")
        bot.delete_message(call.message.chat.id, call.message.message_id)
    
    # Mahsulot aktiv/inaktiv
    elif call.data.startswith("toggle_prod_"):
        if not is_admin(call.from_user.id):
            bot.answer_callback_query(call.id, "❌ Admin emassiz!")
            return
        
        product_id = int(call.data.split("_")[2])
        product = db.get_product(product_id)
        if product:
            new_status = not product.get('available', True)
            db.update_product(product_id, {"available": new_status})
            status_text = "aktiv" if new_status else "inaktiv"
            bot.answer_callback_query(call.id, f"✅ Mahsulot {status_text} qilindi!")
            
            # Xabarni yangilash
            new_text = call.message.text
            new_text = re.sub(r'✅ Aktiv|❌ Aktiv emas', '✅ Aktiv' if new_status else '❌ Aktiv emas', new_text)
            bot.edit_message_text(new_text, call.message.chat.id, call.message.message_id, parse_mode="Markdown")
    
    # Qayta zakaz
    elif call.data.startswith("reorder_"):
        order_id = int(call.data.split("_")[1])
        order = db.get_order(order_id)
        
        if order:
            # Web App ga zakaz ma'lumotlarini yuborish
            bot.send_message(
                call.message.chat.id,
                "🔄 Qayta zakaz berish uchun do'konni oching!\n\n"
                "👇 Quyidagi tugmani bosing:",
                parse_mode="Markdown",
                reply_markup=types.InlineKeyboardMarkup().add(
                    types.InlineKeyboardButton("🛍️ Do'kon", web_app=types.WebAppInfo(url=WEB_APP_URL))
                )
            )
            bot.answer_callback_query(call.id, "✅ Do'kon orqali qayta zakaz bering!")
    
    # Baholash
    elif call.data.startswith("review_"):
        order_id = int(call.data.split("_")[1])
        order = db.get_order(order_id)
        
        if order and order.get('status') == 'delivered':
            bot.answer_callback_query(call.id)
            bot.send_message(
                call.message.chat.id,
                "⭐ *Mahsulotni baholang!*\n\n"
                "1 dan 5 gacha baho bering (masalan: 5):",
                parse_mode="Markdown"
            )
            bot.register_next_step_handler(call.message, save_review, order_id)
        else:
            bot.answer_callback_query(call.id, "❌ Faqat yetkazilgan zakazlarni baholash mumkin!")
    
    # Sevimlilarni tozalash
    elif call.data == "clear_favorites":
        user_id = call.from_user.id
        favorites = db.get_favorites(user_id)
        for fav in favorites[:]:
            db.remove_favorite(user_id, fav)
        bot.answer_callback_query(call.id, "✅ Sevimlilar tozalandi!")
        bot.delete_message(call.message.chat.id, call.message.message_id)
    
    # Ignore
    elif call.data == "ignore":
        bot.answer_callback_query(call.id)
    
    else:
        bot.answer_callback_query(call.id)

def save_review(message: types.Message, order_id: int):
    """Baholashni saqlash"""
    try:
        rating = int(message.text)
        if 1 <= rating <= 5:
            order = db.get_order(order_id)
            if order:
                for item in order.get('items', []):
                    product_id = item.get('id')
                    if product_id:
                        db.add_review(product_id, message.from_user.id, rating, "")
                
                bot.send_message(
                    message.chat.id,
                    f"⭐ *Rahmat!* Bahoingiz: {rating}/5\n\nSizning fikringiz biz uchun muhim!",
                    parse_mode="Markdown"
                )
            else:
                bot.send_message(message.chat.id, "❌ Zakaz topilmadi!")
        else:
            bot.send_message(message.chat.id, "❌ 1-5 oralig'ida son kiriting!")
    except:
        bot.send_message(message.chat.id, "❌ Iltimos, son kiriting!")

# ============ FASTAPI ============
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="uz">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no, viewport-fit=cover">
    <title>🛍️ DO'KON</title>
    <script src="https://telegram.org/js/telegram-web-app.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
            -webkit-tap-highlight-color: transparent;
        }
        
        :root {
            --primary: #FF6B35;
            --primary-dark: #e55a26;
            --primary-light: #FF8C42;
            --secondary: #2D3748;
            --bg: #F7F8FC;
            --card: #FFFFFF;
            --text: #1A202C;
            --text-light: #718096;
            --border: #E2E8F0;
            --success: #48BB78;
            --warning: #F6AD55;
            --danger: #F56565;
            --shadow: 0 2px 8px rgba(0,0,0,0.05);
            --shadow-lg: 0 4px 20px rgba(0,0,0,0.1);
            --radius: 16px;
            --radius-sm: 12px;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
            background: var(--bg);
            color: var(--text);
            padding-bottom: 70px;
        }
        
        /* Header */
        .header {
            background: var(--card);
            padding: 16px 20px;
            position: sticky;
            top: 0;
            z-index: 100;
            box-shadow: var(--shadow);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .logo {
            font-size: 22px;
            font-weight: 800;
            background: linear-gradient(135deg, var(--primary), var(--primary-light));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        
        .header-icons {
            display: flex;
            gap: 12px;
        }
        
        .icon-btn {
            background: var(--bg);
            border: none;
            padding: 10px 14px;
            border-radius: 50px;
            cursor: pointer;
            font-size: 18px;
            position: relative;
            transition: transform 0.2s;
        }
        
        .icon-btn:active {
            transform: scale(0.95);
        }
        
        .cart-count {
            position: absolute;
            top: -5px;
            right: -5px;
            background: var(--primary);
            color: white;
            border-radius: 50%;
            width: 20px;
            height: 20px;
            font-size: 11px;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        /* Search */
        .search-box {
            padding: 12px 20px;
        }
        
        .search-input {
            width: 100%;
            padding: 14px 18px;
            border: 2px solid var(--border);
            border-radius: 50px;
            font-size: 15px;
            outline: none;
            background: var(--card);
            transition: all 0.2s;
        }
        
        .search-input:focus {
            border-color: var(--primary);
            box-shadow: 0 0 0 3px rgba(255,107,53,0.1);
        }
        
        /* Categories */
        .categories {
            padding: 8px 20px;
            overflow-x: auto;
            white-space: nowrap;
            scrollbar-width: none;
        }
        
        .categories::-webkit-scrollbar {
            display: none;
        }
        
        .category-btn {
            display: inline-block;
            padding: 10px 24px;
            margin-right: 10px;
            background: var(--card);
            border: 2px solid var(--border);
            border-radius: 50px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .category-btn.active {
            background: var(--primary);
            color: white;
            border-color: var(--primary);
            box-shadow: 0 4px 12px rgba(255,107,53,0.3);
        }
        
        /* Filter bar */
        .filter-bar {
            padding: 8px 20px;
            display: flex;
            gap: 10px;
            overflow-x: auto;
            white-space: nowrap;
        }
        
        .filter-chip {
            padding: 8px 16px;
            background: var(--card);
            border: 1px solid var(--border);
            border-radius: 20px;
            font-size: 13px;
            font-weight: 500;
            cursor: pointer;
        }
        
        .filter-chip.active {
            background: var(--primary);
            color: white;
            border-color: var(--primary);
        }
        
        /* Products Grid */
        .products {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 16px;
            padding: 16px 20px;
        }
        
        .product-card {
            background: var(--card);
            border-radius: var(--radius);
            overflow: hidden;
            box-shadow: var(--shadow);
            transition: transform 0.2s;
            cursor: pointer;
        }
        
        .product-card:active {
            transform: scale(0.98);
        }
        
        .product-image {
            width: 100%;
            aspect-ratio: 1;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 48px;
            position: relative;
        }
        
        .favorite-icon {
            position: absolute;
            top: 8px;
            right: 8px;
            background: rgba(255,255,255,0.9);
            border-radius: 50%;
            width: 34px;
            height: 34px;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 18px;
            cursor: pointer;
            z-index: 2;
            transition: transform 0.2s;
        }
        
        .favorite-icon:active {
            transform: scale(0.9);
        }
        
        .rating-badge {
            position: absolute;
            bottom: 8px;
            left: 8px;
            background: rgba(0,0,0,0.7);
            color: white;
            padding: 4px 8px;
            border-radius: 20px;
            font-size: 11px;
            display: flex;
            align-items: center;
            gap: 4px;
        }
        
        .product-info {
            padding: 12px;
        }
        
        .product-name {
            font-size: 14px;
            font-weight: 700;
            margin-bottom: 4px;
            line-height: 1.3;
            display: -webkit-box;
            -webkit-line-clamp: 2;
            -webkit-box-orient: vertical;
            overflow: hidden;
        }
        
        .product-price {
            font-size: 16px;
            font-weight: 800;
            color: var(--primary);
            margin-bottom: 8px;
        }
        
        .add-btn {
            width: 100%;
            padding: 10px;
            background: linear-gradient(135deg, var(--primary), var(--primary-light));
            color: white;
            border: none;
            border-radius: var(--radius-sm);
            font-weight: 700;
            font-size: 13px;
            cursor: pointer;
            transition: opacity 0.2s;
        }
        
        .add-btn:active {
            opacity: 0.8;
        }
        
        .qty-control {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .qty-btn {
            flex: 1;
            padding: 8px;
            background: var(--primary);
            color: white;
            border: none;
            border-radius: var(--radius-sm);
            font-size: 16px;
            font-weight: 700;
            cursor: pointer;
        }
        
        .qty-num {
            font-size: 14px;
            font-weight: 700;
            min-width: 35px;
            text-align: center;
        }
        
        /* Bottom Navigation */
        .bottom-nav {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background: var(--card);
            display: flex;
            justify-content: space-around;
            padding: 10px 20px;
            box-shadow: 0 -2px 10px rgba(0,0,0,0.05);
            z-index: 100;
        }
        
        .nav-item {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 4px;
            background: none;
            border: none;
            font-size: 22px;
            color: var(--text-light);
            cursor: pointer;
            padding: 6px 12px;
            border-radius: 20px;
            transition: all 0.2s;
        }
        
        .nav-item.active {
            color: var(--primary);
        }
        
        .nav-item span {
            font-size: 11px;
            font-weight: 500;
        }
        
        /* Modal */
        .modal-overlay {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0,0,0,0.6);
            z-index: 1000;
            animation: fadeIn 0.3s;
        }
        
        .modal-overlay.show {
            display: flex;
            align-items: flex-end;
        }
        
        .modal-content {
            background: var(--card);
            width: 100%;
            max-height: 85vh;
            border-radius: 24px 24px 0 0;
            overflow: hidden;
            animation: slideUp 0.3s ease-out;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; }
            to { opacity: 1; }
        }
        
        @keyframes slideUp {
            from { transform: translateY(100%); }
            to { transform: translateY(0); }
        }
        
        .modal-header {
            padding: 20px;
            border-bottom: 1px solid var(--border);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .modal-header h3 {
            font-size: 20px;
            font-weight: 800;
        }
        
        .close-modal {
            background: var(--bg);
            border: none;
            width: 36px;
            height: 36px;
            border-radius: 50%;
            font-size: 24px;
            cursor: pointer;
        }
        
        .cart-items, .favorites-items, .profile-items, .orders-items {
            max-height: 50vh;
            overflow-y: auto;
            padding: 16px;
        }
        
        .cart-item, .favorite-item, .order-item {
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 12px;
            background: var(--bg);
            border-radius: var(--radius-sm);
            margin-bottom: 10px;
        }
        
        .cart-item-info, .favorite-item-info, .order-item-info {
            flex: 1;
        }
        
        .cart-item-name, .favorite-item-name, .order-item-name {
            font-weight: 700;
            font-size: 14px;
            margin-bottom: 4px;
        }
        
        .cart-item-price, .favorite-item-price {
            font-size: 13px;
            color: var(--primary);
            font-weight: 600;
        }
        
        .cart-item-remove {
            background: none;
            border: none;
            font-size: 20px;
            cursor: pointer;
            color: var(--danger);
            padding: 8px;
        }
        
        .cart-footer {
            padding: 20px;
            border-top: 1px solid var(--border);
        }
        
        .cart-total {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
            font-size: 18px;
        }
        
        .cart-total strong {
            font-size: 24px;
            color: var(--primary);
        }
        
        /* Order Form */
        .order-form {
            padding: 20px;
            display: none;
        }
        
        .order-form.show {
            display: block;
        }
        
        .form-group {
            margin-bottom: 16px;
        }
        
        .form-label {
            display: block;
            font-weight: 600;
            margin-bottom: 8px;
            color: var(--text-light);
        }
        
        .form-input, .form-textarea {
            width: 100%;
            padding: 14px;
            border: 2px solid var(--border);
            border-radius: var(--radius-sm);
            font-size: 15px;
            outline: none;
            background: var(--card);
        }
        
        .form-input:focus, .form-textarea:focus {
            border-color: var(--primary);
        }
        
        .saved-addresses {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin-top: 8px;
        }
        
        .saved-address {
            background: var(--bg);
            padding: 8px 12px;
            border-radius: 20px;
            font-size: 12px;
            cursor: pointer;
            border: 1px solid var(--border);
            transition: all 0.2s;
        }
        
        .saved-address:active {
            background: var(--primary);
            color: white;
        }
        
        .checkout-btn {
            width: 100%;
            padding: 16px;
            background: linear-gradient(135deg, var(--primary), var(--primary-light));
            color: white;
            border: none;
            border-radius: var(--radius-sm);
            font-size: 16px;
            font-weight: 700;
            cursor: pointer;
            margin-top: 16px;
        }
        
        /* Promo Section */
        .promo-input {
            display: flex;
            gap: 10px;
            margin-top: 8px;
        }
        
        .promo-input input {
            flex: 1;
            padding: 12px;
            border: 2px solid var(--border);
            border-radius: var(--radius-sm);
            outline: none;
        }
        
        .promo-input input:focus {
            border-color: var(--primary);
        }
        
        .promo-input button {
            padding: 12px 20px;
            background: var(--secondary);
            color: white;
            border: none;
            border-radius: var(--radius-sm);
            cursor: pointer;
        }
        
        /* Success Modal */
        .success-modal {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background: rgba(0,0,0,0.8);
            z-index: 1100;
            align-items: center;
            justify-content: center;
        }
        
        .success-modal.show {
            display: flex;
        }
        
        .success-card {
            background: var(--card);
            padding: 40px 30px;
            border-radius: 24px;
            text-align: center;
            max-width: 300px;
            animation: popIn 0.4s;
        }
        
        @keyframes popIn {
            from { transform: scale(0.5); opacity: 0; }
            to { transform: scale(1); opacity: 1; }
        }
        
        .success-icon {
            font-size: 64px;
            margin-bottom: 16px;
        }
        
        .success-title {
            font-size: 24px;
            font-weight: 800;
            margin-bottom: 8px;
            color: var(--primary);
        }
        
        /* Empty State */
        .empty-state {
            text-align: center;
            padding: 60px 20px;
            color: var(--text-light);
        }
        
        .empty-icon {
            font-size: 64px;
            margin-bottom: 16px;
        }
        
        /* Loading */
        .loading {
            text-align: center;
            padding: 60px 20px;
        }
        
        .spinner {
            width: 50px;
            height: 50px;
            border: 4px solid var(--border);
            border-top-color: var(--primary);
            border-radius: 50%;
            animation: spin 0.8s linear infinite;
            margin: 0 auto 16px;
        }
        
        @keyframes spin {
            to { transform: rotate(360deg); }
        }
        
        /* Toast */
        .toast {
            position: fixed;
            bottom: 80px;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(0,0,0,0.85);
            color: white;
            padding: 12px 24px;
            border-radius: 50px;
            font-size: 14px;
            z-index: 1200;
            animation: fadeInUp 0.3s;
            white-space: nowrap;
        }
        
        @keyframes fadeInUp {
            from {
                opacity: 0;
                transform: translateX(-50%) translateY(20px);
            }
            to {
                opacity: 1;
                transform: translateX(-50%) translateY(0);
            }
        }
        
        /* Profile Section */
        .profile-header {
            text-align: center;
            padding: 24px;
            background: linear-gradient(135deg, var(--primary), var(--primary-light));
            color: white;
        }
        
        .profile-avatar {
            width: 80px;
            height: 80px;
            background: white;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 40px;
            margin: 0 auto 12px;
            color: var(--primary);
        }
        
        .profile-name {
            font-size: 20px;
            font-weight: 800;
        }
        
        .profile-phone {
            font-size: 14px;
            opacity: 0.9;
            margin-top: 4px;
        }
        
        .profile-stats {
            display: flex;
            justify-content: space-around;
            padding: 20px;
            background: var(--card);
            margin: 16px;
            border-radius: var(--radius);
            box-shadow: var(--shadow);
        }
        
        .stat-item {
            text-align: center;
        }
        
        .stat-value {
            font-size: 24px;
            font-weight: 800;
            color: var(--primary);
        }
        
        .stat-label {
            font-size: 12px;
            color: var(--text-light);
            margin-top: 4px;
        }
        
        /* Order item */
        .order-item {
            display: block;
        }
        
        .order-status {
            display: inline-block;
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            margin-top: 8px;
        }
        
        /* Scrollbar */
        ::-webkit-scrollbar {
            width: 4px;
            height: 4px;
        }
        
        ::-webkit-scrollbar-track {
            background: var(--border);
        }
        
        ::-webkit-scrollbar-thumb {
            background: var(--primary);
            border-radius: 4px;
        }
    </style>
</head>
<body>

<div class="header">
    <div class="logo">🛍️ DO'KON</div>
    <div class="header-icons">
        <button class="icon-btn" onclick="openFavorites()">❤️</button>
        <button class="icon-btn" onclick="openCart()">
            🛒
            <span class="cart-count" id="cartCount">0</span>
        </button>
    </div>
</div>

<div class="search-box">
    <input type="text" class="search-input" placeholder="🔍 Qidirish..." id="searchInput" oninput="filterProducts()">
</div>

<div class="categories" id="categories"></div>

<div class="filter-bar" id="filterBar">
    <button class="filter-chip active" data-filter="all" onclick="setSort('all')">🌟 Barchasi</button>
    <button class="filter-chip" data-filter="popular" onclick="setSort('popular')">🔥 Eng ko'p</button>
    <button class="filter-chip" data-filter="price_asc" onclick="setSort('price_asc')">💰 Narx o'sish</button>
    <button class="filter-chip" data-filter="price_desc" onclick="setSort('price_desc')">💰 Narx kamayish</button>
    <button class="filter-chip" data-filter="rating" onclick="setSort('rating')">⭐ Reyting</button>
</div>

<div class="products" id="products">
    <div class="loading">
        <div class="spinner"></div>
        <div>Mahsulotlar yuklanmoqda...</div>
    </div>
</div>

<div class="bottom-nav">
    <button class="nav-item active" data-nav="shop" onclick="showSection('shop')">
        🛍️
        <span>Do'kon</span>
    </button>
    <button class="nav-item" data-nav="orders" onclick="loadOrders()">
        📦
        <span>Zakazlar</span>
    </button>
    <button class="nav-item" data-nav="favorites" onclick="openFavorites()">
        ❤️
        <span>Sevimlilar</span>
    </button>
    <button class="nav-item" data-nav="profile" onclick="loadProfile()">
        👤
        <span>Profil</span>
    </button>
</div>

<!-- Cart Modal -->
<div class="modal-overlay" id="cartModal">
    <div class="modal-content">
        <div class="modal-header">
            <h3>🛒 Savatcha</h3>
            <button class="close-modal" onclick="closeCart()">&times;</button>
        </div>
        
        <div class="cart-items" id="cartItems"></div>
        
        <div class="order-form" id="orderForm">
            <div class="form-group">
                <label class="form-label">📍 Yetkazib berish manzili *</label>
                <input type="text" class="form-input" id="addressInput" placeholder="Manzilingizni kiriting...">
                <div class="saved-addresses" id="savedAddresses"></div>
            </div>
            <div class="form-group">
                <label class="form-label">🎁 Promo kod</label>
                <div class="promo-input">
                    <input type="text" id="promoInput" placeholder="Promo kodni kiriting">
                    <button onclick="applyPromo()">Qo'llash</button>
                </div>
                <div id="promoInfo" style="font-size: 12px; margin-top: 8px;"></div>
            </div>
            <div class="form-group">
                <label class="form-label">💬 Izoh (ixtiyoriy)</label>
                <textarea class="form-textarea" id="noteInput" rows="2" placeholder="Maxsus talablar..."></textarea>
            </div>
            <button class="checkout-btn" onclick="placeOrder()">✅ Zakaz berish</button>
        </div>
        
        <div class="cart-footer" id="cartFooter">
            <div class="cart-total">
                <span>Jami:</span>
                <strong id="cartTotal">0 so'm</strong>
            </div>
            <div id="deliveryInfo" style="font-size: 12px; color: #718096; margin-bottom: 16px;"></div>
            <button class="checkout-btn" onclick="showOrderForm()">📝 Rasmiylashtirish</button>
        </div>
    </div>
</div>

<!-- Favorites Modal -->
<div class="modal-overlay" id="favoritesModal">
    <div class="modal-content">
        <div class="modal-header">
            <h3>❤️ Sevimlilar</h3>
            <button class="close-modal" onclick="closeFavorites()">&times;</button>
        </div>
        <div class="favorites-items" id="favoritesItems"></div>
    </div>
</div>

<!-- Orders Modal -->
<div class="modal-overlay" id="ordersModal">
    <div class="modal-content">
        <div class="modal-header">
            <h3>📦 Mening zakazlarim</h3>
            <button class="close-modal" onclick="closeOrders()">&times;</button>
        </div>
        <div class="orders-items" id="ordersItems"></div>
    </div>
</div>

<!-- Profile Modal -->
<div class="modal-overlay" id="profileModal">
    <div class="modal-content">
        <div class="modal-header">
            <h3>👤 Profil</h3>
            <button class="close-modal" onclick="closeProfile()">&times;</button>
        </div>
        <div class="profile-items" id="profileItems"></div>
    </div>
</div>

<!-- Success Modal -->
<div class="success-modal" id="successModal">
    <div class="success-card">
        <div class="success-icon">🎉</div>
        <div class="success-title">Rahmat!</div>
        <div class="success-text">Zakazingiz qabul qilindi!<br>Tez orada bog'lanamiz.</div>
    </div>
</div>

<script>
const tg = window.Telegram.WebApp;
tg.ready();
tg.expand();
tg.enableClosingConfirmation();

let products = [];
let cart = {};
let favorites = [];
let currentCategory = 'all';
let currentSort = 'all';
let promoDiscount = 0;
let promoCode = '';

// Load products
async function loadProducts() {
    try {
        const res = await fetch('/api/products?' + Date.now());
        products = await res.json();
        renderCategories();
        renderProducts();
    } catch(e) {
        console.error('Error loading products:', e);
        document.getElementById('products').innerHTML = '<div class="empty-state"><div class="empty-icon">⚠️</div><div>Xatolik yuz berdi!</div></div>';
    }
}

// Render categories
function renderCategories() {
    const categories = ['all', ...new Set(products.map(p => p.category))];
    const container = document.getElementById('categories');
    container.innerHTML = categories.map(cat => `
        <button class="category-btn ${cat === currentCategory ? 'active' : ''}" onclick="filterByCategory('${cat}')">
            ${cat === 'all' ? '🌟 Barchasi' : cat}
        </button>
    `).join('');
}

// Filter by category
function filterByCategory(category) {
    currentCategory = category;
    renderCategories();
    filterProducts();
    if (tg.HapticFeedback) tg.HapticFeedback.impactOccurred('light');
}

// Set sort
function setSort(sort) {
    currentSort = sort;
    document.querySelectorAll('.filter-chip').forEach(chip => {
        chip.classList.remove('active');
        if (chip.dataset.filter === sort) chip.classList.add('active');
    });
    filterProducts();
    if (tg.HapticFeedback) tg.HapticFeedback.impactOccurred('light');
}

// Filter and sort products
function filterProducts() {
    const search = document.getElementById('searchInput').value.toLowerCase();
    let filtered = [...products];
    
    if (currentCategory !== 'all') {
        filtered = filtered.filter(p => p.category === currentCategory);
    }
    
    if (search.length >= 2) {
        filtered = filtered.filter(p => 
            p.name.toLowerCase().includes(search) ||
            (p.description && p.description.toLowerCase().includes(search))
        );
    }
    
    // Sort
    if (currentSort === 'price_asc') {
        filtered.sort((a, b) => a.price - b.price);
    } else if (currentSort === 'price_desc') {
        filtered.sort((a, b) => b.price - a.price);
    } else if (currentSort === 'rating') {
        filtered.sort((a, b) => (b.rating || 0) - (a.rating || 0));
    } else if (currentSort === 'popular') {
        filtered.sort((a, b) => (b.sold || 0) - (a.sold || 0));
    }
    
    renderProducts(filtered);
}

// Render products
function renderProducts(productsList) {
    const container = document.getElementById('products');
    
    if (!productsList || productsList.length === 0) {
        container.innerHTML = `
            <div class="empty-state" style="grid-column: 1/-1;">
                <div class="empty-icon">🔍</div>
                <div style="font-weight: 600;">Mahsulot topilmadi</div>
            </div>
        `;
        return;
    }
    
    container.innerHTML = productsList.map(product => {
        const qty = cart[product.id] || 0;
        const isFavorite = favorites.includes(product.id);
        
        return `
            <div class="product-card">
                <div class="product-image">
                    <div class="favorite-icon" onclick="toggleFavorite(${product.id}, event)">
                        ${isFavorite ? '❤️' : '🤍'}
                    </div>
                    <div class="rating-badge">⭐ ${product.rating || 0}</div>
                    ${getCategoryIcon(product.category)}
                </div>
                <div class="product-info">
                    <div class="product-name">${escapeHtml(product.name)}</div>
                    <div class="product-price">${formatPrice(product.price)} so'm</div>
                    ${qty === 0 ? 
                        `<button class="add-btn" onclick="addToCart(${product.id})">➕ Savatga</button>` :
                        `<div class="qty-control">
                            <button class="qty-btn" onclick="updateQuantity(${product.id}, -1)">-</button>
                            <span class="qty-num">${qty}</span>
                            <button class="qty-btn" onclick="updateQuantity(${product.id}, 1)">+</button>
                        </div>`
                    }
                </div>
            </div>
        `;
    }).join('');
}

// Get category icon
function getCategoryIcon(category) {
    const icons = {
        '👗 Kiyim': '👗', '👟 Poyabzal': '👟', '💄 Kosmetika': '💄',
        '📱 Elektronika': '📱', '🏠 Uy jihozlari': '🏠', '🍕 Oziq-ovqat': '🍕'
    };
    return `<div style="font-size: 48px;">${icons[category] || '🛍️'}</div>`;
}

// Toggle favorite
function toggleFavorite(productId, event) {
    event.stopPropagation();
    
    if (favorites.includes(productId)) {
        favorites = favorites.filter(id => id !== productId);
        showToast('❤️ Sevimlilardan olib tashlandi');
    } else {
        favorites.push(productId);
        showToast('❤️ Sevimlilarga qo\'shildi');
    }
    
    localStorage.setItem('favorites', JSON.stringify(favorites));
    renderProducts(filterProducts());
    if (tg.HapticFeedback) tg.HapticFeedback.impactOccurred('light');
}

// Add to cart
function addToCart(productId) {
    cart[productId] = (cart[productId] || 0) + 1;
    updateCartUI();
    filterProducts();
    showToast('✅ Savatga qo\'shildi');
    if (tg.HapticFeedback) tg.HapticFeedback.impactOccurred('light');
}

// Update quantity
function updateQuantity(productId, delta) {
    const newQty = (cart[productId] || 0) + delta;
    if (newQty <= 0) {
        delete cart[productId];
    } else {
        cart[productId] = newQty;
    }
    updateCartUI();
    filterProducts();
    if (tg.HapticFeedback) tg.HapticFeedback.impactOccurred('light');
}

// Update cart UI
function updateCartUI() {
    const total = Object.values(cart).reduce((a, b) => a + b, 0);
    document.getElementById('cartCount').textContent = total;
    
    let subtotal = 0;
    const cartItemsHtml = Object.entries(cart).map(([id, qty]) => {
        const product = products.find(p => p.id == id);
        if (!product) return '';
        const itemTotal = product.price * qty;
        subtotal += itemTotal;
        return `
            <div class="cart-item">
                <div class="cart-item-info">
                    <div class="cart-item-name">${escapeHtml(product.name)}</div>
                    <div class="cart-item-price">${qty} x ${formatPrice(product.price)} = ${formatPrice(itemTotal)} so'm</div>
                </div>
                <button class="cart-item-remove" onclick="removeFromCart(${id})">🗑️</button>
            </div>
        `;
    }).join('');
    
    document.getElementById('cartItems').innerHTML = cartItemsHtml || '<div class="empty-state">Savat bo\'sh</div>';
    
    // Calculate totals
    let discount = 0;
    if (promoCode) {
        if (promoCode === 'WELCOME10') discount = subtotal * 0.1;
        else if (promoCode === 'WELCOME20') discount = subtotal * 0.2;
    }
    
    let deliveryFee = subtotal - discount >= 100000 ? 0 : 15000;
    const finalTotal = subtotal - discount + deliveryFee;
    
    document.getElementById('cartTotal').innerHTML = formatPrice(finalTotal) + ' so\'m';
    
    let deliveryInfo = '';
    if (subtotal - discount >= 100000) {
        deliveryInfo = '🚚 Yetkazib berish bepul!';
    } else {
        deliveryInfo = `🚚 Yetkazib berish: ${formatPrice(15000)} so'm (${formatPrice(100000 - (subtotal - discount))} so'm qo'shing, bepul bo'lsin)`;
    }
    document.getElementById('deliveryInfo').innerHTML = deliveryInfo;
    
    if (discount > 0) {
        document.getElementById('promoInfo').innerHTML = `🎁 Promo chegirma: -${formatPrice(discount)} so'm`;
    } else {
        document.getElementById('promoInfo').innerHTML = '';
    }
}

// Remove from cart
function removeFromCart(productId) {
    delete cart[productId];
    updateCartUI();
    filterProducts();
    if (Object.keys(cart).length === 0) {
        closeCart();
    }
    if (tg.HapticFeedback) tg.HapticFeedback.impactOccurred('light');
}

// Apply promo
function applyPromo() {
    const code = document.getElementById('promoInput').value.toUpperCase().trim();
    if (code === 'WELCOME10') {
        promoCode = code;
        promoDiscount = 10;
        showToast('🎉 10% chegirma qo\'llandi!');
        updateCartUI();
    } else if (code === 'WELCOME20') {
        promoCode = code;
        promoDiscount = 20;
        showToast('🎉 20% chegirma qo\'llandi!');
        updateCartUI();
    } else {
        showToast('❌ Noto\'g\'ri promo kod');
    }
}

// Open cart
function openCart() {
    if (Object.keys(cart).length === 0) {
        showToast('🛒 Savat bo\'sh!');
        return;
    }
    
    document.getElementById('orderForm').classList.remove('show');
    document.getElementById('cartFooter').style.display = '';
    document.getElementById('cartModal').classList.add('show');
    
    // Load saved addresses
    const savedContainer = document.getElementById('savedAddresses');
    const savedAddresses = JSON.parse(localStorage.getItem('addresses') || '[]');
    if (savedAddresses.length > 0) {
        savedContainer.innerHTML = savedAddresses.slice(-5).map(addr => 
            `<div class="saved-address" onclick="document.getElementById('addressInput').value='${addr.replace(/'/g, "\\'")}'">📍 ${escapeHtml(addr)}</div>`
        ).join('');
    } else {
        savedContainer.innerHTML = '';
    }
}

// Close cart
function closeCart() {
    document.getElementById('cartModal').classList.remove('show');
    document.getElementById('orderForm').classList.remove('show');
    document.getElementById('cartFooter').style.display = '';
}

// Show order form
function showOrderForm() {
    document.getElementById('cartItems').style.display = 'none';
    document.getElementById('cartFooter').style.display = 'none';
    document.getElementById('orderForm').classList.add('show');
}

// Open favorites
function openFavorites() {
    renderFavoritesList();
    document.getElementById('favoritesModal').classList.add('show');
}

function closeFavorites() {
    document.getElementById('favoritesModal').classList.remove('show');
}

function renderFavoritesList() {
    const favProducts = products.filter(p => favorites.includes(p.id));
    const container = document.getElementById('favoritesItems');
    
    if (favProducts.length === 0) {
        container.innerHTML = '<div class="empty-state">❤️ Sevimli mahsulotlar yo\'q</div>';
        return;
    }
    
    container.innerHTML = favProducts.map(product => `
        <div class="cart-item">
            <div class="cart-item-info">
                <div class="cart-item-name">${escapeHtml(product.name)}</div>
                <div class="cart-item-price">${formatPrice(product.price)} so'm</div>
            </div>
            <button class="cart-item-remove" onclick="addToCartFromFav(${product.id})">🛒</button>
            <button class="cart-item-remove" onclick="removeFromFav(${product.id})">🗑️</button>
        </div>
    `).join('');
}

function addToCartFromFav(productId) {
    addToCart(productId);
    closeFavorites();
}

function removeFromFav(productId) {
    favorites = favorites.filter(id => id !== productId);
    localStorage.setItem('favorites', JSON.stringify(favorites));
    renderFavoritesList();
    filterProducts();
    showToast('❤️ Sevimlilardan olib tashlandi');
}

// Load orders
async function loadOrders() {
    const orders = JSON.parse(localStorage.getItem('orders') || '[]');
    const container = document.getElementById('ordersItems');
    
    if (orders.length === 0) {
        container.innerHTML = '<div class="empty-state">📭 Zakazlaringiz yo\'q</div>';
    } else {
        container.innerHTML = orders.slice(-10).reverse().map(order => `
            <div class="order-item" style="padding: 12px; background: #f5f5f5; border-radius: 12px; margin-bottom: 10px;">
                <div><strong>🆔 Zakaz #${order.id}</strong></div>
                <div>💰 ${formatPrice(order.total)} so'm</div>
                <div>📅 ${order.date}</div>
                <div class="order-status" style="background: ${getStatusColor(order.status)}20; color: ${getStatusColor(order.status)};">
                    ${getStatusEmoji(order.status)} ${getStatusText(order.status)}
                </div>
            </div>
        `).join('');
    }
    
    document.getElementById('ordersModal').classList.add('show');
}

function getStatusColor(status) {
    const colors = {
        'new': '#FF6B35',
        'accepted': '#48BB78',
        'preparing': '#F6AD55',
        'courier': '#4299E1',
        'delivering': '#9F7AEA',
        'delivered': '#48BB78',
        'cancelled': '#F56565'
    };
    return colors[status] || '#718096';
}

function getStatusEmoji(status) {
    const emojis = {
        'new': '🆕', 'accepted': '✅', 'preparing': '🔧',
        'courier': '🚚', 'delivering': '🚛', 'delivered': '📦', 'cancelled': '❌'
    };
    return emojis[status] || '📋';
}

function getStatusText(status) {
    const texts = {
        'new': 'Yangi', 'accepted': 'Qabul qilindi', 'preparing': 'Tayyorlanmoqda',
        'courier': 'Kuryerga berildi', 'delivering': 'Yetkazilmoqda', 'delivered': 'Yetkazildi', 'cancelled': 'Bekor qilindi'
    };
    return texts[status] || status;
}

function closeOrders() {
    document.getElementById('ordersModal').classList.remove('show');
}

// Load profile
function loadProfile() {
    const user = tg.initDataUnsafe.user;
    const container = document.getElementById('profileItems');
    
    container.innerHTML = `
        <div class="profile-header">
            <div class="profile-avatar">👤</div>
            <div class="profile-name">${escapeHtml(user?.first_name || '')} ${escapeHtml(user?.last_name || '')}</div>
            <div class="profile-phone">${user?.username ? '@' + user.username : 'Telefon kiritilmagan'}</div>
        </div>
        <div class="profile-stats">
            <div class="stat-item">
                <div class="stat-value">${Object.keys(cart).length}</div>
                <div class="stat-label">Savatda</div>
            </div>
            <div class="stat-item">
                <div class="stat-value">${favorites.length}</div>
                <div class="stat-label">Sevimlilar</div>
            </div>
            <div class="stat-item">
                <div class="stat-value">${JSON.parse(localStorage.getItem('orders') || '[]').length}</div>
                <div class="stat-label">Zakazlar</div>
            </div>
        </div>
        <div style="padding: 16px;">
            <button class="checkout-btn" onclick="shareContact()" style="background: #2D3748;">📞 Telefon raqam yuborish</button>
        </div>
    `;
    
    document.getElementById('profileModal').classList.add('show');
}

function shareContact() {
    tg.sendData(JSON.stringify({ action: 'share_contact' }));
    showToast('📞 Admin bilan bog\'lanamiz');
}

function closeProfile() {
    document.getElementById('profileModal').classList.remove('show');
}

function showSection(section) {
    document.querySelectorAll('.nav-item').forEach(item => {
        item.classList.remove('active');
        if (item.dataset.nav === section) item.classList.add('active');
    });
}

// Place order
function placeOrder() {
    const address = document.getElementById('addressInput').value.trim();
    if (!address) {
        showToast('📍 Manzilni kiriting!');
        return;
    }
    
    const items = Object.entries(cart).map(([id, qty]) => {
        const product = products.find(p => p.id == id);
        return { id: product.id, name: product.name, price: product.price, quantity: qty };
    });
    
    let subtotal = items.reduce((sum, i) => sum + (i.price * i.quantity), 0);
    let discount = 0;
    if (promoCode === 'WELCOME10') discount = subtotal * 0.1;
    else if (promoCode === 'WELCOME20') discount = subtotal * 0.2;
    let deliveryFee = subtotal - discount >= 100000 ? 0 : 15000;
    let total = subtotal - discount + deliveryFee;
    
    const order = {
        items: items,
        total: total,
        address: address,
        note: document.getElementById('noteInput').value,
        promo_code: promoCode,
        date: new Date().toLocaleString()
    };
    
    // Save to localStorage
    const orders = JSON.parse(localStorage.getItem('orders') || '[]');
    order.id = orders.length + 1000;
    orders.push(order);
    localStorage.setItem('orders', JSON.stringify(orders));
    
    // Save address
    const addresses = JSON.parse(localStorage.getItem('addresses') || '[]');
    if (!addresses.includes(address)) {
        addresses.push(address);
        localStorage.setItem('addresses', JSON.stringify(addresses.slice(-5)));
    }
    
    // Send to bot
    tg.sendData(JSON.stringify(order));
    
    cart = {};
    promoCode = '';
    promoDiscount = 0;
    updateCartUI();
    closeCart();
    
    document.getElementById('successModal').classList.add('show');
    setTimeout(() => {
        document.getElementById('successModal').classList.remove('show');
    }, 3000);
    
    if (tg.HapticFeedback) tg.HapticFeedback.notificationOccurred('success');
}

// Show toast
function showToast(message) {
    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 2000);
}

// Format price
function formatPrice(price) {
    return price.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
}

// Escape HTML
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Close modals on outside click
document.getElementById('cartModal').addEventListener('click', function(e) {
    if (e.target === this) closeCart();
});
document.getElementById('favoritesModal').addEventListener('click', function(e) {
    if (e.target === this) closeFavorites();
});
document.getElementById('ordersModal').addEventListener('click', function(e) {
    if (e.target === this) closeOrders();
});
document.getElementById('profileModal').addEventListener('click', function(e) {
    if (e.target === this) closeProfile();
});

// Load saved data
const savedFavs = localStorage.getItem('favorites');
if (savedFavs) favorites = JSON.parse(savedFavs);

// Initialize
loadProducts();
</script>
</body>
</html>
"""

@app.get("/")
async def home():
    """Asosiy sahifa"""
    return {
        "status": "online",
        "bot_name": "Telegram Shop Bot",
        "version": "4.0.0",
        "admin_ids": ADMIN_IDS
    }

@app.get("/shop")
async def shop_page():
    """Web App sahifasi"""
    return HTMLResponse(content=HTML_TEMPLATE)

@app.get("/api/products")
async def get_products_api():
    """Mahsulotlar API"""
    return JSONResponse(db.get_products())

@app.post("/webhook")
async def webhook(request: Request):
    """Telegram webhook"""
    try:
        data = await request.json()
        update = types.Update.de_json(data)
        bot.process_new_updates([update])
        return {"ok": True}
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return {"ok": False}

@app.on_event("startup")
async def startup():
    """Botni ishga tushirish"""
    # Webhook o'rnatish
    webhook_url = f"{RENDER_EXTERNAL_URL}/webhook"
    bot.remove_webhook()
    bot.set_webhook(url=webhook_url)
    logger.info(f"✅ Webhook o'rnatildi: {webhook_url}")
    
    # Default mahsulotlar
    if not db.get_products():
        default_products = [
            {"name": "Classic T-Shirt", "price": 89000, "category": "👗 Kiyim", "description": "Sifatli paxta T-shirt", "stock": 100},
            {"name": "Sport Krossovkalar", "price": 299000, "category": "👟 Poyabzal", "description": "Qulay sport poyabzali", "stock": 50},
            {"name": "Smartfon Pro", "price": 2499000, "category": "📱 Elektronika", "description": "6.5' ekran, 128GB", "stock": 20},
            {"name": "LED Lampochka", "price": 25000, "category": "🏠 Uy jihozlari", "description": "Energiya tejamkor", "stock": 500},
            {"name": "Tandir Non", "price": 5000, "category": "🍕 Oziq-ovqat", "description": "Tandirda pishirilgan", "stock": 200},
            {"name": "Jersi Short", "price": 59000, "category": "👗 Kiyim", "description": "Yozgi shorti", "stock": 150},
            {"name": "Power Bank", "price": 129000, "category": "📱 Elektronika", "description": "10000 mAh", "stock": 30},
        ]
        for p in default_products:
            db.add_product(p)
        logger.info("✅ Default mahsulotlar qo'shildi")
    
    # Default promo kodlar
    if not db.get_promos():
        default_promos = [
            {"code": "WELCOME10", "discount_type": "percentage", "discount_value": 10, "expires_at": (datetime.now() + timedelta(days=30)).isoformat(), "active": True},
            {"code": "WELCOME20", "discount_type": "percentage", "discount_value": 20, "expires_at": (datetime.now() + timedelta(days=30)).isoformat(), "active": True},
        ]
        for p in default_promos:
            db.add_promo(p)
        logger.info("✅ Default promo kodlar qo'shildi")
    
    logger.info(f"🚀 Bot ishga tushdi! Admin ID: {ADMIN_IDS}")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
