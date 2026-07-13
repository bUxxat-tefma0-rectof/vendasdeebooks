from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, ContextTypes
from ...database import Database
import logging

logger = logging.getLogger(__name__)

async def show_shop(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Exibe a loja com categorias"""
    query = update.callback_query
    user_id = query.from_user.id
    
    db_user = db.get_user(user_id)
    
    if not db_user:
        await query.edit_message_text("❌ Erro ao carregar. Use /start")
        return
    
    # Busca categorias
    categorias = db.get_categorias()
    
    shop_text = f"""
🛍️ *LOJA DE LOGINS | CONTAS PREMIUM*

💰 *Seu Saldo:* R$ {db_user.saldo:.2f}

📂 *Categorias disponíveis:*
"""
    
    # Cria botões para cada categoria
    keyboard = []
    
    if categorias:
        for cat in categorias:
            emoji = cat.emoji or "📦"
            keyboard.append([
                InlineKeyboardButton(
                    f"{emoji} {cat.nome}",
                    callback_data=f"cat_{cat.id}"
                )
            ])
    else:
        shop_text += "\n⚠️ Nenhuma categoria disponível no momento."
    
    # Botão voltar
    keyboard.append([InlineKeyboardButton("🔙 VOLTAR", callback_data="menu_principal")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=shop_text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def show_products(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database, categoria_id: int):
    """Mostra produtos de uma categoria específica"""
    query = update.callback_query
    user_id = query.from_user.id
    
    db_user = db.get_user(user_id)
    produtos = db.get_produtos_by_categoria(categoria_id)
    
    products_text = f"""
🛍️ *PRODUTOS DISPONÍVEIS*

💰 *Seu Saldo:* R$ {db_user.saldo:.2f}

📦 *Escolha um produto:*
"""
    
    keyboard = []
    
    if produtos:
        for prod in produtos:
            if prod.estoque > 0:
                keyboard.append([
                    InlineKeyboardButton(
                        f"✅ {prod.nome} - R$ {prod.valor:.2f} ({prod.estoque} un.)",
                        callback_data=f"prod_{prod.id}"
                    )
                ])
            else:
                keyboard.append([
                    InlineKeyboardButton(
                        f"❌ {prod.nome} - ESGOTADO",
                        callback_data="estoque_esgotado"
                    )
                ])
    else:
        products_text += "\n⚠️ Nenhum produto nesta categoria."
    
    keyboard.append([InlineKeyboardButton("🔙 VOLTAR", callback_data="loja")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(
        text=products_text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

# Handler para a loja
shop_handler = CallbackQueryHandler(
    lambda u, c: show_shop(u, c, None),
    pattern="^loja$"
)
