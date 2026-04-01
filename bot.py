import os
import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
from pysilpo import Silpo

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN")
PHONE = os.environ.get("SILPO_PHONE")

WAITING_OTP = 1
WAITING_SEARCH = 2
WAITING_WATCH = 3

watched_items = []
silpo_client = None

main_keyboard = ReplyKeyboardMarkup(
    [
        [KeyboardButton("🔍 Пошук ціни"), KeyboardButton("👁 Відстежувати")],
        [KeyboardButton("📋 Мій список"), KeyboardButton("⚙️ Авторизація")],
    ],
    resize_keyboard=True
)

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
            text_out = "📋 Відстежувані товари:\n\n" + "\n".join(f"• {i}" for i in watched_items)
            await update.message.reply_text(text_out, reply_markup=main_keyboard)

    elif text == "⚙️ Авторизація":
            await update.message.reply_text(f"Надсилаю код на {PHONE}...")
            try:
                global silpo_client
                silpo_client = Silpo(phone_number=PHONE)
                await update.message.reply_text(f"silpo_client створено: {type(silpo_client)}\nВведи код з SMS:")
                context.user_data["action"] = "otp"
            except Exception as e:
                logger.error(f"ДЕТАЛЬНА ПОМИЛКА: {type(e).__name__}: {e}")
                await update.message.reply_text(f"Помилка: {type(e).__name__}: {str(e)[:200]}", reply_markup=main_keyboard)
        
    elif context.user_data.get("action") == "otp":
        try:
            silpo_client.auth.verify_otp(update.message.text.strip())
            context.user_data["action"] = None
            await update.message.reply_text("✅ Авторизація успішна!", reply_markup=main_keyboard)
        except Exception as e:
            logger.error(e)
            await update.message.reply_text("❌ Невірний код. Спробуй ще раз.")

    elif context.user_data.get("action") == "search":
        context.user_data["action"] = None
        query = text
        await update.message.reply_text(f"🔍 Шукаю '{query}'...")
        try:
            products = [p for p in Silpo.product.all() if query.lower() in p.title.lower()][:5]
            if not products:
                await update.message.reply_text("Нічого не знайдено.", reply_markup=main_keyboard)
                return
            result = f"🛒 Результати для '{query}':\n\n"
            for p in products:
                result += f"• {p.title}\n  💰 {p.price} грн\n\n"
            await update.message.reply_text(result, reply_markup=main_keyboard)
        except Exception as e:
            logger.error(e)
            await update.message.reply_text("Помилка пошуку. Спробуй після авторизації.", reply_markup=main_keyboard)

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
