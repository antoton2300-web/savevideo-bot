import os
import yt_dlp
import certifi
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
import logging
import glob
import subprocess
import time

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
user_audios = {}      # {user_id: {категория: [список аудио]}}

# ================== КОМАНДА СТАРТ ==================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Приветствие и инструкция"""
    keyboard = [
        [InlineKeyboardButton("📋 Команды бота", callback_data="show_commands")],
        [InlineKeyboardButton("📁 Мои категории", callback_data="go_to_categories")],
        [InlineKeyboardButton("📊 Статистика", callback_data="show_stats")]
    ]
    
    await update.message.reply_text(
        "👋 <b>Привет! Я бот для скачивания видео и музыки</b>\n\n"
        "📱 <b>Что я умею:</b>\n"
        "• Скачивать видео из Instagram, TikTok, Pinterest, YouTube\n"
        "• Отправлять видео, а потом отдельно музыку (MP3)\n"
        "• Сохранять видео и музыку в категории\n"
        "• Управлять категориями\n"
        "• Удалять отдельные файлы\n\n"
        "🔽 <b>Выберите действие:</b>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

# ================== СКАЧИВАНИЕ ВИДЕО И АУДИО ==================
async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка ссылок на видео - отправляет видео, потом аудио"""
    link = update.message.text
    user_id = update.effective_user.id
    
    msg = await update.message.reply_text("⏳ <b>Скачиваю видео и аудио...</b>", parse_mode='HTML')
    
    try:
        # Создаем папку для пользователя
        os.makedirs(f'downloads/{user_id}', exist_ok=True)
        
        # ===== ШАГ 1: СКАЧИВАЕМ ВИДЕО =====
        video_opts = {
            'format': 'best[ext=mp4]/best',  # Лучшее видео
            'outtmpl': f'downloads/{user_id}/video_%(title)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'socket_timeout': 30,
        }
        
        video_filename = None
        audio_filename = None
        video_title = "video"
        
        with yt_dlp.YoutubeDL(video_opts) as ydl:
            info = ydl.extract_info(link, download=True)
            video_title = info.get('title', 'video')
            
            # Ищем скачанный видеофайл
            video_files = glob.glob(f'downloads/{user_id}/video_*.mp4')
            if video_files:
                video_filename = video_files[-1]
                logger.info(f"Видео скачано: {video_filename}")
        
        # ===== ШАГ 2: СКАЧИВАЕМ ТОЛЬКО АУДИО =====
        audio_opts = {
            'format': 'bestaudio/best',
            'outtmpl': f'downloads/{user_id}/audio_%(title)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '192',
            }],
        }
        
        with yt_dlp.YoutubeDL(audio_opts) as ydl:
            # Скачиваем аудио
            info2 = ydl.extract_info(link, download=True)
            
            # Ищем скачанный аудиофайл
            time.sleep(1)  # Ждем конвертации
            audio_files = glob.glob(f'downloads/{user_id}/audio_*.mp3')
            if audio_files:
                audio_filename = audio_files[-1]
                logger.info(f"Аудио скачано: {audio_filename}")
        
        # ===== ШАГ 3: ОТПРАВЛЯЕМ СНАЧАЛА ВИДЕО, ПОТОМ АУДИО =====
        if video_filename and os.path.exists(video_filename):
            video_size = os.path.getsize(video_filename) / (1024 * 1024)
            
            # Отправляем видео
            with open(video_filename, 'rb') as f:
                await update.message.reply_video(
                    video=f,
                    caption=f"🎬 <b>Видео</b>\n\n{video_title[:50]}\n💾 {video_size:.1f} MB",
                    parse_mode='HTML',
                    supports_streaming=True
                )
            
            # Сохраняем видео в контекст
            context.user_data['current_video'] = {
                'path': video_filename,
                'title': f"{video_title} (видео)",
                'url': link,
                'type': 'video',
                'size': video_size
            }
        
        if audio_filename and os.path.exists(audio_filename):
            audio_size = os.path.getsize(audio_filename) / (1024 * 1024)
            
            # Отправляем аудио отдельно
            with open(audio_filename, 'rb') as f:
                await update.message.reply_audio(
                    audio=f,
                    title=video_title,
                    performer="Из видео",
                    caption=f"🎵 <b>Аудио (MP3)</b>\n\n{ video_title[:50]}\n💾 {audio_size:.1f} MB",
                    parse_mode='HTML'
                )
            
            # Сохраняем аудио в контекст
            context.user_data['current_audio'] = {
                'path': audio_filename,
                'title': f"{video_title} (аудио)",
                'url': link,
                'type': 'audio',
                'size': audio_size
            }
        
        await msg.delete()
        
        # ===== ШАГ 4: ПРЕДЛАГАЕМ СОХРАНИТЬ В КАТЕГОРИИ =====
        await show_save_options_both(update, context, user_id)
        
    except Exception as e:
        error_text = str(e)
        logger.error(f"Ошибка скачивания: {error_text}")
        await msg.edit_text(f"❌ <b>Ошибка:</b> {error_text[:100]}", parse_mode='HTML')

# ================== КНОПКИ СОХРАНЕНИЯ (ДЛЯ ВИДЕО И АУДИО) ==================
async def show_save_options_both(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id):
    """Показывает кнопки для сохранения видео и аудио"""
    
    # Инициализируем данные пользователя
    if user_id not in user_categories:
        user_categories[user_id] = []
    if user_id not in user_videos:
        user_videos[user_id] = {}
    if user_id not in user_audios:
        user_audios[user_id] = {}
    
    has_video = 'current_video' in context.user_data
    has_audio = 'current_audio' in context.user_data
    
    text = "💾 <b>Что сохранить?</b>\n\n"
    keyboard = []
    
    if has_video:
        text += "🎬 Видео доступно для сохранения\n"
    if has_audio:
        text += "🎵 Аудио (MP3) доступно для сохранения\n"
    
    text += "\nВыберите категорию:"
    
    # Кнопки существующих категорий
    for cat in user_categories[user_id]:
        video_count = len(user_videos[user_id].get(cat, []))
        audio_count = len(user_audios[user_id].get(cat, []))
        keyboard.append([InlineKeyboardButton(
            f"📁 {cat} (🎬{video_count} 🎵{audio_count})", 
            callback_data=f"choose_cat_{cat}"
        )])
    
    # Кнопки действий
    keyboard.append([
        InlineKeyboardButton("➕ Новая категория", callback_data="new_category_both"),
        InlineKeyboardButton("⏭ Пропустить всё", callback_data="skip_all")
    ])
    
    # Кнопка помощи
    keyboard.append([InlineKeyboardButton("❓ Помощь", callback_data="show_commands")])
    
    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

# ================== ВЫБОР КАТЕГОРИИ ДЛЯ СОХРАНЕНИЯ ==================
async def choose_category_for_save(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id, cat_name):
    """Показывает что сохранить в выбранную категорию"""
    query = update.callback_query
    
    has_video = 'current_video' in context.user_data
    has_audio = 'current_audio' in context.user_data
    
    keyboard = []
    
    if has_video:
        keyboard.append([InlineKeyboardButton("🎬 Сохранить видео", callback_data=f"save_video_{cat_name}")])
    if has_audio:
        keyboard.append([InlineKeyboardButton("🎵 Сохранить аудио", callback_data=f"save_audio_{cat_name}")])
    if has_video and has_audio:
        keyboard.append([InlineKeyboardButton("🎬🎵 Сохранить всё", callback_data=f"save_both_{cat_name}")])
    
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="back_to_save_options")])
    
    await query.edit_message_text(
        f"📁 <b>Категория: {cat_name}</b>\n\n"
        f"Что хотите сохранить?",
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
    
    elif data == "back_to_save_options":
        await query.message.delete()
        await show_save_options_both(update, context, user_id)
        return
    
    # ===== СОХРАНЕНИЕ В КАТЕГОРИИ =====
    if data == "skip_all":
        await query.message.delete()
        await query.message.reply_text("⏭ <b>Файлы не сохранены</b>", parse_mode='HTML')
        context.user_data.pop('current_video', None)
        context.user_data.pop('current_audio', None)
    
    elif data == "new_category_both":
        await query.message.delete()
        await query.message.reply_text(
            "✏️ <b>Введите название новой категории:</b>",
            parse_mode='HTML'
        )
        context.user_data['waiting_for_category_both'] = True
    
    elif data.startswith("choose_cat_"):
        cat_name = data[11:]  # убираем "choose_cat_"
        await query.message.delete()
        await choose_category_for_save(update, context, user_id, cat_name)
    
    elif data.startswith("save_video_"):
        cat_name = data[11:]  # убираем "save_video_"
        current_video = context.user_data.get('current_video')
        
        if current_video:
            if cat_name not in user_videos[user_id]:
                user_videos[user_id][cat_name] = []
            user_videos[user_id][cat_name].append(current_video)
            
            await query.message.edit_text(
                f"✅ <b>Видео сохранено</b> в категорию «{cat_name}»",
                parse_mode='HTML'
            )
            context.user_data.pop('current_video', None)
    
    elif data.startswith("save_audio_"):
        cat_name = data[11:]  # убираем "save_audio_"
        current_audio = context.user_data.get('current_audio')
        
        if current_audio:
            if cat_name not in user_audios[user_id]:
                user_audios[user_id][cat_name] = []
            user_audios[user_id][cat_name].append(current_audio)
            
            await query.message.edit_text(
                f"✅ <b>Аудио сохранено</b> в категорию «{cat_name}»",
                parse_mode='HTML'
            )
            context.user_data.pop('current_audio', None)
    
    elif data.startswith("save_both_"):
        cat_name = data[10:]  # убираем "save_both_"
        saved = []
        
        current_video = context.user_data.get('current_video')
        if current_video:
            if cat_name not in user_videos[user_id]:
                user_videos[user_id][cat_name] = []
            user_videos[user_id][cat_name].append(current_video)
            saved.append("видео")
            context.user_data.pop('current_video', None)
        
        current_audio = context.user_data.get('current_audio')
        if current_audio:
            if cat_name not in user_audios[user_id]:
                user_audios[user_id][cat_name] = []
            user_audios[user_id][cat_name].append(current_audio)
            saved.append("аудио")
            context.user_data.pop('current_audio', None)
        
        await query.message.edit_text(
            f"✅ <b>Сохранено:</b> {', '.join(saved)} в категорию «{cat_name}»",
            parse_mode='HTML'
        )
    
    # ===== УПРАВЛЕНИЕ КАТЕГОРИЯМИ =====
    elif data == "back_to_categories":
        await show_categories(update, context)
    
    elif data.startswith("view_videos_"):
        cat_name = data[12:]
        await show_category_videos(update, context, user_id, cat_name)
    
    elif data.startswith("view_audios_"):
        cat_name = data[11:]
        await show_category_audios(update, context, user_id, cat_name)
    
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
    
    if (user_id not in user_categories or not user_categories[user_id]) and \
       (user_id not in user_videos or not user_videos[user_id]) and \
       (user_id not in user_audios or not user_audios[user_id]):
        
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
    
    for cat in user_categories[user_id]:
        video_count = len(user_videos[user_id].get(cat, [])) if user_id in user_videos else 0
        audio_count = len(user_audios[user_id].get(cat, [])) if user_id in user_audios else 0
        
        text += f"• <b>{cat}</b> — 🎬{video_count} видео, 🎵{audio_count} аудио\n"
        
        # Кнопки для категории
        row = []
        if video_count > 0:
            row.append(InlineKeyboardButton(f"🎬 Видео", callback_data=f"view_videos_{cat}"))
        if audio_count > 0:
            row.append(InlineKeyboardButton(f"🎵 Аудио", callback_data=f"view_audios_{cat}"))
        keyboard.append(row)
        
        # Кнопки управления
        keyboard.append([
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
        await update.callback_query.message.reply_text(
            f"📁 <b>«{cat_name}»</b> — нет видео",
            parse_mode='HTML'
        )
        return
    
    videos = user_videos[user_id][cat_name]
    text = f"🎬 <b>Видео в «{cat_name}»</b> — {len(videos)} шт.\n\n"
    
    keyboard = []
    
    for i, video in enumerate(videos, 1):
        title = video['title'][:40] + "..." if len(video['title']) > 40 else video['title']
        size = video.get('size', 0)
        text += f"{i}. {title} ({size:.1f}MB)\n"
        
        keyboard.append([
            InlineKeyboardButton(f"▶️ Смотреть {i}", callback_data=f"play_video_{cat_name}_{i-1}"),
            InlineKeyboardButton(f"🗑️ Удалить {i}", callback_data=f"delvideo_{cat_name}_{i-1}")
        ])
    
    keyboard.append([InlineKeyboardButton("◀️ Назад к категориям", callback_data="back_to_categories")])
    
    await update.callback_query.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode='HTML'
    )

# ================== ПОКАЗ АУДИО В КАТЕГОРИИ ==================
async def show_category_audios(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id, cat_name):
    """Показывает все аудио в категории"""
    
    if cat_name not in user_audios[user_id] or not user_audios[user_id][cat_name]:
        await update.callback_query.message.reply_text(
            f"📁 <b>«{cat_name}»</b> — нет аудио",
            parse_mode='HTML'
        )
        return
    
    audios = user_audios[user_id][cat_name]
    text = f"🎵 <b>Аудио в «{cat_name}»</b> — {len(audios)} шт.\n\n"
    
    keyboard = []
    
    for i, audio in enumerate(audios, 1):
        title = audio['title'][:40] + "..." if len(audio['title']) > 40 else audio['title']
        size = audio.get('size', 0)
        text += f"{i}. {title} ({size:.1f}MB)\n"
        
        keyboard.append([
            InlineKeyboardButton(f"▶️ Слушать {i}", callback_data=f"play_audio_{cat_name}_{i-1}"),
            InlineKeyboardButton(f"🗑️ Удалить {i}", callback_data=f"delaudio_{cat_name}_{i-1}")
        ])
    
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
    
    if data.startswith("play_video_"):
        parts = data.split('_')
        cat_name = '_'.join(parts[2:-1])
        index = int(parts[-1])
        
        if (user_id in user_videos and 
            cat_name in user_videos[user_id] and 
            index < len(user_videos[user_id][cat_name])):
            
            video = user_videos[user_id][cat_name][index]
            
            if os.path.exists(video['path']):
                with open(video['path'], 'rb') as f:
                    await query.message.reply_video(
                        video=f,
                        caption=f"🎬 <b>{video['title'][:50]}</b>",
                        parse_mode='HTML'
                    )

# ================== ВОСПРОИЗВЕДЕНИЕ АУДИО ==================
async def play_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отправляет аудио из категории"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data.startswith("play_audio_"):
        parts = data.split('_')
        cat_name = '_'.join(parts[2:-1])
        index = int(parts[-1])
        
        if (user_id in user_audios and 
            cat_name in user_audios[user_id] and 
            index < len(user_audios[user_id][cat_name])):
            
            audio = user_audios[user_id][cat_name][index]
            
            if os.path.exists(audio['path']):
                with open(audio['path'], 'rb') as f:
                    await query.message.reply_audio(
                        audio=f,
                        title=audio['title'][:50],
                        caption=f"🎵 <b>Аудио</b>",
                        parse_mode='HTML'
                    )

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
        "• Бот пришлет видео, потом отдельно аудио\n"
        "• Выбери категорию для сохранения\n\n"
        
        "🔹 <b>ПРИМЕРЫ ССЫЛОК:</b>\n"
        "• Instagram: instagram.com/reel/...\n"
        "• TikTok: tiktok.com/@user/video/...\n"
        "• YouTube: youtu.be/...\n"
        "• Pinterest: pin.it/...\n\n"
        
        "🔹 <b>ФОРМАТ:</b>\n"
        "• Видео: MP4\n"
        "• Аудио: MP3 (192 kbps)\n\n"
        
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

# ================== СТАТИСТИКА ==================
async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает статистику пользователя"""
    user_id = update.effective_user.id
    
    total_categories = len(user_categories.get(user_id, []))
    total_videos = 0
    total_audios = 0
    
    if user_id in user_videos:
        for cat in user_videos[user_id]:
            total_videos += len(user_videos[user_id][cat])
    
    if user_id in user_audios:
        for cat in user_audios[user_id]:
            total_audios += len(user_audios[user_id][cat])
    
    stats_text = (
        f"📊 <b>Ваша статистика:</b>\n\n"
        f"📁 Категорий: {total_categories}\n"
        f"🎬 Видео: {total_videos}\n"
        f"🎵 Аудио: {total_audios}\n"
        f"📦 Всего файлов: {total_videos + total_audios}"
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

# ================== ОБРАБОТКА ТЕКСТА ==================
async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает текстовые сообщения"""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    if context.user_data.get('waiting_for_category_both'):
        if user_id not in user_categories:
            user_categories[user_id] = []
        
        if text not in user_categories[user_id]:
            user_categories[user_id].append(text)
            
            # Сохраняем файлы в новую категорию
            saved = []
            
            if 'current_video' in context.user_data:
                if user_id not in user_videos:
                    user_videos[user_id] = {}
                if text not in user_videos[user_id]:
                    user_videos[user_id][text] = []
                user_videos[user_id][text].append(context.user_data['current_video'])
                saved.append("видео")
                context.user_data.pop('current_video', None)
            
            if 'current_audio' in context.user_data:
                if user_id not in user_audios:
                    user_audios[user_id] = {}
                if text not in user_audios[user_id]:
                    user_audios[user_id][text] = []
                user_audios[user_id][text].append(context.user_data['current_audio'])
                saved.append("аудио")
                context.user_data.pop('current_audio', None)
            
            await update.message.reply_text(
                f"✅ <b>Категория «{text}» создана!</b>\n"
                f"Сохранено: {', '.join(saved)}",
                parse_mode='HTML'
            )
        else:
            await update.message.reply_text(
                f"❌ <b>Категория «{text}» уже существует</b>",
                parse_mode='HTML'
            )
        
        context.user_data['waiting_for_category_both'] = False
    
    elif context.user_data.get('waiting_for_rename'):
        old_name = context.user_data.get('rename_category')
        new_name = text
        
        if user_id in user_categories and old_name in user_categories[user_id]:
            index = user_categories[user_id].index(old_name)
            user_categories[user_id][index] = new_name
            
            # Переименовываем в видео
            if user_id in user_videos and old_name in user_videos[user_id]:
                user_videos[user_id][new_name] = user_videos[user_id].pop(old_name)
            
            # Переименовываем в аудио
            if user_id in user_audios and old_name in user_audios[user_id]:
                user_audios[user_id][new_name] = user_audios[user_id].pop(old_name)
            
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

# ================== ЗАПУСК БОТА ==================
def main():
    """Главная функция запуска"""
    print("🔄 Запуск бота...")
    print("🎬 Режим: видео + отдельно аудио")
    
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
    app.add_handler(CallbackQueryHandler(button_handler, pattern='^(show_commands|go_to_categories|show_stats|back_to_start|skip_all|new_category_both|back_to_save_options|choose_cat_|save_video_|save_audio_|save_both_|back_to_categories|view_videos_|view_audios_|rename_|delete_)$'))
    app.add_handler(CallbackQueryHandler(play_video, pattern='^play_video_'))
    app.add_handler(CallbackQueryHandler(play_audio, pattern='^play_audio_'))
    
    # Текст
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    
    print("✅ Бот успешно запущен!")
    print("🤖 @SaveVideosInsbot")
    print("📁 /categories - управление категориями")
    print("🎬 Сначала видео, потом 🎵 аудио отдельно!")
    
    app.run_polling()

if __name__ == '__main__':
    main()
