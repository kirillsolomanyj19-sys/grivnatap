import os
import sqlite3
from datetime import datetime, date
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

TOKEN = os.environ.get("BOT_TOKEN", "YOUR_TOKEN_HERE")
DB_PATH = "grivnatap.db"

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
    if referral_id:
        c.execute("UPDATE users SET coins=coins+500 WHERE user_id=?", (referral_id,))
    conn.commit()
    conn.close()

def add_tap(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET coins=coins+10, taps=taps+1 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

def get_stats(user_id):
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

def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("TAP +10 monet", callback_data="tap")],
        [InlineKeyboardButton("Ezhednevnaya nagrada +200", callback_data="daily")],
        [InlineKeyboardButton("Referaly", callback_data="referrals"),
         InlineKeyboardButton("Top igrokov", callback_data="top")],
        [InlineKeyboardButton("Moy balans", callback_data="balance")],
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    referral_id = None
    if args and args[0].isdigit():
        ref = int(args[0])
        if ref != user.id:
            referral_id = ref
    if not get_user(user.id):
        create_user(user.id, user.username or "", user.first_name, referral_id)
    coins, taps = get_stats(user.id)
    total = get_total_users()
    text = (
        f"Privet, {user.first_name}!\n\n"
        f"Dobro pozhalovat v GrivnaTap!\n"
        f"Tapay - kopi monety!\n\n"
        f"Balans: {coins} monet\n"
        f"Tapov: {taps}\n"
        f"Igrokov: {total}\n\n"
        f"Nazhmi TAP chtoby nachat!"
    )
    await update.message.reply_text(text, reply_markup=main_keyboard())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    await query.answer()

    if query.data == "tap":
        add_tap(user.id)
        coins, taps = get_stats(user.id)
        await query.edit_message_text(
            f"+10 monet!\nBalans: {coins}\nTapov: {taps}",
            reply_markup=main_keyboard()
        )

    elif query.data == "daily":
        success = claim_daily(user.id)
        coins, _ = get_stats(user.id)
        if success:
            await query.edit_message_text(f"+200 monet! Balans: {coins}", reply_markup=main_keyboard())
        else:
            await query.edit_message_text(f"Uzhe polucheno segodnya. Balans: {coins}", reply_markup=main_keyboard())

    elif query.data == "referrals":
        ref_count = get_referral_count(user.id)
        link = f"https://t.me/GrivnaTap_bot?start={user.id}"
        await query.edit_message_text(
            f"Referaly: {ref_count}\nZarabotano: {ref_count*500} monet\n\nSsylka: {link}",
            reply_markup=main_keyboard()
        )

    elif query.data == "top":
        top = get_top10()
        text = "Top 10:\n\n"
        for i, (name, coins) in enumerate(top, 1):
            text += f"{i}. {name} - {coins}\n"
        if not top:
            text = "Poka pustomto. Bud pervym!"
        await query.edit_message_text(text, reply_markup=main_keyboard())

    elif query.data == "balance":
        coins, taps = get_stats(user.id)
        ref_count = get_referral_count(user.id)
        await query.edit_message_text(
            f"Balans: {coins} monet\nTapov: {taps}\nRefiralov: {ref_count}",
            reply_markup=main_keyboard()
        )

def main():
    init_db()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("GrivnaTap started!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
