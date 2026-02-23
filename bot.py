import os
import yt_dlp
import certifi
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import logging
import glob
import subprocess

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
        
        # ========== УЛУЧШЕННЫЕ НАСТРОЙКИ ДЛЯ СКАЧИВАНИЯ СО ЗВУКОМ ==========
        ydl_opts = {
            'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',  # Явно берем видео и аудио
            'outtmpl': f'downloads/{user_id}/%(title)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'socket_timeout': 30,
            'retries': 3,
            'merge_output_format': 'mp4',  # Объединяем в MP4
            'postprocessors': [{  # Постобработка
                'key': 'FFmpegVideoConvertor',
                'preferedformat': 'mp4',
            }],
            'prefer_ffmpeg': True,  # Используем ffmpeg
            'keepvideo': True,  # Сохраняем оригинал
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Скачиваем видео
            info = ydl.extract_info(link, download=True)
            video_title = info.get('title', 'video')
            
            # Ищем скачанный файл (MP4)
            files = glob.glob(f'downloads/{user_id}/*.mp4')
            
            if files:
                filename = files[-1]  # Берем последний скачанный файл
                
                # Проверяем размер файла (должен быть больше 1MB)
                file_size = os.path.getsize(filename) / (1024 * 1024)
                logger.info(f"Файл скачан: {filename}, размер: {file_size:.2f} MB")
                
                # Сохраняем информацию о видео
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
                        parse_mode='HTML',
                        supports_streaming=True  # Важно для потокового видео
                    )
                
                await msg.delete()
                
                # ПОКАЗЫВАЕМ КНОПКИ ДЛЯ СОХРАНЕНИЯ
                await show_save_options(update, context, user_id)
            else:
                # Если MP4 не найден, ищем другие форматы
                all_files = glob.glob(f'downloads/{user_id}/*')
                if all_files:
                    filename = all_files[-1]
                    logger.warning(f"MP4 не найден, использую: {filename}")
                    
                    # Конвертируем в MP4 если нужно
                    if not filename.endswith('.mp4'):
                        mp4_filename = filename.rsplit('.', 1)[0] + '.mp4'
                        try:
                            # Пробуем сконвертировать
                            cmd = ['ffmpeg', '-i', filename, '-c', 'copy', mp4_filename]
                            subprocess.run(cmd, capture_output=True)
                            if os.path.exists(mp4_filename):
                                filename = mp4_filename
                        except:
                            pass
                    
                    with open(filename, 'rb') as f:
                        await update.message.reply_video(
                            video=f,
                            caption=f"✅ <b>Видео скачано!</b>\n\n{video_title[:50]}",
                            parse_mode='HTML'
                        )
                    
                    await msg.delete()
                    await show_save_options(update, context, user_id)
                else:
                    await msg.edit_text("❌ <b>Файл не найден</b>", parse_mode='HTML')
                
    except Exception as e:
        error_text = str(e)
        logger.error(f"Ошибка скачивания: {error_text}")
        
        if "ffmpeg" in error_text.lower():
            await msg.edit_text("❌ <b>Ошибка ffmpeg</b>\nПроверьте установку на сервере", parse_mode='HTML')
        elif "private" in error_text.lower():
            await msg.edit_text("❌ <b>Это приватное видео</b>", parse_mode='HTML')
        elif "unavailable" in error_text.lower():
            await msg.edit_text("❌ <b>Видео недоступно</b>", parse_mode='HTML')
        else:
            await msg.edit_text(f"❌ <b>Ошибка:</b> {error_text[:100]}", parse_mode='HTML')

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
    
    # Кнопка помощи
    keyboard.append([InlineKeyboardButton("❓ Помощь", callback_data="show_commands")])
    
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
    
    # КОМАНДЫ (не удаляем сообщение)
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
    
    # Удаляем сообщение с кнопками для остальных действий
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
        cat_name = data[5:]
        current_video = context.user_data.get('current_video')
        
        if current_video:
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
    
    # ===== УДАЛЕНИЕ ОТДЕЛЬНОГО ВИДЕО =====
    elif data.startswith("delvideo_"):
        parts = data.split('_')
        cat_name = '_'.join(parts[1:-1])
        index = int(parts[-1])
        await delete_single_video(update, context, user_id, cat_name, index)

