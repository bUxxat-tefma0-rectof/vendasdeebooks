import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Telegram
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    ADMIN_ID = int(os.getenv("ADMIN_ID"))
    
    # Mercado Pago
    MP_ACCESS_TOKEN = os.getenv("MP_ACCESS_TOKEN")
    
    # Database
    DATABASE_URL = os.getenv("DATABASE_URL")
    
    # Geral
    SUPPORT_LINK = os.getenv("SUPPORT_LINK")
    LOG_CHANNEL_ID = os.getenv("LOG_CHANNEL_ID")
    
    # Pix
    PIX_MIN_VALUE = float(os.getenv("PIX_MIN_VALUE", 5.00))
    PIX_MAX_VALUE = float(os.getenv("PIX_MAX_VALUE", 1000.00))
    PIX_EXPIRATION_MINUTES = int(os.getenv("PIX_EXPIRATION_MINUTES", 30))
    
    # Afiliados
    AFFILIATE_COMMISSION = float(os.getenv("AFFILIATE_COMMISSION", 10))
    AFFILIATE_ENABLED = os.getenv("AFFILIATE_ENABLED", "true").lower() == "true"
    
    # Bonus
    REGISTER_BONUS = float(os.getenv("REGISTER_BONUS", 0.00))
    DEPOSIT_BONUS = float(os.getenv("DEPOSIT_BONUS", 0.00))
