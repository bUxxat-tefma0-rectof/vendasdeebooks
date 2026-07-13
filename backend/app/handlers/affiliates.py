from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from sqlalchemy import select, func
from app.database import AsyncSessionLocal, User, Transaction
from app.config import Config

async def affiliates_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    is_command = update.message is not None

    if query:
        await query.answer()

    user_tg = update.effective_user

    async with AsyncSessionLocal() as session:
        user_result = await session.execute(select(User).where(User.telegram_id == user_tg.id))
        user = user_result.scalar_one_or_none()

        referrals_result = await session.execute(
            select(func.count(User.id)).where(User.referred_by == user_tg.id)
        )
        total_referrals = referrals_result.scalar() or 0

        earnings_result = await session.execute(
            select(func.sum(Transaction.amount)).where(
                Transaction.user_id == user.id,
                Transaction.type == "affiliate",
                Transaction.status == "completed"
            )
        )
        total_earnings = earnings_result.scalar() or 0.0

    bot_info = await context.bot.get_me()
    bot_username = bot_info.username
    affiliate_link = f"https://t.me/{bot_username}?start={user_tg.id}"

    keyboard = [[InlineKeyboardButton("🔙 Voltar", callback_data="start")]]

    text = (
        f"🤝 *Programa de Afiliados*\n\n"
        f"{'✅ Sistema Ativo' if Config.AFFILIATE_ENABLED else '❌ Sistema Desativado'}\n\n"
        f"💰 Comissão: {Config.AFFILIATE_COMMISSION}% por recarga\n"
        f"👥 Indicados: {total_referrals}\n"
        f"💵 Total ganho: R$ {total_earnings:.2f}\n\n"
        f"🔗 *Seu link de indicação:*\n`{affiliate_link}`"
    )

    if query:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
