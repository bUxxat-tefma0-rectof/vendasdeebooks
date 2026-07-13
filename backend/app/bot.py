from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from app.config import Config
from app.database import init_db
from app.handlers.start import start_handler
from app.handlers.shop import shop_handler, product_handler, buy_handler
from app.handlers.profile import profile_handler, history_handler
from app.handlers.recharge import recharge_handler, recharge_pix_handler, pix_amount_message_handler, pix_command
from app.handlers.ranking import ranking_handler
from app.handlers.support import support_handler, search_message_handler
from app.handlers.alerts import alerts_handler
from app.handlers.affiliates import affiliates_handler
from app.admin import admin_handler
import logging

logging.basicConfig(level=logging.INFO)

async def post_init(application):
    await init_db()

def create_app():
    app = ApplicationBuilder()\
        .token(Config.BOT_TOKEN)\
        .post_init(post_init)\
        .build()

    # Comandos
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("pix", pix_command))
    app.add_handler(CommandHandler("historico", history_handler))
    app.add_handler(CommandHandler("afiliados", affiliates_handler))
    app.add_handler(CommandHandler("ranking", ranking_handler))
    app.add_handler(CommandHandler("saldo", profile_handler))
    app.add_handler(CommandHandler("alertas", alerts_handler))
    app.add_handler(CommandHandler("admin", admin_handler))

    # Callbacks
    app.add_handler(CallbackQueryHandler(shop_handler, pattern="^shop$|^shop_cat_"))
    app.add_handler(CallbackQueryHandler(product_handler, pattern="^product_"))
    app.add_handler(CallbackQueryHandler(buy_handler, pattern="^buy_"))
    app.add_handler(CallbackQueryHandler(profile_handler, pattern="^profile$"))
    app.add_handler(CallbackQueryHandler(history_handler, pattern="^history$"))
    app.add_handler(CallbackQueryHandler(recharge_handler, pattern="^recharge$"))
    app.add_handler(CallbackQueryHandler(recharge_pix_handler, pattern="^recharge_pix$"))
    app.add_handler(CallbackQueryHandler(ranking_handler, pattern="^ranking"))
    app.add_handler(CallbackQueryHandler(support_handler, pattern="^support"))
    app.add_handler(CallbackQueryHandler(alerts_handler, pattern="^alerts"))
    app.add_handler(CallbackQueryHandler(affiliates_handler, pattern="^affiliates$"))
    app.add_handler(CallbackQueryHandler(admin_handler, pattern="^admin"))

    # Mensagens de texto
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    return app

async def handle_text(update, context):
    from app.handlers.recharge import pix_amount_message_handler, WAITING_PIX_AMOUNT
    from app.handlers.support import search_message_handler

    user_id = update.effective_user.id

    if user_id in WAITING_PIX_AMOUNT:
        await pix_amount_message_handler(update, context)
    elif context.user_data.get("waiting_search"):
        await search_message_handler(update, context)
    elif context.user_data.get("waiting_admin_input"):
        from app.admin import handle_admin_input
        await handle_admin_input(update, context)
