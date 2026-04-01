import os
import json
import logging
import requests
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN")
WATCHED_FILE = "/data/watched.json"

main_keyboard = ReplyKeyboardMarkup(
    [
        [KeyboardButton("🔍 Пошук ціни"), KeyboardButton("👁 Відстежувати")],
        [KeyboardButton("📋 Мій список")],
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привіт! Я бот для відстеження цін у Сільпо.\n\nОбери дію:",
        reply_markup=main_keyboard
    )
async def myid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"Твій chat_id: {update.effective_chat.id}")

async def show_search_results(send_func, query):
    try:
        data = search_silpo(query)
        items = data.get("items", [])
        if items:
            logger.info(f"ITEM KEYS: {items[0].keys()}")
            logger.info(f"ITEM DATA: {items[0]}")
        if not items:
            await send_func("Нічого не знайдено.")
            return
        result = f"🛒 Результати для '{query}':\n\n"
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
        await send_func("Помилка пошуку.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "🔍 Пошук ціни":
        await update.message.reply_text("Напиши назву товару:")
        context.user_data["action"] = "search"

    elif text == "👁 Відстежувати":
        await update.message.reply_text("Напиши назву товару для відстеження:")
        context.user_data["action"] = "watch"

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

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myid", myid))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.run_polling()

if __name__ == "__main__":
    main()
