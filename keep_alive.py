#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Script para mantener el bot despierto.
Pincha el bot cada 5 minutos para evitar que Railway lo duerma.
"""

import asyncio
import logging
from telegram import Bot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = "8687327095:AAGn0C3_hJJJrf6oqcXf5kNZzuQ_X-D5pjA"
TARGET_GROUP_ID = -1003534894759

async def keep_alive():
    """Mantener el bot despierto."""
    bot = Bot(token=BOT_TOKEN)
    
    logger.info("🔔 Keep-alive iniciado - Pinchazo cada 5 minutos")
    
    while True:
        try:
            # Esperar 5 minutos
            await asyncio.sleep(300)
            
            # Pinchar el bot obteniendo info del grupo
            chat = await bot.get_chat(TARGET_GROUP_ID)
            logger.info(f"✅ Pinchazo OK - Grupo: {chat.title}")
        
        except Exception as e:
            logger.error(f"❌ Error en keep-alive: {e}")
            # Esperar 1 minuto antes de reintentar
            await asyncio.sleep(60)

if __name__ == "__main__":
    try:
        asyncio.run(keep_alive())
    except KeyboardInterrupt:
        logger.info("⛔ Keep-alive detenido")
    except Exception as e:
        logger.error(f"❌ Error fatal: {e}")
