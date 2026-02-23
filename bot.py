import os
import yt_dlp
import certifi
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import logging
import glob
import time
import random

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ТОКЕН
BOT_TOKEN = '8431619576:AAFDh6Lee8mqDVZ5_BiAgTDDrHQvUAXGt5o'

# Устанавливаем сертификаты
os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()

# Хранилище данных пользователей
user_categories = {}
user_videos = {}

# Список User-Agent для имитации разных браузеров
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/537.36 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/537.36'
]

# ================== КОМАНДА СТАРТ ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приветствие и инструкция"""
    keyboard = [
        [InlineKeyboardButton("📋 Команды бота", callback_data="show_commands")],
        [InlineKeyboardButton("📁 Мои категории", callback_data="go_to_categories")],
        [InlineKeyboardButton("📊 Статистика", callback_data="show_stats")]
    ]
    
    await update.message.reply_text(
        "👋 <b>Привет! Я бот для скачивания видео</b>\n\n"
        "📱 <b>Что я умею:</b>\n"
        "• Скачивать видео из Instagram, TikTok, Pinterest, YouTube\n"
        "• Сохранять видео в категории\n"
        "• Управлять категориями\n"
        "• Удалять отдельные видео\n\n"
        "🔽 <b>Выберите действие:</b>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

# ================== СКАЧИВАНИЕ ВИДЕО ==================
async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ссылок на видео"""
    link = update.message.text
    user_id = update.effective_user.id
    
    msg = await update.message.reply_text("⏳ <b>Скачиваю видео...</b>", parse_mode='HTML')
    
    try:
        # Создаем папку для пользователя
        os.makedirs(f'downloads/{user_id}', exist_ok=True)
        
        # Случайный User-Agent для обхода блокировки
        user_agent = random.choice(USER_AGENTS)
        
        # Настройки для скачивания с обходом блокировки
        ydl_opts = {
            'format': 'best[ext=mp4]/best',
            'outtmpl': f'downloads/{user_id}/video.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'socket_timeout': 30,
            'retries': 5,
            'user_agent': user_agent,
            'headers': {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-us,en;q=0.5',
                'Sec-Fetch-Mode': 'navigate',
            }
        }
        
        # Пробуем скачать
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(link, download=True)
                video_title = info.get('title', 'video')
        except Exception as e:
            error_text = str(e).lower()
            
            # Если заблокировали, пробуем другой метод
            if 'block' in error_text or '403' in error_text or 'tiktok' in error_text:
                await msg.edit_text("🔄 <b>TikTok блокирует запрос, пробую другой метод...</b>", parse_mode='HTML')
                
                # Альтернативные настройки для TikTok
                ydl_opts = {
                    'format': 'best',
                    'outtmpl': f'downloads/{user_id}/video.%(ext)s',
                    'quiet': True,
                    'extract_flat': False,
                    'force_generic_extractor': True,  # Используем общий экстрактор
                    'user_agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/537.36',
                }
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(link, download=True)
                    video_title = info.get('title', 'video')
            else:
                raise e
        
        # Ищем файл
        files = glob.glob(f'downloads/{user_id}/*.mp4')
        if not files:
            files = glob.glob(f'downloads/{user_id}/*')
        
        if files:
            filename = files[-1]
            file_size = os.path.getsize(filename) / (1024 * 1024)
            
            context.user_data['current_video'] = {
                'path': filename,
                'title': video_title,
                'url': link,
                'size': file_size
            }
            
            # Отправляем видео
            with open(filename, 'rb') as f:
                await update.message.reply_video(
                    video=f,
                    caption=f"✅ <b>Видео скачано!</b>\n\n{video_title[:50]}\n💾 {file_size:.1f} MB",
                    parse_mode='HTML'
                )
            
            await msg.delete()
            await show_save_options(update, context, user_id)
        else:
            await msg.edit_text("❌ <b>Файл не найден</b>", parse_mode='HTML')
                
    except Exception as e:
        error_text = str(e).lower()
        logger.error(f"Ошибка: {error_text}")
        
        if 'private' in error_text:
            await msg.edit_text("❌ <b>Это приватное видео</b>", parse_mode='HTML')
        elif 'unavailable' in error_text:
            await msg.edit_text("❌ <b>Видео недоступно</b>", parse_mode='HTML')
        elif 'block' in error_text or '403' in error_text:
            await msg.edit_text(
                "❌ <b>TikTok заблокировал запрос</b>\n\n"
                "Попробуйте:\n"
                "• Отправить другую ссылку\n"
                "• Подождать 5-10 минут\n"
                "• Использовать Instagram или YouTube",
                parse_mode='HTML'
            )
        else:
            await msg.edit_text(f"❌ <b>Ошибка:</b> {str(e)[:100]}", parse_mode='HTML')

# ================== КНОПКИ СОХРАНЕНИЯ ==================
async def show_save_options(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id):
    """Показывает кнопки для сохранения видео"""
    
    if user_id not in user_categories:
        user_categories[user_id] = []
    if user_id not in user_videos:
        user_videos[user_id] = {}
    
    keyboard = []
    
    for cat in user_categories[user_id]:
        count = len(user_videos[user_id].get(cat, []))
        keyboard.append([InlineKeyboardButton(
            f"📁 {cat} ({count})", 
            callback_data=f"save_{cat}"
        )])
    
    keyboard.append([
        InlineKeyboardButton("➕ Новая категория", callback_data="new_category"),
        InlineKeyboardButton("⏭ Пропустить", callback_data="skip_save")
    ])
    
    keyboard.append([InlineKeyboardButton("❓ Помощь", callback_data="show_commands")])
    
    await update.message.reply_text(
        "💾 <b>Сохранить видео?</b>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

# ================== ОБРАБОТКА КНОПОК ==================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопок"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data == "show_commands":
        await show_commands_menu(query)
        return
    elif data == "go_to_categories":
        await query.message.delete()
        await show_categories(update, context)
        return
    elif data == "show_stats":
        await query.message.delete()
        await show_stats(update, context)
        return
    elif data == "back_to_start":
        await back_to_start(update, context)
        return
    
    await query.message.delete()
    
    if data == "skip_save":
        await query.message.reply_text("⏭ Видео не сохранено")
        context.user_data.pop('current_video', None)
    
    elif data == "new_category":
        await query.message.reply_text("✏️ Введите название категории:")
        context.user_data['waiting_for_category'] = True
    
    elif data.startswith("save_"):
        cat_name = data[5:]
        current_video = context.user_data.get('current_video')
        
        if current_video:
            if cat_name not in user_videos[user_id]:
                user_videos[user_id][cat_name] = []
            user_videos[user_id][cat_name].append(current_video)
            await query.message.reply_text(f"✅ Сохранено в «{cat_name}»")
        context.user_data.pop('current_video', None)
    
    elif data.startswith("delete_"):
        cat_name = data[7:]
        if cat_name in user_categories[user_id]:
            user_categories[user_id].remove(cat_name)
            if cat_name in user_videos[user_id]:
                del user_videos[user_id][cat_name]
            await query.message.reply_text(f"🗑️ Категория «{cat_name}» удалена")

# ================== МЕНЮ КОМАНД ==================
async def show_commands_menu(query):
    """Показывает меню команд"""
    commands_text = (
        "📋 <b>КОМАНДЫ</b>\n\n"
        "• /start - Главное меню\n"
        "• /categories - Категории\n"
        "• /stats - Статистика\n"
        "• /help - Помощь\n\n"
        "Просто отправь ссылку на видео!"
    )
    
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="back_to_start")]]
    
    await query.edit_message_text(
        commands_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

# ================== ПОКАЗ КАТЕГОРИЙ ==================
async def show_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает категории"""
    user_id = update.effective_user.id
    
    if user_id not in user_categories or not user_categories[user_id]:
        await update.message.reply_text("📁 У вас пока нет категорий")
        return
    
    text = "📁 Ваши категории:\n\n"
    keyboard = []
    
    for i, cat in enumerate(user_categories[user_id], 1):
        count = len(user_videos[user_id].get(cat, []))
        text += f"{i}. {cat} — {count} видео\n"
        keyboard.append([InlineKeyboardButton(f"🗑️ {cat}", callback_data=f"delete_{cat}")])
    
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="back_to_start")])
    
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

