import os
import logging
import re
from datetime import datetime
from dotenv import load_dotenv
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    CallbackQueryHandler
)
import requests

# Загрузка переменных окружения
load_dotenv()

# Настройка логгера
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

USER_PREFERENCES = {}

# ================== КОМАНДЫ ================== #
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start с интерактивным меню"""
    keyboard = [
        ["🌤 Текущая погода", "📅 Прогноз"],
        ["⚙️ Настройки", "❓ Помощь"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        'Привет! Я погодный бот. Выбери действие:',
        reply_markup=reply_markup
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    help_text = (
        "📚 *Доступные команды:*\n\n"
        "🌤 *Текущая погода* - Отправь название города или нажми кнопку\n"
        "📅 *Прогноз* - Показать прогноз погоды на 3 дня\n"
        "⚙️ *Настройки* - Изменить единицы измерения (°C/°F)\n"
        "/help - Показать это сообщение\n"
        "/units - Изменить единицы измерения\n"
        "/forecast [город] - Прогноз погоды для конкретного города\n\n"
        "Просто отправь мне название города, и я покажу погоду!"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

# ================== НАСТРОЙКИ ================== #
async def set_units(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор единиц измерения температуры"""
    keyboard = [[
        InlineKeyboardButton('°C (Цельсий)', callback_data='unit_c'),
        InlineKeyboardButton('°F (Фаренгейт)', callback_data='unit_f')
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Выберите единицы измерения:', reply_markup=reply_markup)

# ================== ПОГОДА ================== #
def validate_city(city: str) -> bool:
    """Валидация названия города"""
    return bool(re.match(r'^[A-Za-zА-Яа-я\s-]{2,50}$', city))

async def get_weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение текущей погоды"""
    city = update.message.text
    
    if not validate_city(city):
        await update.message.reply_text("❌ Некорректное название города. Используйте только буквы и дефис!")
        return
    
    try:
        user_id = update.message.from_user.id
        units = USER_PREFERENCES.get(user_id, 'c')
        api_key = os.getenv('OWM_API_KEY')
        api_units = 'metric' if units == 'c' else 'imperial'
        
        url = f'http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units={api_units}&lang=ru'
        response = requests.get(url)
        response.raise_for_status()
        
        data = response.json()
        temp = int(data['main']['temp'])
        temp_symbol = '°C' if units == 'c' else '°F'
        
        weather_info = (
            f"🌆 *Город:* {data['name']}\n"
            f"🌡 *Температура:* {temp}{temp_symbol}\n"
            f"💨 *Ветер:* {data['wind']['speed']} м/с\n"
            f"☁️ *Описание:* {data['weather'][0]['description'].capitalize()}"
        )
        
        keyboard = [[
            InlineKeyboardButton('📅 Прогноз на 3 дня', callback_data=f'forecast_{city}'),
            InlineKeyboardButton('⚙️ Изменить единицы', callback_data='change_units')
        ]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(weather_info, parse_mode='Markdown', reply_markup=reply_markup)

    except requests.exceptions.HTTPError as e:
        if response.status_code == 404:
            await update.message.reply_text("❌ Город не найден. Проверьте написание и попробуйте снова!")
        else:
            await update.message.reply_text("😞 Ошибка при запросе к API погоды")
        logger.error(f"Weather API error: {e}")
    except Exception as e:
        await update.message.reply_text("⚠️ Внутренняя ошибка. Попробуйте позже")
        logger.error(f"General error: {e}")

# ================== ПРОГНОЗ ================== #
async def get_forecast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Получение прогноза погоды"""
    try:
        city = None
        chat_id = None

        # Определяем источник запроса
        if update.callback_query:
            query = update.callback_query
            city = query.data.split('_')[1]
            chat_id = query.message.chat_id
        elif context.args:
            city = ' '.join(context.args)
            chat_id = update.message.chat_id
        else:
            await update.message.reply_text("Укажите город: /forecast <город>")
            return

        user_id = update.effective_user.id
        units = USER_PREFERENCES.get(user_id, 'c')
        api_units = 'metric' if units == 'c' else 'imperial'
        api_key = os.getenv('OWM_API_KEY')

        url = f'http://api.openweathermap.org/data/2.5/forecast?q={city}&appid={api_key}&units={api_units}&lang=ru'
        response = requests.get(url)
        response.raise_for_status()
        
        data = response.json()
        forecast_text = f'📅 Прогноз погоды в {city} на 3 дня:\n'
        temp_symbol = '°C' if units == 'c' else '°F'

        for i in range(0, 24, 8):
            day_data = data['list'][i]
            date = datetime.strptime(day_data['dt_txt'], '%Y-%m-%d %H:%M:%S').strftime('%d.%m.%Y')
            temp = int(day_data['main']['temp'])
            desc = day_data['weather'][0]['description'].capitalize()
            forecast_text += f'📆 {date}: 🌡 {temp}{temp_symbol}, ☁ {desc}\n'

        await context.bot.send_message(chat_id=chat_id, text=forecast_text)

    except requests.exceptions.HTTPError as e:
        error_text = "❌ Ошибка при получении данных" if e.response.status_code != 404 else "❌ Город не найден"
        await context.bot.send_message(chat_id=chat_id, text=error_text)
        logger.error(f"Forecast API error: {e}")
    except Exception as e:
        await context.bot.send_message(chat_id=chat_id, text="⚠️ Внутренняя ошибка")
        logger.error(f"Forecast error: {e}")

# ================== КНОПКИ ================== #
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик инлайн-кнопок"""
    query = update.callback_query
    await query.answer()
    
    try:
        if query.data.startswith('forecast_'):
            await get_forecast(update, context)
            
        elif query.data == 'change_units':
            keyboard = [[
                InlineKeyboardButton('°C (Цельсий)', callback_data='unit_c'),
                InlineKeyboardButton('°F (Фаренгейт)', callback_data='unit_f')
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.message.reply_text('Выберите единицы измерения:', reply_markup=reply_markup)
            
        elif query.data.startswith('unit_'):
            unit = query.data.split('_')[1]
            USER_PREFERENCES[query.from_user.id] = unit
            unit_name = 'Цельсий' if unit == 'c' else 'Фаренгейт'
            await query.message.reply_text(f"✅ Установлены единицы измерения: {unit_name}")
            
    except Exception as e:
        logger.error(f"Button callback error: {e}")
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="❌ Ошибка при обработке запроса"
        )

# ================== ТЕКСТ ================== #
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений"""
    text = update.message.text
    if text == "🌤 Текущая погода":
        await update.message.reply_text("Отправьте название города:")
    elif text == "📅 Прогноз":
        await update.message.reply_text("Отправьте название города для прогноза:")
    elif text == "⚙️ Настройки":
        await set_units(update, context)
    elif text == "❓ Помощь":
        await help_command(update, context)
    else:
        await get_weather(update, context)

def main():
    """Запуск бота"""
    app = Application.builder().token(os.getenv('TELEGRAM_BOT_TOKEN')).build()
    
    # Регистрация обработчиков
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("units", set_units))
    app.add_handler(CommandHandler("forecast", get_forecast))
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    # Запуск бота
    app.run_polling()

if __name__ == '__main__':
    main()