#!/usr/bin/env python3
"""
Bot de Vendas Telegram - Ponto de entrada principal
"""
import asyncio
import logging
import sys
import os
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)


def check_env():
    """Verifica variáveis de ambiente"""
    required_vars = ['BOT_TOKEN']
    missing = []
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)
    if missing:
        logger.error(f"❌ Variáveis faltando: {', '.join(missing)}")
        sys.exit(1)
    logger.info("✅ Variáveis de ambiente verificadas!")


async def main():
    """Função principal"""
    try:
        logger.info("=" * 50)
        logger.info("🤖 INICIANDO BOT DE VENDAS")
        logger.info(f"📅 {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        logger.info("=" * 50)
        
        check_env()
        
        from app.database.connection import Database
        
        # URL FIXA DO SEU BANCO NO RENDER
        DATABASE_URL = "postgresql://xixa00marketingoff_user:dVejVbGNqXI2EyafJXlYv4eMovSiWsuT@dpg-d98ovvreo5us73fgjuig-a.oregon-postgres.render.com/xixa00marketingoff"
        
        logger.info("📊 Conectando ao PostgreSQL no Render...")
        
        db = Database(DATABASE_URL)
        db.create_tables()
        
        from app.bot import StoreBot
        
        bot = StoreBot()
        bot.db = db
        await bot.setup()
        
        logger.info("🚀 Bot iniciado!")
        
        await bot.application.run_polling(
            allowed_updates=['message', 'callback_query'],
            drop_pending_updates=True
        )
        
    except KeyboardInterrupt:
        logger.info("👋 Bot finalizado")
    except Exception as e:
        logger.error(f"❌ Erro fatal: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
