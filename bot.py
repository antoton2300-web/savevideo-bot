import os
import yt_dlp
import certifi
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# ТОКЕН
BOT_TOKEN = '8431619576:AAFDh6Lee8mqDVZ5_BiAgTDDrHQvUAXGt5o'

# Устанавливаем сертификаты
os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()

# Простой старт
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Бот работает! Отправь ссылку на видео")

# Простое скачивание
async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = update.message.text
    user_id = update.effective_user.id
    
    msg = await update.message.reply_text("Скачиваю...")
    
    try:
        os.makedirs(f'downloads/{user_id}', exist_ok=True)
        
        ydl_opts = {
            'format': 'best',
            'outtmpl': f'downloads/{user_id}/video.%(ext)s',
            'quiet': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(link, download=True)
            
            # Отправляем видео
            files = os.listdir(f'downloads/{user_id}')
            if files:
                with open(f'downloads/{user_id}/{files[0]}', 'rb') as f:
                    await update.message.reply_video(f, caption="✅ Готово!")
                await msg.delete()
            else:
                await msg.edit_text("❌ Ошибка")
    except Exception as e:
        await msg.edit_text(f"❌ Ошибка: {str(e)[:50]}")

# Запуск
def main():
    # Простейший запуск
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_link))
    
    print("✅ Бот запущен!")
    app.run_polling()

if __name__ == '__main__':
    main()
