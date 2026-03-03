import logging
import sqlite3
import asyncio
import os
import datetime
from flask import Flask, request, redirect, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters

# Configuración
TOKEN = "8723515974:AAF1PIZPXu8qNB4u_LQgKvi0Zz8qGKpkkUE"
BASE_URL = os.getenv('BASE_URL', 'https://telegram-bot-railway-production-1ec5.up.railway.app')
DB_PATH = '/tmp/referrals.db'
REQUIRED_REFERRALS = 4
TIKTOK_URL = "https://www.tiktok.com/@lizbethleo6?_r=1&_t=ZS-948qjocXenn"
DEFAULT_GROUP_ID = -1003534894759

logging.disable(logging.CRITICAL)

flask_app = Flask(__name__)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS referrals 
                 (user_id TEXT PRIMARY KEY, click_count INTEGER DEFAULT 0, username TEXT, first_name TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS visitor_ips 
                 (user_id TEXT, visitor_ip TEXT, UNIQUE(user_id, visitor_ip))''')
    c.execute('''CREATE TABLE IF NOT EXISTS config 
                 (key TEXT PRIMARY KEY, value TEXT)''')
    row = c.execute("SELECT value FROM config WHERE key = 'group_id'").fetchone()
    if not row:
        c.execute("INSERT INTO config (key, value) VALUES (?, ?)", ('group_id', str(DEFAULT_GROUP_ID)))
    conn.commit()
    conn.close()

def get_group_id():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    row = c.execute("SELECT value FROM config WHERE key = 'group_id'").fetchone()
    conn.close()
    return int(row[0]) if row else DEFAULT_GROUP_ID

def get_referral_count(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    row = c.execute("SELECT click_count FROM referrals WHERE user_id = ?", (str(user_id),)).fetchone()
    conn.close()
    return row[0] if row else 0

def register_user(user_id, username, first_name):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT OR IGNORE INTO referrals (user_id, click_count, username, first_name) 
                 VALUES (?, 0, ?, ?)''', (str(user_id), username or '', first_name or ''))
    conn.commit()
    conn.close()

def add_referral(referrer_id, visitor_ip):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("INSERT INTO visitor_ips (user_id, visitor_ip) VALUES (?, ?)", 
                  (str(referrer_id), visitor_ip))
        c.execute("UPDATE referrals SET click_count = click_count + 1 WHERE user_id = ?", 
                  (str(referrer_id),))
        conn.commit()
        added = True
    except sqlite3.IntegrityError:
        added = False
    conn.close()
    return added

