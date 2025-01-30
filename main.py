import os
import logging
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import requests

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

USER_PREFERENCES = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Привет! Отправь мне название города на русском, и я покажу погоду.')

async def set_units(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if context.args and context.args[0].lower() in ['c', 'f']:
        USER_PREFERENCES[user_id] = context.args[0].lower()
        unit_text = 'Цельсия' if context.args[0].lower() == 'c' else 'Фаренгейта'
        await update.message.reply_text(f'Единицы измерения установлены: {unit_text}')
    else:
        await update.message.reply_text('Используйте /units c или /units f для выбора единиц измерения.')

async def get_weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    city = update.message.text
    user_id = update.message.from_user.id
    units = USER_PREFERENCES.get(user_id, 'c')
    api_units = 'metric' if units == 'c' else 'imperial'
    api_key = os.getenv('OWM_API_KEY')
    url = f'http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units={api_units}&lang=ru'
    
    try:
        response = requests.get(url)
        data = response.json()
        
        if response.status_code == 200:
            temp = int(data['main']['temp'])
            wind = data['wind']['speed']
            desc = data['weather'][0]['description'].capitalize()
            temp_symbol = '°C' if units == 'c' else '°F'
            
            mood = '❄️ Очень холодно! Одевайтесь теплее!' if temp < 0 else '🌞 Отличная погода для прогулки!' if temp > 20 else '⛅️ Свежо, но комфортно!'
            weather = f"🌆 Город: {data['name']}\n🌡 Температура: {temp}{temp_symbol}\n💨 Ветер: {wind} м/с\n☁️ Описание: {desc}\n{mood}"
            
            keyboard = [[
                InlineKeyboardButton('Прогноз на 3 дня', callback_data=f'forecast_{city}'),
                InlineKeyboardButton('Изменить единицы', callback_data='change_units')
            ]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(weather, reply_markup=reply_markup)
        else:
            await update.message.reply_text("Город не найден. Попробуйте еще раз.")
            
    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await update.message.reply_text("Произошла ошибка. Попробуйте позже.")

async def get_forecast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    city = None
    
    if isinstance(update, Update) and update.message:
        city = ' '.join(context.args) if context.args else None
    elif update.callback_query:
        city = update.callback_query.data.split('_')[1]
    
    if not city:
        await update.callback_query.message.reply_text("Используйте /forecast <город>")
        return
    
    user_id = update.effective_user.id
    units = USER_PREFERENCES.get(user_id, 'c')
    api_units = 'metric' if units == 'c' else 'imperial'
    api_key = os.getenv('OWM_API_KEY')
    url = f'http://api.openweathermap.org/data/2.5/forecast?q={city}&appid={api_key}&units={api_units}&lang=ru'
    
    try:
        response = requests.get(url)
        data = response.json()
        
        if response.status_code == 200:
            forecast_text = f'📅 Прогноз погоды в {city} на 3 дня:\n'
            temp_symbol = '°C' if units == 'c' else '°F'
            
            for i in range(0, 24, 8):  # 3 дня (интервал каждые 8 часов)
                day_data = data['list'][i]
                date = day_data['dt_txt'].split(' ')[0]
                temp = int(day_data['main']['temp'])
                desc = day_data['weather'][0]['description'].capitalize()
                forecast_text += f'📅 {date}: {temp}{temp_symbol}, {desc}\n'
            
            await update.callback_query.message.reply_text(forecast_text)
        else:
            await update.callback_query.message.reply_text("Город не найден. Попробуйте еще раз.")
            
    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await update.callback_query.message.reply_text("Произошла ошибка. Попробуйте позже.")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data.startswith('forecast_'):
        city = query.data.split('_')[1]
        await get_forecast(query, context)
    elif query.data == 'change_units':
        await query.message.reply_text("Используйте /units c или /units f для выбора единиц измерения.")

def main():
    app = Application.builder().token(os.getenv('TELEGRAM_BOT_TOKEN')).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("units", set_units))
    app.add_handler(CommandHandler("forecast", get_forecast))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, get_weather))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    app.run_polling()

if __name__ == '__main__':
    main()
