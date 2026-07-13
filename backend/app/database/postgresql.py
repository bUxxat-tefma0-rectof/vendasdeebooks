"""
Configuração e Gerenciamento do PostgreSQL
Conexão, pooling, migrações e otimizações
"""
import logging
import os
import time
from typing import Optional, Dict, Any, Generator
from sqlalchemy import create_engine, text, event, pool, inspect
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError, DisconnectionError
from contextlib import contextmanager

from ..config import config

logger = logging.getLogger(__name__)


class PostgreSQLConfig:
    """Configurações do PostgreSQL"""
    
    DEFAULT_HOST = "localhost"
    DEFAULT_PORT = 5432
    DEFAULT_USER = "postgres"
    DEFAULT_PASSWORD = "postgres"
    DEFAULT_DATABASE = "bot_vendas"
    
    POOL_SIZE = 10
    MAX_OVERFLOW = 20
    POOL_TIMEOUT = 30
    POOL_RECYCLE = 3600
    
    @classmethod
    def build_url(cls, host: str = None, port: int = None, user: str = None,
                  password: str = None, database: str = None) -> str:
        """Constrói URL de conexão PostgreSQL"""
        host = host or os.getenv("PG_HOST", cls.DEFAULT_HOST)
        port = port or int(os.getenv("PG_PORT", cls.DEFAULT_PORT))
        user = user or os.getenv("PG_USER", cls.DEFAULT_USER)
        password = password or os.getenv("PG_PASSWORD", cls.DEFAULT_PASSWORD)
        database = database or os.getenv("PG_DATABASE", cls.DEFAULT_DATABASE)
        
        return f"postgresql://{user}:{password}@{host}:{port}/{database}"
    
    @classmethod
    def from_env(cls) -> Dict[str, Any]:
        """Carrega configurações de variáveis de ambiente"""
        return {
            'host': os.getenv("PG_HOST", cls.DEFAULT_HOST),
            'port': int(os.getenv("PG_PORT", cls.DEFAULT_PORT)),
            'user': os.getenv("PG_USER", cls.DEFAULT_USER),
            'password': os.getenv("PG_PASSWORD", cls.DEFAULT_PASSWORD),
            'database': os.getenv("PG_DATABASE", cls.DEFAULT_DATABASE),
            'pool_size': int(os.getenv("PG_POOL_SIZE", cls.POOL_SIZE)),
            'max_overflow': int(os.getenv("PG_MAX_OVERFLOW", cls.MAX_OVERFLOW)),
        }


