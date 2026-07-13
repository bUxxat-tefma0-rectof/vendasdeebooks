import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes
)
from .config import config

logger = logging.getLogger(__name__)

class StoreBot:
    """Bot principal de vendas"""
    
    def __init__(self):
        self.application = None
        self.db = None
        
    async def setup(self):
        logger.info("🚀 Inicializando StoreBot...")
        
        self.application = Application.builder().token(config.BOT_TOKEN).build()
        self._register_handlers()
        
        logger.info(f"✅ Bot {config.NOME_BOT} v{config.VERSAO} configurado!")
        
    def _register_handlers(self):
        """Registra handlers"""
        db = self.db  # Captura a instância do banco
        
        # Comando /start
        async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
            user = update.effective_user
            
            # Salva usuário no banco
            if db:
                try:
                    db.get_or_create_user(user.id, user.first_name or "", user.username or "")
                except Exception as e:
                    logger.error(f"Erro ao criar usuário: {e}")
            
            welcome_text = f"""
🎉 *BEM-VINDO AO {config.NOME_BOT}!*

👤 *Usuário:* {user.first_name}
🆔 *Seu ID:* `{user.id}`

🔹 *Escolha uma opção:*
"""
            
            keyboard = [
                [InlineKeyboardButton("🛒 LOJA", callback_data="menu_loja")],
                [InlineKeyboardButton("👤 PERFIL", callback_data="menu_perfil")],
                [InlineKeyboardButton("💳 RECARGA", callback_data="menu_recarga")],
                [InlineKeyboardButton("🏆 RANKING", callback_data="menu_ranking")],
                [InlineKeyboardButton("📞 SUPORTE", callback_data="menu_info")],
            ]
            
            await update.message.reply_text(
                welcome_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        
        # Callback handler
        async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
            query = update.callback_query
            await query.answer()
            
            data = query.data
            
            respostas = {
                "menu_loja": "🛒 *LOJA*\n\nEm breve os produtos estarão disponíveis!",
                "menu_perfil": "👤 *PERFIL*\n\nEm breve você poderá ver seu perfil completo!",
                "menu_recarga": "💳 *RECARGA*\n\nUse /pix + valor para recarregar!\nExemplo: /pix 50",
                "menu_ranking": "🏆 *RANKING*\n\nEm breve!",
                "menu_info": "📞 *SUPORTE*\n\nEntre em contato com o administrador.",
                "menu_principal": "🔙 Voltando ao menu principal..."
            }
            
            resposta = respostas.get(data, "Opção em desenvolvimento...")
            
            if data == "menu_principal":
                await start_cmd(update, context)
            else:
                keyboard = [[InlineKeyboardButton("🔙 VOLTAR", callback_data="menu_principal")]]
                await query.edit_message_text(
                    resposta,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode="Markdown"
                )
        
        self.application.add_handler(CommandHandler("start", start_cmd))
        self.application.add_handler(CallbackQueryHandler(handle_callback))
        
        # Erro handler
        async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
            logger.error(f"❌ Erro: {context.error}")
        
        self.application.add_error_handler(error_handler)
