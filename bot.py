import os
import asyncio
import sqlite3
import random
import hashlib
from datetime import datetime
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandObject
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.exceptions import TelegramUnauthorizedError, TelegramNetworkError

# --- 1. الإعدادات وقراءة المتغيرات ---
TOKEN = os.environ.get("8686945908:AAFW7CFWmqkZy-qrMQQ4bBqHG4EpFWqIYRM")
# تأكد من حذف أي مسافات زائدة قد تكون في التوكن من Render
if TOKEN:
    TOKEN = TOKEN.strip()

ADMIN_ID = int(os.environ.get("5022700372", "0"))
VIP_PRICE = 25

# --- 2. إعداد البوت مع فحص الخطأ ---
try:
    bot = Bot(token=TOKEN)
    dp = Dispatcher()
except Exception as e:
    print(f"❌ خطأ في تهيئة البوت: {e}")

# --- 3. إدارة قاعدة البيانات ---
def init_db():
    conn = sqlite3.connect('bot_pro.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, username TEXT, points INTEGER DEFAULT 0,
        is_vip INTEGER DEFAULT 0, referred_by INTEGER, ref_count INTEGER DEFAULT 0,
        level INTEGER DEFAULT 1, last_wheel DATE, join_date DATE)''')
    c.execute('CREATE TABLE IF NOT EXISTS downloads (hash TEXT PRIMARY KEY, file_id TEXT)')
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect('bot_pro.db')
    conn.row_factory = sqlite3.Row
    user = conn.execute('SELECT * FROM users WHERE user_id = ?', (user_id,)).fetchone()
    conn.close()
    return user

def add_user(user_id, username, ref_by=None):
    conn = sqlite3.connect('bot_pro.db')
    try:
        conn.execute('INSERT OR IGNORE INTO users (user_id, username, referred_by, join_date) VALUES (?, ?, ?, ?)', 
                     (user_id, username, ref_by, datetime.now().date()))
        if ref_by:
            # نظام النقاط: +1 للدعوة، +5 إضافية لكل 10 دعوات
            conn.execute('UPDATE users SET points = points + 1, ref_count = ref_count + 1 WHERE user_id = ?', (ref_by,))
            u = conn.execute('SELECT ref_count FROM users WHERE user_id = ?', (ref_by,)).fetchone()
            if u and u[0] % 10 == 0:
                conn.execute('UPDATE users SET points = points + 5 WHERE user_id = ?', (ref_by,))
        conn.commit()
    except Exception as e:
        print(f"DB Error: {e}")
    finally:
        conn.close()

# --- 4. لوحة المفاتيح ---
def get_main_menu(user_id):
    buttons = [
        [InlineKeyboardButton(text="👤 بياناتي", callback_query_data="profile"),
         InlineKeyboardButton(text="🎡 عجلة الحظ", callback_query_data="wheel")],
        [InlineKeyboardButton(text="🔗 رابط الدعوة", callback_query_data="invite"),
         InlineKeyboardButton(text="⭐ شراء VIP", callback_query_data="buy_vip")]
    ]
    if user_id == ADMIN_ID:
        buttons.append([InlineKeyboardButton(text="⚙️ لوحة التحكم", callback_query_data="admin")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# --- 5. المعالجات ---
@dp.message(Command("start"))
async def start_handler(message: types.Message, command: CommandObject):
    user_id = message.from_user.id
    user = get_user(user_id)
    if not user:
        ref_id = int(command.args) if command.args and command.args.isdigit() else None
        add_user(user_id, message.from_user.username, ref_id)
        if ref_id:
            try: await bot.send_message(ref_id, "🎉 صديقك انضم! حصلت على نقاط مكافأة.")
            except: pass
    
    await message.answer(f"أهلاً بك {message.from_user.first_name}! 🚀\nاستخدم القائمة أدناه:", 
                         reply_markup=get_main_menu(user_id))

@dp.callback_query(F.data == "profile")
async def profile_handler(call: CallbackQuery):
    u = get_user(call.from_user.id)
    text = (f"📊 **إحصائياتك:**\n\n"
            f"💰 النقاط: `{u['points']}`\n"
            f"👥 الدعوات: `{u['ref_count']}`\n"
            f"👑 VIP: `{'نعم' if u['is_vip'] else 'لا'}`")
    await call.message.edit_text(text, reply_markup=get_main_menu(call.from_user.id), parse_mode="Markdown")

@dp.callback_query(F.data == "wheel")
async def wheel_handler(call: CallbackQuery):
    u = get_user(call.from_user.id)
    today = datetime.now().date().isoformat()
    if u['last_wheel'] == today:
        return await call.answer("❌ استخدمتها اليوم! عد غداً.", show_alert=True)
    
    prize = random.choices([1, 2, 3], weights=[95, 4, 1], k=1)[0]
    conn = sqlite3.connect('bot_pro.db')
    conn.execute('UPDATE users SET points = points + ?, last_wheel = ? WHERE user_id = ?', (prize, today, u['user_id']))
    conn.commit()
    conn.close()
    await call.answer(f"🎡 فزت بـ {prize} نقطة!", show_alert=True)

@dp.callback_query(F.data == "invite")
async def invite_handler(call: CallbackQuery):
    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start={call.from_user.id}"
    await call.message.answer(f"🔗 رابط الدعوة الخاص بك:\n`{link}`\n\nكل دعوة = 1 نقطة.")

# --- 6. نظام التحميل الذكي ---
@dp.message(F.text.contains("tiktok.com") | F.text.contains("instagram.com"))
async def download_logic(message: types.Message):
    url_hash = hashlib.md5(message.text.encode()).hexdigest()
    conn = sqlite3.connect('bot_pro.db')
    exist = conn.execute('SELECT file_id FROM downloads WHERE hash = ?', (url_hash,)).fetchone()
    
    if exist:
        conn.close()
        return await message.answer_video(exist[0], caption="✅ تم تحميله سابقاً")
    
    await message.answer("⏳ جاري التحميل... (تأكد من تنصيب yt-dlp على السيرفر)")

# --- 7. التشغيل ---
async def main():
    init_db()
    try:
        print("✅ جاري فحص الاتصال مع تليجرام...")
        await dp.start_polling(bot)
    except TelegramUnauthorizedError:
        print("❌ خطأ: التوكن غير صحيح! تأكد من التوكن في إعدادات Render.")
    except Exception as e:
        print(f"❌ حدث خطأ غير متوقع: {e}")

if __name__ == "__main__":
    asyncio.run(main())
