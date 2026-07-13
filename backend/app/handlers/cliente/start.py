from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, ContextTypes, CommandHandler
from ...config import config
from ...database import Database
import logging

logger = logging.getLogger(__name__)

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Comando /start - Boas-vindas e menu principal"""
    user = update.effective_user
    user_id = user.id
    
    # Busca ou cria usuário no banco
    db_user = db.get_or_create_user(
        telegram_id=user_id,
        nome=user.first_name or "",
        username=user.username or ""
    )
    
    # Mensagem de boas-vindas
    welcome_text = f"""
🎉 *BEM-VINDO AO {config.NOME_BOT}* 🎉

👤 *Usuário:* {user.first_name}
🆔 *Seu ID:* `{user_id}`
💰 *Saldo:* R$ {db_user.saldo:.2f}

🔹 *Escolha uma opção abaixo:*
"""
    
    # Teclado principal
    keyboard = [
        [InlineKeyboardButton("🔐 LOGINS | CONTAS PREMIUM", callback_data="loja")],
        [
            InlineKeyboardButton("👤 PERFIL", callback_data="perfil"),
            InlineKeyboardButton("💳 RECARGA", callback_data="recarga")
        ],
        [InlineKeyboardButton("🏆 RANKING", callback_data="ranking")],
        [
            InlineKeyboardButton("📞 SUPORTE", url=config.GRUPO_SUPORTE_LINK),
            InlineKeyboardButton("ℹ️ INFORMAÇÕES", callback_data="info")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Envia mensagem com foto (se tiver)
    try:
        await update.message.reply_photo(
            photo=open("assets/banner.jpg", "rb") if __import__('os').path.exists("assets/banner.jpg") else None,
            caption=welcome_text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
    except:
        await update.message.reply_text(
            text=welcome_text,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Mostra o menu principal (via callback)"""
    query = update.callback_query
    user_id = query.from_user.id
    
    db_user = db.get_user(user_id)
    
    if not db_user:
        await query.edit_message_text("❌ Usuário não encontrado. Use /start")
        return
    
    welcome_text = f"""
🎉 *MENU PRINCIPAL*

👤 *Usuário:* {query.from_user.first_name}
🆔 *Seu ID:* `{user_id}`
💰 *Saldo:* R$ {db_user.saldo:.2f}

🔹 *Escolha uma opção abaixo:*
"""
    
    keyboard = [
        [InlineKeyboardButton("🔐 LOGINS | CONTAS PREMIUM", callback_data="loja")],
        [
            InlineKeyboardButton("👤 PERFIL", callback_data="perfil"),
            InlineKeyboardButton("💳 RECARGA", callback_data="recarga")
        ],
        [InlineKeyboardButton("🏆 RANKING", callback_data="ranking")],
        [
            InlineKeyboardButton("📞 SUPORTE", url=config.GRUPO_SUPORTE_LINK),
            InlineKeyboardButton("ℹ️ INFORMAÇÕES", callback_data="info")
        ]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=welcome_text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

# Handler para o comando /start
start_handler = CommandHandler("start", lambda u, c: cmd_start(u, c, None))
