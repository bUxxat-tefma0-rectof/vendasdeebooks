from sqlalchemy import (
    Column, Integer, String, Float, DateTime, 
    Boolean, Text, ForeignKey, BigInteger
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta
import enum

Base = declarative_base()


class StatusTransacao(str, enum.Enum):
    PENDENTE = "pendente"
    APROVADO = "aprovado"
    CANCELADO = "cancelado"
    EXPIRADO = "expirado"
    REEMBOLSADO = "reembolsado"


class TipoTransacao(str, enum.Enum):
    PIX = "pix"
    COMPRA = "compra"
    GIFT = "gift"
    COMISSAO = "comissao"
    BONUS = "bonus"
    ESTORNO = "estorno"
    AJUSTE = "ajuste"


class Usuario(Base):
    __tablename__ = "usuarios"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False, index=True)
    nome = Column(String(100), default="")
    username = Column(String(100), default="")
    saldo = Column(Float, default=0.0)
    whatsapp = Column(String(20), default="")
    
    is_admin = Column(Boolean, default=False)
    is_banido = Column(Boolean, default=False)
    is_ativo = Column(Boolean, default=True)
    motivo_ban = Column(Text, default="")
    
    data_registro = Column(DateTime, default=datetime.now)
    ultima_atividade = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    data_ban = Column(DateTime, nullable=True)
    
    codigo_afiliado = Column(String(50), unique=True, nullable=True)
    afiliado_por = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    comissao_acumulada = Column(Float, default=0.0)
    total_indicacoes = Column(Integer, default=0)
    
    notificacoes_ativas = Column(Boolean, default=True)
    alertas_produtos = Column(Text, default="")
    
    compras = relationship("Compra", back_populates="usuario", lazy="dynamic", foreign_keys="Compra.usuario_id")
    transacoes = relationship("Transacao", back_populates="usuario", lazy="dynamic", foreign_keys="Transacao.usuario_id")
    
    def __repr__(self):
        return f"<Usuario(id={self.id}, telegram_id={self.telegram_id})>"


class Categoria(Base):
    __tablename__ = "categorias"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String(100), nullable=False)
    emoji = Column(String(10), default="📦")
    descricao = Column(Text, default="")
    ordem = Column(Integer, default=0)
    ativo = Column(Boolean, default=True)
    total_vendas = Column(Integer, default=0)
    total_produtos = Column(Integer, default=0)
    data_criacao = Column(DateTime, default=datetime.now)
    data_atualizacao = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    produtos = relationship("Produto", back_populates="categoria", lazy="dynamic")


class Produto(Base):
    __tablename__ = "produtos"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    nome = Column(String(200), nullable=False)
    descricao = Column(Text, default="")
    valor = Column(Float, nullable=False)
    valor_promocional = Column(Float, nullable=True)
    estoque = Column(Integer, default=0)
    estoque_minimo = Column(Integer, default=5)
    estoque_ilimitado = Column(Boolean, default=False)
    categoria_id = Column(Integer, ForeignKey("categorias.id"), nullable=False)
    imagem_id = Column(String(200), default="")
    garantia = Column(String(200), default="7 dias")
    plataforma = Column(String(100), default="")
    duracao_padrao = Column(String(50), default="30 dias")
    ativo = Column(Boolean, default=True)
    em_promocao = Column(Boolean, default=False)
    destaque = Column(Boolean, default=False)
    total_vendas = Column(Integer, default=0)
    alertas_ativos = Column(Integer, default=0)
    visualizacoes = Column(Integer, default=0)
    avaliacao_media = Column(Float, default=5.0)
    vip_exclusivo = Column(Boolean, default=False)
    minimo_compras = Column(Integer, default=0)
    data_criacao = Column(DateTime, default=datetime.now)
    data_ultima_venda = Column(DateTime, nullable=True)
    
    categoria = relationship("Categoria", back_populates="produtos")
    logins = relationship("EstoqueLogin", back_populates="produto", lazy="dynamic")
    compras = relationship("Compra", back_populates="produto", lazy="dynamic")
    alertas = relationship("AlertaProduto", back_populates="produto", lazy="dynamic")
    
    @property
    def preco_atual(self):
        if self.em_promocao and self.valor_promocional:
            return self.valor_promocional
        return self.valor


class EstoqueLogin(Base):
    __tablename__ = "estoque_logins"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    produto_id = Column(Integer, ForeignKey("produtos.id"), nullable=False)
    email = Column(String(200), nullable=False)
    senha = Column(String(200), nullable=False)
    perfil = Column(String(200), default="")
    pin = Column(String(50), default="")
    duracao = Column(String(50), default="30 dias")
    plataforma = Column(String(100), default="")
    observacoes = Column(Text, default="")
    vendido = Column(Boolean, default=False)
    reservado = Column(Boolean, default=False)
    bloqueado = Column(Boolean, default=False)
    comprador_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    data_venda = Column(DateTime, nullable=True)
    valor_venda = Column(Float, nullable=True)
    data_adicao = Column(DateTime, default=datetime.now)
    
    produto = relationship("Produto", back_populates="logins")
    comprador = relationship("Usuario", foreign_keys=[comprador_id])


