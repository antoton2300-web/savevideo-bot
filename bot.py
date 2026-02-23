import os
import yt_dlp
import certifi
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import logging

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ТОКЕН
BOT_TOKEN = '8431619576:AAFDh6Lee8mqDVZ5_BiAgTDDrHQvUAXGt5o'

# Устанавливаем сертификаты
os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()

# Хранилище данных пользователей
user_categories = {}  # {user_id: [список категорий]}
user_videos = {}      # {user_id: {категория: [список видео]}}

# ================== КОМАНДА СТАРТ ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приветствие и инструкция"""
    await update.message.reply_text(
        "👋 <b>Привет! Я бот для скачивания видео</b>\n\n"
        "📱 <b>Что я умею:</b>\n"
        "• Скачивать видео из Instagram, TikTok, Pinterest\n"
        "• Сохранять видео в категории\n"
        "• Управлять категориями (создание/удаление/переименование)\n"
        "• Показывать статистику\n\n"
        "📁 <b>Команды:</b>\n"
        "/start - Начать работу\n"
        "/categories - Управление категориями\n"
        "/stats - Моя статистика\n"
        "/help - Помощь",
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
        
        # Настройки для скачивания
        ydl_opts = {
            'format': 'best[ext=mp4]/best',
            'outtmpl': f'downloads/{user_id}/%(title)s.%(ext)s',
            'quiet': True,
            'socket_timeout': 30,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Скачиваем видео
            info = ydl.extract_info(link, download=True)
            video_title = info.get('title', 'video')
            
            # Ищем скачанный файл
            filename = None
            import glob
            files = glob.glob(f'downloads/{user_id}/*.mp4')
            if files:
                filename = files[-1]  # Берем последний скачанный файл
            
            if filename and os.path.exists(filename):
                # Сохраняем информацию о видео
                context.user_data['current_video'] = {
                    'path': filename,
                    'title': video_title,
                    'url': link
                }
                
                # Отправляем видео
                with open(filename, 'rb') as f:
                    await update.message.reply_video(
                        video=f,
                        caption=f"✅ <b>Видео скачано!</b>\n\n{video_title[:50]}",
                        parse_mode='HTML'
                    )
                
                await msg.delete()
                
                # ПОКАЗЫВАЕМ КНОПКИ ДЛЯ СОХРАНЕНИЯ
                await show_save_options(update, context, user_id)
            else:
                await msg.edit_text("❌ <b>Файл не найден</b>", parse_mode='HTML')
                
    except Exception as e:
        await msg.edit_text(f"❌ <b>Ошибка:</b> {str(e)[:100]}", parse_mode='HTML')

# ================== КНОПКИ СОХРАНЕНИЯ ==================
async def show_save_options(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id):
    """Показывает кнопки для сохранения видео в категорию"""
    
    # Инициализируем данные пользователя
    if user_id not in user_categories:
        user_categories[user_id] = []
    if user_id not in user_videos:
        user_videos[user_id] = {}
    
    keyboard = []
    
    # Кнопки существующих категорий
    for cat in user_categories[user_id]:
        # Считаем сколько видео в категории
        count = len(user_videos[user_id].get(cat, []))
        keyboard.append([InlineKeyboardButton(
            f"📁 {cat} ({count} видео)", 
            callback_data=f"save_{cat}"
        )])
    
    # Кнопки действий
    keyboard.append([
        InlineKeyboardButton("➕ Новая категория", callback_data="new_category"),
        InlineKeyboardButton("⏭ Пропустить", callback_data="skip_save")
    ])
    
    await update.message.reply_text(
        "💾 <b>Сохранить видео?</b>\n\n"
        "Выберите категорию или создайте новую:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

# ================== ОБРАБОТКА КНОПОК ==================
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик всех кнопок"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    # Удаляем сообщение с кнопками
    await query.message.delete()
    
    # ===== СОХРАНЕНИЕ ВИДЕО =====
    if data == "skip_save":
        await query.message.reply_text("⏭ <b>Видео не сохранено</b>", parse_mode='HTML')
        context.user_data.pop('current_video', None)
    
    elif data == "new_category":
        await query.message.reply_text(
            "✏️ <b>Введите название новой категории:</b>",
            parse_mode='HTML'
        )
        context.user_data['waiting_for_category'] = True
    
    elif data.startswith("save_"):
        cat_name = data[5:]  # Убираем "save_"
        current_video = context.user_data.get('current_video')
        
        if current_video:
            # Сохраняем видео в категорию
            if cat_name not in user_videos[user_id]:
                user_videos[user_id][cat_name] = []
            
            user_videos[user_id][cat_name].append(current_video)
            
            await query.message.reply_text(
                f"✅ <b>Видео сохранено в категорию</b> «{cat_name}»\n\n"
                f"📁 /categories - управлять категориями",
                parse_mode='HTML'
            )
        else:
            await query.message.reply_text("❌ <b>Ошибка: видео не найдено</b>", parse_mode='HTML')
        
        context.user_data.pop('current_video', None)
    
    # ===== УПРАВЛЕНИЕ КАТЕГОРИЯМИ =====
    elif data == "back_to_categories":
        await show_categories(update, context)
    
    elif data.startswith("view_"):
        cat_name = data[5:]
        await show_category_videos(update, context, user_id, cat_name)
    
    elif data.startswith("rename_"):
        cat_name = data[7:]
        context.user_data['rename_category'] = cat_name
        context.user_data['waiting_for_rename'] = True
        await query.message.reply_text(
            f"✏️ <b>Введите новое название для категории</b> «{cat_name}»:",
            parse_mode='HTML'
        )
    
    elif data.startswith("delete_"):
        cat_name = data[7:]
        await delete_category(update, context, user_id, cat_name)

# ================== ПОКАЗ КАТЕГОРИЙ ==================
async def show_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает все категории с кнопками управления"""
    user_id = update.effective_user.id
    
    if user_id not in user_categories or not user_categories[user_id]:
        await update.message.reply_text(
            "📁 <b>У вас пока нет категорий</b>\n\n"
            "Отправьте видео и создайте первую категорию!",
            parse_mode='HTML'
        )
        return
    
    text = "📁 <b>Ваши категории:</b>\n\n"
    keyboard = []
    
    for i, cat in enumerate(user_categories[user_id], 1):
        # Считаем видео
        count = len(user_videos[user_id].get(cat, []))
        text += f"{i}. <b>{cat}</b> — {count} видео\n"
        
        # Кнопки для категории
        keyboard.append([
            InlineKeyboardButton(f"👁️ Смотреть", callback_data=f"view_{cat}"),
            InlineKeyboardButton(f"✏️ Переименовать", callback_data=f"rename_{cat}"),
            InlineKeyboardButton(f"🗑️ Удалить", callback_data=f"delete_{cat}")
        ])
    
    text += "\n<i>Выберите действие для категории:</i>"
    
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

# ================== ПОКАЗ ВИДЕО В КАТЕГОРИИ ==================
async def show_category_videos(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id, cat_name):
    """Показывает все видео в категории"""
    
    if cat_name not in user_videos[user_id] or not user_videos[user_id][cat_name]:
        await update.callback_query.message.reply_text(
            f"📁 <b>«{cat_name}»</b> — в категории нет видео",
            parse_mode='HTML'
        )
        return
    
    videos = user_videos[user_id][cat_name]
    text = f"📁 <b>«{cat_name}»</b> — {len(videos)} видео\n\n"
    
    keyboard = []
    
    for i, video in enumerate(videos, 1):
        # Обрезаем длинное название
        title = video['title'][:30] + "..." if len(video['title']) > 30 else video['title']
        text += f"{i}. {title}\n"
        
        # Кнопка для просмотра видео
        keyboard.append([InlineKeyboardButton(
            f"▶️ Смотреть видео {i}", 
            callback_data=f"play_{cat_name}_{i-1}"
        )])
    
    # Кнопка назад
    keyboard.append([InlineKeyboardButton("◀️ Назад к категориям", callback_data="back_to_categories")])
    
    await update.callback_query.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

# ================== ВОСПРОИЗВЕДЕНИЕ ВИДЕО ==================
async def play_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет видео из категории"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data.startswith("play_"):
        parts = data.split('_')
        cat_name = '_'.join(parts[1:-1])
        index = int(parts[-1])
        
        if (user_id in user_videos and 
            cat_name in user_videos[user_id] and 
            index < len(user_videos[user_id][cat_name])):
            
            video = user_videos[user_id][cat_name][index]
            
            if os.path.exists(video['path']):
                with open(video['path'], 'rb') as f:
                    await query.message.reply_video(
                        video=f,
                        caption=f"🎬 <b>{video['title'][:50]}</b>\n📁 Категория: {cat_name}",
                        parse_mode='HTML'
                    )
            else:
                await query.message.reply_text("❌ <b>Видео не найдено на диске</b>", parse_mode='HTML')

# ================== УДАЛЕНИЕ КАТЕГОРИИ ==================
async def delete_category(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id, cat_name):
    """Удаляет категорию и все видео в ней"""
    
    # Удаляем из списка категорий
    if cat_name in user_categories[user_id]:
        user_categories[user_id].remove(cat_name)
    
    # Удаляем видео
    if cat_name in user_videos[user_id]:
        # Опционально: удаляем файлы с диска
        for video in user_videos[user_id][cat_name]:
            try:
                if os.path.exists(video['path']):
                    os.remove(video['path'])
            except:
                pass
        del user_videos[user_id][cat_name]
    
    await update.callback_query.message.reply_text(
        f"🗑️ <b>Категория «{cat_name}» удалена</b>",
        parse_mode='HTML'
    )

# ================== ОБРАБОТКА ТЕКСТА ==================
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает текстовые сообщения (новые категории, переименование)"""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    # Создание новой категории
    if context.user_data.get('waiting_for_category'):
        if user_id not in user_categories:
            user_categories[user_id] = []
        
        if text not in user_categories[user_id]:
            user_categories[user_id].append(text)
            
            # Если есть видео для сохранения
            current_video = context.user_data.get('current_video')
            if current_video:
                if text not in user_videos[user_id]:
                    user_videos[user_id][text] = []
                user_videos[user_id][text].append(current_video)
                await update.message.reply_text(
                    f"✅ <b>Категория «{text}» создана!</b>\n"
                    f"🎬 Видео сохранено в новую категорию",
                    parse_mode='HTML'
                )
                context.user_data.pop('current_video', None)
            else:
                await update.message.reply_text(
                    f"✅ <b>Категория «{text}» создана!</b>",
                    parse_mode='HTML'
                )
        else:
            await update.message.reply_text(
                f"❌ <b>Категория «{text}» уже существует</b>",
                parse_mode='HTML'
            )
        
        context.user_data['waiting_for_category'] = False
    
    # Переименование категории
    elif context.user_data.get('waiting_for_rename'):
        old_name = context.user_data.get('rename_category')
        new_name = text
        
        if user_id in user_categories and old_name in user_categories[user_id]:
            # Переименовываем в списке
            index = user_categories[user_id].index(old_name)
            user_categories[user_id][index] = new_name
            
            # Переименовываем в словаре видео
            if user_id in user_videos and old_name in user_videos[user_id]:
                user_videos[user_id][new_name] = user_videos[user_id].pop(old_name)
            
            await update.message.reply_text(
                f"✏️ <b>Категория переименована</b>\n"
                f"«{old_name}» → «{new_name}»",
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text(
                f"❌ <b>Категория не найдена</b>",
                parse_mode='HTML'
            )
        
        context.user_data['waiting_for_rename'] = False
        context.user_data.pop('rename_category', None)
    
    else:
        # Если не ждем ничего - обрабатываем как ссылку
        await handle_link(update, context)

# ================== СТАТИСТИКА ==================
async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает статистику пользователя"""
    user_id = update.effective_user.id
    
    total_categories = len(user_categories.get(user_id, []))
    total_videos = 0
    
    if user_id in user_videos:
        for cat in user_videos[user_id]:
            total_videos += len(user_videos[user_id][cat])
    
    # Считаем место на диске
    import glob
    files = glob.glob(f'downloads/{user_id}/*.mp4')
    total_size = 0
    for f in files:
        total_size += os.path.getsize(f)
    
    # Переводим в MB
    size_mb = total_size / (1024 * 1024)
    
    stats_text = (
        f"📊 <b>Ваша статистика:</b>\n\n"
        f"📁 Категорий: {total_categories}\n"
        f"🎬 Всего видео: {total_videos}\n"
        f"💾 Занято места: {size_mb:.1f} MB\n"
        f"📦 Файлов на диске: {len(files)}"
    )
    
    await update.message.reply_text(stats_text, parse_mode='HTML')

# ================== ПОМОЩЬ ==================
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подробная помощь"""
    help_text = (
        "📱 <b>Помощь по боту</b>\n\n"
        "<b>🔹 Основные команды:</b>\n"
        "/start - Начать работу\n"
        "/categories - Управление категориями\n"
        "/stats - Моя статистика\n"
        "/help - Эта справка\n\n"
        
        "<b>🔹 Как пользоваться:</b>\n"
        "1️⃣ Отправьте ссылку на видео\n"
        "2️⃣ После загрузки выберите категорию\n"
        "3️⃣ Видео сохранится в выбранную категорию\n\n"
        
        "<b>🔹 Управление категориями:</b>\n"
        "• Нажмите /categories чтобы увидеть все категории\n"
        "• Для каждой категории есть кнопки:\n"
        "  👁️ Смотреть — показать все видео\n"
        "  ✏️ Переименовать — изменить название\n"
        "  🗑️ Удалить — удалить категорию с видео\n\n"
        
        "<b>🔹 Поддерживаемые платформы:</b>\n"
        "• Instagram (reels, посты)\n"
        "• TikTok\n"
        "• Pinterest\n"
        "• YouTube\n\n"
        
        "<b>🔹 Советы:</b>\n"
        "• Создавайте категории по темам (Музыка, Фильмы, Обучение)\n"
        "• Используйте /stats чтобы следить за местом на диске\n"
        "• Видео хранятся на сервере, но можно скачать в любой момент"
    )
    
    await update.message.reply_text(help_text, parse_mode='HTML')

# ================== ЗАПУСК БОТА ==================
def main():
    """Главная функция запуска"""
    print("🔄 Запуск бота...")
    
    # Создаем папку для загрузок
    os.makedirs('downloads', exist_ok=True)
    
    # Создаем приложение
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Команды
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("categories", show_categories))
    app.add_handler(CommandHandler("stats", show_stats))
    
    # Кнопки
    app.add_handler(CallbackQueryHandler(button_handler, pattern='^(save_|new_category|skip_save|back_to_categories|view_|rename_|delete_)$'))
    app.add_handler(CallbackQueryHandler(play_video, pattern='^play_'))
    
    # Текст
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    
    print("✅ Бот успешно запущен!")
    print("🤖 @SaveVideosInsbot")
    print("📁 /categories - управление категориями")
    
    app.run_polling()

if __name__ == '__main__':
    main()