def get_progress_message(count, referral_link):
    if count >= REQUIRED_REFERRALS:
        msg = f"✅ *¡Completaste los {REQUIRED_REFERRALS} referidos!*\n\n"
        msg += "🎉 Recibirás el enlace al grupo FREE en breve."
    else:
        remaining = REQUIRED_REFERRALS - count
        msg = f"📊 *Tu progreso: {count}/{REQUIRED_REFERRALS} referidos*\n\n"
        if count == 0:
            msg += "Aún no tienes referidos. Comparte tu enlace para comenzar.\n\n"
        else:
            msg += f"¡Vas bien! Te faltan *{remaining}* referidos más.\n\n"
        msg += f"📋 *Tu enlace de referido (CÓPIALO Y COMPARTE):*\n\n"
        msg += f"🔗 {referral_link}\n\n"
        msg += "Comparte este enlace con tus amigos.\n"
        msg += "Cada persona diferente que haga clic se contará automáticamente.\n\n"
        msg += f"Cuando completes los {REQUIRED_REFERRALS} referidos, recibirás un enlace para unirte al grupo FREE (válido 1 hora)."
    return msg

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    
    register_user(user_id, user.username, user.first_name)
    count = get_referral_count(user_id)
    referral_link = f"{BASE_URL}/ref/{user_id}"
    
    if count >= REQUIRED_REFERRALS:
        # Generar enlace al grupo
        try:
            expire_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
            invite = await context.bot.create_chat_invite_link(
                chat_id=get_group_id(),
                expire_date=expire_time,
                member_limit=1
            )
            msg = f"✅ *¡Felicitaciones {user.first_name}!*\n\n"
            msg += f"Has completado los {REQUIRED_REFERRALS} referidos.\n\n"
            msg += f"🔗 *Enlace al grupo FREE (válido 1 hora):*\n{invite.invite_link}"
            await update.message.reply_text(msg, parse_mode='Markdown')
        except Exception:
            msg = get_progress_message(count, referral_link)
            keyboard = [[InlineKeyboardButton("🔄 Actualizar", callback_data="check_progress")]]
            await update.message.reply_text(msg, parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        msg = f"¡Hola {user.first_name}! 👋\n\n"
        msg += f"Para unirte al grupo FREE, necesitas que *{REQUIRED_REFERRALS} PERSONAS DIFERENTES* hagan clic en tu enlace.\n\n"
        msg += f"📋 *Tu enlace de referido (CÓPIALO Y COMPARTE):*\n\n"
        msg += f"🔗 {referral_link}\n\n"
        msg += f"📊 *Tu progreso: {count}/{REQUIRED_REFERRALS} referidos completados*\n\n"
        msg += "Comparte este enlace con tus amigos.\n"
        msg += "Cada persona diferente que haga clic se contará automáticamente.\n\n"
        msg += f"Cuando completes los {REQUIRED_REFERRALS} referidos, recibirás un enlace para unirte al grupo FREE (válido 1 hora)."
        
        keyboard = [[InlineKeyboardButton("🔄 Ver mi progreso", callback_data="check_progress")]]
        await update.message.reply_text(msg, parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard))

async def check_progress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    count = get_referral_count(user_id)
    referral_link = f"{BASE_URL}/ref/{user_id}"
    
    if count >= REQUIRED_REFERRALS:
        try:
            expire_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
            invite = await context.bot.create_chat_invite_link(
                chat_id=get_group_id(),
                expire_date=expire_time,
                member_limit=1
            )
            msg = f"✅ *¡Completaste los {REQUIRED_REFERRALS} referidos!*\n\n"
            msg += f"🔗 *Enlace al grupo FREE (válido 1 hora):*\n{invite.invite_link}"
            await query.edit_message_text(msg, parse_mode='Markdown')
        except Exception:
            msg = get_progress_message(count, referral_link)
            keyboard = [[InlineKeyboardButton("🔄 Actualizar", callback_data="check_progress")]]
            await query.edit_message_text(msg, parse_mode='Markdown',
                reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        msg = get_progress_message(count, referral_link)
        keyboard = [[InlineKeyboardButton("🔄 Actualizar", callback_data="check_progress")]]
        await query.edit_message_text(msg, parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard))

# ============ FLASK ROUTES ============

@flask_app.route('/health')
def health():
    return jsonify({"status": "ok", "bot": "active"})

@flask_app.route('/ref/<user_id>')
def referral_redirect(user_id):
    visitor_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if visitor_ip:
        visitor_ip = visitor_ip.split(',')[0].strip()
    add_referral(user_id, visitor_ip)
    return redirect(TIKTOK_URL)

@flask_app.route('/')
def index():
    return jsonify({"status": "Bot de Referidos activo"})

# ============ MAIN ============

async def main():
    init_db()
    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(check_progress, pattern="check_progress"))
    
    await application.initialize()
    await application.start()
    await application.updater.start_polling(
        poll_interval=0.5,
        timeout=10,
        allowed_updates=['message', 'callback_query'],
        drop_pending_updates=True
    )
    
    # Mantener corriendo
    while True:
        await asyncio.sleep(3600)

if __name__ == '__main__':
    import threading
    
    # Flask en thread separado
    def run_flask():
        port = int(os.environ.get('PORT', 5000))
        flask_app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
    
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Bot en main thread con asyncio
    asyncio.run(main())
