import os
import asyncio
import aiohttp
import json
import time
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from dotenv import load_dotenv

# ================= CONFIGURACIÓN ==================
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
KEEPA_API_KEY = os.getenv("KEEPA_API_KEY")
AMAZON_TAG = os.getenv("AMAZON_TAG")
CHANNEL_ID = "@eeuuamazon"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

CACHE_FILE = "sent_products.json"
MAX_PER_HOUR = 5
DISCOUNT_THRESHOLD = 10  # %
CHECK_INTERVAL = 3600  # 1 hora

# ===================================================

if os.path.exists(CACHE_FILE):
    with open(CACHE_FILE, "r") as f:
        sent_products = json.load(f)
else:
    sent_products = {}

async def get_keepa_offers():
    url = f"https://api.keepa.com/query?key={KEEPA_API_KEY}&domain=1&priceDrop=10"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status != 200:
                return []
            data = await response.json()
            return data.get("products", [])

async def send_offer(product):
    asin = product["asin"]
    title = product.get("title", "Producto sin nombre")
    price = product.get("buyBoxPrice", None)
    old_price = product.get("buyBoxShipping", None)
    image_url = f"https://images-na.ssl-images-amazon.com/images/P/{asin}.jpg"

    if not price:
        return

    price = price / 100
    link = f"https://www.amazon.com/dp/{asin}/?tag={AMAZON_TAG}"

    caption = (
        f"📦 <b>{title}</b>
"
        f"💰 <b>OFERTA:</b> ${price:.2f}
"
        f"🔗 <a href='{link}'>Ir a la OFERTA ⚡</a>

"
        f"👁️ Visto en: @eeuuamazon"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⚡ Ir a la OFERTA ⚡", url=link)
    ]])

    await bot.send_photo(CHANNEL_ID, photo=image_url, caption=caption, reply_markup=kb, parse_mode="HTML")

async def clean_old_cache():
    now = time.time()
    for asin, date in list(sent_products.items()):
        if now - date > 7 * 24 * 3600:
            del sent_products[asin]
    with open(CACHE_FILE, "w") as f:
        json.dump(sent_products, f)

async def price_watcher():
    while True:
        print(f"[{datetime.now()}] Buscando nuevas ofertas...")
        offers = await get_keepa_offers()
        sent_this_hour = 0

        for product in offers:
            if sent_this_hour >= MAX_PER_HOUR:
                break

            asin = product["asin"]
            if asin in sent_products:
                continue

            if not product.get("buyBoxPrice") or not product.get("buyBoxShipping"):
                continue

            current_price = product["buyBoxPrice"]
            old_price = product["buyBoxShipping"]
            if old_price <= 0:
                continue

            discount = (1 - current_price / old_price) * 100
            if discount >= DISCOUNT_THRESHOLD:
                await send_offer(product)
                sent_products[asin] = time.time()
                sent_this_hour += 1

        await clean_old_cache()
        await asyncio.sleep(CHECK_INTERVAL)

async def main():
    asyncio.create_task(price_watcher())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
