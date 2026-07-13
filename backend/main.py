from app.bot import create_app

if __name__ == "__main__":
    app = create_app()
    print("✅ Bot iniciado!")
    app.run_polling()
