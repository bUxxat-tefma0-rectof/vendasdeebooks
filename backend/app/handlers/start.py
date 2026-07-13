from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from sqlalchemy import select
from app.database import AsyncSessionLocal, User
from app.config import Config
import random, string

def generate_affiliate_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

async def get_or_create_user(telegram_id, username, full_name, referred_by=None):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if not user:
            bonus = float(Config.REGISTER_BONUS)
            user = User(
                telegram_id=telegram_id,
                username=username,
                full_name=full_name,
                balance=bonus,
                affiliate_code=generate_affiliate_code(),
                referred_by=referred_by
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)
        return user

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_tg = update.effective_user
    args = context.args
    referred_by = int(args[0]) if args else None
    user = await get_or_create_user(user_tg.id, user_tg.username, user_tg.full_name, referred_by)

    if user.is_banned:
        await update.message.reply_text("🚫 Você foi banido do bot.")
        return

    keyboard = [
        [InlineKeyboardButton("🛒 Loja", callback_data="shop")],
        [InlineKeyboardButton("👤 Perfil", callback_data="profile"),
         InlineKeyboardButton("💰 Recarga", callback_data="recharge")],
        [InlineKeyboardButton("🏆 Ranking", callback_data="ranking")],
        [InlineKeyboardButton("🆘 Suporte", callback_data="support"),
         InlineKeyboardButton("ℹ️ Informações", callback_data="support_info")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = (
        f"👋 Olá, *{user_tg.first_name}*!\n\n"
        f"🆔 ID: `{user_tg.id}`\n"
        f"💰 Saldo: R$ {user.balance:.2f}\n"
        f"👤 Usuário: @{user_tg.username or 'sem username'}\n\n"
        f"Escolha uma opção abaixo:"
    )

    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode="Markdown")
