import os
import sqlite3
import asyncio
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
        [InlineKeyboardButton("👆 ТАП (+10 монет)", callback_data="tap")],
        [InlineKeyboardButton("🎁 Ежедневная награда", callback_data="daily")],
        [InlineKeyboardButton("👥 Рефералы", callback_data="referrals"),
         InlineKeyboardButton("🏆 Топ игроков", callback_data="top")],
        [InlineKeyboardButton("💰 Мой баланс", callback_data="balance")],
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = context.args
    referral_id = None

    if args and args[0].isdigit():
        ref = int(args[0])
        if ref != user.id:
            referral_id = ref

    existing = get_user(user.id)
    if not existing:
        create_user(user.id, user.username or "", user.first_name, referral_id)
        bonus_text = "\n🎉 *+500 монет* получил тот кто тебя пригласил!" if referral_id else ""
    else:
        bonus_text = ""

    coins, taps = get_stats(user.id)
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
        add_tap(user.id)
        coins, taps = get_stats(user.id)
        text = (
            f"👆 *+10 монет!*\n\n"
            f"💰 Баланс: *{coins} монет*\n"
            f"👆 Тапов: *{taps}*\n\n"
            f"Продолжай тапать! 🚀"
        )
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=main_keyboard())

    elif query.data == "daily":
        success = claim_daily(user.id)
        coins, _ = get_stats(user.id)
        if success:
            text = (
                f"🎁 *+200 монет!*\n\n"
                f"Ежедневная награда получена!\n"
                f"💰 Баланс: *{coins} монет*\n\n"
                f"Возвращайся завтра за новой наградой! 🔥"
            )
        else:
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
            f"💰 Заработано: *{ref_count * 500} монет*\n\n"
            f"🔗 Твоя ссылка:\n`{ref_link}`\n\n"
            f"Поделись с друзьями! 🚀"
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
        coins, taps = get_stats(user.id)
        ref_count = get_referral_count(user.id)
        text = (
            f"💰 *Твой баланс*\n\n"
            f"💵 Монет: *{coins}*\n"
            f"👆 Тапов: *{taps}*\n"
            f"👥 Рефералов: *{ref_count}*\n\n"
            f"Продолжай тапать и приглашать друзей! 💪"
        )
        await query.edit_message_text(text, parse_mode="Markdown", reply_markup=main_keyboard())

def main():
    init_db()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("GrivnaTap bot started!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()cat > /home/claude/grivnatap/bot.py << 'BOTEOF'
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
        [InlineKeyboardButton("TAP (+10 monets)", callback_data="tap")],
        [InlineKeyboardButton("Ezhednevnaya nagrada", callback_data="daily")],
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
    existing = get_user(user.id)
    if not existing:
        create_user(user.id, user.username or "", user.first_name, referral_id)
    coins, taps = get_stats(user.id)
    total = get_total_users()
    text = (
        f"Privet, {user.first_name}!\n\n"
        f"Dobro pozhalovat v GrivnaTap!\n"
        f"Tapay - kopi monety - poluchay nagrady!\n\n"
        f"Tvoy balans: {coins} monet\n"
        f"Vsego tapov: {taps}\n"
        f"Igrokov v igre: {total}\n\n"
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
        text = f"+10 monet!\n\nBalans: {coins} monet\nTapov: {taps}\n\nProdolzhay tapaty! :rocket:"
        await query.edit_message_text(text, reply_markup=main_keyboard())

    elif query.data == "daily":
        success = claim_daily(user.id)
        coins, _ = get_stats(user.id)
        if success:
            text = f"+200 monet!\n\nEzhednevnaya nagrada poluchena!\nBalans: {coins} monet\n\nVozvrachaysya zavtra!"
        else:
            text = f"Ty uzhe poluchil nagradu segodnya!\n\nBalans: {coins} monet\n\nVozvrachaysya zavtra!"
        await query.edit_message_text(text, reply_markup=main_keyboard())

    elif query.data == "referrals":
        ref_count = get_referral_count(user.id)
        ref_link = f"https://t.me/GrivnaTap_bot?start={user.id}"
        text = f"Referalnaya programma\n\nPriglashay druzey i poluchay 500 monet za kazhdogo!\n\nTvoikh refiralov: {ref_count}\nZarabotano: {ref_count * 500} monet\n\nTvoya ssylka:\n{ref_link}"
        await query.edit_message_text(text, reply_markup=main_keyboard())

    elif query.data == "top":
        top = get_top10()
        text = "Top 10 igrokov\n\n"
        for i, (name, coins) in enumerate(top, 1):
            text += f"{i}. {name} - {coins} monet\n"
        if not top:
            text += "Poka nikogo net - bud pervym!"
        await query.edit_message_text(text, reply_markup=main_keyboard())

    elif query.data == "balance":
        coins, taps = get_stats(user.id)
        ref_count = get_referral_count(user.id)
        text = f"Tvoy balans\n\nMonet: {coins}\nTapov: {taps}\nRefiralov: {ref_count}\n\nProdolzhay tapaty!"
        await query.edit_message_text(text, reply_markup=main_keyboard())

def main():
    init_db()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("GrivnaTap bot started!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
BOTEOF
echo "Done"
