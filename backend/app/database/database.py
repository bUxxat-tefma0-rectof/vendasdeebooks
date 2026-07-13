from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import StaticPool
from contextlib import contextmanager
from typing import Generator, Any
import logging

logger = logging.getLogger(__name__)

class Database:
    """Gerenciador de conexão com banco de dados"""
    
    def __init__(self, database_url: str):
        """
        Inicializa a conexão com o banco de dados
        
        Args:
            database_url: URL de conexão com o banco
        """
        self.engine = create_engine(
            database_url,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
            echo=False,
            connect_args={"check_same_thread": False} if "sqlite" in database_url else {}
        )
        
        self.session_factory = sessionmaker(
            bind=self.engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False
        )
        
        self.Session = scoped_session(self.session_factory)
    
    def create_tables(self):
        """Cria todas as tabelas no banco de dados"""
        from .models import Base
        Base.metadata.create_all(bind=self.engine)
        logger.info("✅ Tabelas criadas com sucesso!")
    
    def drop_tables(self):
        """Remove todas as tabelas do banco de dados"""
        from .models import Base
        Base.metadata.drop_all(bind=self.engine)
        logger.warning("⚠️ Todas as tabelas foram removidas!")
    
    @contextmanager
    def get_session(self) -> Generator[Any, None, None]:
        """
        Context manager para sessões do banco de dados
        
        Yields:
            Sessão do SQLAlchemy
        """
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"❌ Erro na sessão do banco: {e}")
            raise
        finally:
            session.close()
    
    def get_user(self, telegram_id: int):
        """Busca usuário pelo ID do Telegram"""
        from .models import Usuario
        with self.get_session() as session:
            return session.query(Usuario).filter_by(telegram_id=telegram_id).first()
    
    def create_user(self, telegram_id: int, nome: str = "", username: str = ""):
        """Cria um novo usuário"""
        from .models import Usuario
        with self.get_session() as session:
            user = Usuario(
                telegram_id=telegram_id,
                nome=nome,
                username=username,
                saldo=0.0
            )
            session.add(user)
            session.flush()
            return user
    
    def get_or_create_user(self, telegram_id: int, nome: str = "", username: str = ""):
        """Busca ou cria um usuário"""
        user = self.get_user(telegram_id)
        if not user:
            user = self.create_user(telegram_id, nome, username)
        return user
    
    def update_user_balance(self, telegram_id: int, valor: float, operacao: str = "add"):
        """
        Atualiza o saldo do usuário
        
        Args:
            telegram_id: ID do Telegram
            valor: Valor a ser adicionado/removido
            operacao: 'add' para adicionar, 'sub' para subtrair
        """
        from .models import Usuario
        with self.get_session() as session:
            user = session.query(Usuario).filter_by(telegram_id=telegram_id).first()
            if user:
                if operacao == "add":
                    user.saldo += valor
                elif operacao == "sub":
                    user.saldo -= valor
                session.flush()
                return user.saldo
        return None
    
    def get_categorias(self):
        """Busca todas as categorias ativas"""
        from .models import Categoria
        with self.get_session() as session:
            return session.query(Categoria).order_by(Categoria.ordem).all()
    
    def get_produtos_by_categoria(self, categoria_id: int):
        """Busca produtos de uma categoria"""
        from .models import Produto
        with self.get_session() as session:
            return session.query(Produto).filter_by(
                categoria_id=categoria_id,
                ativo=True
            ).all()
    
    def get_produto(self, produto_id: int):
        """Busca um produto pelo ID"""
        from .models import Produto
        with self.get_session() as session:
            return session.query(Produto).filter_by(id=produto_id).first()

# Instância global do banco
db = Database
