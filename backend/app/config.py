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
    MP_CLIENT_ID: str = os.getenv("MP_CLIENT_ID", "")
    MP_CLIENT_SECRET: str = os.getenv("MP_CLIENT_SECRET", "")
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///bot_vendas.db")
    
    # Admin IDs
    ADMIN_IDS: List[int] = [
        int(id.strip()) 
        for id in os.getenv("ADMIN_IDS", "").split(",") 
        if id.strip()
    ]
    
    # Gateway
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
    
    # Redis
    REDIS_HOST: str = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", "")
    
    # Geral
    TIMEZONE: str = os.getenv("TIMEZONE", "America/Sao_Paulo")
    IDIOMA_PADRAO: str = os.getenv("IDIOMA_PADRAO", "pt-BR")
    CANAL_LOG_ID: str = os.getenv("CANAL_LOG_ID", "")
    GRUPO_SUPORTE_LINK: str = os.getenv("GRUPO_SUPORTE_LINK", "")
    TERMOS_USO_LINK: str = os.getenv("TERMOS_USO_LINK", "")
    
    @classmethod
    def is_admin(cls, user_id: int) -> bool:
        """Verifica se o usuário é administrador"""
        return user_id in cls.ADMIN_IDS

config = Config()
