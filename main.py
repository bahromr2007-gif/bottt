import telebot
from telebot import types
import json
import os
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse

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
        types.KeyboardButton("📦 Mening zakazlarim"),
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


@bot.message_handler(func=lambda m: m.text == "📦 Mening zakazlarim")
def my_orders(message):
    user_id = message.from_user.id
    orders = get_orders()
    user_orders = [o for o in orders if o.get("user_id") == user_id]

    if not user_orders:
        bot.send_message(message.chat.id, "📦 Hozircha zakazlaringiz yo'q.")
        return

    text = "📦 Sizning zakazlaringiz:\n\n"
    for o in user_orders[-5:]:
        text += f"📦 Zakaz #{o['id']}\n"
        text += f"📅 {o['date']}\n"
        text += f"💰 {o['total']:,} so'm\n\n"

    bot.send_message(message.chat.id, text)


@bot.message_handler(func=lambda m: m.text == "📞 Aloqa")
def contact_info(message):
    bot.send_message(message.chat.id, "📞 Admin: @admin_username\n📞 Telefon: +998 XX XXX XX XX")


@bot.message_handler(func=lambda m: m.text == "ℹ️ Yordam")
def help_info(message):
    bot.send_message(
        message.chat.id,
        "ℹ️ *Yordam:*\n\n"
        "🛍️ Do'konni ochib mahsulot tanlang\n"
        "📦 Zakazlaringizni 'Mening zakazlarim' bo'limida ko'ring\n"
        "📞 Aloqa bo'limi orqali admin bilan bog'lanishingiz mumkin",
        parse_mode="Markdown"
    )


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

        # Admin uchun xabar
        for admin_id in ADMIN_IDS:
            try:
                items_text = "\n".join([f"  - {item.get('name', '')} x{item.get('quantity', 1)} = {item.get('price', 0):,} so'm" for item in new_order['items']])
                bot.send_message(
                    admin_id,
                    f"🆕 *Yangi zakaz!*\n\n"
                    f"👤 Foydalanuvchi: {new_order['user']}\n"
                    f"🆔 ID: {new_order['user_id']}\n"
                    f"📦 Mahsulotlar:\n{items_text}\n"
                    f"💰 Jami: {new_order['total']:,} so'm\n"
                    f"📅 Vaqt: {new_order['date']}",
                    parse_mode="Markdown"
                )
            except:
                pass

        bot.send_message(
            message.chat.id,
            f"✅ *Zakaz qabul qilindi!*\n\n"
            f"📦 Jami: {new_order['total']:,} so'm\n"
            f"🆔 Zakaz raqami: #{new_order['id']}\n\n"
            f"Tez orada admin siz bilan bog'lanadi!",
            parse_mode="Markdown"
        )
    except Exception as e:
        print("web_app_order error:", e)
        bot.send_message(message.chat.id, "❌ Xatolik yuz berdi. Iltimos qaytadan urinib ko'ring.")


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
            "id": len(products) + 1 if products else 1,
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

        user_states[user_id] = {"state": "idle", "temp": {}}

        bot.send_message(
            message.chat.id,
            f"✅ *Mahsulot qo'shildi!*\n\n"
            f"📌 {new_product['name']}\n"
            f"💰 {new_product['price']:,} so'm\n"
            f"🏷 {new_product['category']}",
            parse_mode="Markdown",
            reply_markup=get_admin_menu()
        )


# FastAPI endpoints
@app.get("/")
def home():
    return {"status": "Bot ishlayapti", "web_app": WEB_APP_URL}