# ================== УДАЛЕНИЕ ОДНОГО ВИДЕО ==================
async def delete_single_video(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id, cat_name, video_index):
    """Удаляет одно конкретное видео из категории"""
    
    if (user_id in user_videos and 
        cat_name in user_videos[user_id] and 
        video_index < len(user_videos[user_id][cat_name])):
        
        video = user_videos[user_id][cat_name][video_index]
        video_title = video['title']
        
        # Удаляем файл с диска
        try:
            if os.path.exists(video['path']):
                os.remove(video['path'])
        except:
            pass
        
        # Удаляем из списка
        user_videos[user_id][cat_name].pop(video_index)
        
        if not user_videos[user_id][cat_name]:
            keyboard = [
                [InlineKeyboardButton(f"🗑️ Удалить пустую категорию", callback_data=f"delete_{cat_name}")],
                [InlineKeyboardButton("◀️ Назад к категориям", callback_data="back_to_categories")]
            ]
            await update.callback_query.message.reply_text(
                f"✅ <b>Видео «{video_title[:30]}» удалено</b>\n\n"
                f"📁 Категория «{cat_name}» теперь пуста. Хотите удалить её?",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode='HTML'
            )
        else:
            await show_category_videos(update, context, user_id, cat_name)
    else:
        await update.callback_query.message.reply_text("❌ <b>Видео не найдено</b>", parse_mode='HTML')

# ================== МЕНЮ КОМАНД ==================
async def show_commands_menu(query):
    """Показывает меню со всеми командами"""
    
    commands_text = (
        "📋 <b>ВСЕ КОМАНДЫ БОТА</b>\n\n"
        
        "🔹 <b>ОСНОВНЫЕ:</b>\n"
        "• /start - Главное меню\n"
        "• /help - Подробная помощь\n"
        "• /commands - Это меню\n\n"
        
        "🔹 <b>КАТЕГОРИИ:</b>\n"
        "• /categories - Управление категориями\n"
        "• /stats - Моя статистика\n\n"
        
        "🔹 <b>БЫСТРЫЕ ДЕЙСТВИЯ:</b>\n"
        "• Отправь ссылку - скачать видео\n"
        "• После скачивания выбери категорию\n"
        "• В категории можно удалить любое видео\n\n"
        
        "🔹 <b>ПРИМЕРЫ ССЫЛОК:</b>\n"
        "• Instagram: instagram.com/reel/...\n"
        "• TikTok: tiktok.com/@user/video/...\n"
        "• YouTube: youtu.be/...\n"
        "• Pinterest: pin.it/...\n\n"
        
        "❓ <b>Нужна помощь?</b> Напиши /help"
    )
    
    keyboard = [
        [InlineKeyboardButton("📁 К категориям", callback_data="go_to_categories")],
        [InlineKeyboardButton("📊 Статистика", callback_data="show_stats")],
        [InlineKeyboardButton("◀️ Назад", callback_data="back_to_start")]
    ]
    
    await query.edit_message_text(
        commands_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML',
        disable_web_page_preview=True
    )

