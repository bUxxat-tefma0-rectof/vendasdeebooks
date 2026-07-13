from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters
from app.config import Config
from app.database import init_db
from app.handlers.start import start_handler
from app.handlers.shop import shop_handler, product_handler, buy_handler
from app.handlers.profile import profile_handler, history_handler
from app.handlers.recharge import recharge_handler, pix_command
from app.handlers.ranking import ranking_handler
from app.handlers.support import support_handler
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

    # Callbacks dos botões
    app.add_handler(CallbackQueryHandler(shop_handler, pattern="^shop"))
    app.add_handler(CallbackQueryHandler(product_handler, pattern="^product_"))
    app.add_handler(CallbackQueryHandler(buy_handler, pattern="^buy_"))
    app.add_handler(CallbackQueryHandler(profile_handler, pattern="^profile"))
    app.add_handler(CallbackQueryHandler(recharge_handler, pattern="^recharge"))
    app.add_handler(CallbackQueryHandler(ranking_handler, pattern="^ranking"))
    app.add_handler(CallbackQueryHandler(support_handler, pattern="^support"))
    app.add_handler(CallbackQueryHandler(alerts_handler, pattern="^alerts"))
    app.add_handler(CallbackQueryHandler(affiliates_handler, pattern="^affiliates"))
    app.add_handler(CallbackQueryHandler(admin_handler, pattern="^admin"))

    return app
