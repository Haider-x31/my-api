hereimport asyncio
import random
import datetime
import aiosqlite
import os

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("8686945908:AAFW7CFWmqkZy-qrMQQ4bBqHG4EpFWqIYRM")
ADMIN_ID = int(os.getenv("5022700372", "0"))

bot = Bot(token=TOKEN)
dp = Dispatcher()

DB_NAME = "bot.db"

# ---------------- DATABASE ----------------

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            name TEXT,
            points INTEGER DEFAULT 0,
            invites INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            vip INTEGER DEFAULT 0,
            last_spin TEXT,
            banned INTEGER DEFAULT 0
        )
        """)
        await db.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            url TEXT PRIMARY KEY
        )
        """)
        await db.commit()

async def get_user(user_id):
    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
        return await cur.fetchone()

async def add_user(user_id, name):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT OR IGNORE INTO users(user_id,name) VALUES(?,?)", (user_id,name))
        await db.commit()

async def update_points(user_id, amount):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET points = points + ? WHERE user_id=?", (amount, user_id))
        await db.commit()

# ---------------- START ----------------

@dp.message(CommandStart())
async def start(msg: Message):
    user_id = msg.from_user.id
    name = msg.from_user.first_name

    await add_user(user_id, name)

    kb = InlineKeyboardBuilder()
    kb.button(text="📊 بياناتي", callback_data="me")
    kb.button(text="🎯 عجلة الحظ", callback_data="spin")
    kb.button(text="👑 VIP", callback_data="vip")
    kb.adjust(2)

    await msg.answer("🔥 أهلاً بك في البوت الخارق", reply_markup=kb.as_markup())

# ---------------- PROFILE ----------------

@dp.callback_query(F.data == "me")
async def profile(call: CallbackQuery):
    user = await get_user(call.from_user.id)

    text = f"""
📊 بياناتك:

💰 النقاط: {user[2]}
👥 الدعوات: {user[3]}
📈 المستوى: {user[4]}
👑 VIP: {'نعم' if user[5] else 'لا'}
    """

    await call.message.answer(text)

# ---------------- SPIN ----------------

@dp.callback_query(F.data == "spin")
async def spin(call: CallbackQuery):
    user = await get_user(call.from_user.id)

    today = str(datetime.date.today())

    if user[6] == today:
        return await call.answer("❌ استخدمت اليوم", show_alert=True)

    rand = random.random()

    if rand < 0.95:
        reward = 1
    elif rand < 0.99:
        reward = 2
    else:
        reward = 3

    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET last_spin=? WHERE user_id=?", (today, call.from_user.id))
        await db.commit()

    await update_points(call.from_user.id, reward)

    await call.message.answer(f"🎯 ربحت {reward} نقطة!")

# ---------------- VIP ----------------

VIP_PRICE = 25

@dp.callback_query(F.data == "vip")
async def vip(call: CallbackQuery):
    user = await get_user(call.from_user.id)

    if user[5]:
        return await call.answer("أنت VIP بالفعل")

    if user[2] < VIP_PRICE:
        return await call.answer("❌ نقاطك غير كافية", show_alert=True)

    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET vip=1, points=points-? WHERE user_id=?", (VIP_PRICE, call.from_user.id))
        await db.commit()

    await call.message.answer("👑 تم تفعيل VIP")

# ---------------- VIDEO ----------------

@dp.message(F.text)
async def video(msg: Message):
    url = msg.text

    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT * FROM videos WHERE url=?", (url,))
        exists = await cur.fetchone()

        if exists:
            return await msg.answer("⚠️ هذا الفيديو تم تحميله سابقاً")

        await db.execute("INSERT INTO videos(url) VALUES(?)", (url,))
        await db.commit()

    await msg.answer("📥 جاري تحميل الفيديو (وهمي الآن)")

# ---------------- ADMIN ----------------

@dp.message(F.text == "/stats")
async def stats(msg: Message):
    if msg.from_user.id != ADMIN_ID:
        return

    async with aiosqlite.connect(DB_NAME) as db:
        cur = await db.execute("SELECT COUNT(*) FROM users")
        users = await cur.fetchone()

    await msg.answer(f"👥 عدد المستخدمين: {users[0]}")

# ---------------- RUN ----------------

async def main():
    await init_db()
    print("BOT STARTED 🔥")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
