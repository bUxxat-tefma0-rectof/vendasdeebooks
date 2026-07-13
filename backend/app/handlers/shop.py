from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from sqlalchemy import select, func
from app.database import AsyncSessionLocal, Product, Stock, User, Transaction
from datetime import datetime

async def shop_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    async with AsyncSessionLocal() as session:
        user_result = await session.execute(select(User).where(User.telegram_id == update.effective_user.id))
        user = user_result.scalar_one_or_none()

        result = await session.execute(select(Product.category).distinct().where(Product.is_active == True))
        categories = result.scalars().all()

    keyboard = [[InlineKeyboardButton(f"📦 {cat}", callback_data=f"shop_cat_{cat}")] for cat in categories]
    keyboard.append([InlineKeyboardButton("🔙 Voltar", callback_data="start")])

    await query.edit_message_text(
        f"🛒 *Loja*\n💰 Saldo: R$ {user.balance:.2f}\n\nEscolha uma categoria:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

async def product_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("shop_cat_"):
        category = data.replace("shop_cat_", "")
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Product).where(Product.category == category, Product.is_active == True))
            products = result.scalars().all()

            keyboard = []
            for p in products:
                stock_count = await session.execute(select(func.count()).where(Stock.product_id == p.id, Stock.is_sold == False))
                count = stock_count.scalar()
                keyboard.append([InlineKeyboardButton(f"{p.name} — R$ {p.price:.2f} ({count} disponíveis)", callback_data=f"product_{p.id}")])
            keyboard.append([InlineKeyboardButton("🔙 Voltar", callback_data="shop")])

        await query.edit_message_text(f"📦 *{category}*\nEscolha um produto:", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

    elif data.startswith("product_"):
        product_id = int(data.replace("product_", ""))
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(Product).where(Product.id == product_id))
            product = result.scalar_one_or_none()
            stock_count = await session.execute(select(func.count()).where(Stock.product_id == product_id, Stock.is_sold == False))
            count = stock_count.scalar()
            user_result = await session.execute(select(User).where(User.telegram_id == update.effective_user.id))
            user = user_result.scalar_one_or_none()

        keyboard = [
            [InlineKeyboardButton("✅ COMPRAR", callback_data=f"buy_{product_id}")],
            [InlineKeyboardButton("🔙 Voltar", callback_data=f"shop_cat_{product.category}")]
        ]
        text = (
            f"🛍 *{product.name}*\n"
            f"💰 Preço: R$ {product.price:.2f}\n"
            f"👛 Seu saldo: R$ {user.balance:.2f}\n"
            f"📦 Estoque: {count} disponíveis\n\n"
            f"📝 {product.description or 'Sem descrição.'}\n"
            f"🛡 Garantia: {product.warranty or 'Sem garantia.'}"
        )
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def buy_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    product_id = int(query.data.replace("buy_", ""))

    async with AsyncSessionLocal() as session:
        user_result = await session.execute(select(User).where(User.telegram_id == update.effective_user.id))
        user = user_result.scalar_one_or_none()
        product_result = await session.execute(select(Product).where(Product.id == product_id))
        product = product_result.scalar_one_or_none()
        stock_result = await session.execute(select(Stock).where(Stock.product_id == product_id, Stock.is_sold == False).limit(1))
        stock_item = stock_result.scalar_one_or_none()

        if not stock_item:
            await query.edit_message_text("❌ Produto sem estoque no momento.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Voltar", callback_data="shop")]]))
            return

        if user.balance < product.price:
            await query.edit_message_text(f"❌ Saldo insuficiente!\n💰 Seu saldo: R$ {user.balance:.2f}\n💸 Necessário: R$ {product.price:.2f}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💰 Recarregar", callback_data="recharge"), InlineKeyboardButton("🔙 Voltar", callback_data="shop")]]))
            return

        user.balance -= product.price
        stock_item.is_sold = True
        stock_item.sold_at = datetime.utcnow()

        transaction = Transaction(user_id=user.id, type="purchase", amount=product.price, product_id=product.id, status="completed")
        session.add(transaction)
        await session.commit()

        await query.edit_message_text(
            f"✅ *Compra realizada com sucesso!*\n\n"
            f"🛍 Produto: *{product.name}*\n"
            f"📦 Conteúdo:\n`{stock_item.content}`\n\n"
            f"💰 Saldo restante: R$ {user.balance:.2f}",
            parse_mode="Markdown"
        )
