"""
Database Connection - Compatível com PostgreSQL e SQLite
"""
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import QueuePool, StaticPool
from contextlib import contextmanager
from typing import Generator, Optional

logger = logging.getLogger(__name__)

class Database:
    _instance = None
    _engine = None
    _session_factory = None
    _scoped_session = None
    
    def __new__(cls, database_url: Optional[str] = None):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, database_url: Optional[str] = None):
        if self._engine is not None:
            return
        
        if database_url is None:
            from ..config import config
            database_url = config.DATABASE_URL
        
        self.database_url = database_url
        self._setup_engine()
    
    def _setup_engine(self):
        is_postgresql = "postgresql" in self.database_url
        
        if is_postgresql:
            connect_args = {"connect_timeout": 10}
            poolclass = QueuePool
            pool_size = 10
        else:
            connect_args = {"check_same_thread": False}
            poolclass = StaticPool
            pool_size = 1
        
        self._engine = create_engine(
            self.database_url,
            poolclass=poolclass,
            pool_size=pool_size,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=False,
            connect_args=connect_args
        )
        
        self._session_factory = sessionmaker(
            bind=self._engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False
        )
        
        self._scoped_session = scoped_session(self._session_factory)
        logger.info(f"✅ Database conectado: {'PostgreSQL' if is_postgresql else 'SQLite'}")
    
    def create_tables(self):
        from .models import Base
        Base.metadata.create_all(bind=self._engine)
        logger.info("✅ Tabelas criadas!")
    
    @contextmanager
    def get_session(self) -> Generator:
        session = self._scoped_session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"❌ Erro na sessão: {e}")
            raise
        finally:
            session.close()
    
    def get_user(self, telegram_id: int):
        from .models import Usuario
        with self.get_session() as session:
            return session.query(Usuario).filter_by(telegram_id=telegram_id).first()
    
    def get_or_create_user(self, telegram_id: int, nome: str = "", username: str = ""):
        from .models import Usuario
        with self.get_session() as session:
            user = session.query(Usuario).filter_by(telegram_id=telegram_id).first()
            if not user:
                user = Usuario(telegram_id=telegram_id, nome=nome, username=username, saldo=0.0)
                session.add(user)
                session.flush()
            return user
    
    def close(self):
        if self._engine:
            self._scoped_session.remove()
            self._engine.dispose()
            logger.info("🔒 Conexão fechada")