# ================== СТАТИСТИКА ==================
async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает статистику"""
    user_id = update.effective_user.id
    
    total_categories = len(user_categories.get(user_id, []))
    total_videos = 0
    if user_id in user_videos:
        for cat in user_videos[user_id]:
            total_videos += len(user_videos[user_id][cat])
    
    await update.message.reply_text(
        f"📊 Статистика:\n\n📁 Категорий: {total_categories}\n🎬 Видео: {total_videos}",
        parse_mode='HTML'
    )

# ================== ОБРАБОТКА ТЕКСТА ==================
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает текст"""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    if context.user_data.get('waiting_for_category'):
        if user_id not in user_categories:
            user_categories[user_id] = []
        
        if text not in user_categories[user_id]:
            user_categories[user_id].append(text)
            
            current_video = context.user_data.get('current_video')
            if current_video:
                if text not in user_videos[user_id]:
                    user_videos[user_id][text] = []
                user_videos[user_id][text].append(current_video)
                await update.message.reply_text(f"✅ Категория «{text}» создана! Видео сохранено")
                context.user_data.pop('current_video', None)
            else:
                await update.message.reply_text(f"✅ Категория «{text}» создана!")
        else:
            await update.message.reply_text(f"❌ Категория уже существует")
        
        context.user_data['waiting_for_category'] = False
    else:
        await handle_link(update, context)

# ================== ПОДРОБНАЯ ПОМОЩЬ ==================
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подробная помощь"""
    help_text = (
        "📱 <b>ПОМОЩЬ</b>\n\n"
        "1. Отправь ссылку на видео\n"
        "2. Дождись загрузки\n"
        "3. Выбери категорию\n\n"
        "Если TikTok блокирует:\n"
        "• Подожди 5-10 минут\n"
        "• Попробуй Instagram\n"
        "• Попробуй YouTube"
    )
    
    await update.message.reply_text(help_text, parse_mode='HTML')

# ================== ВОЗВРАТ В ГЛАВНОЕ МЕНЮ ==================
async def back_to_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возврат в главное меню"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("📋 Команды", callback_data="show_commands")],
        [InlineKeyboardButton("📁 Категории", callback_data="go_to_categories")],
        [InlineKeyboardButton("📊 Статистика", callback_data="show_stats")]
    ]
    
    await query.edit_message_text(
        "👋 <b>Главное меню</b>\n\nОтправьте ссылку на видео:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

# ================== ЗАПУСК БОТА ==================
def main():
    """Запуск бота"""
    print("🔄 Запуск бота...")
    
    os.makedirs('downloads', exist_ok=True)
    
    app = Application.builder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("categories", show_categories))
    app.add_handler(CommandHandler("stats", show_stats))
    
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    
    print("✅ Бот запущен!")
    print("🤖 @SaveVideosInsbot")
    
    app.run_polling()

if __name__ == '__main__':
    main()
