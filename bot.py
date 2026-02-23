import os
import yt_dlp
import certifi
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ТОКЕН - лучше через переменные окружения
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8431619576:AAFDh6Lee8mqDVZ5_BiAgTDDrHQvUAXGt5o')

# Устанавливаем сертификаты
os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()

# Хранилище
user_categories = {}
user_videos = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет! Я бот для скачивания видео\n\n"
        "📱 Отправь мне ссылку на видео"
    )

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = update.message.text
    user_id = update.effective_user.id
    
    msg = await update.message.reply_text("⏳ Скачиваю видео...")
    
    try:
        os.makedirs(f'downloads/{user_id}', exist_ok=True)
        
        ydl_opts = {
            'format': 'best[ext=mp4]/best',
            'outtmpl': f'downloads/{user_id}/video.%(ext)s',
            'quiet': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(link, download=True)
            
            # Ищем файл
            files = os.listdir(f'downloads/{user_id}')
            if files:
                filename = f'downloads/{user_id}/{files[0]}'
                with open(filename, 'rb') as f:
                    await update.message.reply_video(f, caption="✅ Готово!")
                
                await msg.delete()
                
                # Кнопки
                if user_id not in user_categories:
                    user_categories[user_id] = []
                
                keyboard = []
                for cat in user_categories[user_id]:
                    keyboard.append([InlineKeyboardButton(f"📁 {cat}", callback_data=f"cat_{cat}")])
                
                keyboard.append([InlineKeyboardButton("➕ Новая", callback_data="new")])
                keyboard.append([InlineKeyboardButton("⏭ Пропустить", callback_data="skip")])
                
                await update.message.reply_text("Сохранить?", reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        await msg.edit_text(f"❌ Ошибка: {str(e)[:100]}")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.message.delete()
    
    if query.data == "skip":
        await query.message.reply_text("✅ Ок")
    elif query.data == "new":
        await query.message.reply_text("✏️ Название:")
        context.user_data['waiting'] = True
    elif query.data.startswith("cat_"):
        await query.message.reply_text(f"✅ Сохранено")

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('waiting'):
        user_id = update.effective_user.id
        cat = update.message.text.strip()
        
        if user_id not in user_categories:
            user_categories[user_id] = []
        if cat not in user_categories[user_id]:
            user_categories[user_id].append(cat)
            await update.message.reply_text(f"✅ Категория '{cat}' создана")
        
        context.user_data['waiting'] = False
    else:
        await handle_link(update, context)

async def show_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in user_categories and user_categories[user_id]:
        text = "📁 Категории:\n" + "\n".join(f"{i}. {c}" for i, c in enumerate(user_categories[user_id], 1))
        await update.message.reply_text(text)
    else:
        await update.message.reply_text("Нет категорий")

def main():
    # Создаем папку
    os.makedirs('downloads', exist_ok=True)
    
    # Создаем приложение
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Добавляем обработчики
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("categories", show_categories))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    
    logger.info("✅ Бот запущен!")
    app.run_polling()

if __name__ == '__main__':
    main()
