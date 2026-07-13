import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)
from .config import config
from .database import Database
from .database.models import Base

# Configuração de logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=getattr(logging, config.LOG_LEVEL)
)
logger = logging.getLogger(__name__)

class StoreBot:
    """Bot principal de vendas"""
    
    def __init__(self):
        """Inicializa o bot"""
        self.application = None
        self.db = None
        
    async def setup(self):
        """Configura o bot e banco de dados"""
        logger.info("🚀 Inicializando StoreBot...")
        
        # Inicializa banco de dados
        self.db = Database(config.DATABASE_URL)
        self.db.create_tables()
        logger.info("✅ Banco de dados conectado!")
        
        # Cria aplicação do bot
        self.application = Application.builder().token(config.BOT_TOKEN).build()
        
        # Registra handlers
        self._register_handlers()
        
        logger.info(f"✅ Bot {config.NOME_BOT} v{config.VERSAO} configurado!")
        
    def _register_handlers(self):
        """Registra todos os handlers do bot"""
        from .handlers.cliente.start import start_handler
        from .handlers.cliente.shop import shop_handler
        from .handlers.cliente.profile import profile_handler
        
        # Comandos
        self.application.add_handler(CommandHandler("start", self._start_command))
        
        # Handlers modulares
        self.application.add_handler(start_handler)
        self.application.add_handler(shop_handler)
        self.application.add_handler(profile_handler)
        
        # Callback queries
        self.application.add_handler(CallbackQueryHandler(self._handle_callback))
        
        # Mensagens
        self.application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._handle_message)
        )
        
        # Erro handler
        self.application.add_error_handler(self._error_handler)
        
    async def _start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Comando /start"""
        from .handlers.cliente.start import cmd_start
        await cmd_start(update, context, self.db)
    
    async def _handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Gerencia todos os callbacks"""
        query = update.callback_query
        await query.answer()
        
        # Router de callbacks
        callback_routes = {
            "menu_principal": self._menu_principal,
            "loja": self._show_shop,
            "perfil": self._show_profile,
            "voltar": self._menu_principal,
        }
        
        data = query.data
        if data in callback_routes:
            await callback_routes[data](update, context)
    
    async def _handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Gerencia mensagens de texto"""
        user_id = update.effective_user.id
        
        # Verifica se está em modo de manutenção
        # Processa comandos especiais
        # etc.
        
        await update.message.reply_text(
            f"👋 Use os botões do menu para navegar!\n"
            f"Seu ID: {user_id}"
        )
    
    async def _menu_principal(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Retorna ao menu principal"""
        from .handlers.cliente.start import show_main_menu
        await show_main_menu(update, context, self.db)
    
    async def _show_shop(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Mostra a loja"""
        from .handlers.cliente.shop import show_shop
        await show_shop(update, context, self.db)
    
    async def _show_profile(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Mostra o perfil"""
        from .handlers.cliente.profile import show_profile
        await show_profile(update, context, self.db)
    
    async def _error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Gerencia erros do bot"""
        logger.error(f"❌ Erro: {context.error}")
        
        if update and update.effective_message:
            await update.effective_message.reply_text(
                "❌ Ocorreu um erro inesperado. Tente novamente mais tarde."
            )
    
    def run(self):
        """Inicia o bot"""
        if not self.application:
            raise RuntimeError("Bot não configurado! Execute setup() primeiro.")
        
        logger.info("🤖 Bot iniciado! Pressione CTRL+C para parar.")
        self.application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True
        )

# Instância global do bot
bot = StoreBot()
