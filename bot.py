import logging
import sqlite3
import asyncio
import os
import threading
import datetime
from flask import Flask, request, redirect, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler, MessageHandler, filters

# Configuración
TOKEN = "8723515974:AAF1PIZPXu8qNB4u_LQgKvi0Zz8qGKpkkUE"
BASE_URL = os.getenv('BASE_URL', 'https://telegram-bot-railway-production-1ec5.up.railway.app')
DB_PATH = 'referrals.db'
REQUIRED_REFERRALS = 4
TIKTOK_URL = "https://www.tiktok.com/@lizbethleo6?_r=1&_t=ZS-948qjocXenn"
DEFAULT_GROUP_ID = -1003534894759

# Flask app para keep-alive y tracking de referidos
app = Flask(__name__)

# Logging
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS referrals 
                 (user_id TEXT PRIMARY KEY, click_count INTEGER DEFAULT 0)''')
    c.execute('''CREATE TABLE IF NOT EXISTS visitor_ips 
                 (user_id TEXT, visitor_ip TEXT, UNIQUE(user_id, visitor_ip))''')
    c.execute('''CREATE TABLE IF NOT EXISTS config 
                 (key TEXT PRIMARY KEY, value TEXT)''')
    c.execute("SELECT value FROM config WHERE key = 'group_id'")
    if c.fetchone() is None:
        c.execute("INSERT INTO config (key, value) VALUES (?, ?)", ('group_id', str(DEFAULT_GROUP_ID)))
    conn.commit()
    conn.close()

def get_group_id():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT value FROM config WHERE key = 'group_id'")
    row = c.fetchone()
    conn.close()
    if row:
        return int(row[0])
    return DEFAULT_GROUP_ID

def set_group_id(group_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", ('group_id', str(group_id)))
    conn.commit()
    conn.close()

def get_progress_message(count, referral_link):
    remaining = REQUIRED_REFERRALS - count
    if count == 0:
        progress_text = "Aún no tienes referidos. Comparte tu enlace para comenzar."
    else:
        progress_text = f"Ya completaste {count} referido(s), te faltan {remaining} más."
    return (
        f"📊 **Tu progreso:** {count}/{REQUIRED_REFERRALS} referidos\n\n"
        f"{progress_text}\n\n"
        f"📋 **Tu enlace de referido (CÓPIALO Y COMPARTE):**\n\n"
        f"🔗 [{referral_link}]({referral_link})\n\n"
        f"Cuando completes los 4 referidos, recibirás el enlace para el grupo FREE."
    )

# ============ RUTAS FLASK (keep-alive + tracking) ============

@app.route('/')
def home():
    return jsonify({"status": "ok", "bot": "referral_bot"}), 200

@app.route('/health')
def health():
    return jsonify({"status": "ok"}), 200

@app.route('/ref/<user_id>')
def track_referral(user_id):
    visitor_ip = request.remote_addr
    if request.headers.get('X-Forwarded-For'):
        visitor_ip = request.headers.get('X-Forwarded-For').split(',')[0]

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("SELECT COUNT(*) FROM visitor_ips WHERE user_id = ? AND visitor_ip = ?", (user_id, visitor_ip))
        ip_exists = c.fetchone()[0] > 0

        if not ip_exists:
            c.execute("INSERT INTO visitor_ips (user_id, visitor_ip) VALUES (?, ?)", (user_id, visitor_ip))
            c.execute("INSERT OR IGNORE INTO referrals (user_id, click_count) VALUES (?, 0)", (user_id,))
            c.execute("UPDATE referrals SET click_count = click_count + 1 WHERE user_id = ?", (user_id,))
        
        conn.commit()
        conn.close()
        return redirect(TIKTOK_URL)
    except Exception as e:
        conn.close()
        return jsonify({"error": str(e)}), 500

@app.route('/status/<user_id>')
def get_status(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT click_count FROM referrals WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    count = row[0] if row else 0
    return jsonify({"user_id": user_id, "click_count": count})

# ============ HANDLERS DEL BOT ============

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    referral_link = f"{BASE_URL}/ref/{user_id}"
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT click_count FROM referrals WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    
    count = row[0] if row else 0
    
    message = (
        f"¡Hola {update.effective_user.first_name}! 👋\n\n"
        "**Para unirte al grupo FREE, necesitas que 4 PERSONAS DIFERENTES hagan clic en tu enlace.**\n\n"
        f"📋 **Tu enlace de referido (CÓPIALO Y COMPARTE):**\n\n"
        f"🔗 [{referral_link}]({referral_link})\n\n"
        f"📊 **Tu progreso:** {count}/{REQUIRED_REFERRALS} referidos completados\n\n"
        "Comparte este enlace con tus amigos. Cada persona diferente que haga clic se contará automáticamente.\n\n"
        "**Cuando completes los 4 referidos, recibirás un enlace para unirte al grupo FREE (válido 1 hora).**"
    )
    
    keyboard = [[InlineKeyboardButton("🔄 Ver mi progreso", callback_data="check_progress")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(message, reply_markup=reply_markup, parse_mode='Markdown')

async def check_progress(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = str(query.from_user.id)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT click_count FROM referrals WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    
    count = row[0] if row else 0
    referral_link = f"{BASE_URL}/ref/{user_id}"
    
    if count >= REQUIRED_REFERRALS:
        group_id = get_group_id()
        
        try:
            expire_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
            
            invite_link = await context.bot.create_chat_invite_link(
                chat_id=group_id,
                expire_date=int(expire_time.timestamp()),
                member_limit=1
            )
            
            # Reiniciar contador
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("UPDATE referrals SET click_count = 0 WHERE user_id = ?", (user_id,))
            c.execute("DELETE FROM visitor_ips WHERE user_id = ?", (user_id,))
            conn.commit()
            conn.close()

            await query.edit_message_text(
                "🎉 **¡Felicidades! Completaste los 4 referidos.**\n\n"
                "Tu acceso al grupo FREE está confirmado.\n\n"
                "Revisa el siguiente mensaje para unirte al grupo.",
                parse_mode='Markdown'
            )
            
            try:
                await context.bot.send_message(
                    chat_id=user_id,
                    text=invite_link.invite_link
                )
            except Exception as e:
                logger.error(f"Error enviando enlace: {e}")
                
        except Exception as e:
            error_msg = str(e)
            await query.edit_message_text(
                f"❌ Error al generar el enlace.\n\n"
                f"Detalles: {error_msg}"
            )
    else:
        message = get_progress_message(count, referral_link)
        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Actualizar", callback_data="check_progress")]]),
            parse_mode='Markdown'
        )

async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message and update.message.chat.type in ['group', 'supergroup']:
        group_id = update.message.chat_id
        set_group_id(group_id)

# ============ INICIAR BOT EN THREAD SEPARADO ============

def run_bot():
    init_db()
    application = ApplicationBuilder().token(TOKEN).build()
    
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CallbackQueryHandler(check_progress, pattern="check_progress"))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_group_message))
    
    asyncio.run(application.run_polling(
        poll_interval=0.5,
        timeout=10,
        allowed_updates=['message', 'callback_query'],
        drop_pending_updates=True
    ))

if __name__ == '__main__':
    # Iniciar bot de Telegram en thread separado
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # Iniciar Flask (para keep-alive y tracking de referidos)
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False)
