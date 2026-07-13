import os
from dotenv import load_dotenv
from typing import List

load_dotenv()

class Config:
    """Configurações gerais do bot"""
    
    # Bot
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    NOME_BOT: str = os.getenv("NOME_BOT", "StoreBot")
    VERSAO: str = os.getenv("VERSAO_BOT", "1.0.0")
    
    # Mercado Pago
    MP_ACCESS_TOKEN: str = os.getenv("MP_ACCESS_TOKEN", "")
    MP_PUBLIC_KEY: str = os.getenv("MP_PUBLIC_KEY", "")
    
    # Database - URL FIXA DO RENDER
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql://xixa00marketingoff_user:dVejVbGNqXI2EyafJXlYv4eMovSiWsuT@dpg-d98ovvreo5us73fgjuig-a.oregon-postgres.render.com/xixa00marketingoff"
    )
    
    # Admin IDs
    ADMIN_IDS: List[int] = [
        int(id.strip()) 
        for id in os.getenv("ADMIN_IDS", "").split(",") 
        if id.strip()
    ]
    
    # Gateway PIX
    VALOR_MINIMO_PIX: float = float(os.getenv("VALOR_MINIMO_PIX", "10.00"))
    VALOR_MAXIMO_PIX: float = float(os.getenv("VALOR_MAXIMO_PIX", "500.00"))
    TEMPO_EXPIRACAO_PIX: int = int(os.getenv("TEMPO_EXPIRACAO_PIX", "300"))
    BONUS_DEPOSITO: float = float(os.getenv("BONUS_DEPOSITO_PORCENTAGEM", "5.0"))
    
    # Afiliados
    COMISSAO_AFILIADO: float = float(os.getenv("COMISSAO_AFILIADO_PADRAO", "10.0"))
    SISTEMA_AFILIADOS_ATIVO: bool = os.getenv("SISTEMA_AFILIADOS_ATIVO", "true").lower() == "true"
    
    # Logs
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", "bot_vendas.log")
    
    # Geral
    TIMEZONE: str = os.getenv("TIMEZONE", "America/Sao_Paulo")
    GRUPO_SUPORTE_LINK: str = os.getenv("GRUPO_SUPORTE_LINK", "https://t.me/seu_grupo")
    TERMOS_USO_LINK: str = os.getenv("TERMOS_USO_LINK", "https://telegra.ph/Termos")
    
    @classmethod
    def is_admin(cls, user_id: int) -> bool:
        return user_id in cls.ADMIN_IDS


config = Config()
