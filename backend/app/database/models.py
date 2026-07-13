from sqlalchemy import (
    Column, Integer, String, Float, DateTime, 
    Boolean, Text, ForeignKey, Enum, BigInteger,
    Table, Index
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
import enum
import secrets
import string

Base = declarative_base()

# ============================================
# ENUMS
# ============================================

class StatusTransacao(str, enum.Enum):
    """Status de transações financeiras"""
    PENDENTE = "pendente"
    APROVADO = "aprovado"
    CANCELADO = "cancelado"
    EXPIRADO = "expirado"
    REEMBOLSADO = "reembolsado"

class TipoTransacao(str, enum.Enum):
    """Tipos de transações"""
    PIX = "pix"
    COMPRA = "compra"
    GIFT = "gift"
    COMISSAO = "comissao"
    BONUS = "bonus"
    ESTORNO = "estorno"
    AJUSTE = "ajuste"

class TipoRanking(str, enum.Enum):
    """Tipos de ranking"""
    SERVICOS = "servicos"
    RECARGAS = "recargas"
    COMPRAS = "compras"
    SALDO = "saldo"

class TipoMidia(str, enum.Enum):
    """Tipos de mídia para produtos"""
    IMAGEM = "imagem"
    VIDEO = "video"
    GIF = "gif"

# ============================================
# TABELAS PRINCIPAIS
# ============================================

class Usuario(Base):
    """Tabela de usuários do bot"""
    __tablename__ = "usuarios"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    nome = Column(String(100), default="")
    username = Column(String(100), default="")
    saldo = Column(Float, default=0.0)
    whatsapp = Column(String(20), default="")
    
    # Status
    is_admin = Column(Boolean, default=False)
    is_banido = Column(Boolean, default=False)
    is_ativo = Column(Boolean, default=True)
    motivo_ban = Column(Text, default="")
    
    # Datas
    data_registro = Column(DateTime, default=datetime.now)
    ultima_atividade = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    data_ban = Column(DateTime, nullable=True)
    
    # Afiliado
    codigo_afiliado = Column(String(50), unique=True, nullable=True)
    afiliado_por = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    comissao_acumulada = Column(Float, default=0.0)
    total_indicacoes = Column(Integer, default=0)
    
    # Preferências
    notificacoes_ativas = Column(Boolean, default=True)
    alertas_produtos = Column(Text, default="")  # IDs dos produtos com alerta
    
    # Relacionamentos
    compras = relationship("Compra", back_populates="usuario", lazy="dynamic")
    transacoes = relationship("Transacao", back_populates="usuario", lazy="dynamic")
    indicacoes = relationship("Usuario", backref="afiliador", remote_side=[id])
    
    def gerar_codigo_afiliado(self):
        """Gera código de afiliado único"""
        while True:
            codigo = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(8))
            if not self.codigo_afiliado:  # Verificar unicidade no banco
                self.codigo_afiliado = f"AF{codigo}"
                break
    
    def __repr__(self):
        return f"<Usuario(id={self.id}, telegram_id={self.telegram_id}, nome={self.nome})>"


class Categoria(Base):
    """Tabela de categorias de produtos"""
    __tablename__ = "categorias"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String(100), nullable=False)
    emoji = Column(String(10), default="📦")
    descricao = Column(Text, default="")
    ordem = Column(Integer, default=0)
    ativo = Column(Boolean, default=True)
    
    # Estatísticas
    total_vendas = Column(Integer, default=0)
    total_produtos = Column(Integer, default=0)
    
    # Datas
    data_criacao = Column(DateTime, default=datetime.now)
    data_atualizacao = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # Relacionamentos
    produtos = relationship("Produto", back_populates="categoria", lazy="dynamic")
    
    def __repr__(self):
        return f"<Categoria(id={self.id}, nome={self.nome})>"


