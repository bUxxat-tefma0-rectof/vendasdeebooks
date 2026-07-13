from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import StaticPool, QueuePool
from contextlib import contextmanager
from typing import Generator, Optional
import logging
import os

logger = logging.getLogger(__name__)

class Database:
    """Gerenciador de conexão com banco de dados"""
    
    _instance = None
    _engine = None
    _session_factory = None
    _scoped_session = None
    
    def __new__(cls, database_url: Optional[str] = None):
        """Singleton pattern para garantir uma única instância"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self, database_url: Optional[str] = None):
        """
        Inicializa a conexão com o banco de dados
        
        Args:
            database_url: URL de conexão com o banco
        """
        if self._engine is not None:
            return  # Já inicializado
        
        if database_url is None:
            from ..config import config
            database_url = config.DATABASE_URL
        
        self.database_url = database_url
        self._setup_engine()
        
    def _setup_engine(self):
        """Configura a engine do SQLAlchemy"""
        
        # Configurações específicas por tipo de banco
        if "sqlite" in self.database_url:
            connect_args = {"check_same_thread": False}
            poolclass = StaticPool
            pool_size = 1
        else:
            connect_args = {}
            poolclass = QueuePool
            pool_size = 10
        
        # Cria a engine
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
        
        # Cria fábrica de sessões
        self._session_factory = sessionmaker(
            bind=self._engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False
        )
        
        # Cria sessão thread-safe
        self._scoped_session = scoped_session(self._session_factory)
        
        logger.info(f"✅ Database conectado: {self.database_url}")
    
    def create_tables(self):
        """Cria todas as tabelas no banco de dados"""
        from .models import Base
        Base.metadata.create_all(bind=self._engine)
        logger.info("✅ Tabelas criadas/verificadas com sucesso!")
    
    def drop_tables(self):
        """Remove todas as tabelas do banco de dados"""
        from .models import Base
        Base.metadata.drop_all(bind=self._engine)
        logger.warning("⚠️ Todas as tabelas foram removidas!")
    
    def reset_database(self):
        """Reseta completamente o banco de dados"""
        self.drop_tables()
        self.create_tables()
        logger.info("🔄 Banco de dados resetado com sucesso!")
    
    @contextmanager
    def get_session(self) -> Generator:
        """
        Context manager para sessões do banco de dados
        
        Yields:
            Sessão do SQLAlchemy
        
        Usage:
            with db.get_session() as session:
                user = session.query(Usuario).first()
        """
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
    
    def get_session_factory(self):
        """Retorna a fábrica de sessões"""
        return self._session_factory
    
    @property
    def engine(self):
        """Retorna a engine do banco"""
        return self._engine
    
    @property
    def session(self):
        """Retorna uma sessão nova"""
        return self._scoped_session()
    
    # ============================================
    # MÉTODOS DE CONVENIÊNCIA
    # ============================================
    
    def executar_query(self, query, params=None):
        """Executa uma query SQL diretamente"""
        with self.get_session() as session:
            result = session.execute(query, params or {})
            return result
    
    def inserir(self, objeto):
        """Insere um objeto no banco"""
        with self.get_session() as session:
            session.add(objeto)
            session.flush()
            return objeto
    
    def atualizar(self, objeto):
        """Atualiza um objeto no banco"""
        with self.get_session() as session:
            session.merge(objeto)
            session.flush()
            return objeto
    
    def deletar(self, objeto):
        """Remove um objeto do banco"""
        with self.get_session() as session:
            session.delete(objeto)
            session.flush()
    
    def buscar_por_id(self, model, id):
        """Busca um objeto pelo ID"""
        with self.get_session() as session:
            return session.query(model).get(id)
    
    def buscar_todos(self, model, filtros=None):
        """Busca todos os objetos de um modelo"""
        with self.get_session() as session:
            query = session.query(model)
            if filtros:
                query = query.filter_by(**filtros)
            return query.all()
    
    def contar(self, model, filtros=None):
        """Conta registros de um modelo"""
        with self.get_session() as session:
            query = session.query(model)
            if filtros:
                query = query.filter_by(**filtros)
            return query.count()
    
    def backup_database(self, caminho_backup: str = "backup.sql"):
        """Cria backup do banco de dados (apenas SQLite)"""
        if "sqlite" in self.database_url:
            import shutil
            db_path = self.database_url.replace("sqlite:///", "")
            shutil.copy2(db_path, caminho_backup)
            logger.info(f"✅ Backup criado: {caminho_backup}")
        else:
            logger.warning("⚠️ Backup automático apenas para SQLite")
    
    def close(self):
        """Fecha a conexão com o banco"""
        if self._engine:
            self._scoped_session.remove()
            self._engine.dispose()
            logger.info("🔒 Conexão com banco fechada")

# Instância global do banco (será configurada no bot.py)
db = Database()
