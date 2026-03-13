import os
import sqlite3
from datetime import datetime, date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

TOKEN = os.environ.get("BOT_TOKEN", "YOUR_TOKEN_HERE")
DB_PATH = "grivnatap.db"

# ── База данных ──────────────────────────────────────
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        coins INTEGER DEFAULT 0,
        taps INTEGER DEFAULT 0,
        referral_id INTEGER DEFAULT NULL,
        joined_at TEXT,
        last_daily TEXT DEFAULT NULL
    )''')
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = c.fetchone()
    conn.close()
    return user

def create_user(user_id, username, first_name, referral_id=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO users (user_id, username, first_name, coins, taps, referral_id, joined_at) VALUES (?,?,?,0,0,?,?)",
              (user_id, username, first_name, referral_id, datetime.now().isoformat()))
    # Бонус рефереру
    if referral_id:
        c.execute("UPDATE users SET coins=coins+500 WHERE user_id=?", (referral_id,))
    conn.commit()
    conn.close()

def add_coins(user_id, amount):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET coins=coins+?, taps=taps+1 WHERE user_id=?", (amount, user_id))
    conn.commit()
    conn.close()

def get_coins(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT coins, taps FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row if row else (0, 0)

def get_referral_count(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users WHERE referral_id=?", (user_id,))
    count = c.fetchone()[0]
    conn.close()
    return count

def get_top10():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT first_name, coins FROM users ORDER BY coins DESC LIMIT 10")
    rows = c.fetchall()
    conn.close()
    return rows

def claim_daily(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT last_daily FROM users WHERE user_id=?", (user_id,))
    row = c.fetchone()
    today = date.today().isoformat()
    if row and row[0] == today:
        conn.close()
        return False
    c.execute("UPDATE users SET coins=coins+200, last_daily=? WHERE user_id=?", (today, user_id))
    conn.commit()
    conn.close()
    return True

def get_total_users():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    count = c.fetchone()[0]
    conn.close()
    return count

# ── Клавиатуры ───────────────────────────────────────
def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("👆 ТАП (+10 монет)", callback_data="tap")],
        [InlineKeyboardButton("🎁 Ежедневная награда", callback_data="daily")],
        [InlineKeyboardButton("👥 Рефералы", callback_data="referrals"),
         InlineKeyboardButton("🏆 Топ игроков", callback_data="top")],
        [InlineKeyboardButton("💰 Мой баланс", callback_data="balance")],
    ])

# ── Команды ──────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    referral_id = None

    if args and args[0].isdigit():
        referral_id = int(args[0])
        if referral_id == user.id:
            referral_id = None

    existing = get_user(user.id)
    if not existing:
        create_user(user.id, user.username or "", user.first_name, referral_id)
        bonus_text = "\n🎉 *+500 монет* получил тот кто тебя пригласил!" if referral_id else ""
    else:
        bonus_text = ""

    coins, taps = get_coins(user.id)
    total = get_total_users()

    text = (
        f"👋 Привет, *{user.first_name}*!\n\n"
        f"🎮 Добро пожаловать в *GrivnaTap*!\n"
        f"💰 Тапай — копи монеты — получай награды!\n\n"
        f"💵 Твой баланс: *{coins} монет*\n"
        f"👆 Всего тапов: *{taps}*\n"
        f"👥 Игроков в игре: *{total}*\n"
        f"{bonus_text}\n\n"
        f"👇 Нажми *ТАП* чтобы начать!"
    )
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=main_keyboard())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    await query.answer()

    if query.data == "tap":
        add_coins(user.id, 10)
        coins, taps = get_coins(user.id)
        text = (
            f"👆 *+10 монет!*\n\n"
            f"💰 Баланс: *{coins} монет*\n"
            f"👆 Тапов: *{taps}*\n\n"
            f"Продолжай тапать! 🚀"
        )
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=main_keyboard())

    elif query.data == "daily":
        success = claim_daily(user.id)
        if success:
            coins, _ = get_coins(user.id)
            text = (
                f"🎁 *+200 монет!*\n\n"
                f"Ежедневная награда получена!\n"
                f"💰 Баланс: *{coins} монет*\n\n"
                f"Возвращайся завтра за новой наградой! 🔥"
            )
        else:
            coins, _ = get_coins(user.id)
            text = (
                f"⏰ Ты уже получил награду сегодня!\n\n"
                f"💰 Баланс: *{coins} монет*\n\n"
                f"Возвращайся завтра! 😄"
            )
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=main_keyboard())

    elif query.data == "referrals":
        ref_count = get_referral_count(user.id)
        ref_link = f"https://t.me/GrivnaTap_bot?start={user.id}"
        text = (
            f"👥 *Реферальная программа*\n\n"
            f"Приглашай друзей и получай *500 монет* за каждого!\n\n"
            f"👤 Твоих рефералов: *{ref_count}*\n"
            f"💰 Заработано на рефералах: *{ref_count * 500} монет*\n\n"
            f"🔗 Твоя ссылка:\n`{ref_link}`\n\n"
            f"Поделись ссылкой с друзьями! 🚀"
        )
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=main_keyboard())

    elif query.data == "top":
        top = get_top10()
        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        text = "🏆 *Топ 10 игроков*\n\n"
        for i, (name, coins) in enumerate(top):
            text += f"{medals[i]} *{name}* — {coins} монет\n"
        if not top:
            text += "Пока никого нет — будь первым! 🚀"
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=main_keyboard())

    elif query.data == "balance":
        coins, taps = get_coins(user.id)
        ref_count = get_referral_count(user.id)
        text = (
            f"💰 *Твой баланс*\n\n"
            f"💵 Монет: *{coins}*\n"
            f"👆 Тапов: *{taps}*\n"
            f"👥 Рефералов: *{ref_count}*\n\n"
            f"Продолжай тапать и приглашать друзей! 💪"
        )
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=main_keyboard())

# ── Запуск ───────────────────────────────────────────
def main():
    init_db()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("GrivnaTap bot started!")
    app.run_polling()

if __name__ == "__main__":
    main()