class PostgreSQLDatabase:
    """Gerenciador de banco de dados PostgreSQL"""
    
    def __init__(self, database_url: str = None):
        self.database_url = database_url or config.DATABASE_URL
        self.engine = None
        self.session_factory = None
        self.Session = None
        self._connected = False
    
    def connect(self, max_retries: int = 5, retry_delay: int = 3) -> bool:
        """Conecta ao banco com retry automático"""
        for attempt in range(1, max_retries + 1):
            try:
                logger.info(f"🔄 Tentativa {attempt}/{max_retries} de conexão ao PostgreSQL...")
                
                self.engine = create_engine(
                    self.database_url,
                    poolclass=pool.QueuePool,
                    pool_size=PostgreSQLConfig.POOL_SIZE,
                    max_overflow=PostgreSQLConfig.MAX_OVERFLOW,
                    pool_timeout=PostgreSQLConfig.POOL_TIMEOUT,
                    pool_recycle=PostgreSQLConfig.POOL_RECYCLE,
                    pool_pre_ping=True,
                    echo=False,
                    connect_args={
                        "connect_timeout": 10,
                        "options": "-c statement_timeout=30000"
                    }
                )
                
                # Registra eventos
                self._register_events()
                
                # Testa conexão
                with self.engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                    result = conn.execute(text("SELECT version()")).scalar()
                
                self.session_factory = sessionmaker(
                    bind=self.engine,
                    autocommit=False,
                    autoflush=False,
                    expire_on_commit=False
                )
                
                self.Session = scoped_session(self.session_factory)
                self._connected = True
                
                logger.info(f"✅ PostgreSQL conectado com sucesso!")
                logger.info(f"📊 Versão: {result}")
                
                return True
                
            except OperationalError as e:
                logger.warning(f"⚠️ Falha na tentativa {attempt}: {e}")
                
                if attempt < max_retries:
                    time.sleep(retry_delay)
                else:
                    logger.error(f"❌ Todas as {max_retries} tentativas falharam")
                    return False
            
            except Exception as e:
                logger.error(f"❌ Erro inesperado: {e}")
                return False
        
        return False
    
    def _register_events(self):
        """Registra eventos do SQLAlchemy para debugging"""
        
        @event.listens_for(Engine, "connect")
        def receive_connect(dbapi_connection, connection_record):
            """Evento disparado ao conectar"""
            logger.debug("🔗 Nova conexão estabelecida")
        
        @event.listens_for(Engine, "checkout")
        def receive_checkout(dbapi_connection, connection_record, connection_proxy):
            """Evento disparado ao pegar conexão do pool"""
            pass
        
        @event.listens_for(Engine, "checkin")
        def receive_checkin(dbapi_connection, connection_record):
            """Evento disparado ao devolver conexão ao pool"""
            pass
        
        @event.listens_for(Engine, "close")
        def receive_close(dbapi_connection, connection_record):
            """Evento disparado ao fechar conexão"""
            logger.debug("🔌 Conexão fechada")
    
    def create_database_if_not_exists(self):
        """Cria o banco de dados se não existir"""
        db_name = PostgreSQLConfig.DEFAULT_DATABASE
        
        # Conecta sem especificar banco
        url_sem_banco = self.database_url.rsplit("/", 1)[0] + "/postgres"
        
        try:
            temp_engine = create_engine(url_sem_banco, isolation_level="AUTOCOMMIT")
            
            with temp_engine.connect() as conn:
                result = conn.execute(
                    text(f"SELECT 1 FROM pg_database WHERE datname = '{db_name}'")
                )
                
                if not result.scalar():
                    conn.execute(text(f"CREATE DATABASE {db_name}"))
                    logger.info(f"✅ Banco de dados '{db_name}' criado!")
                    
                    conn.execute(text(f"""
                        ALTER DATABASE {db_name} 
                        SET timezone TO 'America/Sao_Paulo'
                    """))
                else:
                    logger.info(f"ℹ️ Banco '{db_name}' já existe")
            
            temp_engine.dispose()
            
        except Exception as e:
            logger.error(f"❌ Erro ao criar banco: {e}")
    
    def create_tables(self):
        """Cria todas as tabelas"""
        if not self.engine:
            raise RuntimeError("Banco não conectado. Execute connect() primeiro.")
        
        from .models import Base
        
        Base.metadata.create_all(bind=self.engine)
        logger.info("✅ Tabelas criadas/verificadas com sucesso!")
    
    def create_indexes(self):
        """Cria índices para otimização"""
        indexes = [
            # Índices para Usuario
            "CREATE INDEX IF NOT EXISTS idx_usuarios_telegram ON usuarios(telegram_id);",
            "CREATE INDEX IF NOT EXISTS idx_usuarios_saldo ON usuarios(saldo);",
            "CREATE INDEX IF NOT EXISTS idx_usuarios_afiliado ON usuarios(afiliado_por);",
            
            # Índices para Compra
            "CREATE INDEX IF NOT EXISTS idx_compras_usuario ON compras(usuario_id);",
            "CREATE INDEX IF NOT EXISTS idx_compras_produto ON compras(produto_id);",
            "CREATE INDEX IF NOT EXISTS idx_compras_data ON compras(data);",
            
            # Índices para Transacao
            "CREATE INDEX IF NOT EXISTS idx_transacoes_usuario ON transacoes(usuario_id);",
            "CREATE INDEX IF NOT EXISTS idx_transacoes_status ON transacoes(status);",
            "CREATE INDEX IF NOT EXISTS idx_transacoes_tipo ON transacoes(tipo);",
            
            # Índices para Produto
            "CREATE INDEX IF NOT EXISTS idx_produtos_categoria ON produtos(categoria_id);",
            "CREATE INDEX IF NOT EXISTS idx_produtos_ativo ON produtos(ativo);",
            
            # Índices para EstoqueLogin
            "CREATE INDEX IF NOT EXISTS idx_estoque_produto ON estoque_logins(produto_id);",
            "CREATE INDEX IF NOT EXISTS idx_estoque_vendido ON estoque_logins(vendido);",
            
            # Índices para AlertaProduto
            "CREATE INDEX IF NOT EXISTS idx_alertas_usuario ON alertas_produtos(usuario_id);",
            "CREATE INDEX IF NOT EXISTS idx_alertas_produto ON alertas_produtos(produto_id);",
        ]
        
        with self.engine.connect() as conn:
            for index_sql in indexes:
                try:
                    conn.execute(text(index_sql))
                except Exception as e:
                    logger.warning(f"⚠️ Erro ao criar índice: {e}")
        
        logger.info("✅ Índices criados!")
    
    def create_functions(self):
        """Cria funções e triggers"""
        functions = [
            # Função para atualizar timestamp
            """
            CREATE OR REPLACE FUNCTION update_timestamp()
            RETURNS TRIGGER AS $$
            BEGIN
                NEW.data_atualizacao = NOW();
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
            """,
            
            # Função para atualizar estoque após venda
            """
            CREATE OR REPLACE FUNCTION atualizar_estoque_pos_venda()
            RETURNS TRIGGER AS $$
            BEGIN
                UPDATE produtos 
                SET estoque = estoque - 1,
                    total_vendas = COALESCE(total_vendas, 0) + 1,
                    data_ultima_venda = NOW()
                WHERE id = NEW.produto_id AND estoque_ilimitado = FALSE;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql;
            """,
        ]
        
        with self.engine.connect() as conn:
            for func_sql in functions:
                try:
                    conn.execute(text(func_sql))
                except Exception as e:
                    logger.warning(f"⚠️ Erro ao criar função: {e}")
        
        logger.info("✅ Funções PostgreSQL criadas!")
    
    def vacuum_analyze(self):
        """Executa VACUUM ANALYZE para otimização"""
        try:
            with self.engine.connect() as conn:
                conn.execute(text("VACUUM ANALYZE"))
            logger.info("✅ VACUUM ANALYZE executado!")
        except Exception as e:
            logger.error(f"❌ Erro no VACUUM: {e}")
    
    @contextmanager
    def get_session(self) -> Generator:
        """Context manager para sessões"""
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"❌ Erro na sessão: {e}")
            raise
        finally:
            session.close()
    
    def get_pool_status(self) -> Dict:
        """Retorna status do pool de conexões"""
        if not self.engine:
            return {}
        
        pool = self.engine.pool
        
        return {
            'size': pool.size(),
            'checked_in': pool.checkedin(),
            'checked_out': pool.checkedout(),
            'overflow': pool.overflow(),
            'total': pool.size() + pool.overflow()
        }
    
    def health_check(self) -> bool:
        """Verifica se o banco está saudável"""
        try:
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False
    
    def backup(self, filename: str = None) -> str:
        """Cria backup do banco usando pg_dump"""
        import subprocess
        from datetime import datetime
        
        if not filename:
            filename = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
        
        backup_dir = "backups"
        os.makedirs(backup_dir, exist_ok=True)
        
        filepath = os.path.join(backup_dir, filename)
        
        cfg = PostgreSQLConfig.from_env()
        
        cmd = [
            "pg_dump",
            "-h", cfg['host'],
            "-p", str(cfg['port']),
            "-U", cfg['user'],
            "-d", cfg['database'],
            "-f", filepath,
            "--no-owner",
            "--no-acl"
        ]
        
        env = os.environ.copy()
        env["PGPASSWORD"] = cfg['password']
        
        try:
            subprocess.run(cmd, env=env, check=True, capture_output=True, text=True)
            logger.info(f"✅ Backup criado: {filepath}")
            return filepath
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Erro no backup: {e.stderr}")
            return None
    
    def restore(self, filename: str) -> bool:
        """Restaura banco de um backup"""
        import subprocess
        
        if not os.path.exists(filename):
            logger.error(f"❌ Arquivo não encontrado: {filename}")
            return False
        
        cfg = PostgreSQLConfig.from_env()
        
        cmd = [
            "psql",
            "-h", cfg['host'],
            "-p", str(cfg['port']),
            "-U", cfg['user'],
            "-d", cfg['database'],
            "-f", filename
        ]
        
        env = os.environ.copy()
        env["PGPASSWORD"] = cfg['password']
        
        try:
            subprocess.run(cmd, env=env, check=True, capture_output=True, text=True)
            logger.info(f"✅ Backup restaurado: {filename}")
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Erro ao restaurar: {e.stderr}")
            return False
    
    def get_table_sizes(self) -> Dict:
        """Retorna tamanho das tabelas"""
        with self.engine.connect() as conn:
            result = conn.execute(text("""
                SELECT 
                    tablename,
                    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size,
                    pg_total_relation_size(schemaname||'.'||tablename) AS size_bytes
                FROM pg_tables
                WHERE schemaname = 'public'
                ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;
            """))
            
            return {row[0]: {'size': row[1], 'bytes': row[2]} for row in result}
    
    def close(self):
        """Fecha conexão com o banco"""
        if self.Session:
            self.Session.remove()
        if self.engine:
            self.engine.dispose()
            self._connected = False
        logger.info("🔒 Conexão com PostgreSQL fechada")


