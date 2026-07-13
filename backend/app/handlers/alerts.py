from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from sqlalchemy import select
from app.database import AsyncSessionLocal, User, Product, Alert

async def alerts_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    is_command = update.message is not None

    if query:
        await query.answer()
        data = query.data
    else:
        data = "alerts_menu"

    user_tg = update.effective_user

    if data == "alerts_menu" or data == "alertas":
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Product).where(Product.is_active == True))
            products = result.scalars().all()

            user_result = await session.execute(select(User).where(User.telegram_id == user_tg.id))
            user = user_result.scalar_one_or_none()

            alert_result = await session.execute(select(Alert).where(Alert.user_id == user.id, Alert.is_active == True))
            active_alerts = [a.product_id for a in alert_result.scalars().all()]

        keyboard = []
        for p in products:
            status = "🔔" if p.id in active_alerts else "🔕"
            keyboard.append([InlineKeyboardButton(f"{status} {p.name}", callback_data=f"alerts_toggle_{p.id}")])
        keyboard.append([InlineKeyboardButton("🔙 Voltar", callback_data="start")])

        text = "🔔 *Alertas de Reabastecimento*\n\nAtive o alerta para ser notificado quando um produto for reabastecido:"

        if query:
            await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
        else:
            await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data.startswith("alerts_toggle_"):
        product_id = int(data.replace("alerts_toggle_", ""))

        async with AsyncSessionLocal() as session:
            user_result = await session.execute(select(User).where(User.telegram_id == user_tg.id))
            user = user_result.scalar_one_or_none()

            alert_result = await session.execute(
                select(Alert).where(Alert.user_id == user.id, Alert.product_id == product_id)
            )
            alert = alert_result.scalar_one_or_none()

            if alert:
                alert.is_active = not alert.is_active
                status = "ativado" if alert.is_active else "desativado"
            else:
                alert = Alert(user_id=user.id, product_id=product_id, is_active=True)
                session.add(alert)
                status = "ativado"

            await session.commit()

        await query.answer(f"🔔 Alerta {status}!", show_alert=True)

        # Recarrega o menu
        await alerts_handler(update, context)

async def notify_restock(context, product_id: int, product_name: str):
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Alert).where(Alert.product_id == product_id, Alert.is_active == True)
        )
        alerts = result.scalars().all()

        for alert in alerts:
            user_result = await session.execute(select(User).where(User.id == alert.user_id))
            user = user_result.scalar_one_or_none()
            if user:
                try:
                    await context.bot.send_message(
                        chat_id=user.telegram_id,
                        text=f"🔔 *Produto reabastecido!*\n\n🛍 *{product_name}* está disponível novamente!\n\nAcesse a loja para comprar.",
                        parse_mode="Markdown"
                    )
                except Exception:
                    pass
