import logging
import sqlite3
import asyncio
import os
import datetime
import threading
from flask import Flask, request, redirect, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler

# ============ CONFIGURACIÓN ============
TOKEN = "8723515974:AAF1PIZPXu8qNB4u_LQgKvi0Zz8qGKpkkUE"
PORT = int(os.environ.get('PORT', 8080))
BASE_URL = os.getenv('BASE_URL', 'https://telegram-bot-railway-production-1ec5.up.railway.app')
DB_PATH = '/tmp/referrals.db'
REQUIRED_REFERRALS = 4
TIKTOK_URL = "https://www.tiktok.com/@lizbethleo6?_r=1&_t=ZS-948qjocXenn"
DEFAULT_GROUP_ID = -1003534894759

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============ BASE DE DATOS ============

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

# ============ FLASK ============

flask_app = Flask(__name__)

@flask_app.route('/health')
def health():
    return jsonify({"status": "ok"})

@flask_app.route('/')
def index():
    return jsonify({"status": "Bot activo"})

@flask_app.route('/ref/<user_id>')
def referral_redirect(user_id):
    visitor_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if visitor_ip:
        visitor_ip = visitor_ip.split(',')[0].strip()
    add_referral(user_id, visitor_ip)
    return redirect(TIKTOK_URL)

# ============ BOT ============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id = user.id
    register_user(user_id, user.username, user.first_name)
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
            msg = f"✅ *¡Felicitaciones {user.first_name}!*\n\n"
            msg += f"Has completado los {REQUIRED_REFERRALS} referidos.\n\n"
            msg += f"🔗 *Enlace al grupo FREE (válido 1 hora):*\n{invite.invite_link}"
            await update.message.reply_text(msg, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Error creando invite: {e}")
            await update.message.reply_text("✅ ¡Completaste los referidos! Contacta al admin.")
    else:
        remaining = REQUIRED_REFERRALS - count
        msg = f"¡Hola {user.first_name}! 👋\n\n"
        msg += f"Para unirte al grupo FREE, necesitas que *{REQUIRED_REFERRALS} PERSONAS DIFERENTES* hagan clic en tu enlace.\n\n"
        msg += f"📋 *Tu enlace de referido:*\n\n"
        msg += f"🔗 {referral_link}\n\n"
        msg += f"📊 *Progreso: {count}/{REQUIRED_REFERRALS}*\n"
        if count > 0:
            msg += f"¡Vas bien! Te faltan *{remaining}* más.\n\n"
        else:
            msg += "\n"
        msg += f"Cuando completes {REQUIRED_REFERRALS} referidos recibirás el enlace al grupo FREE (válido 1 hora)."

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
            await query.edit_message_text("✅ ¡Completaste los referidos! Contacta al admin.")
    else:
        remaining = REQUIRED_REFERRALS - count
        msg = f"📊 *Tu progreso: {count}/{REQUIRED_REFERRALS} referidos*\n\n"
        msg += f"Te faltan *{remaining}* referidos más.\n\n"
        msg += f"🔗 Tu enlace:\n{referral_link}"
        keyboard = [[InlineKeyboardButton("🔄 Actualizar", callback_data="check_progress")]]
        await query.edit_message_text(msg, parse_mode='Markdown',
            reply_markup=InlineKeyboardMarkup(keyboard))

# ============ MAIN ============

def run_bot():
    """Bot en su propio event loop en thread separado."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def _start_bot():
        init_db()
        app = ApplicationBuilder().token(TOKEN).build()
        app.add_handler(CommandHandler('start', start))
        app.add_handler(CallbackQueryHandler(check_progress, pattern="check_progress"))
        await app.initialize()
        await app.start()
        await app.updater.start_polling(
            poll_interval=1.0,
            timeout=10,
            allowed_updates=['message', 'callback_query'],
            drop_pending_updates=True
        )
        logger.info("Bot de Telegram iniciado correctamente")
        while True:
            await asyncio.sleep(3600)

    loop.run_until_complete(_start_bot())

if __name__ == '__main__':
    logger.info(f"Iniciando en puerto {PORT}")
    
    # Bot en thread separado
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # Flask en main thread con el PORT correcto de Railway
    flask_app.run(host='0.0.0.0', port=PORT, debug=False, use_reloader=False)
