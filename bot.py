import os
import json
import logging
import requests
import aiohttp
from aiohttp import web
import asyncio
from datetime import time
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN")
WATCHED_FILE = "/data/watched.json"
CHAT_ID = os.environ.get("CHAT_ID")

main_keyboard = ReplyKeyboardMarkup(
    [
        [KeyboardButton("🔍 Пошук ціни"), KeyboardButton("👁 Відстежувати")],
        [KeyboardButton("📋 Мій список"), KeyboardButton("🔥 Акції Сільпо")],
    ],
    resize_keyboard=True
)

def load_watched():
    if os.path.exists(WATCHED_FILE):
        with open(WATCHED_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_watched(items):
    with open(WATCHED_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False)

def search_silpo(query):
    url = "https://api.catalog.ecom.silpo.ua/api/2.0/exec/EcomCatalogGlobal"
    payload = {
        "method": "GetSimpleCatalogItems",
        "data": {
            "customFilter": query,
            "filialId": "2405",
            "skuPerPage": 5,
            "pageNumber": 1
        }
    }
    headers = {"Content-Type": "application/json;charset=UTF-8"}
    response = requests.post(url, json=payload, headers=headers, timeout=10)
    return response.json()

def search_metro(query):
    url = "https://stores-api.zakaz.ua/stores/48215611/products/search/"
    params = {"q": query, "per_page": 5}
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36",
        "x-chain": "metro",
        "x-version": "65",
        "Accept": "application/json",
        "Origin": "https://metro.zakaz.ua",
    }
    response = requests.get(url, params=params, headers=headers, timeout=10)
    return response.json()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(
            "🛒 Відкрити BePrice",
            web_app=WebAppInfo(url="https://irinaunhul.github.io/beprice_bot/")
        )
    ]])
    await update.message.reply_text(
        "👋 Привіт! Я бот для відстеження цін.",
        reply_markup=keyboard
    )

async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Твій chat_id: {update.effective_chat.id}")

async def check_sales(context: ContextTypes.DEFAULT_TYPE):
    watched = load_watched()
    if not watched:
        return
    found = []
    for item in watched:
        try:
            data = search_silpo(item)
            items = data.get("items", [])
            for p in items[:3]:
                if p.get("oldPrice") and p.get("oldPrice") != p.get("price"):
                    found.append(f"🔥 {p['name']} {p.get('unit','')} — {p['price']} грн (було {p['oldPrice']} грн)")
        except Exception as e:
            logger.error(e)
    if found:
        text = "🛒 Акції на твої товари:\n\n" + "\n".join(found)
        await context.bot.send_message(chat_id=CHAT_ID, text=text)

