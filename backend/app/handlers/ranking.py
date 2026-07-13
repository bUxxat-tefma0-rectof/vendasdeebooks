from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from sqlalchemy import select, func, desc
from app.database import AsyncSessionLocal, User, Transaction

async def ranking_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    is_command = update.message is not None

    if query:
        await query.answer()
        data = query.data
    else:
        data = "ranking_compras"

    categories = {
        "ranking_compras": "🛍 Mais Compras",
        "ranking_recargas": "💰 Mais Recargas",
        "ranking_saldo": "💳 Maior Saldo",
    }

    keyboard = [
        [
            InlineKeyboardButton("🛍 Compras" if data != "ranking_compras" else "✅ Compras", callback_data="ranking_compras"),
            InlineKeyboardButton("💰 Recargas" if data != "ranking_recargas" else "✅ Recargas", callback_data="ranking_recargas"),
        ],
        [
            InlineKeyboardButton("💳 Saldo" if data != "ranking_saldo" else "✅ Saldo", callback_data="ranking_saldo"),
        ],
        [InlineKeyboardButton("🔙 Voltar", callback_data="start")]
    ]

    async with AsyncSessionLocal() as session:
        if data == "ranking_compras":
            result = await session.execute(
                select(User.full_name, func.count(Transaction.id).label("total"))
                .join(Transaction, Transaction.user_id == User.id)
                .where(Transaction.type == "purchase", Transaction.status == "completed")
                .group_by(User.id)
                .order_by(desc("total"))
                .limit(10)
            )
            rows = result.all()
            title = "🛍 Top 10 — Mais Compras"
            lines = [f"{i+1}. {r.full_name or 'Usuário'} — {r.total} compras" for i, r in enumerate(rows)]

        elif data == "ranking_recargas":
            result = await session.execute(
                select(User.full_name, func.sum(Transaction.amount).label("total"))
                .join(Transaction, Transaction.user_id == User.id)
                .where(Transaction.type == "pix", Transaction.status == "completed")
                .group_by(User.id)
                .order_by(desc("total"))
                .limit(10)
            )
            rows = result.all()
            title = "💰 Top 10 — Mais Recargas"
            lines = [f"{i+1}. {r.full_name or 'Usuário'} — R$ {r.total:.2f}" for i, r in enumerate(rows)]

        elif data == "ranking_saldo":
            result = await session.execute(
                select(User.full_name, User.balance)
                .order_by(desc(User.balance))
                .limit(10)
            )
            rows = result.all()
            title = "💳 Top 10 — Maior Saldo"
            lines = [f"{i+1}. {r.full_name or 'Usuário'} — R$ {r.balance:.2f}" for i, r in enumerate(rows)]

        else:
            lines = []
            title = "🏆 Ranking"

    text = f"🏆 *{title}*\n\n"
    if lines:
        text += "\n".join(lines)
    else:
        text += "Nenhum dado ainda."

    if query:
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
