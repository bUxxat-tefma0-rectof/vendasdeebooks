from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from sqlalchemy import select
from app.database import AsyncSessionLocal, Product, BotSettings

async def get_setting(key: str, default: str = ""):
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(BotSettings).where(BotSettings.key == key))
        setting = result.scalar_one_or_none()
        return setting.value if setting else default

async def support_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "support":
        support_link = await get_setting("support_link", "https://t.me/suporte")
        keyboard = [
            [InlineKeyboardButton("🆘 Falar com Suporte", url=support_link)],
            [InlineKeyboardButton("🔍 Pesquisar Produtos", callback_data="support_search")],
            [InlineKeyboardButton("🔙 Voltar", callback_data="start")]
        ]
        await query.edit_message_text(
            "🆘 *Suporte & Informações*\n\nEscolha uma opção:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif data == "support_info":
        support_link = await get_setting("support_link", "https://t.me/suporte")
        keyboard = [
            [InlineKeyboardButton("🆘 Falar com Suporte", url=support_link)],
            [InlineKeyboardButton("🔍 Pesquisar Produtos", callback_data="support_search")],
            [InlineKeyboardButton("🔙 Voltar", callback_data="start")]
        ]
        await query.edit_message_text(
            "ℹ️ *Informações*\n\nUse a busca para encontrar produtos disponíveis:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )

    elif data == "support_search":
        context.user_data["waiting_search"] = True
        await query.edit_message_text(
            "🔍 *Pesquisar Produto*\n\nDigite o nome do produto que procura:",
            parse_mode="Markdown"
        )

async def search_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("waiting_search"):
        return

    context.user_data["waiting_search"] = False
    query_text = update.message.text.lower()

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Product).where(Product.is_active == True))
        products = result.scalars().all()

    found = [p for p in products if query_text in p.name.lower() or query_text in (p.description or "").lower()]

    if not found:
        await update.message.reply_text("❌ Nenhum produto encontrado.")
        return

    keyboard = [[InlineKeyboardButton(f"🛍 {p.name} — R$ {p.price:.2f}", callback_data=f"product_{p.id}")] for p in found]
    keyboard.append([InlineKeyboardButton("🔙 Voltar", callback_data="start")])

    await update.message.reply_text(
        f"🔍 *Resultados para:* _{query_text}_\n\n{len(found)} produto(s) encontrado(s):",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