@app.get("/shop")
async def shop():
    html_content = """
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=yes">
        <title>Do'kon</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                background: #f5f5f5;
                padding: 16px;
                padding-bottom: 80px;
            }
            .header {
                background: white;
                padding: 16px;
                border-radius: 12px;
                margin-bottom: 16px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
                position: sticky;
                top: 0;
                z-index: 10;
            }
            .header h1 {
                font-size: 20px;
                margin-bottom: 8px;
            }
            .cart-info {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-top: 8px;
                padding-top: 8px;
                border-top: 1px solid #eee;
            }
            .cart-total {
                font-weight: bold;
                color: #2c3e50;
            }
            .cart-btn {
                background: #2c3e50;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 8px;
                cursor: pointer;
            }
            .products {
                display: grid;
                gap: 16px;
            }
            .product-card {
                background: white;
                border-radius: 12px;
                padding: 16px;
                box-shadow: 0 1px 3px rgba(0,0,0,0.1);
            }
            .product-name {
                font-size: 18px;
                font-weight: 600;
                margin-bottom: 8px;
            }
            .product-desc {
                color: #666;
                font-size: 14px;
                margin-bottom: 8px;
            }
            .product-price {
                font-size: 20px;
                font-weight: bold;
                color: #27ae60;
                margin-bottom: 12px;
            }
            .product-actions {
                display: flex;
                gap: 12px;
                align-items: center;
            }
            .quantity-btn {
                background: #3498db;
                color: white;
                border: none;
                width: 32px;
                height: 32px;
                border-radius: 8px;
                font-size: 18px;
                cursor: pointer;
            }
            .quantity {
                font-size: 16px;
                font-weight: 500;
                min-width: 30px;
                text-align: center;
            }
            .add-btn {
                background: #27ae60;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 8px;
                cursor: pointer;
                font-weight: 500;
                margin-left: auto;
            }
            .checkout-btn {
                position: fixed;
                bottom: 0;
                left: 0;
                right: 0;
                background: #2c3e50;
                color: white;
                border: none;
                padding: 16px;
                font-size: 18px;
                font-weight: bold;
                cursor: pointer;
                transition: background 0.3s;
            }
            .checkout-btn:hover {
                background: #34495e;
            }
            .empty {
                text-align: center;
                padding: 48px;
                color: #999;
            }
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🛍️ Bizning do'kon</h1>
            <div class="cart-info">
                <span>🛒 Savatdagi mahsulotlar: <span id="cart-count">0</span></span>
                <span class="cart-total">💰 <span id="cart-total">0</span> so'm</span>
                <button class="cart-btn" onclick="viewCart()">📋 Savat</button>
            </div>
        </div>
        
        <div class="products" id="products"></div>
        <button class="checkout-btn" onclick="checkout()">✅ Zakaz berish</button>

        <script>
            let products = [];
            let cart = JSON.parse(localStorage.getItem('cart') || '{}');
            
            function loadProducts() {
                fetch('/webapp_products.json')
                    .then(res => res.json())
                    .then(data => {
                        products = data;
                        renderProducts();
                    })
                    .catch(err => console.error('Error loading products:', err));
            }
            
            function renderProducts() {
                const container = document.getElementById('products');
                if (!products.length) {
                    container.innerHTML = '<div class="empty">📭 Hozircha mahsulot yo\'q</div>';
                    return;
                }
                
                container.innerHTML = products.map(product => `
                    <div class="product-card">
                        <div class="product-name">${escapeHtml(product.name)}</div>
                        <div class="product-desc">${escapeHtml(product.description || '')}</div>
                        <div class="product-price">${formatNumber(product.price)} so'm</div>
                        <div class="product-actions">
                            <button class="quantity-btn" onclick="changeQuantity(${product.id}, -1)">-</button>
                            <span class="quantity" id="qty-${product.id}">${cart[product.id] || 0}</span>
                            <button class="quantity-btn" onclick="changeQuantity(${product.id}, 1)">+</button>
                            <button class="add-btn" onclick="addToCart(${product.id})">➕ Qo'shish</button>
                        </div>
                    </div>
                `).join('');
            }
            
            function changeQuantity(productId, delta) {
                const current = cart[productId] || 0;
                const newQty = Math.max(0, current + delta);
                if (newQty === 0) {
                    delete cart[productId];
                } else {
                    cart[productId] = newQty;
                }
                updateCart();
                document.getElementById(`qty-${productId}`).innerText = cart[productId] || 0;
            }
            
            function addToCart(productId) {
                cart[productId] = (cart[productId] || 0) + 1;
                updateCart();
                document.getElementById(`qty-${productId}`).innerText = cart[productId];
            }
            
            function updateCart() {
                localStorage.setItem('cart', JSON.stringify(cart));
                const total = getCartTotal();
                const count = Object.values(cart).reduce((a,b) => a + b, 0);
                document.getElementById('cart-count').innerText = count;
                document.getElementById('cart-total').innerText = formatNumber(total);
            }
            
            function getCartTotal() {
                let total = 0;
                for (const [id, qty] of Object.entries(cart)) {
                    const product = products.find(p => p.id == id);
                    if (product) total += product.price * qty;
                }
                return total;
            }
            
            function viewCart() {
                if (Object.keys(cart).length === 0) {
                    alert('Savat bo\'sh!');
                    return;
                }
                
                let message = '📋 Savatingiz:\\n\\n';
                let total = 0;
                for (const [id, qty] of Object.entries(cart)) {
                    const product = products.find(p => p.id == id);
                    if (product) {
                        const subtotal = product.price * qty;
                        message += `${product.name} x${qty} = ${formatNumber(subtotal)} so'm\\n`;
                        total += subtotal;
                    }
                }
                message += `\\n💰 Jami: ${formatNumber(total)} so'm`;
                alert(message);
            }
            
            function checkout() {
                if (Object.keys(cart).length === 0) {
                    alert('Savat bo\'sh! Iltimos mahsulot qo\'shing.');
                    return;
                }
                
                const items = [];
                for (const [id, qty] of Object.entries(cart)) {
                    const product = products.find(p => p.id == id);
                    if (product) {
                        items.push({
                            id: product.id,
                            name: product.name,
                            price: product.price,
                            quantity: qty
                        });
                    }
                }
                
                const orderData = {
                    items: items,
                    total: getCartTotal()
                };
                
                Telegram.WebApp.sendData(JSON.stringify(orderData));
                localStorage.removeItem('cart');
                cart = {};
                updateCart();
                renderProducts();
                Telegram.WebApp.close();
            }
            
            function formatNumber(num) {
                return num.toString().replace(/\\B(?=(\\d{3})+(?!\\d))/g, ",");
            }
            
            function escapeHtml(str) {
                if (!str) return '';
                return str.replace(/[&<>]/g, function(m) {
                    if (m === '&') return '&amp;';
                    if (m === '<') return '&lt;';
                    if (m === '>') return '&gt;';
                    return m;
                });
            }
            
            Telegram.WebApp.ready();
            Telegram.WebApp.expand();
            loadProducts();
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@app.get("/webapp_products.json")
def get_products_json():
    return JSONResponse(get_products())


@app.post("/bot")
async def webhook(request: Request):
    try:
        data = await request.json()
        update = telebot.types.Update.de_json(data)
        bot.process_new_updates([update])
        return {"ok": True}
    except Exception as e:
        print("Webhook error:", e)
        return {"ok": False, "error": str(e)}


@app.on_event("startup")
async def startup():
    if not os.path.exists(PRODUCTS_FILE):
        sample_products = [
            {
                "id": 1,
                "name": "Misol Mahsulot",
                "description": "Bu test mahsulot",
                "price": 50000,
                "category": "🎁 Boshqa",
                "photo": None,
                "available": True,
                "added": datetime.now().strftime("%Y-%m-%d %H:%M")
            }
        ]
        save_products(sample_products)

    # Webhook o'rnatish
    webhook_url = f"{RENDER_EXTERNAL_URL}/bot"
    try:
        bot.remove_webhook()
        bot.set_webhook(url=webhook_url)
        print(f"✅ Webhook o'rnatildi: {webhook_url}")
    except Exception as e:
        print(f"Webhook o'rnatishda xatolik: {e}")
