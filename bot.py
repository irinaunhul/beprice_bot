import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN")
PHONE = os.environ.get("SILPO_PHONE")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привіт! Я бот для відстеження цін.\n\n"
        "Команди:\n"
        "/price <назва> — пошук ціни товару\n"
        "/watch <назва> — додати до відстеження\n"
        "/list — мій список відстеження\n"
    )

async def price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Напиши назву товару. Наприклад: /price молоко")
        return
    query = " ".join(context.args)
    await update.message.reply_text(f"🔍 Шукаю '{query}'... (поки в розробці)")

async def watch(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ Функція відстеження — скоро буде!")

async def list_watched(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📋 Список порожній поки що.")

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("price", price))
    app.add_handler(CommandHandler("watch", watch))
    app.add_handler(CommandHandler("list", list_watched))
    app.run_polling()

if __name__ == "__main__":
    main()
```

**`Procfile`** — заміни на:
```
worker: python bot.py
