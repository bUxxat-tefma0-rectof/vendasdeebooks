from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from sqlalchemy import select, func
from app.database import AsyncSessionLocal, User, Product, Stock, Transaction, BotSettings
from app.config import Config

def is_admin(user_id: int) -> bool:
    return user_id == Config.ADMIN_ID

async def get_setting(key: str, default: str = ""):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(BotSettings).where(BotSettings.key == key))
        s = result.scalar_one_or_none()
        return s.value if s else default

async def set_setting(key: str, value: str):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(BotSettings).where(BotSettings.key == key))
        s = result.scalar_one_or_none()
        if s:
            s.value = value
        else:
            s = BotSettings(key=key, value=value)
            session.add(s)
        await session.commit()

async def admin_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = update.effective_user.id

    if not is_admin(user_id):
        if query:
            await query.answer("❌ Sem permissão.", show_alert=True)
        else:
            await update.message.reply_text("❌ Você não tem permissão.")
        return

    if query:
        await query.answer()
        data = query.data
    else:
        data = "admin_dashboard"

    if data == "admin_dashboard" or data == "admin":
        async with AsyncSessionLocal() as session:
            total_users = (await session.execute(select(func.count(User.id)))).scalar()
            total_sales = (await session.execute(
                select(func.sum(Transaction.amount)).where(Transaction.type == "purchase", Transaction.status == "completed")
            )).scalar() or 0.0
            total_revenue = (await session.execute(
                select(func.sum(Transaction.amount)).where(Transaction.type == "pix", Transaction.status == "completed")
            )).scalar() or 0.0
            total_products = (await session.execute(select(func.count(Product.id)).where(Product.is_active == True))).scalar()
            total_stock = (await session.execute(select(func.count(Stock.id)).where(Stock.is_sold == False))).scalar()

        keyboard = [
            [InlineKeyboardButton("⚙️ Configurações", callback_data="admin_settings")],
            [InlineKeyboardButton("⚡ Ações", callback_data="admin_actions")],
            [InlineKeyboardButton("💳 Transações", callback_data="admin_transactions")],
            [InlineKeyboardButton("📢 Atualizações", callback_data="admin_updates")],
        ]

        text = (
            f"🤖 *Painel Admin*\n\n"
            f"👥 Usuários: {total_users}\n"
            f"📦 Produtos ativos: {total_products}\n"
            f"🗃 Estoque disponível: {total_stock}\n"
            f"💰 Receita total (Pix): R$ {total_revenue:.2f}\n"
            f"🛍 Vendas totais: R$ {total_sales:.2f}"
        )

        if query:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        else:
            await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data == "admin_settings":
        await show_settings_menu(update, context)

    elif data == "admin_actions":
        await show_actions_menu(update, context)

    elif data == "admin_transactions":
        await show_transactions_menu(update, context)

    elif data == "admin_updates":
        await show_updates_menu(update, context)

    else:
        await handle_admin_callbacks(update, context, data)

async def show_settings_menu(update, context):
    keyboard = [
        [InlineKeyboardButton("🔧 Configurações Gerais", callback_data="admin_general")],
        [InlineKeyboardButton("👤 Gerenciar Usuários", callback_data="admin_users")],
        [InlineKeyboardButton("💳 Configurar Pix", callback_data="admin_pix")],
        [InlineKeyboardButton("📦 Gerenciar Produtos", callback_data="admin_products")],
        [InlineKeyboardButton("🤝 Configurar Afiliados", callback_data="admin_affiliates_config")],
        [InlineKeyboardButton("🔙 Voltar", callback_data="admin_dashboard")],
    ]
    query = update.callback_query
    await query.edit_message_text("⚙️ *Configurações*\n\nEscolha uma opção:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def show_actions_menu(update, context):
    keyboard = [
        [InlineKeyboardButton("🚫 Banir Usuário", callback_data="admin_ban")],
        [InlineKeyboardButton("✅ Desbanir Usuário", callback_data="admin_unban")],
        [InlineKeyboardButton("🎁 Enviar Gift", callback_data="admin_gift")],
        [InlineKeyboardButton("📢 Transmissão", callback_data="admin_broadcast")],
        [InlineKeyboardButton("🔙 Voltar", callback_data="admin_dashboard")],
    ]
    query = update.callback_query
    await query.edit_message_text("⚡ *Ações*\n\nEscolha uma ação:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def show_transactions_menu(update, context):
    async with AsyncSessionLocal() as session:
        pix_total = (await session.execute(
            select(func.sum(Transaction.amount)).where(Transaction.type == "pix", Transaction.status == "completed")
        )).scalar() or 0.0
        sales_total = (await session.execute(
            select(func.sum(Transaction.amount)).where(Transaction.type == "purchase", Transaction.status == "completed")
        )).scalar() or 0.0
        pix_count = (await session.execute(
            select(func.count(Transaction.id)).where(Transaction.type == "pix", Transaction.status == "completed")
        )).scalar() or 0
        sales_count = (await session.execute(
            select(func.count(Transaction.id)).where(Transaction.type == "purchase", Transaction.status == "completed")
        )).scalar() or 0

    keyboard = [
        [InlineKeyboardButton("💳 Ver Recargas", callback_data="admin_view_recharges")],
        [InlineKeyboardButton("🛍 Ver Compras", callback_data="admin_view_purchases")],
        [InlineKeyboardButton("🔙 Voltar", callback_data="admin_dashboard")],
    ]

    text = (
        f"💳 *Transações*\n\n"
        f"💰 Recargas: {pix_count} transações — R$ {pix_total:.2f}\n"
        f"🛍 Compras: {sales_count} transações — R$ {sales_total:.2f}"
    )

    query = update.callback_query
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def show_updates_menu(update, context):
    keyboard = [
        [InlineKeyboardButton("📢 Avisar sobre novo produto", callback_data="admin_notify_product")],
        [InlineKeyboardButton("🔙 Voltar", callback_data="admin_dashboard")],
    ]
    query = update.callback_query
    await query.edit_message_text(
        "📢 *Atualizações*\n\nEnvie avisos sobre novos produtos para todos os usuários:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def handle_admin_callbacks(update, context, data):
    pass

async def handle_admin_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass
