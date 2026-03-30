import telebot
import requests
import sqlite3
import time
import random

TOKEN = "8686945908:AAFW7CFWmqkZy-qrMQQ4bBqHG4EpFWqIYRM"
ADMIN_ID = "5022700372"

bot = telebot.TeleBot(TOKEN)

# ---------------- DATABASE ----------------
conn = sqlite3.connect("bot.db", check_same_thread=False)
db = conn.cursor()

db.execute("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, points INTEGER, vip INTEGER)")
db.execute("CREATE TABLE IF NOT EXISTS invites (user_id INTEGER, inviter INTEGER)")
db.execute("CREATE TABLE IF NOT EXISTS channels (username TEXT)")
conn.commit()

# ---------------- FUNCTIONS ----------------
def get_user(user_id):
    db.execute("SELECT * FROM users WHERE id=?", (user_id,))
    return db.fetchone()

def add_user(user_id):
    if not get_user(user_id):
        db.execute("INSERT INTO users VALUES (?, ?, ?)", (user_id, 0, 0))
        conn.commit()

def add_points(user_id, pts):
    db.execute("UPDATE users SET points = points + ? WHERE id=?", (pts, user_id))
    conn.commit()

def get_points(user_id):
    db.execute("SELECT points FROM users WHERE id=?", (user_id,))
    return db.fetchone()[0]

def set_vip(user_id, val):
    db.execute("UPDATE users SET vip=? WHERE id=?", (val, user_id))
    conn.commit()

def is_vip(user_id):
    db.execute("SELECT vip FROM users WHERE id=?", (user_id,))
    return db.fetchone()[0] == 1

def get_channels():
    db.execute("SELECT username FROM channels")
    return [c[0] for c in db.fetchall()]

# ---------------- SUB ----------------
def is_subscribed(user_id):
    channels = get_channels()
    if not channels:
        return True
    for ch in channels:
        try:
            status = bot.get_chat_member(ch, user_id).status
            if status not in ["member","administrator","creator"]:
                return False
        except:
            return True
    return True

# ---------------- CAPTCHA ----------------
captcha = {}

def send_captcha(chat_id, user_id):
    a, b = random.randint(1,9), random.randint(1,9)
    captcha[user_id] = a+b
    bot.send_message(chat_id, f"🔐 تحقق:\n{a}+{b}=?")

# ---------------- SPAM ----------------
last_msg = {}
def spam(user_id):
    now = time.time()
    if user_id in last_msg and now-last_msg[user_id] < 1.5:
        return True
    last_msg[user_id] = now
    return False

# ---------------- MENU ----------------
def menu(chat_id):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("📥 تحميل","👥 دعواتي")
    kb.add("💰 نقاطي","⭐ VIP")
    bot.send_message(chat_id, "اختر:", reply_markup=kb)

# ---------------- START ----------------
@bot.message_handler(commands=['start'])
def start(msg):
    uid = msg.from_user.id
    args = msg.text.split()

    add_user(uid)

    # invite system
    if len(args)>1:
        inviter = int(args[1])
        if inviter != uid:
            db.execute("SELECT * FROM invites WHERE user_id=?", (uid,))
            if not db.fetchone():
                db.execute("INSERT INTO invites VALUES (?,?)",(uid,inviter))
                add_points(inviter,1)
                bot.send_message(inviter,"🎉 تم إضافة نقطة")

    send_captcha(msg.chat.id, uid)

# ---------------- MAIN ----------------
@bot.message_handler(func=lambda m: True)
def all(msg):
    uid = msg.from_user.id
    text = msg.text

    if uid in captcha:
        if text.isdigit() and int(text)==captcha[uid]:
            del captcha[uid]
            menu(msg.chat.id)
        else:
            bot.reply_to(msg,"❌ خطأ")
        return

    if spam(uid):
        return

    if not is_subscribed(uid) and not is_vip(uid):
        chs = get_channels()
        kb = types.InlineKeyboardMarkup()
        for ch in chs:
            kb.add(types.InlineKeyboardButton("اشترك", url=f"https://t.me/{ch.replace('@','')}"))
        return bot.send_message(msg.chat.id,"❌ اشترك أولاً",reply_markup=kb)

    # ---------------- تحميل ----------------
    if "tiktok.com" in text or "instagram.com" in text:
        if not is_vip(uid) and get_points(uid) <= 0:
            return bot.reply_to(msg,"❌ تحتاج نقاط")

        bot.send_message(msg.chat.id,"⏳ جاري التحميل...")

        try:
            # TikTok API قوي بدون علامة
            api = f"https://tikwm.com/api/?url={text}"
            r = requests.get(api).json()
            video = r["data"]["play"]

            bot.send_video(msg.chat.id, video)

            if not is_vip(uid):
                add_points(uid, -1)

        except Exception as e:
            bot.reply_to(msg,"❌ فشل التحميل")

        return

    # ---------------- BUTTONS ----------------
    if text=="💰 نقاطي":
        bot.reply_to(msg,f"💰 نقاطك: {get_points(uid)}")

    elif text=="👥 دعواتي":
        db.execute("SELECT COUNT(*) FROM invites WHERE inviter=?", (uid,))
        c = db.fetchone()[0]
        bot.reply_to(msg,f"👥 دعواتك: {c}")

    elif text=="⭐ VIP":
        if is_vip(uid):
            bot.reply_to(msg,"👑 انت VIP")
        else:
            kb = types.InlineKeyboardMarkup()
            kb.add(types.InlineKeyboardButton("شراء VIP (25 نقطة)", callback_data="buyvip"))
            bot.send_message(msg.chat.id,"شراء VIP:",reply_markup=kb)

    elif text=="📥 تحميل":
        bot.reply_to(msg,"ارسل رابط الفيديو")

# ---------------- BUY VIP ----------------
@bot.callback_query_handler(func=lambda c: True)
def cb(call):
    uid = call.from_user.id

    if call.data=="buyvip":
        if get_points(uid) >= 25:
            add_points(uid,-25)
            set_vip(uid,1)
            bot.answer_callback_query(call.id,"✅ تم التفعيل")
        else:
            bot.answer_callback_query(call.id,"❌ نقاطك غير كافية")

# ---------------- ADMIN ----------------
@bot.message_handler(commands=['stats'])
def stats(msg):
    if msg.from_user.id != ADMIN_ID:
        return
    db.execute("SELECT COUNT(*) FROM users")
    users = db.fetchone()[0]
    db.execute("SELECT COUNT(*) FROM users WHERE vip=1")
    vip = db.fetchone()[0]
    bot.reply_to(msg,f"👥 المستخدمين: {users}\n⭐ VIP: {vip}")

print("RUNNING...")
bot.infinity_polling()

