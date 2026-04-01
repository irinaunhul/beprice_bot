import os
import logging
import requests
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN")

main_keyboard = ReplyKeyboardMarkup(
    [
        [KeyboardButton("🔍 Пошук ціни"), KeyboardButton("👁 Відстежувати")],
        [KeyboardButton("📋 Мій список")],
    ],
    resize_keyboard=True
)

watched_items = []

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

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "🔍 Пошук ціни":
        await update.message.reply_text("Напиши назву товару:")
        context.user_data["action"] = "search"

    elif text == "👁 Відстежувати":
        await update.message.reply_text("Напиши назву товару для відстеження:")
        context.user_data["action"] = "watch"

    elif text == "📋 Мій список":
        if not watched_items:
            await update.message.reply_text("Список порожній.", reply_markup=main_keyboard)
        else:
            out = "📋 Відстежувані товари:\n\n" + "\n".join(f"• {i}" for i in watched_items)
            await update.message.reply_text(out, reply_markup=main_keyboard)

    elif context.user_data.get("action") == "search":
        context.user_data["action"] = None
        await update.message.reply_text(f"🔍 Шукаю '{text}'...")
        try:
            data = search_silpo(text)
            items = data.get("items", [])
            if not items:
                await update.message.reply_text("Нічого не знайдено.", reply_markup=main_keyboard)
                return
            result = f"🛒 Результати для '{text}':\n\n"
            for item in items[:5]:
                name = item.get("name", "?")
                price = item.get("price", "?")
                old_price = item.get("oldPrice")
                line = f"• {name}\n  💰 {price} грн"
                if old_price and old_price != price:
                    line += f" ~~{old_price}~~ 🔥"
                result += line + "\n\n"
            await update.message.reply_text(result, reply_markup=main_keyboard)
        except Exception as e:
            logger.error(e)
            await update.message.reply_text("Помилка пошуку.", reply_markup=main_keyboard)

    elif context.user_data.get("action") == "watch":
        context.user_data["action"] = None
        watched_items.append(text)
        await update.message.reply_text(f"✅ '{text}' додано до відстеження!", reply_markup=main_keyboard)

    else:
        await update.message.reply_text("Обери дію:", reply_markup=main_keyboard)

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.run_polling()

if __name__ == "__main__":
    main()
```

І `requirements.txt` спрощуємо — прибираємо `pysilpo` і `cryptography` бо вони більше не потрібні:
```
requests
python-telegram-bot==22.7
httpx