async def show_search_results(send_func, query):
    try:
        data = search_silpo(query)
        items = data.get("items", [])
        if not items:
            await send_func("Нічого не знайдено.")
            return
        result = f"🛒 Сільпо для '{query}':\n\n"
        for item in items[:5]:
            name = item.get("name", "?")
            price = item.get("price", "?")
            old_price = item.get("oldPrice")
            unit = item.get("unit", "")
            line = f"• {name} {unit}\n  💰 {price} грн"
            if old_price and old_price != price:
                line += f" ~~{old_price}~~ 🔥"
            result += line + "\n\n"
        await send_func(result)
    except Exception as e:
        logger.error(e)
        await send_func("Помилка пошуку Сільпо.")

    try:
        metro_data = search_metro(query)
        metro_items = metro_data.get("results", [])
        if metro_items:
            metro_result = f"🏪 Метро для '{query}':\n\n"
            for item in metro_items[:5]:
                name = item.get("title", "?")
                price = round(item.get("price", 0) / 100, 2)
                old_price = item.get("original_price")
                if old_price:
                    old_price = round(old_price / 100, 2)
                unit = item.get("unit", "")
                line = f"• {name} {unit}\n  💰 {price} грн"
                if old_price and old_price != price:
                    line += f" ~~{old_price}~~ 🔥"
                metro_result += line + "\n\n"
            await send_func(metro_result)
    except Exception as e:
        logger.error(f"Метро помилка: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "🔍 Пошук ціни":
        await update.message.reply_text("Напиши назву товару:")
        context.user_data["action"] = "search"

    elif text == "👁 Відстежувати":
        await update.message.reply_text("Напиши назву товару для відстеження:")
        context.user_data["action"] = "watch"

    elif text == "🔥 Акції Сільпо":
        await update.message.reply_text("⏳ Завантажую акції...")
        try:
            url = "https://api.catalog.ecom.silpo.ua/api/2.0/exec/EcomCatalogGlobal"
            payload = {
                "method": "GetSimpleCatalogItems",
                "data": {
                    "filialId": "2405",
                    "skuPerPage": 10,
                    "pageNumber": 1,
                    "sortBy": "popularity",
                    "onlyWithDiscounts": True
                }
            }
            headers = {"Content-Type": "application/json;charset=UTF-8"}
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            data = response.json()
            items = data.get("items", [])
            total = data.get("itemsCount", 0)
            if not items:
                await update.message.reply_text("Акцій не знайдено.", reply_markup=main_keyboard)
                return
            text_out = "🔥 Акції Сільпо (стор. 1):\n\n"
            for item in items:
                name = item.get("name", "?")
                price = item.get("price", "?")
                old_price = item.get("oldPrice")
                unit = item.get("unit", "")
                line = f"• {name} {unit}\n  💰 {price} грн"
                if old_price:
                    line += f" (було {old_price} грн)"
                text_out += line + "\n\n"
            loaded = len(items)
            if loaded < total:
                text_out += f"Показано {loaded} з {total}"
                keyboard = InlineKeyboardMarkup([[
                    InlineKeyboardButton("Показати ще ➡️", callback_data="sales_page_2")
                ]])
                await update.message.reply_text(text_out, reply_markup=keyboard)
            else:
                await update.message.reply_text(text_out, reply_markup=main_keyboard)
        except Exception as e:
            logger.error(e)
            await update.message.reply_text("Помилка завантаження акцій.", reply_markup=main_keyboard)

    elif text == "📋 Мій список":
        watched = load_watched()
        if not watched:
            await update.message.reply_text("Список порожній.", reply_markup=main_keyboard)
        else:
            buttons = [[InlineKeyboardButton(f"🔍 {item}", callback_data=f"search:{item}")] for item in watched]
            buttons.append([InlineKeyboardButton("🗑 Видалити товар", callback_data="delete_menu")])
            await update.message.reply_text(
                "📋 Відстежувані товари:\nНатисни щоб перевірити ціну:",
                reply_markup=InlineKeyboardMarkup(buttons)
            )

    elif context.user_data.get("action") == "search":
        context.user_data["action"] = None
        await update.message.reply_text(f"🔍 Шукаю '{text}'...", reply_markup=main_keyboard)
        await show_search_results(update.message.reply_text, text)

    elif context.user_data.get("action") == "watch":
        context.user_data["action"] = None
        watched = load_watched()
        if text not in watched:
            watched.append(text)
            save_watched(watched)
            await update.message.reply_text(f"✅ '{text}' додано до відстеження!", reply_markup=main_keyboard)
        else:
            await update.message.reply_text(f"'{text}' вже є у списку.", reply_markup=main_keyboard)

    else:
        await update.message.reply_text("Обери дію:", reply_markup=main_keyboard)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("search:"):
        item = data[7:]
        await query.message.reply_text(f"🔍 Шукаю '{item}'...")
        await show_search_results(query.message.reply_text, item)

    elif data == "delete_menu":
        watched = load_watched()
        buttons = [[InlineKeyboardButton(f"❌ {item}", callback_data=f"delete:{item}")] for item in watched]
        buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="back_to_list")])
        await query.message.edit_text(
            "Натисни на товар щоб видалити:",
            reply_markup=InlineKeyboardMarkup(buttons)
        )

    elif data.startswith("delete:"):
        item = data[7:]
        watched = load_watched()
        if item in watched:
            watched.remove(item)
            save_watched(watched)
        if not watched:
            await query.message.edit_text("Список порожній.")
        else:
            buttons = [[InlineKeyboardButton(f"❌ {item}", callback_data=f"delete:{item}")] for item in watched]
            buttons.append([InlineKeyboardButton("◀️ Назад", callback_data="back_to_list")])
            await query.message.edit_text(
                f"✅ '{item}' видалено.\nНатисни на товар щоб видалити:",
                reply_markup=InlineKeyboardMarkup(buttons)
            )

    elif data.startswith("sales_page_"):
        page = int(data.split("_")[-1])
        try:
            url = "https://api.catalog.ecom.silpo.ua/api/2.0/exec/EcomCatalogGlobal"
            payload = {
                "method": "GetSimpleCatalogItems",
                "data": {
                    "filialId": "2405",
                    "skuPerPage": 10,
                    "pageNumber": page,
                    "sortBy": "popularity",
                    "onlyWithDiscounts": True
                }
            }
            headers = {"Content-Type": "application/json;charset=UTF-8"}
            response = requests.post(url, json=payload, headers=headers, timeout=10)
            data_r = response.json()
            items = data_r.get("items", [])
            total = data.get("itemsCount", 0)
            text_out = f"🔥 Акції Сільпо (стор. {page}):\n\n"
            for item in items:
                name = item.get("name", "?")
                price = item.get("price", "?")
                old_price = item.get("oldPrice")
                unit = item.get("unit", "")
                line = f"• {name} {unit}\n  💰 {price} грн"
                if old_price:
                    line += f" (було {old_price} грн)"
                text_out += line + "\n\n"
            loaded = (page - 1) * 10 + len(items)
            if loaded < total:
                text_out += f"Показано {loaded} з {total}"
                keyboard = InlineKeyboardMarkup([[
                    InlineKeyboardButton("Показати ще ➡️", callback_data=f"sales_page_{page + 1}")
                ]])
                await query.message.reply_text(text_out, reply_markup=keyboard)
            else:
                await query.message.reply_text(text_out + "✅ Це всі акції!", reply_markup=main_keyboard)
        except Exception as e:
            logger.error(e)
            await query.message.reply_text("Помилка.", reply_markup=main_keyboard)

    elif data == "back_to_list":
        watched = load_watched()
        if not watched:
            await query.message.edit_text("Список порожній.")
        else:
            buttons = [[InlineKeyboardButton(f"🔍 {item}", callback_data=f"search:{item}")] for item in watched]
            buttons.append([InlineKeyboardButton("🗑 Видалити товар", callback_data="delete_menu")])
            await query.message.edit_text(
                "📋 Відстежувані товари:\nНатисни щоб перевірити ціну:",
                reply_markup=InlineKeyboardMarkup(buttons)
            )