class Produto(Base):
    """Tabela de produtos/serviços"""
    __tablename__ = "produtos"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String(200), nullable=False)
    descricao = Column(Text, default="")
    valor = Column(Float, nullable=False)
    valor_promocional = Column(Float, nullable=True)
    
    # Estoque
    estoque = Column(Integer, default=0)
    estoque_minimo = Column(Integer, default=5)
    estoque_ilimitado = Column(Boolean, default=False)
    
    # Categoria
    categoria_id = Column(Integer, ForeignKey("categorias.id"), nullable=False)
    
    # Mídia
    imagem_id = Column(String(200), default="")
    video_id = Column(String(200), default="")
    tipo_midia = Column(String(20), default="imagem")
    
    # Informações
    garantia = Column(String(200), default="7 dias")
    plataforma = Column(String(100), default="")
    duracao_padrao = Column(String(50), default="30 dias")
    
    # Status
    ativo = Column(Boolean, default=True)
    em_promocao = Column(Boolean, default=False)
    destaque = Column(Boolean, default=False)
    
    # Métricas
    total_vendas = Column(Integer, default=0)
    alertas_ativos = Column(Integer, default=0)
    visualizacoes = Column(Integer, default=0)
    avaliacao_media = Column(Float, default=5.0)
    
    # Controle de acesso
    vip_exclusivo = Column(Boolean, default=False)
    minimo_compras = Column(Integer, default=0)
    
    # Datas
    data_criacao = Column(DateTime, default=datetime.now)
    data_atualizacao = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    data_ultima_venda = Column(DateTime, nullable=True)
    
    # Relacionamentos
    categoria = relationship("Categoria", back_populates="produtos")
    logins = relationship("EstoqueLogin", back_populates="produto", lazy="dynamic")
    compras = relationship("Compra", back_populates="produto", lazy="dynamic")
    alertas = relationship("AlertaProduto", back_populates="produto", lazy="dynamic")
    
    @property
    def estoque_disponivel(self):
        """Retorna quantidade real disponível"""
        if self.estoque_ilimitado:
            return 999999
        return self.estoque
    
    @property
    def preco_atual(self):
        """Retorna preço atual (promocional ou normal)"""
        if self.em_promocao and self.valor_promocional:
            return self.valor_promocional
        return self.valor
    
    def __repr__(self):
        return f"<Produto(id={self.id}, nome={self.nome}, valor={self.valor})>"


class EstoqueLogin(Base):
    """Tabela de logins em estoque"""
    __tablename__ = "estoque_logins"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    produto_id = Column(Integer, ForeignKey("produtos.id"), nullable=False)
    
    # Dados do login
    email = Column(String(200), nullable=False)
    senha = Column(String(200), nullable=False)
    perfil = Column(String(200), default="")
    pin = Column(String(50), default="")
    
    # Informações adicionais
    duracao = Column(String(50), default="30 dias")
    plataforma = Column(String(100), default="")
    observacoes = Column(Text, default="")
    
    # Status
    vendido = Column(Boolean, default=False)
    reservado = Column(Boolean, default=False)
    bloqueado = Column(Boolean, default=False)
    motivo_bloqueio = Column(Text, default="")
    
    # Dados da venda
    comprador_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    data_venda = Column(DateTime, nullable=True)
    valor_venda = Column(Float, nullable=True)
    
    # Datas
    data_adicao = Column(DateTime, default=datetime.now)
    data_expiracao = Column(DateTime, nullable=True)
    data_bloqueio = Column(DateTime, nullable=True)
    
    # Relacionamentos
    produto = relationship("Produto", back_populates="logins")
    comprador = relationship("Usuario", foreign_keys=[comprador_id])
    
    def __repr__(self):
        return f"<EstoqueLogin(id={self.id}, email={self.email}, vendido={self.vendido})>"


