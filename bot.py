import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from openai import OpenAI

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
API_KEY = os.environ.get("API_KEY")
API_BASE_URL = os.environ.get("API_BASE_URL", "https://api.chr6.com/v1")
DEFAULT_MODEL = os.environ.get("DEFAULT_MODEL", "[xy6-按量计费]claude-opus-4-6-thinking")

MODELS = [
    "[xy6-按量计费]claude-opus-4-6-thinking",
]

client = OpenAI(api_key=API_KEY, base_url=API_BASE_URL)
user_data = {}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("你好！直接发消息开聊~\n/model 切换模型\n/clear 清空对话")

async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in user_data:
        user_data[user_id]["history"] = []
    await update.message.reply_text("已清空~")

async def model_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton(m, callback_data=f"model:{m}")] for m in MODELS]
    await update.message.reply_text("选择模型：", reply_markup=InlineKeyboardMarkup(keyboard))

async def model_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    model = query.data.replace("model:", "")
    user_id = query.from_user.id
    if user_id not in user_data:
        user_data[user_id] = {"history": [], "model": DEFAULT_MODEL}
    user_data[user_id]["model"] = model
    await query.edit_message_text(f"已切换到：{model}")

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_data:
        user_data[user_id] = {"history": [], "model": DEFAULT_MODEL}
    user_data[user_id]["history"].append({"role": "user", "content": update.message.text})
    if len(user_data[user_id]["history"]) > 20:
        user_data[user_id]["history"] = user_data[user_id]["history"][-20:]
    msg = await update.message.reply_text("思考中...")
    try:
        response = client.chat.completions.create(
            model=user_data[user_id]["model"],
            messages=user_data[user_id]["history"],
            max_tokens=4096,
        )
        reply = response.choices[0].message.content
        user_data[user_id]["history"].append({"role": "assistant", "content": reply})
        await msg.edit_text(reply)
    except Exception as e:
        await msg.edit_text(f"出错了：{str(e)}")

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("clear", clear))
    app.add_handler(CommandHandler("model", model_command))
    app.add_handler(CallbackQueryHandler(model_callback, pattern="^model:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    app.run_polling()

if __name__ == "__main__":
    main()
    
