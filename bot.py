import os 
import asyncio
import sqlite3
import random
import hashlib
from datetime import datetime
from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command, CommandObject
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery

# --- 1. الإعدادات (قراءة من Render/VPS) ---
TOKEN = os.getenv("8686945908:AAFW7CFWmqkZy-qrMQQ4bBqHG4EpFWqIYRM")
ADMIN_ID = int(os.getenv("5022700372", "0"))
VIP_PRICE = 25

if not TOKEN:
    print("❌ خطأ: BOT_TOKEN مفقود في إعدادات السيرفر!")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# --- 2. نظام قاعدة البيانات (الاستمرارية) ---
class Database:
    def __init__(self):
        self.conn = sqlite3.connect('bot_pro.db')
        self.create_tables()

    def create_tables(self):
        c = self.conn.cursor()
        # جدول المستخدمين: تخزين دائم (ID، نقاط، VIP، إحالات، مستوى)
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, username TEXT, points INTEGER DEFAULT 0,
            is_vip INTEGER DEFAULT 0, referred_by INTEGER, ref_count INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1, last_wheel DATE, join_date DATE, is_banned INTEGER DEFAULT 0)''')
        # جدول التحميلات: لمنع تكرار التحميل واستهلاك السيرفر
        c.execute('CREATE TABLE IF NOT EXISTS downloads (link_hash TEXT PRIMARY KEY, file_id TEXT)')
        self.conn.commit()

    def get_user(self, user_id):
        self.conn.row_factory = sqlite3.Row
        return self.conn.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)).fetchone()

    def add_user(self, user_id, username, ref_by=None):
        try:
            self.conn.execute("INSERT OR IGNORE INTO users (user_id, username, referred_by, join_date) VALUES (?, ?, ?, ?)",
                             (user_id, username, ref_by, datetime.now().date()))
            if ref_by:
                # نظام النقاط: +1 للدعوة، +5 إضافية لكل 10 دعوات (نظام مستويات)
                self.conn.execute("UPDATE users SET points = points + 1, ref_count = ref_count + 1 WHERE user_id = ?", (ref_by,))
                u = self.get_user(ref_by)
                if u and u['ref_count'] % 10 == 0:
                    self.conn.execute("UPDATE users SET points = points + 5 WHERE user_id = ?", (ref_by,))
            self.conn.commit()
        except: pass

    def update_val(self, user_id, column, value):
        self.conn.execute(f"UPDATE users SET {column} = ? WHERE user_id = ?", (value, user_id))
        self.conn.commit()

db = Database()

# --- 3. واجهة المستخدم (Keyboards) ---
def main_menu(user_id):
    u = db.get_user(user_id)
    is_vip = u['is_vip'] if u else 0
    kb = [
        [InlineKeyboardButton(text="👤 بياناتي", callback_data="profile"),
         InlineKeyboardButton(text="🎡 عجلة الحظ", callback_data="wheel")],
        [InlineKeyboardButton(text="🔗 رابط الدعوة", callback_data="invite"),
         InlineKeyboardButton(text="⭐ شراء VIP", callback_data="buy_vip")],
        [InlineKeyboardButton(text="📺 شاهد إعلان (+1)", callback_data="watch_ad")]
    ]
    if user_id == ADMIN_ID:
        kb.append([InlineKeyboardButton(text="⚙️ لوحة الأدمن", callback_data="admin_stats")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

# --- 4. معالجات الأوامر (Handlers) ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message, command: CommandObject):
    user_id = message.from_user.id
    user = db.get_user(user_id)
    
    if not user:
        ref_id = int(command.args) if command.args and command.args.isdigit() else None
        db.add_user(user_id, message.from_user.username, ref_id)
        if ref_id:
            try: await bot.send_message(ref_id, "✅ صديقك انضم عبر رابطك! حصلت على نقاط مكافأة.")
            except: pass

    await message.answer(f"أهلاً بك {message.from_user.first_name}! 🚀\nبوت الخدمات المتكاملة (بدون AI) جاهز لخدمتك.", 
                         reply_markup=main_menu(user_id))

@dp.callback_query(F.data == "profile")
async def profile_handler(call: CallbackQuery):
    u = db.get_user(call.from_user.id)
    status = "👑 VIP" if u['is_vip'] else "عادي"
    text = (f"👤 **ملفك الشخصي:**\n\n💰 النقاط: `{u['points']}`\n👥 الدعوات: `{u['ref_count']}`\n"
            f"🆙 المستوى: `{u['level']}`\n💎 الحالة: `{status}`")
    await call.message.edit_text(text, reply_markup=main_menu(call.from_user.id), parse_mode="Markdown")

@dp.callback_query(F.data == "wheel")
async def wheel_handler(call: CallbackQuery):
    u = db.get_user(call.from_user.id)
    today = datetime.now().date().isoformat()
    if u['last_wheel'] == today:
        return await call.answer("❌ استخدمتها اليوم! عد غداً.", show_alert=True)
    
    # احتمالات عجلة الحظ المطلوبة: 95% (1)، 4% (2)، 1% (3)
    prize = random.choices([1, 2, 3], weights=[95, 4, 1], k=1)[0]
    db.update_val(u['user_id'], "points", u['points'] + prize)
    db.update_val(u['user_id'], "last_wheel", today)
    await call.answer(f"🎡 فزت بـ {prize} نقطة!", show_alert=True)
    await profile_handler(call)

@dp.callback_query(F.data == "invite")
async def invite_handler(call: CallbackQuery):
    me = await bot.get_me()
    link = f"https://t.me/{me.username}?start={call.from_user.id}"
    await call.message.answer(f"🔗 **رابط الدعوة الخاص بك:**\n`{link}`\n\nكل دعوة = 1 نقطة.\nكل 10 دعوات = 5 نقاط مكافأة!")

@dp.callback_query(F.data == "buy_vip")
async def buy_vip_handler(call: CallbackQuery):
    u = db.get_user(call.from_user.id)
    if u['is_vip']: return await call.answer("أنت VIP بالفعل! ✅", show_alert=True)
    
    if u['points'] >= VIP_PRICE:
        db.update_val(u['user_id'], "points", u['points'] - VIP_PRICE)
        db.update_val(u['user_id'], "is_vip", 1)
        await call.answer("🎉 مبروك! تم تفعيل VIP بنجاح.", show_alert=True)
        await profile_handler(call)
    else:
        await call.answer(f"❌ تحتاج {VIP_PRICE} نقطة على الأقل.", show_alert=True)

# --- 5. نظام التحميل الذكي (Logic) ---
@dp.message(F.text.contains("tiktok.com") | F.text.contains("instagram.com"))
async def download_manager(message: types.Message):
    u = db.get_user(message.from_user.id)
    url_hash = hashlib.md5(message.text.encode()).hexdigest()
    
    # فحص إذا تم تحميل الفيديو مسبقاً (توفير استهلاك)
    conn = sqlite3.connect('bot_pro.db')
    exist = conn.execute('SELECT file_id FROM downloads WHERE hash = ?', (url_hash,)).fetchone()
    if exist:
        conn.close()
        return await message.answer_video(exist[0], caption="✅ هذا الفيديو تم تحميله سابقاً")
    
    msg = await message.answer("⏳ جاري جلب الفيديو بدون علامة مائية...")
    # ملاحظة: يتطلب تفعيل yt-dlp و ffmpeg على السيرفر للتحميل الفعلي
    await asyncio.sleep(2)
    await msg.edit_text("⚠️ نظام التحميل الفعلي يتطلب ربط مكتبة yt-dlp بالسيرفر.")

# --- 6. لوحة التحكم للأدمن (Admin) ---
@dp.callback_query(F.data == "admin_stats")
async def admin_stats(call: CallbackQuery):
    if call.from_user.id != ADMIN_ID: return
    conn = sqlite3.connect('bot_pro.db')
    total = conn.execute('SELECT COUNT(*) FROM users').fetchone()[0]
    vips = conn.execute('SELECT COUNT(*) FROM users WHERE is_vip = 1').fetchone()[0]
    conn.close()
    
    text = (f"⚙️ **لوحة التحكم:**\n\n👥 إجمالي المستخدمين: `{total}`\n👑 مستخدمي VIP: `{vips}`\n"
            f"💰 سعر الـ VIP الحالي: `{VIP_PRICE}`")
    await call.message.answer(text, parse_mode="Markdown")

# --- 7. التشغيل الرئيسي ---
async def main():
    print("✅ البوت يعمل الآن بدون أخطاء...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