class Compra(Base):
    """Tabela de compras realizadas"""
    __tablename__ = "compras"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    produto_id = Column(Integer, ForeignKey("produtos.id"), nullable=False)
    login_id = Column(Integer, ForeignKey("estoque_logins.id"), nullable=True)
    
    # Valores
    valor = Column(Float, nullable=False)
    valor_original = Column(Float, nullable=True)
    desconto = Column(Float, default=0.0)
    
    # Status
    status = Column(String(20), default="concluida")
    reembolsada = Column(Boolean, default=False)
    motivo_reembolso = Column(Text, default="")
    
    # Afiliado
    comissao_gerada = Column(Float, default=0.0)
    afiliado_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    
    # Dados de entrega
    login_entregue = Column(Text, default="")
    data_entrega = Column(DateTime, default=datetime.now)
    
    # Datas
    data = Column(DateTime, default=datetime.now)
    data_reembolso = Column(DateTime, nullable=True)
    
    # Relacionamentos
    usuario = relationship("Usuario", back_populates="compras", foreign_keys=[usuario_id])
    produto = relationship("Produto", back_populates="compras")
    login = relationship("EstoqueLogin", foreign_keys=[login_id])
    afiliado = relationship("Usuario", foreign_keys=[afiliado_id])
    
    def __repr__(self):
        return f"<Compra(id={self.id}, usuario={self.usuario_id}, valor={self.valor})>"


class Transacao(Base):
    """Tabela de transações financeiras"""
    __tablename__ = "transacoes"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    
    # Tipo e status
    tipo = Column(String(20), default=TipoTransacao.PIX.value)
    status = Column(String(20), default=StatusTransacao.PENDENTE.value)
    
    # Valores
    valor = Column(Float, nullable=False)
    valor_bonus = Column(Float, default=0.0)
    valor_total = Column(Float, nullable=False)
    
    # Gateway de pagamento
    gateway = Column(String(50), default="mercado_pago")
    gateway_id = Column(String(200), default="")
    gateway_status = Column(String(50), default="")
    
    # Pix
    qr_code = Column(Text, default="")
    qr_code_base64 = Column(Text, default="")
    copia_cola = Column(Text, default="")
    chave_pix = Column(String(100), default="")
    
    # Metadados
    descricao = Column(Text, default="")
    ip_comprador = Column(String(45), default="")
    metadata = Column(Text, default="{}")  # JSON com dados extras
    
    # Datas
    data_criacao = Column(DateTime, default=datetime.now)
    data_expiracao = Column(DateTime, default=lambda: datetime.now() + timedelta(minutes=5))
    data_aprovacao = Column(DateTime, nullable=True)
    data_cancelamento = Column(DateTime, nullable=True)
    
    # Relacionamentos
    usuario = relationship("Usuario", back_populates="transacoes")
    
    @property
    def expirada(self):
        """Verifica se a transação expirou"""
        return datetime.now() > self.data_expiracao if self.data_expiracao else False
    
    def __repr__(self):
        return f"<Transacao(id={self.id}, tipo={self.tipo}, valor={self.valor}, status={self.status})>"


# ============================================
# TABELAS AUXILIARES
# ============================================

class AlertaProduto(Base):
    """Tabela de alertas de reabastecimento"""
    __tablename__ = "alertas_produtos"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    produto_id = Column(Integer, ForeignKey("produtos.id"), nullable=False)
    
    ativo = Column(Boolean, default=True)
    notificado = Column(Boolean, default=False)
    
    data_criacao = Column(DateTime, default=datetime.now)
    data_notificacao = Column(DateTime, nullable=True)
    
    # Relacionamentos
    usuario = relationship("Usuario")
    produto = relationship("Produto", back_populates="alertas")
    
    def __repr__(self):
        return f"<AlertaProduto(usuario={self.usuario_id}, produto={self.produto_id})>"


class Cupom(Base):
    """Tabela de cupons de desconto"""
    __tablename__ = "cupons"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    codigo = Column(String(50), unique=True, nullable=False)
    
    # Tipo e valor
    tipo_desconto = Column(String(20), default="porcentagem")  # porcentagem ou fixo
    valor_desconto = Column(Float, nullable=False)
    
    # Limitações
    quantidade_maxima = Column(Integer, default=100)
    quantidade_usada = Column(Integer, default=0)
    valor_minimo_compra = Column(Float, default=0.0)
    
    # Validade
    data_inicio = Column(DateTime, default=datetime.now)
    data_expiracao = Column(DateTime, nullable=True)
    ativo = Column(Boolean, default=True)
    
    # Aplicação
    aplica_todos_produtos = Column(Boolean, default=True)
    categorias_aplicaveis = Column(Text, default="")  # IDs separados por vírgula
    primeira_compra_apenas = Column(Boolean, default=False)
    
    def __repr__(self):
        return f"<Cupom(codigo={self.codigo}, desconto={self.valor_desconto})>"