# ================== ПОКАЗ КАТЕГОРИЙ ==================
async def show_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает все категории с кнопками управления"""
    user_id = update.effective_user.id
    
    if user_id not in user_categories or not user_categories[user_id]:
        keyboard = [
            [InlineKeyboardButton("📋 Команды", callback_data="show_commands")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_start")]
        ]
        await update.message.reply_text(
            "📁 <b>У вас пока нет категорий</b>\n\n"
            "Отправьте видео и создайте первую категорию!",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        return
    
    text = "📁 <b>Ваши категории:</b>\n\n"
    keyboard = []
    
    for i, cat in enumerate(user_categories[user_id], 1):
        count = len(user_videos[user_id].get(cat, []))
        text += f"{i}. <b>{cat}</b> — {count} видео\n"
        
        keyboard.append([
            InlineKeyboardButton(f"👁️ Смотреть ({count})", callback_data=f"view_{cat}"),
            InlineKeyboardButton(f"✏️ Переименовать", callback_data=f"rename_{cat}"),
            InlineKeyboardButton(f"🗑️ Удалить всё", callback_data=f"delete_{cat}")
        ])
    
    keyboard.append([
        InlineKeyboardButton("📋 Команды", callback_data="show_commands"),
        InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_start")
    ])
    
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

# ================== ПОКАЗ ВИДЕО В КАТЕГОРИИ ==================
async def show_category_videos(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id, cat_name):
    """Показывает все видео в категории"""
    
    if cat_name not in user_videos[user_id] or not user_videos[user_id][cat_name]:
        keyboard = [[InlineKeyboardButton("◀️ Назад к категориям", callback_data="back_to_categories")]]
        await update.callback_query.message.reply_text(
            f"📁 <b>«{cat_name}»</b> — в категории нет видео",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='HTML'
        )
        return
    
    videos = user_videos[user_id][cat_name]
    text = f"📁 <b>«{cat_name}»</b> — {len(videos)} видео\n\n"
    
    keyboard = []
    
    for i, video in enumerate(videos, 1):
        title = video['title'][:40] + "..." if len(video['title']) > 40 else video['title']
        size = video.get('size', 0)
        size_text = f" ({size:.1f}MB)" if size > 0 else ""
        text += f"{i}. {title}{size_text}\n"
        
        keyboard.append([
            InlineKeyboardButton(f"▶️ Смотреть {i}", callback_data=f"play_{cat_name}_{i-1}"),
            InlineKeyboardButton(f"🗑️ Удалить {i}", callback_data=f"delvideo_{cat_name}_{i-1}")
        ])
    
    keyboard.append([
        InlineKeyboardButton("◀️ Назад к категориям", callback_data="back_to_categories"),
        InlineKeyboardButton("📋 Команды", callback_data="show_commands")
    ])
    
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
                        parse_mode='HTML',
                        supports_streaming=True
                    )
            else:
                await query.message.reply_text("❌ <b>Видео не найдено на диске</b>", parse_mode='HTML')

# ================== УДАЛЕНИЕ КАТЕГОРИИ ==================
async def delete_category(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id, cat_name):
    """Удаляет категорию и все видео в ней"""
    
    if cat_name in user_categories[user_id]:
        user_categories[user_id].remove(cat_name)
    
    if cat_name in user_videos[user_id]:
        for video in user_videos[user_id][cat_name]:
            try:
                if os.path.exists(video['path']):
                    os.remove(video['path'])
            except:
                pass
        del user_videos[user_id][cat_name]
    
    keyboard = [[InlineKeyboardButton("◀️ Назад к категориям", callback_data="back_to_categories")]]
    
    await update.callback_query.message.reply_text(
        f"🗑️ <b>Категория «{cat_name}» удалена</b>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

# ================== ОБРАБОТКА ТЕКСТА ==================
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает текстовые сообщения"""
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
                await update.message.reply_text(
                    f"✅ <b>Категория «{text}» создана!</b>\n🎬 Видео сохранено",
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
    
    elif context.user_data.get('waiting_for_rename'):
        old_name = context.user_data.get('rename_category')
        new_name = text
        
        if user_id in user_categories and old_name in user_categories[user_id]:
            index = user_categories[user_id].index(old_name)
            user_categories[user_id][index] = new_name
            
            if user_id in user_videos and old_name in user_videos[user_id]:
                user_videos[user_id][new_name] = user_videos[user_id].pop(old_name)
            
            await update.message.reply_text(
                f"✏️ <b>Категория переименована</b>\n«{old_name}» → «{new_name}»",
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text("❌ <b>Категория не найдена</b>", parse_mode='HTML')
        
        context.user_data['waiting_for_rename'] = False
        context.user_data.pop('rename_category', None)
    
    else:
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
    
    files = glob.glob(f'downloads/{user_id}/*.mp4')
    total_size = 0
    for f in files:
        total_size += os.path.getsize(f)
    
    size_mb = total_size / (1024 * 1024)
    
    stats_text = (
        f"📊 <b>Ваша статистика:</b>\n\n"
        f"📁 Категорий: {total_categories}\n"
        f"🎬 Всего видео: {total_videos}\n"
        f"💾 Занято места: {size_mb:.1f} MB\n"
        f"📦 Файлов на диске: {len(files)}"
    )
    
    keyboard = [
        [InlineKeyboardButton("📁 К категориям", callback_data="go_to_categories")],
        [InlineKeyboardButton("📋 Команды", callback_data="show_commands")],
        [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_start")]
    ]
    
    await update.message.reply_text(
        stats_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

# ================== ПОДРОБНАЯ ПОМОЩЬ ==================
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подробная помощь"""
    help_text = (
        "📱 <b>ПОДРОБНАЯ ПОМОЩЬ</b>\n\n"
        
        "🔹 <b>КАК СКАЧАТЬ ВИДЕО:</b>\n"
        "1. Скопируйте ссылку на видео\n"
        "2. Отправьте её боту\n"
        "3. Дождитесь загрузки (10-30 секунд)\n"
        "4. Выберите категорию для сохранения\n\n"
        
        "🔹 <b>ГДЕ БРАТЬ ССЫЛКИ:</b>\n"
        "• Instagram: нажмите ⋮ → Скопировать ссылку\n"
        "• TikTok: нажмите Поделиться → Копировать ссылку\n"
        "• YouTube: скопируйте из адресной строки\n"
        "• Pinterest: нажмите ⋮ → Скопировать ссылку\n\n"
        
        "🔹 <b>УПРАВЛЕНИЕ ВИДЕО:</b>\n"
        "• /categories - открыть категории\n"
        "• Нажмите «Смотреть» на категории\n"
        "• Для каждого видео есть кнопки:\n"
        "  ▶️ Смотреть - посмотреть видео\n"
        "  🗑️ Удалить - удалить конкретное видео\n\n"
        
        "🔹 <b>КОМАНДЫ:</b>\n"
        "/start - Главное меню\n"
        "/categories - Категории\n"
        "/stats - Статистика\n"
        "/commands - Список команд\n"
        "/help - Эта помощь\n\n"
        
        "🎵 <b>ЗВУК:</b>\n"
        "• Все видео скачиваются со звуком!\n"
        "• Если звука нет - проверьте источник"
    )
    
    keyboard = [[InlineKeyboardButton("◀️ В главное меню", callback_data="back_to_start")]]
    
    await update.message.reply_text(
        help_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

# ================== ВОЗВРАТ В ГЛАВНОЕ МЕНЮ ==================
async def back_to_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Возвращает в главное меню"""
    query = update.callback_query
    await query.answer()
    
    keyboard = [
        [InlineKeyboardButton("📋 Команды бота", callback_data="show_commands")],
        [InlineKeyboardButton("📁 Мои категории", callback_data="go_to_categories")],
        [InlineKeyboardButton("📊 Статистика", callback_data="show_stats")]
    ]
    
    await query.edit_message_text(
        "👋 <b>Главное меню</b>\n\n"
        "📱 Отправьте мне ссылку на видео\n"
        "или выберите действие:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

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
    app.add_handler(CommandHandler("commands", show_commands_menu))
    app.add_handler(CommandHandler("categories", show_categories))
    app.add_handler(CommandHandler("stats", show_stats))
    
    # Кнопки
    app.add_handler(CallbackQueryHandler(button_handler, pattern='^(save_|new_category|skip_save|back_to_categories|view_|rename_|delete_|go_to_categories|show_stats|show_commands|delvideo_)'))
    app.add_handler(CallbackQueryHandler(play_video, pattern='^play_'))
    app.add_handler(CallbackQueryHandler(back_to_start, pattern='^back_to_start$'))
    
    # Текст
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    
    print("✅ Бот успешно запущен!")
    print("🤖 @SaveVideosInsbot")
    print("📁 /categories - управление категориями")
    print("🎵 ВИДЕО СО ЗВУКОМ!")
    
    app.run_polling()

if __name__ == '__main__':
    main()
