#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, filters, ContextTypes, CommandHandler

logging.disable(logging.CRITICAL)

BOT_TOKEN = "8687327095:AAGn0C3_hJJJrf6oqcXf5kNZzuQ_X-D5pjA"
TARGET_GROUP_ID = -1003534894759
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

async def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS, handle_msg))
    
    await app.initialize()
    await app.start()
    await app.updater.start_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
