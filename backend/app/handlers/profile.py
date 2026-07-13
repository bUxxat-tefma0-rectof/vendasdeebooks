from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from sqlalchemy import select
from app.database import AsyncSessionLocal, User, Transaction, Product

async def profile_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()

    user_tg = update.effective_user
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.telegram_id == user_tg.id))
        user = result.scalar_one_or_none()

    keyboard = [
        [InlineKeyboardButton("📋 Histórico de Compras", callback_data="history")],
        [InlineKeyboardButton("🔙 Voltar", callback_data="start")]
    ]

    text = (
        f"👤 *Meu Perfil*\n\n"
        f"🆔 ID: `{user_tg.id}`\n"
        f"💰 Saldo: R$ {user.balance:.2f}\n"
        f"📱 WhatsApp: {user.whatsapp or 'Não cadastrado'}\n"
        f"🔗 Código de afiliado: `{user.affiliate_code}`"
    )

    if query:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def history_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if query:
        await query.answer()

    user_tg = update.effective_user
    async with AsyncSessionLocal() as session:
        user_result = await session.execute(select(User).where(User.telegram_id == user_tg.id))
        user = user_result.scalar_one_or_none()
        tx_result = await session.execute(
            select(Transaction).where(Transaction.user_id == user.id, Transaction.type == "purchase").order_by(Transaction.created_at.desc()).limit(10)
        )
        transactions = tx_result.scalars().all()

    if not transactions:
        text = "📋 *Histórico de Compras*\n\nVocê ainda não fez nenhuma compra."
    else:
        text = "📋 *Histórico de Compras*\n\n"
        for tx in transactions:
            text += f"🛍 Produto ID: {tx.product_id} — R$ {tx.amount:.2f} — {tx.created_at.strftime('%d/%m/%Y %H:%M')}\n"

    keyboard = [[InlineKeyboardButton("🔙 Voltar", callback_data="profile")]]
    if query:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
