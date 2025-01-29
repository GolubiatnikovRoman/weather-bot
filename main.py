import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import requests

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Привет! Отправь мне название города на русском, и я покажу погоду.')

async def get_weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
    city = update.message.text
    api_key = os.getenv('OWM_API_KEY')
    url = f'http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric&lang=ru'
    
    try:
        response = requests.get(url)
        data = response.json()
        
        if response.status_code == 200:
            weather = (
                f"🌆 Город: {data['name']}\n"
                f"🌡 Температура: {int(data['main']['temp'])}°C\n"  # Целое число
                f"💨 Ветер: {data['wind']['speed']} м/с\n"
                f"☁️ Описание: {data['weather'][0]['description'].capitalize()}"
            )
            await update.message.reply_text(weather)
        else:
            await update.message.reply_text("Город не найден. Попробуйте еще раз.")
            
    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await update.message.reply_text("Произошла ошибка. Попробуйте позже.")

def main():
    app = Application.builder().token(os.getenv('TELEGRAM_BOT_TOKEN')).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, get_weather))
    app.run_polling()

if __name__ == '__main__':
    main()