from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, ContextTypes
from ...database import Database
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Exibe o perfil do usuário"""
    query = update.callback_query
    user_id = query.from_user.id
    
    db_user = db.get_user(user_id)
    
    if not db_user:
        await query.edit_message_text("❌ Erro ao carregar perfil. Use /start")
        return
    
    # Calcula total de compras
    total_compras = 0
    if hasattr(db_user, 'compras'):
        total_compras = len(db_user.compras)
    
    profile_text = f"""
👤 *MEU PERFIL*

🆔 *ID:* `{db_user.telegram_id}`
👤 *Nome:* {db_user.nome or 'Não definido'}
📱 *Username:* @{db_user.username or 'Não definido'}
📞 *WhatsApp:* {db_user.whatsapp or 'Não cadastrado'}

💰 *Saldo Atual:* R$ {db_user.saldo:.2f}
🛒 *Total de Compras:* {total_compras}
📅 *Registro:* {db_user.data_registro.strftime('%d/%m/%Y') if db_user.data_registro else 'N/A'}

🔗 *Código Afiliado:* `{db_user.codigo_afiliado or 'Não disponível'}`
💎 *Comissões:* R$ {db_user.comissao_acumulada:.2f}
"""
    
    keyboard = [
        [InlineKeyboardButton("📊 HISTÓRICO DE COMPRAS", callback_data="historico")],
        [InlineKeyboardButton("📱 CADASTRAR WHATSAPP", callback_data="add_whatsapp")],
        [InlineKeyboardButton("🔗 AFILIADOS", callback_data="afiliados")],
        [InlineKeyboardButton("🔙 VOLTAR", callback_data="menu_principal")]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=profile_text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def show_history(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Mostra o histórico de compras"""
    query = update.callback_query
    user_id = query.from_user.id
    
    db_user = db.get_user(user_id)
    
    if not db_user or not hasattr(db_user, 'compras') or not db_user.compras:
        await query.edit_message_text(
            "📊 *HISTÓRICO DE COMPRAS*\n\n"
            "⚠️ Você ainda não realizou nenhuma compra.\n\n"
            "🛍️ Volte para a loja e escolha um produto!",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 VOLTAR", callback_data="perfil")
            ]]),
            parse_mode="Markdown"
        )
        return
    
    history_text = "📊 *HISTÓRICO DE COMPRAS*\n\n"
    
    for i, compra in enumerate(db_user.compras[:10], 1):
        produto_nome = compra.produto.nome if hasattr(compra, 'produto') else "Produto"
        data = compra.data.strftime('%d/%m/%Y %H:%M') if compra.data else "N/A"
        history_text += f"{i}. {produto_nome}\n"
        history_text += f"   💰 R$ {compra.valor:.2f} | 📅 {data}\n\n"
    
    keyboard = [[InlineKeyboardButton("🔙 VOLTAR", callback_data="perfil")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=history_text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

# Handler para o perfil
profile_handler = CallbackQueryHandler(
    lambda u, c: show_profile(u, c, None),
    pattern="^perfil$"
)

# Handler para histórico
history_handler = CallbackQueryHandler(
    lambda u, c: show_history(u, c, None),
    pattern="^historico$"
)
