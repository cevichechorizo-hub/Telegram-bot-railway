#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import asyncio
import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, ContextTypes
from flask import Flask, request, jsonify

logging.disable(logging.CRITICAL)

BOT_TOKEN = "8687327095:AAGn0C3_hJJJrf6oqcXf5kNZzuQ_X-D5pjA"
TARGET_GROUP_ID = -1003534894759
WEBHOOK_URL = "https://telegram-bot-railway-production-1ec5.up.railway.app/webhook"

app = Flask(__name__)
application = None
admin_cache = set()
admin_time = 0

async def check_admin(context, uid):
    global admin_cache, admin_time
    import time
    t = time.time()
    if t - admin_time < 600:
        return uid in admin_cache
    try:
        admin_cache = {a.user.id for a in await context.bot.get_chat_administrators(TARGET_GROUP_ID)}
        admin_time = t
    except:
        pass
    return uid in admin_cache

async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat_id != TARGET_GROUP_ID or await check_admin(context, update.message.from_user.id):
        return
    
    if not update.message.from_user.username:
        # Borrar y enviar notificación EN PARALELO (sin esperar)
        asyncio.create_task(update.message.delete())
        
        msg = await context.bot.send_message(
            TARGET_GROUP_ID,
            "<b>❌ No puedes enviar mensajes a este grupo porque no tienes un nombre de usuario.</b>\n\nPara que puedas escribir, ponte un nombre de usuario.\n\nPresiona el botón de abajo para ver las instrucciones 👇",
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📖 Ver instrucciones", url="https://t.me/Aliaselmenchobot?start=help")]])
        )
        
        # Borrar notificación después de 30 segundos
        async def del30():
            await asyncio.sleep(30)
            try:
                await context.bot.delete_message(TARGET_GROUP_ID, msg.message_id)
            except:
                pass
        
        asyncio.create_task(del30())

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = await context.bot.send_message(
        update.message.from_user.id,
        "<b>📋 CÓMO CREAR TU NOMBRE DE USUARIO</b>\n\n1️⃣ Abre Telegram → Toca tu foto de perfil\n2️⃣ Toca 'Editar perfil'\n3️⃣ Busca 'Nombre de usuario' (desplázate abajo)\n4️⃣ Escribe tu nombre único (sin espacios, letras y números)\n5️⃣ Toca el icono de verificación (✓)\n\n<b>✅ ¡Listo! Ahora puedes escribir en el grupo.</b>",
        parse_mode='HTML'
    )
    
    async def del60():
        await asyncio.sleep(60)
        try:
            await context.bot.delete_message(update.message.from_user.id, msg.message_id)
        except:
            pass
    
    asyncio.create_task(del60())

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json()
        update = Update.de_json(data, application.bot)
        
        # Procesar en background (no bloquear respuesta)
        asyncio.create_task(process_update(update))
        
        return jsonify({"ok": True}), 200
    except Exception as e:
        print(f"Error en webhook: {e}")
        return jsonify({"ok": False}), 500

async def process_update(update: Update):
    try:
        context = ContextTypes.DEFAULT_TYPE()
        context.bot = application.bot
        context.application = application
        
        if update.message:
            if update.message.text and update.message.text.startswith('/start'):
                await start(update, context)
            else:
                await handle_msg(update, context)
    except Exception as e:
        print(f"Error procesando update: {e}")

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"}), 200

async def setup_webhook():
    """Configura el webhook en Telegram"""
    try:
        await application.bot.set_webhook(
            url=WEBHOOK_URL,
            allowed_updates=["message", "callback_query"]
        )
        print(f"✅ Webhook configurado: {WEBHOOK_URL}")
    except Exception as e:
        print(f"❌ Error configurando webhook: {e}")

async def main():
    global application
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Inicializar la aplicación
    await application.initialize()
    
    # Configurar webhook
    await setup_webhook()
    
    print("✅ Bot webhook iniciado")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
