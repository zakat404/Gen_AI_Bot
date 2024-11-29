from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
import os
import requests
import uuid
from g4f.client import Client
import g4f.models
from dotenv import load_dotenv

load_dotenv()

# Папка для сохранения изображений
OUTPUT_FOLDER = "images_gen"
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

# Генерация изображения через flux-realism
def generate_image(prompt, output_name):

    providers = ["Airforce", "AmigoChat"]

    for provider in providers:
        try:
            print(f"Попытка генерации через провайдера: {provider}")

            response = g4f.ChatCompletion.create(
                model="flux-realism",
                provider=provider,  # Указываем текущего провайдера
                messages=[{"role": "user", "content": f"Generate an image: {prompt}"}]
            )

            if response and "](" in response:
                image_url = response.split("](")[1].split(")")[0]
                image_data = requests.get(image_url, timeout=120).content
                output_path = os.path.join(OUTPUT_FOLDER, output_name)

# Сохранение изображения
                with open(output_path, "wb") as f:
                    f.write(image_data)
                print(f"Изображение успешно сгенерировано через провайдера: {provider}")
                return output_path
            else:
                print(f"Провайдер {provider} не смог сгенерировать изображение. Переход к следующему.")

        except Exception as e:
            print(f"Ошибка при использовании провайдера {provider}: {e}")


    print("Все провайдеры не смогли выполнить запрос. Проверьте соединение или баланс.")
    return None
# Генерация промта через GPT
def generate_prompt(user_message):
    try:
        client = Client()
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Ты создаешь промты для генерации реалистичных изображений. "
                        "Пиши подробные, детализированные описания сцены, включая освещение, фон, атмосферу, эмоции и важные детали. "
                        "Фотографии должны быть реалистичными и в хорошем качестве. "
                        "Текст должен быть на английском языке. "
                        "Не задавай уточняющих вопросов, просто пиши промт."
                    )
                },
                {"role": "user", "content": user_message}
            ]
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error generating prompt: {e}")
        return None


#/start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("Привет! Что умеет бот?", callback_data="about_bot")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Добро пожаловать в бота для генерации изображений! Нажмите на кнопку, чтобы узнать больше.",
        reply_markup=reply_markup,
    )


# Обработка кнопок
async def handle_about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    keyboard = [[InlineKeyboardButton("Продолжить", callback_data="start_prompt")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text="Этот бот может помочь вам создать изображения по вашим описаниям. Вы можете использовать свой текст или улучшить его с помощью GPT-4o. Нажмите 'Продолжить', чтобы начать.",
        reply_markup=reply_markup,
    )


async def handle_continue(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    keyboard = [
        [
            InlineKeyboardButton("Улучшить промт через GPT-4o", callback_data="expand_prompt"),
            InlineKeyboardButton("Использовать мой текст", callback_data="use_my_prompt"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(
        text="Выберите, хотите ли вы улучшить промт через GPT-4o или использовать ваш текст без изменений:",
        reply_markup=reply_markup,
    )


async def handle_user_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action = query.data

    context.user_data["use_gpt"] = action == "expand_prompt"

    await query.edit_message_text(
        text="Ожидаем ваш промт для генерации. Пожалуйста, отправьте его."
    )


# Обработка промта пользователя
async def handle_user_prompt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_message = update.message.text
    use_gpt = context.user_data.get("use_gpt", False)

    if use_gpt:
        await update.message.reply_text("Улучшаем ваш промт... Пожалуйста, подождите.")
        final_prompt = generate_prompt(user_message)
        if not final_prompt:
            await update.message.reply_text("Не удалось улучшить промт. Используем ваш текст.")
            final_prompt = user_message
    else:
        final_prompt = user_message

    context.user_data["final_prompt"] = final_prompt

    keyboard = [
        [
            InlineKeyboardButton("1", callback_data="generate_1"),
            InlineKeyboardButton("2", callback_data="generate_2"),
            InlineKeyboardButton("3", callback_data="generate_3"),
            InlineKeyboardButton("4", callback_data="generate_4"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "Выберите количество изображений для генерации:",
        reply_markup=reply_markup,
    )


# Генерация картинок
async def handle_generate_images(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    action = query.data
    count = int(action.split("_")[1])  # Получаем количество изображений
    prompt = context.user_data.get("final_prompt", "Default prompt")
    await query.edit_message_text(f"Генерация {count} изображения(ий)... Пожалуйста, подождите.")

    generated_files = []
    for i in range(count):
        output_name = f"{uuid.uuid4()}.png"
        image_path = generate_image(prompt, output_name)
        if image_path:
            generated_files.append(image_path)
        else:
            await query.message.reply_text(f"Ошибка при генерации изображения {i + 1}.")

    if generated_files:
        media_group = [InputMediaPhoto(open(file_path, "rb")) for file_path in generated_files]
        await query.message.reply_media_group(media_group)

        for file_path in generated_files:
            os.remove(file_path)

    keyboard = [[InlineKeyboardButton("Новая генерация", callback_data="start_prompt")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.message.reply_text("Нажмите 'Новая генерация', чтобы создать новое изображение.", reply_markup=reply_markup)


def main():
    TOKEN = os.getenv("TELEGRAM_TOKEN")
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(handle_about, pattern="about_bot"))
    app.add_handler(CallbackQueryHandler(handle_continue, pattern="start_prompt"))
    app.add_handler(CallbackQueryHandler(handle_user_choice, pattern="expand_prompt|use_my_prompt"))
    app.add_handler(CallbackQueryHandler(handle_generate_images, pattern="generate_1|generate_2|generate_3|generate_4"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_prompt))

    print("Бот запущен!")
    app.run_polling()


if __name__ == "__main__":
    main()
