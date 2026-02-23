import os
import yt_dlp
import certifi
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

# ТОКЕН
BOT_TOKEN = '8431619576:AAFDh6Lee8mqDVZ5_BiAgTDDrHQvUAXGt5o'

# Устанавливаем сертификаты
os.environ['SSL_CERT_FILE'] = certifi.where()
os.environ['REQUESTS_CA_BUNDLE'] = certifi.where()

# Хранилище
user_categories = {}  # {user_id: [категории]}
user_videos = {}      # {user_id: {category: [видео]}}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет! Я бот для скачивания видео\n\n"
        "📱 Отправь мне ссылку на видео\n"
        "📁 Используй /categories чтобы управлять категориями"
    )

async def handle_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    link = update.message.text
    user_id = update.effective_user.id
    
    msg = await update.message.reply_text("⏳ Скачиваю видео...")
    
    try:
        os.makedirs(f'downloads/{user_id}', exist_ok=True)
        
        ydl_opts = {
            'format': 'best[ext=mp4]/best',
            'outtmpl': f'downloads/{user_id}/%(title)s.%(ext)s',
            'quiet': True,
            'socket_timeout': 30,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(link, download=True)
            
            # Ищем файл
            filename = None
            for file in os.listdir(f'downloads/{user_id}'):
                if file.endswith('.mp4'):
                    filename = f'downloads/{user_id}/{file}'
                    video_title = file.replace('.mp4', '')
                    break
            
            if filename:
                context.user_data['current_video'] = {
                    'path': filename,
                    'title': video_title,
                    'url': link
                }
                
                with open(filename, 'rb') as f:
                    await update.message.reply_video(f, caption="✅ Видео скачано!")
                
                await msg.delete()
                
                # Кнопки категорий
                keyboard = []
                
                if user_id not in user_categories:
                    user_categories[user_id] = []
                if user_id not in user_videos:
                    user_videos[user_id] = {}
                
                for cat in user_categories[user_id]:
                    keyboard.append([InlineKeyboardButton(f"📁 {cat}", callback_data=f"cat_{cat}")])
                
                keyboard.append([InlineKeyboardButton("➕ Новая категория", callback_data="new")])
                keyboard.append([InlineKeyboardButton("⏭ Пропустить", callback_data="skip")])
                
                await update.message.reply_text(
                    "💾 Сохранить видео?",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
            else:
                await msg.edit_text("❌ Файл не найден")
                
    except Exception as e:
        await msg.edit_text(f"❌ Ошибка: {str(e)[:100]}")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    await query.message.delete()
    
    if data == "skip":
        await query.message.reply_text("✅ Хорошо!")
        context.user_data.pop('current_video', None)
        
    elif data == "new":
        await query.message.reply_text("✏️ Введите название категории:")
        context.user_data['waiting_for_category'] = True
        
    elif data.startswith("cat_"):
        cat_name = data[4:]
        current_video = context.user_data.get('current_video')
        
        if current_video:
            if cat_name not in user_videos[user_id]:
                user_videos[user_id][cat_name] = []
            
            user_videos[user_id][cat_name].append({
                'title': current_video['title'],
                'path': current_video['path'],
                'url': current_video['url']
            })
            
            await query.message.reply_text(f"✅ Видео сохранено в '{cat_name}'!")
        else:
            await query.message.reply_text("❌ Ошибка")
        
        context.user_data.pop('current_video', None)

async def text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    if context.user_data.get('waiting_for_category'):
        if user_id not in user_categories:
            user_categories[user_id] = []
        
        if text not in user_categories[user_id]:
            user_categories[user_id].append(text)
            
            current_video = context.user_data.get('current_video')
            if current_video:
                if user_id not in user_videos:
                    user_videos[user_id] = {}
                if text not in user_videos[user_id]:
                    user_videos[user_id][text] = []
                
                user_videos[user_id][text].append(current_video)
                await update.message.reply_text(f"✅ Категория '{text}' создана! Видео сохранено.")
                context.user_data.pop('current_video', None)
            else:
                await update.message.reply_text(f"✅ Категория '{text}' создана!")
        else:
            await update.message.reply_text(f"❌ Категория уже существует")
        
        context.user_data['waiting_for_category'] = False
    elif context.user_data.get('waiting_for_rename'):
        # Переименование категории
        old_name = context.user_data.get('rename_category')
        new_name = text
        
        if user_id in user_categories and old_name in user_categories[user_id]:
            # Переименовываем в списке категорий
            index = user_categories[user_id].index(old_name)
            user_categories[user_id][index] = new_name
            
            # Переименовываем в словаре видео
            if user_id in user_videos and old_name in user_videos[user_id]:
                user_videos[user_id][new_name] = user_videos[user_id].pop(old_name)
            
            await update.message.reply_text(f"✅ Категория '{old_name}' переименована в '{new_name}'!")
        else:
            await update.message.reply_text(f"❌ Категория не найдена")
        
        context.user_data['waiting_for_rename'] = False
        context.user_data.pop('rename_category', None)
    else:
        await handle_link(update, context)

async def show_categories(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id in user_categories and user_categories[user_id]:
        text = "📁 <b>Управление категориями:</b>\n\n"
        
        for i, cat in enumerate(user_categories[user_id], 1):
            video_count = 0
            if user_id in user_videos and cat in user_videos[user_id]:
                video_count = len(user_videos[user_id][cat])
            
            text += f"{i}. {cat} <i>({video_count} видео)</i>\n"
        
        text += "\nВыберите действие:"
        
        # Создаем кнопки для каждой категории
        keyboard = []
        for cat in user_categories[user_id]:
            row = [
                InlineKeyboardButton(f"✏️ {cat}", callback_data=f"rename_{cat}"),
                InlineKeyboardButton(f"🗑 {cat}", callback_data=f"delete_{cat}")
            ]
            keyboard.append(row)
        
        await update.message.reply_text(
            text, 
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    else:
        await update.message.reply_text("📁 У вас пока нет категорий")

async def category_action_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопок управления категориями"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    data = query.data
    
    if data.startswith("delete_"):
        cat_name = data[7:]
        
        if user_id in user_categories and cat_name in user_categories[user_id]:
            # Удаляем категорию
            user_categories[user_id].remove(cat_name)
            
            # Удаляем видео
            if user_id in user_videos and cat_name in user_videos[user_id]:
                for video in user_videos[user_id][cat_name]:
                    try:
                        if os.path.exists(video['path']):
                            os.remove(video['path'])
                    except:
                        pass
                del user_videos[user_id][cat_name]
            
            await query.edit_message_text(f"✅ Категория '{cat_name}' удалена!")
        else:
            await query.edit_message_text(f"❌ Категория не найдена")
    
    elif data.startswith("rename_"):
        cat_name = data[7:]
        context.user_data['waiting_for_rename'] = True
        context.user_data['rename_category'] = cat_name
        await query.edit_message_text(f"✏️ Введите новое название для категории '{cat_name}':")

async def delete_category_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для быстрого удаления категории"""
    user_id = update.effective_user.id
    
    if not context.args:
        await show_categories(update, context)
        return
    
    cat_name = ' '.join(context.args)
    
    if user_id in user_categories and cat_name in user_categories[user_id]:
        user_categories[user_id].remove(cat_name)
        
        if user_id in user_videos and cat_name in user_videos[user_id]:
            del user_videos[user_id][cat_name]
        
        await update.message.reply_text(f"✅ Категория '{cat_name}' удалена!")
    else:
        await update.message.reply_text(f"❌ Категория не найдена")

async def rename_category_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для быстрого переименования категории"""
    user_id = update.effective_user.id
    
    if len(context.args) < 2:
        await update.message.reply_text(
            "❌ Использование: /rename старая_категория новая_категория\n"
            "Пример: /rename Мои видео Любимые видео"
        )
        return
    
    old_name = context.args[0]
    new_name = ' '.join(context.args[1:])
    
    if user_id in user_categories and old_name in user_categories[user_id]:
        index = user_categories[user_id].index(old_name)
        user_categories[user_id][index] = new_name
        
        if user_id in user_videos and old_name in user_videos[user_id]:
            user_videos[user_id][new_name] = user_videos[user_id].pop(old_name)
        
        await update.message.reply_text(f"✅ Категория '{old_name}' переименована в '{new_name}'!")
    else:
        await update.message.reply_text(f"❌ Категория '{old_name}' не найдена")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📱 <b>Команды бота:</b>\n\n"
        "/start - Начать работу\n"
        "/categories - Управление категориями\n"
        "/deletecat [название] - Удалить категорию\n"
        "/rename [старое] [новое] - Переименовать\n"
        "/help - Эта справка\n\n"
        "<b>Примеры:</b>\n"
        "/deletecat Мои видео\n"
        "/rename Мои Любимые\n\n"
        "Или просто /categories для удобного меню"
    )
    
    await update.message.reply_text(help_text, parse_mode='HTML')

def main():
    # Создаем папку для загрузок
    os.makedirs('downloads', exist_ok=True)
    
    # Запускаем бота
    app = Application.builder().token(BOT_TOKEN).build()
    
    # Добавляем обработчики
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("categories", show_categories))
    app.add_handler(CommandHandler("deletecat", delete_category_command))
    app.add_handler(CommandHandler("rename", rename_category_command))
    
    # Обработчики кнопок
    app.add_handler(CallbackQueryHandler(button_handler, pattern='^(cat_|new|skip)$'))
    app.add_handler(CallbackQueryHandler(category_action_callback, pattern='^(delete_|rename_)'))
    
    # Обработчик текста
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    
    print("✅ Бот запущен!")
    print(f"🤖 @SaveVideosInsbot")
    print("📱 Отправьте боту ссылку на видео")
    print("📁 /categories - управление категориями")
    
    app.run_polling()

if __name__ == '__main__':
    main()