# No topo, adiciona:
from app.handlers.recharge import recharge_pix_handler, pix_amount_message_handler

# Dentro do create_app(), adiciona:
app.add_handler(CallbackQueryHandler(recharge_pix_handler, pattern="^recharge_pix"))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, pix_amount_message_handler))