class Avaliacao(Base):
    """Tabela de avaliações de produtos"""
    __tablename__ = "avaliacoes"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    produto_id = Column(Integer, ForeignKey("produtos.id"), nullable=False)
    compra_id = Column(Integer, ForeignKey("compras.id"), nullable=True)
    
    nota = Column(Integer, default=5)  # 1 a 5
    comentario = Column(Text, default="")
    
    data = Column(DateTime, default=datetime.now)
    
    # Relacionamentos
    usuario = relationship("Usuario")
    produto = relationship("Produto")
    compra = relationship("Compra")
    
    def __repr__(self):
        return f"<Avaliacao(usuario={self.usuario_id}, nota={self.nota})>"


class ConfiguracaoBot(Base):
    """Tabela de configurações dinâmicas do bot"""
    __tablename__ = "configuracoes_bot"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Chave e valor
    chave = Column(String(100), unique=True, nullable=False)
    valor = Column(Text, default="")
    tipo = Column(String(20), default="string")  # string, int, float, bool, json
    
    # Descrição
    descricao = Column(Text, default="")
    categoria = Column(String(50), default="geral")
    
    # Controle
    editavel = Column(Boolean, default=True)
    
    data_atualizacao = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    def __repr__(self):
        return f"<ConfiguracaoBot(chave={self.chave}, valor={self.valor})>"


class LogAtividade(Base):
    """Tabela de logs de atividades"""
    __tablename__ = "logs_atividades"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    
    # Ação
    acao = Column(String(50), nullable=False)
    descricao = Column(Text, default="")
    
    # IP e localização
    ip = Column(String(45), default="")
    
    # Dados extras
    dados_antes = Column(Text, default="{}")  # JSON
    dados_depois = Column(Text, default="{}")  # JSON
    
    data = Column(DateTime, default=datetime.now)
    
    # Relacionamentos
    usuario = relationship("Usuario")
    
    def __repr__(self):
        return f"<LogAtividade(usuario={self.usuario_id}, acao={self.acao})>"


class Blacklist(Base):
    """Tabela de blacklist (usuários banidos permanentemente)"""
    __tablename__ = "blacklist"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    
    motivo = Column(Text, default="")
    banido_por = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    
    data_ban = Column(DateTime, default=datetime.now)
    data_expiracao = Column(DateTime, nullable=True)  # Se None, é permanente
    
    ativo = Column(Boolean, default=True)
    
    # Relacionamentos
    admin = relationship("Usuario", foreign_keys=[banido_por])
    
    def __repr__(self):
        return f"<Blacklist(telegram_id={self.telegram_id})>"


# ============================================
# ÍNDICES PARA PERFORMANCE
# ============================================

# Índices para Usuario
Index('idx_usuario_telegram', Usuario.telegram_id)
Index('idx_usuario_saldo', Usuario.saldo)

# Índices para Produto
Index('idx_produto_categoria', Produto.categoria_id)
Index('idx_produto_ativo', Produto.ativo)
Index('idx_produto_estoque', Produto.estoque)

# Índices para Compra
Index('idx_compra_usuario', Compra.usuario_id)
Index('idx_compra_data', Compra.data)
Index('idx_compra_status', Compra.status)

# Índices para Transacao
Index('idx_transacao_usuario', Transacao.usuario_id)
Index('idx_transacao_status', Transacao.status)
Index('idx_transacao_data', Transacao.data_criacao)

# Índices para EstoqueLogin
Index('idx_estoque_produto', EstoqueLogin.produto_id)
Index('idx_estoque_vendido', EstoqueLogin.vendido)
