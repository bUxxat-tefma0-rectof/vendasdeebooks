import asyncio
import base64
from io import BytesIO
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from sqlalchemy import select
from app.database import AsyncSessionLocal, User, Transaction
from app.payments import create_pix_payment, check_payment_status
from app.config import Config
from datetime import datetime

WAITING_PIX_AMOUNT = {}

async def recharge_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_tg = update.effective_user
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.telegram_id == user_tg.id))
        user = result.scalar_one_or_none()

    keyboard = [
        [InlineKeyboardButton("💳 Pagar com Pix", callback_data="recharge_pix")],
        [InlineKeyboardButton("🔙 Voltar", callback_data="start")]
    ]

    text = (
        f"💰 *Recarga*\n\n"
        f"🆔 ID: `{user_tg.id}`\n"
        f"💰 Saldo atual: R$ {user.balance:.2f}\n\n"
        f"Mínimo: R$ {Config.PIX_MIN_VALUE:.2f}\n"
        f"Máximo: R$ {Config.PIX_MAX_VALUE:.2f}"
    )

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def recharge_pix_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    WAITING_PIX_AMOUNT[update.effective_user.id] = True

    await query.edit_message_text(
        f"💳 *Pagamento via Pix*\n\n"
        f"Digite o valor que deseja recarregar:\n"
        f"_(Mínimo: R$ {Config.PIX_MIN_VALUE:.2f} | Máximo: R$ {Config.PIX_MAX_VALUE:.2f})_",
        parse_mode="Markdown"
    )

async def pix_amount_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id not in WAITING_PIX_AMOUNT:
        return

    del WAITING_PIX_AMOUNT[user_id]

    try:
        amount = float(update.message.text.replace(",", "."))
    except ValueError:
        await update.message.reply_text("❌ Valor inválido. Digite apenas números. Ex: 20 ou 20.50")
        return

    if amount < Config.PIX_MIN_VALUE or amount > Config.PIX_MAX_VALUE:
        await update.message.reply_text(
            f"❌ Valor fora do limite.\n"
            f"Mínimo: R$ {Config.PIX_MIN_VALUE:.2f}\n"
            f"Máximo: R$ {Config.PIX_MAX_VALUE:.2f}"
        )
        return

    msg = await update.message.reply_text("⏳ Gerando Pix, aguarde...")

    try:
        pix = await create_pix_payment(user_id, amount)
    except Exception as e:
        await msg.edit_text(f"❌ Erro ao gerar Pix: {e}")
        return

    # Salva transação pendente
    async with AsyncSessionLocal() as session:
        user_result = await session.execute(select(User).where(User.telegram_id == user_id))
        user = user_result.scalar_one_or_none()
        tx = Transaction(
            user_id=user.id,
            type="pix",
            amount=amount,
            status="pending",
            payment_id=str(pix["payment_id"])
        )
        session.add(tx)
        await session.commit()
        tx_id = tx.id

    # Envia QR Code
    qr_image = base64.b64decode(pix["qr_code_base64"])
    bio = BytesIO(qr_image)
    bio.name = "qrcode.png"

    await context.bot.send_photo(
        chat_id=update.effective_chat.id,
        photo=bio,
        caption=(
            f"✅ *Pix Gerado!*\n\n"
            f"💰 Valor: R$ {amount:.2f}\n"
            f"⏳ Expira em: {Config.PIX_EXPIRATION_MINUTES} minutos\n\n"
            f"*Pix Copia e Cola:*\n`{pix['qr_code']}`\n\n"
            f"_Aguardando pagamento..._"
        ),
        parse_mode="Markdown"
    )

    await msg.delete()

    # Verifica pagamento em loop
    asyncio.create_task(check_payment_loop(context, user_id, pix["payment_id"], amount, tx_id, update.effective_chat.id))

async def check_payment_loop(context, user_id, payment_id, amount, tx_id, chat_id):
    max_checks = Config.PIX_EXPIRATION_MINUTES * 2  # checa a cada 30s
    for _ in range(max_checks):
        await asyncio.sleep(30)
        status = await check_payment_status(str(payment_id))

        if status == "approved":
            async with AsyncSessionLocal() as session:
                user_result = await session.execute(select(User).where(User.telegram_id == user_id))
                user = user_result.scalar_one_or_none()

                bonus = amount * (Config.DEPOSIT_BONUS / 100)
                user.balance += amount + bonus

                tx_result = await session.execute(select(Transaction).where(Transaction.id == tx_id))
                tx = tx_result.scalar_one_or_none()
                tx.status = "completed"
                await session.commit()

            bonus_text = f"\n🎁 Bônus: R$ {bonus:.2f}" if bonus > 0 else ""
            await context.bot.send_message(
                chat_id=chat_id,
                text=(
                    f"✅ *Pagamento confirmado!*\n\n"
                    f"💰 Valor: R$ {amount:.2f}{bonus_text}\n"
                    f"💳 Saldo atualizado!"
                ),
                parse_mode="Markdown"
            )
            return

    # Expirou
    async with AsyncSessionLocal() as session:
        tx_result = await session.execute(select(Transaction).where(Transaction.id == tx_id))
        tx = tx_result.scalar_one_or_none()
        if tx and tx.status == "pending":
            tx.status = "failed"
            await session.commit()

    await context.bot.send_message(chat_id=chat_id, text="⌛ Pix expirado. Gere um novo se quiser recarregar.")

async def pix_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❌ Use: /pix 20")
        return

    try:
        amount = float(context.args[0].replace(",", "."))
    except ValueError:
        await update.message.reply_text("❌ Valor inválido. Ex: /pix 20")
        return

    update.message.text = str(amount)
    WAITING_PIX_AMOUNT[update.effective_user.id] = True
    await pix_amount_message_handler(update, context)