class Compra(Base):
    __tablename__ = "compras"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    produto_id = Column(Integer, ForeignKey("produtos.id"), nullable=False)
    login_id = Column(Integer, ForeignKey("estoque_logins.id"), nullable=True)
    valor = Column(Float, nullable=False)
    valor_original = Column(Float, nullable=True)
    desconto = Column(Float, default=0.0)
    status = Column(String(20), default="concluida")
    reembolsada = Column(Boolean, default=False)
    motivo_reembolso = Column(Text, default="")
    comissao_gerada = Column(Float, default=0.0)
    afiliado_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    data_entrega = Column(DateTime, default=datetime.now)
    data = Column(DateTime, default=datetime.now)
    data_reembolso = Column(DateTime, nullable=True)
    
    usuario = relationship("Usuario", back_populates="compras", foreign_keys=[usuario_id])
    produto = relationship("Produto", back_populates="compras")
    login = relationship("EstoqueLogin", foreign_keys=[login_id])
    afiliado = relationship("Usuario", foreign_keys=[afiliado_id])


class Transacao(Base):
    __tablename__ = "transacoes"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    tipo = Column(String(20), default=TipoTransacao.PIX.value)
    status = Column(String(20), default=StatusTransacao.PENDENTE.value)
    valor = Column(Float, nullable=False)
    valor_bonus = Column(Float, default=0.0)
    valor_total = Column(Float, nullable=False)
    gateway = Column(String(50), default="mercado_pago")
    gateway_id = Column(String(200), default="")
    qr_code = Column(Text, default="")
    qr_code_base64 = Column(Text, default="")
    copia_cola = Column(Text, default="")
    descricao = Column(Text, default="")
    dados_extras = Column(Text, default="{}")
    data_criacao = Column(DateTime, default=datetime.now)
    data_expiracao = Column(DateTime, default=lambda: datetime.now() + timedelta(minutes=5))
    data_aprovacao = Column(DateTime, nullable=True)
    data_cancelamento = Column(DateTime, nullable=True)
    
    usuario = relationship("Usuario", back_populates="transacoes", foreign_keys=[usuario_id])
    
    @property
    def expirada(self):
        return datetime.now() > self.data_expiracao if self.data_expiracao else False


class AlertaProduto(Base):
    __tablename__ = "alertas_produtos"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    produto_id = Column(Integer, ForeignKey("produtos.id"), nullable=False)
    ativo = Column(Boolean, default=True)
    notificado = Column(Boolean, default=False)
    data_criacao = Column(DateTime, default=datetime.now)
    data_notificacao = Column(DateTime, nullable=True)
    
    usuario = relationship("Usuario")
    produto = relationship("Produto", back_populates="alertas")


class Cupom(Base):
    __tablename__ = "cupons"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    codigo = Column(String(50), unique=True, nullable=False)
    tipo_desconto = Column(String(20), default="porcentagem")
    valor_desconto = Column(Float, nullable=False)
    quantidade_maxima = Column(Integer, default=100)
    quantidade_usada = Column(Integer, default=0)
    valor_minimo_compra = Column(Float, default=0.0)
    data_inicio = Column(DateTime, default=datetime.now)
    data_expiracao = Column(DateTime, nullable=True)
    ativo = Column(Boolean, default=True)
    primeira_compra_apenas = Column(Boolean, default=False)


class Blacklist(Base):
    __tablename__ = "blacklist"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    motivo = Column(Text, default="")
    banido_por = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    data_ban = Column(DateTime, default=datetime.now)
    ativo = Column(Boolean, default=True)


class ConfiguracaoBot(Base):
    __tablename__ = "configuracoes_bot"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    chave = Column(String(100), unique=True, nullable=False)
    valor = Column(Text, default="")
    tipo = Column(String(20), default="string")
    descricao = Column(Text, default="")
    data_atualizacao = Column(DateTime, default=datetime.now, onupdate=datetime.now)


class LogAtividade(Base):
    __tablename__ = "logs_atividades"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True)
    acao = Column(String(50), nullable=False)
    descricao = Column(Text, default="")
    ip = Column(String(45), default="")
    data = Column(DateTime, default=datetime.now)


class Avaliacao(Base):
    __tablename__ = "avaliacoes"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False)
    produto_id = Column(Integer, ForeignKey("produtos.id"), nullable=False)
    compra_id = Column(Integer, ForeignKey("compras.id"), nullable=True)
    nota = Column(Integer, default=5)
    comentario = Column(Text, default="")
    data = Column(DateTime, default=datetime.now)
