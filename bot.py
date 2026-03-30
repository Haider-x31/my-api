import os
import asyncio
import sqlite3
import random
import hashlib
from datetime import datetime
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandObject
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.utils.token import TokenValidationError

# --- 1. معالجة المتغيرات بأمان (Render & Local) ---
# نحاول جلب التوكن، إذا لم يوجد نترك المستخدم يضعه يدوياً كحل أخير
TOKEN = os.environ.get("BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
VIP_PRICE = 25

# فحص أمان التوكن
if not TOKEN or TOKEN == "None":
    print("❌ خطأ قاتل: لم يتم العثور على BOT_TOKEN في إعدادات Render!")
    print("💡 تأكد من إضافة BOT_TOKEN في قسم Environment Variables في لوحة تحكم Render.")
    # لتجربة الكود فوراً إذا فشل Render، يمكنك لصق التوكن هنا مؤقتاً:
    # TOKEN = "ضع_توكن_بوتك_هنا"

# --- 2. إعداد البوت والداتابيز ---
try:
    bot = Bot(token=TOKEN)
    dp = Dispatcher()
except Exception as e:
    print(f"❌ فشل تشغيل البوت بسبب التوكن: {e}")

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
            conn.execute('UPDATE users SET points = points + 1, ref_count = ref_count + 1 WHERE user_id = ?', (ref_by,))
        conn.commit()
    except: pass
    finally: conn.close()

# --- 3. الكيبورد والمعالجات ---
def main_menu(user_id):
    kb = [
        [InlineKeyboardButton(text="👤 بياناتي", callback_query_data="profile"),
         InlineKeyboardButton(text="🎡 عجلة الحظ", callback_query_data="wheel")],
        [InlineKeyboardButton(text="🔗 رابط الدعوة", callback_query_data="invite"),
         InlineKeyboardButton(text="⭐ شراء VIP", callback_query_data="buy_vip")]
    ]
    if user_id == ADMIN_ID:
        kb.append([InlineKeyboardButton(text="⚙️ لوحة الأدمن", callback_query_data="admin")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

@dp.message(Command("start"))
async def start(message: types.Message, command: CommandObject):
    user_id = message.from_user.id
    user = get_user(user_id)
    if not user:
        ref_by = int(command.args) if command.args and command.args.isdigit() else None
        add_user(user_id, message.from_user.username, ref_by)
    await message.answer(f"أهلاً {message.from_user.first_name}! البوت جاهز لخدمتك.", reply_markup=main_menu(user_id))

@dp.callback_query(F.data == "profile")
async def profile(call: CallbackQuery):
    u = get_user(call.from_user.id)
    text = f"📊 نقاطك: {u['points']}\n👥 دعواتك: {u['ref_count']}\n👑 VIP: {'نعم' if u['is_vip'] else 'لا'}"
    await call.message.edit_text(text, reply_markup=main_menu(call.from_user.id))

@dp.callback_query(F.data == "wheel")
async def wheel(call: CallbackQuery):
    u = get_user(call.from_user.id)
    today = datetime.now().date().isoformat()
    if u['last_wheel'] == today:
        return await call.answer("عد غداً! ❌", show_alert=True)
    
    res = random.choices([1, 2, 3], weights=[95, 4, 1], k=1)[0]
    conn = sqlite3.connect('bot_pro.db')
    conn.execute('UPDATE users SET points = points + ?, last_wheel = ? WHERE user_id = ?', (res, today, u['user_id']))
    conn.commit()
    conn.close()
    await call.answer(f"مبروك! فزت بـ {res} نقطة 🎡")

@dp.callback_query(F.data == "invite")
async def invite(call: CallbackQuery):
    me = await bot.get_me()
    await call.message.answer(f"🔗 رابطك: https://t.me/{me.username}?start={call.from_user.id}")

# --- 4. تشغيل البوت ---
async def main():
    init_db()
    if not TOKEN: return # منع التشغيل إذا التوكن مفقود
    print("✅ البوت يعمل الآن...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