async def api_get_watched(request):
    watched = load_watched()
    return web.json_response(watched, headers={"Access-Control-Allow-Origin": "*"})

async def api_add_watched(request):
    data = await request.json()
    item = data.get("item", "").strip()
    if item:
        watched = load_watched()
        if item not in watched:
            watched.append(item)
            save_watched(watched)
    return web.json_response({"ok": True}, headers={"Access-Control-Allow-Origin": "*"})

async def api_remove_watched(request):
    data = await request.json()
    item = data.get("item", "").strip()
    watched = load_watched()
    if item in watched:
        watched.remove(item)
        save_watched(watched)
    return web.json_response({"ok": True}, headers={"Access-Control-Allow-Origin": "*"})

async def api_search_metro(request):
    query = request.rel_url.query.get('q', '')
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f'https://stores-api.zakaz.ua/stores/48215611/products/search/?q={query}&per_page=5',
                headers={
                    'x-chain': 'metro',
                    'x-version': '65',
                    'Accept': 'application/json'
                }
            ) as resp:
                data = await resp.json(content_type=None)
                return web.json_response(data, headers={'Access-Control-Allow-Origin': '*'})
    except Exception as e:
        logger.error(f"Metro error: {e}")
        return web.json_response({'results': []}, headers={'Access-Control-Allow-Origin': '*'})

async def api_options(request):
    return web.Response(headers={
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type"
    })

async def start_api():
    app = web.Application()
    app.router.add_get("/watched", api_get_watched)
    app.router.add_post("/watched/add", api_add_watched)
    app.router.add_post("/watched/remove", api_remove_watched)
    app.router.add_options("/watched", api_options)
    app.router.add_options("/watched/add", api_options)
    app.router.add_options("/watched/remove", api_options)
    app.router.add_get("/metro", api_search_metro)
    app.router.add_options("/metro", api_options)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()

def main():
    async def run():
        await start_api()
        app = Application.builder().token(TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("myid", myid))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        app.add_handler(CallbackQueryHandler(handle_callback))
        job_queue = app.job_queue
        job_queue.run_daily(check_sales, time=time(8, 0))
        await app.initialize()
        await app.start()
        await app.updater.start_polling()
        await asyncio.Event().wait()
    asyncio.run(run())

if __name__ == "__main__":
    main()
