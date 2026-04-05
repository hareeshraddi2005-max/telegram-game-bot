print("TOKEN:", TOKEN)
print("ADMIN:", ADMIN_ID)
print("MONGO:", MONGO_URI)
import logging
import threading
from flask import Flask
from pymongo import MongoClient

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)

# ===== CONFIG =====
TOKEN = "8227958604:AAECXGzNpCW0Qg3JOevvzdWjzFNBl5eiOF8"
ADMIN_ID = 7254020951
MONGO_URI = "mongodb+srv://hp848293093_db_user:4SMYd31qZqK8eVJF@cluster0.w6siu4p.mongodb.net/?appName=Cluster0"

# ===== SETUP =====
logging.basicConfig(level=logging.INFO)

client = MongoClient(MONGO_URI)
db = client["telegram_shop"]
games_collection = db["games"]

user_state = {}

# ===== WEB SERVER (for Render) =====
app = Flask(__name__)

@app.route('/')
def home():
    return "Bot is running!"

def run_web():
    app.run(host="0.0.0.0", port=10000)

# ===== START =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🎮 Steam", callback_data="steam")],
        [InlineKeyboardButton("🎯 Epic", callback_data="epic")]
    ]

    await update.message.reply_text(
        "🔥 Welcome to Game Store!\nChoose platform:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ===== PLATFORM SELECT =====
async def platform_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    platform = query.data

    games = list(games_collection.find({"platform": platform}))

    if not games:
        await query.message.reply_text("❌ No games available")
        return

    keyboard = []
    for g in games:
        keyboard.append([
            InlineKeyboardButton(
                g["name"],
                callback_data=f"buy_{g['_id']}"
            )
        ])

    await query.message.reply_text(
        "🎮 Select a game:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ===== BUY GAME =====
async def buy_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    game_id = query.data.replace("buy_", "")
    game = games_collection.find_one({"_id": game_id})

    user = query.from_user

    if not game:
        await query.message.reply_text("Game not found ❌")
        return

    text = f"""
🛒 New Order

👤 User: @{user.username}
🆔 ID: {user.id}

🎮 Game: {game['name']}
💰 Price: {game['price']}
🖥 Platform: {game['platform']}
"""

    await context.bot.send_message(chat_id=ADMIN_ID, text=text)

    await query.message.reply_text(
        "✅ Order sent! Admin will contact you."
    )

# ===== ADMIN PANEL =====
async def admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.from_user.id != ADMIN_ID:
        return

    keyboard = [
        [InlineKeyboardButton("➕ Add Game", callback_data="add_game")],
        [InlineKeyboardButton("❌ Delete Game", callback_data="delete_game")],
        [InlineKeyboardButton("📦 View Games", callback_data="view_games")]
    ]

    await update.message.reply_text(
        "🛠 Admin Panel",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ===== ADMIN BUTTON HANDLER =====
async def admin_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id

    if user_id != ADMIN_ID:
        return

    if query.data == "add_game":
        user_state[user_id] = {"step": "name"}
        await query.message.reply_text("Enter game name:")

    elif query.data == "delete_game":
        games = list(games_collection.find())

        if not games:
            await query.message.reply_text("No games to delete")
            return

        keyboard = []
        for g in games:
            keyboard.append([
                InlineKeyboardButton(
                    g["name"],
                    callback_data=f"del_{g['_id']}"
                )
            ])

        await query.message.reply_text(
            "Select game to delete:",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

    elif query.data == "view_games":
        games = list(games_collection.find())

        if not games:
            await query.message.reply_text("No games available")
            return

        text = "📦 Game List:\n\n"
        for g in games:
            text += f"{g['name']} | {g['price']} | {g['platform']}\n"

        await query.message.reply_text(text)

# ===== DELETE GAME =====
async def delete_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.from_user.id != ADMIN_ID:
        return

    game_id = query.data.replace("del_", "")
    games_collection.delete_one({"_id": game_id})

    await query.message.reply_text("❌ Game deleted")

# ===== ADMIN INPUT FLOW =====
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    if user_id not in user_state:
        return

    data = user_state[user_id]
    text = update.message.text

    if data["step"] == "name":
        data["name"] = text
        data["step"] = "platform"
        await update.message.reply_text("Enter platform (steam/epic):")

    elif data["step"] == "platform":
        data["platform"] = text.lower()
        data["step"] = "price"
        await update.message.reply_text("Enter price:")

    elif data["step"] == "price":
        data["price"] = text
        data["step"] = "description"
        await update.message.reply_text("Enter description:")

    elif data["step"] == "description":
        data["description"] = text

        # SAVE TO DB
        game_id = str(len(list(games_collection.find())) + 1)

        games_collection.insert_one({
            "_id": game_id,
            "name": data["name"],
            "platform": data["platform"],
            "price": data["price"],
            "description": data["description"]
        })

        user_state.pop(user_id)

        await update.message.reply_text("✅ Game added successfully!")

# ===== MAIN =====
def main():
    threading.Thread(target=run_web).start()

    app_bot = ApplicationBuilder().token(TOKEN).build()

    app_bot.add_handler(CommandHandler("start", start))
    app_bot.add_handler(CommandHandler("admin", admin))

    app_bot.add_handler(CallbackQueryHandler(platform_choice, pattern="^(steam|epic)$"))
    app_bot.add_handler(CallbackQueryHandler(buy_game, pattern="^buy_"))
    app_bot.add_handler(CallbackQueryHandler(delete_game, pattern="^del_"))
    app_bot.add_handler(CallbackQueryHandler(admin_buttons))

    app_bot.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot running...")
    app_bot.run_polling()

if __name__ == "__main__":
    main()
