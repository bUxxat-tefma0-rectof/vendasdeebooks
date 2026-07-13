import asyncio
from app.bot import create_app

if __name__ == "__main__":
    app = create_app()
    print("✅ Bot iniciado com sucesso!")
    app.run_polling(allowed_updates=["message", "callback_query"])
