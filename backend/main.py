#!/usr/bin/env python3
"""
Bot de Vendas Telegram - Ponto de entrada principal
Compatível com Render, Railway e VPS
"""
import asyncio
import logging
import sys
import os
from datetime import datetime

# Configura logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Verifica variáveis de ambiente obrigatórias
def check_env():
    """Verifica se todas as variáveis necessárias estão configuradas"""
    required_vars = [
        'BOT_TOKEN',
    ]
    
    missing = []
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)
    
    if missing:
        logger.error(f"❌ Variáveis de ambiente faltando: {', '.join(missing)}")
        logger.error("Configure as variáveis no painel do Render ou no arquivo .env")
        sys.exit(1)
    
    logger.info("✅ Variáveis de ambiente verificadas!")

async def main():
    """Função principal"""
    try:
        logger.info("=" * 50)
        logger.info("🤖 INICIANDO BOT DE VENDAS")
        logger.info(f"📅 {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        logger.info("=" * 50)
        
        # Verifica ambiente
        check_env()
        
        # Importa após verificação
        from app.bot import StoreBot
        from app.database.postgresql import db_manager
        from app.services.scheduler import iniciar_tarefas
        
        # Inicializa banco de dados
        database_url = os.getenv('DATABASE_URL', 'sqlite:///bot_vendas.db')
        logger.info(f"📊 Conectando ao banco: {database_url[:50]}...")
        
        db = db_manager.auto_init()
        
        # Cria e configura bot
        bot = StoreBot()
        bot.db = db
        await bot.setup()
        
        # Inicia tarefas automáticas
        await iniciar_tarefas(db, bot.application.bot)
        
        # Inicia o bot
        logger.info("🚀 Bot iniciado! Pressione CTRL+C para parar.")
        
        # Configura webhook ou polling
        render_env = os.getenv('RENDER', 'false').lower() == 'true'
        
        if render_env:
            # Modo webhook para Render
            port = int(os.getenv('PORT', 8080))
            webhook_url = os.getenv('WEBHOOK_URL', '')
            
            if webhook_url:
                await bot.application.bot.set_webhook(url=webhook_url)
                logger.info(f"🔗 Webhook configurado: {webhook_url}")
            
            # Inicia servidor web
            from aiohttp import web
            
            async def handle(request):
                return web.Response(text="Bot is running!")
            
            app = web.Application()
            app.router.add_get('/', handle)
            app.router.add_post('/webhook', handle)
            
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, '0.0.0.0', port)
            await site.start()
            
            logger.info(f"🌐 Servidor web rodando na porta {port}")
            
            # Mantém rodando
            while True:
                await asyncio.sleep(3600)
        else:
            # Modo polling (desenvolvimento)
            await bot.application.run_polling(
                allowed_updates=['message', 'callback_query'],
                drop_pending_updates=True
            )
        
    except KeyboardInterrupt:
        logger.info("👋 Bot finalizado pelo usuário")
    except Exception as e:
        logger.error(f"❌ Erro fatal: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