class DatabaseManager:
    """Gerenciador completo de banco de dados"""
    
    def __init__(self):
        self.db = None
    
    def init_postgresql(self, database_url: str = None) -> PostgreSQLDatabase:
        """Inicializa banco PostgreSQL"""
        self.db = PostgreSQLDatabase(database_url)
        
        # Tenta conectar
        if not self.db.connect():
            raise ConnectionError("Falha ao conectar ao PostgreSQL")
        
        # Cria banco se necessário
        self.db.create_database_if_not_exists()
        
        # Cria tabelas
        self.db.create_tables()
        
        # Cria índices
        self.db.create_indexes()
        
        # Cria funções
        self.db.create_functions()
        
        # Vacuum inicial
        self.db.vacuum_analyze()
        
        logger.info("✅ PostgreSQL completamente inicializado!")
        return self.db
    
    def init_sqlite(self, database_url: str = None) -> 'SQLiteDatabase':
        """Fallback para SQLite (desenvolvimento)"""
        from .connection import Database
        return Database(database_url or "sqlite:///bot_vendas.db")
    
    def auto_init(self) -> Any:
        """Detecta automaticamente qual banco usar"""
        database_url = config.DATABASE_URL
        
        if "postgresql" in database_url:
            return self.init_postgresql(database_url)
        else:
            return self.init_sqlite(database_url)


# Instância global
db_manager = DatabaseManager()


__all__ = [
    'PostgreSQLConfig',
    'PostgreSQLDatabase',
    'DatabaseManager',
    'db_manager',
]
