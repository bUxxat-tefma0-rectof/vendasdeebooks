#!/usr/bin/env python3
"""
Bot de Vendas Telegram - Ponto de entrada principal
Versão: 1.0.0
"""

import asyncio
import logging
import sys
from app.bot import bot

# Configuração de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bot_vendas.log', encoding='utf-8')
    ]
)

logger = logging.getLogger(__name__)

def main():
    """Função principal"""
    try:
        logger.info("=" * 50)
        logger.info("🤖 INICIANDO BOT DE VENDAS")
        logger.info("=" * 50)
        
        # Configura e inicia o bot
        asyncio.run(bot.setup())
        bot.run()
        
    except KeyboardInterrupt:
        logger.info("👋 Bot finalizado pelo usuário")
    except Exception as e:
        logger.error(f"❌ Erro fatal: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
