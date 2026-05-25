import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from openai import OpenAI
from mem0 import MemoryClient

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
API_KEY = os.environ.get("API_KEY")
API_BASE_URL = os.environ.get("API_BASE_URL", "https://api.chr6.com/v1")
DEFAULT_MODEL = os.environ.get("DEFAULT_MODEL", "[xy6-按量计费]claude-opus-4-6-thinking")
MEM0_API_KEY = os.environ.get("MEM0_API_KEY")

MODELS = ["[xy6-按量计费]claude-opus-4-6-thinking"]
client = OpenAI(api_key=API_KEY, base_url=API_BASE_URL)
mem0 = MemoryClient(api_key=MEM0_API_KEY)
user_data = {}

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'ok')
    def log_message(self, format, *args):
        pass

def run_server():
    HTTPServer(('0.0.0.0', 10000), Handler).serve_forever()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("你好！直接发消息开聊~\n/model 切换模型\n/clear 清空对话\n/memory 查看记忆")

async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id in user_data:
        user_data[user_id]["history"] = []
    await update.message.reply_text("短期对话已清空~")

async def memory_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    try:
        result = mem0.get_all(filters={"user_id": user_id})
        if isinstance(result, dict):
            memories = result.get("results", [])
        else:
            memories = list(result) if result else []
        if not memories:
            await update.message.reply_text("还没有长期记忆~")
            return
        text = "\n".join([f"• {m['memory']}" for m in memories[:10]])
        await update.message.reply_text(f"我记得关于你的：\n{text}")
    except Exception as e:
        await update.message.reply_text(f"获取记忆失败：{str(e)}")

async def model_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton(m, callback_data=f"model:{m}")] for m in MODELS]
    await update.message.reply_text("选择模型：", reply_markup=InlineKeyboardMarkup(keyboard))

async def model_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    model = query.data.replace("model:", "")
    user_id = str(query.from_user.id)
    if user_id not in user_data:
        user_data[user_id] = {"history": [], "model": DEFAULT_MODEL}
    user_data[user_id]["model"] = model
    await query.edit_message_text(f"已切换到：{model}")

async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id not in user_data:
        user_data[user_id] = {"history": [], "model": DEFAULT_MODEL}

    user_message = update.message.text
    user_data[user_id]["history"].append({"role": "user", "content": user_message})
    if len(user_data[user_id]["history"]) > 20:
        user_data[user_id]["history"] = user_data[user_id]["history"][-20:]

    try:
        memories = mem0.search(user_message, user_id=user_id, limit=5)
        if isinstance(memories, dict):
            memories = memories.get("results", [])
        memory_text = "\n".join([m['memory'] for m in memories]) if memories else ""
    except:
        memory_text = ""

    messages = []
    if memory_text:
        messages.append({"role": "system", "content": f"以下是关于用户的长期记忆，请参考：\n{memory_text}"})
    messages += user_data[user_id]["history"]

    msg = await update.message.reply_text("思考中...")
    try:
        response = client.chat.completions.create(
            model=user_data[user_id]["model"],
            messages=messages,
            max_tokens=4096,
        )
        reply = response.choices[0].message.content
        user_data[user_id]["history"].append({"role": "assistant", "content": reply})
        await msg.edit_text(reply)

        mem0.add([
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": reply}
        ], user_id=user_id)
    except Exception as e:
        await msg.edit_text(f"出错了：{str(e)}")

def main():
    threading.Thread(target=run_server, daemon=True).start()
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("clear", clear))
    app.add_handler(CommandHandler("memory", memory_command))
    app.add_handler(CommandHandler("model", model_command))
    app.add_handler(CallbackQueryHandler(model_callback, pattern="^model:"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chat))
    app.run_polling()

if __name__ == "__main__":
    main()
