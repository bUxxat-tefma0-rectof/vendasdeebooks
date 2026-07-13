"""
Serviço de Catálogo - Gerenciamento de Produtos, Categorias e Estoque
"""
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy import func, and_, or_

from ..database.connection import Database
from ..database.models import (
    Categoria, Produto, EstoqueLogin, Compra, 
    AlertaProduto, Usuario
)
from ..utils.utils import formatar_moeda, calcular_desconto

logger = logging.getLogger(__name__)


# ============================================
# SERVIÇO DE CATEGORIAS
# ============================================

class CategoriaService:
    """Gerencia categorias de produtos"""
    
    def __init__(self, db: Database):
        self.db = db
    
    def listar_todas(self, apenas_ativas: bool = True) -> List[Categoria]:
        """Lista todas as categorias"""
        with self.db.get_session() as session:
            query = session.query(Categoria).order_by(Categoria.ordem)
            if apenas_ativas:
                query = query.filter_by(ativo=True)
            return query.all()
    
    def listar_com_produtos(self) -> List[Dict]:
        """Lista categorias com contagem de produtos"""
        with self.db.get_session() as session:
            categorias = session.query(Categoria).filter_by(ativo=True).order_by(Categoria.ordem).all()
            
            resultado = []
            for cat in categorias:
                total = session.query(func.count(Produto.id)).filter_by(
                    categoria_id=cat.id, ativo=True
                ).scalar()
                
                resultado.append({
                    'id': cat.id,
                    'nome': cat.nome,
                    'emoji': cat.emoji,
                    'descricao': cat.descricao,
                    'total_produtos': total,
                    'ordem': cat.ordem
                })
            
            return resultado
    
    def buscar_por_id(self, categoria_id: int) -> Optional[Categoria]:
        """Busca categoria por ID"""
        with self.db.get_session() as session:
            return session.query(Categoria).get(categoria_id)
    
    def criar(self, nome: str, emoji: str = "📦", descricao: str = "", ordem: int = 0) -> Categoria:
        """Cria uma nova categoria"""
        with self.db.get_session() as session:
            categoria = Categoria(
                nome=nome,
                emoji=emoji,
                descricao=descricao,
                ordem=ordem
            )
            session.add(categoria)
            session.flush()
            logger.info(f"✅ Categoria criada: {nome}")
            return categoria
    
    def atualizar(self, categoria_id: int, **kwargs) -> bool:
        """Atualiza uma categoria"""
        with self.db.get_session() as session:
            categoria = session.query(Categoria).get(categoria_id)
            if not categoria:
                return False
            
            for key, value in kwargs.items():
                if hasattr(categoria, key):
                    setattr(categoria, key, value)
            
            categoria.data_atualizacao = datetime.now()
            session.flush()
            logger.info(f"✅ Categoria atualizada: {categoria_id}")
            return True
    
    def remover(self, categoria_id: int) -> bool:
        """Remove uma categoria (soft delete)"""
        with self.db.get_session() as session:
            categoria = session.query(Categoria).get(categoria_id)
            if not categoria:
                return False
            
            # Verifica se tem produtos
            total = session.query(func.count(Produto.id)).filter_by(
                categoria_id=categoria_id
            ).scalar()
            
            if total > 0:
                logger.warning(f"⚠️ Categoria {categoria_id} tem {total} produtos")
                return False
            
            categoria.ativo = False
            session.flush()
            logger.info(f"✅ Categoria removida: {categoria_id}")
            return True
    
    def reordenar(self, ordens: Dict[int, int]) -> bool:
        """Reordena categorias (id: nova_ordem)"""
        with self.db.get_session() as session:
            for cat_id, nova_ordem in ordens.items():
                categoria = session.query(Categoria).get(cat_id)
                if categoria:
                    categoria.ordem = nova_ordem
            session.flush()
            logger.info(f"✅ Categorias reordenadas")
            return True


# ============================================
# SERVIÇO DE PRODUTOS
# ============================================

class ProdutoService:
    """Gerencia produtos e catálogo"""
    
    def __init__(self, db: Database):
        self.db = db
    
    def listar_por_categoria(self, categoria_id: int, apenas_com_estoque: bool = False) -> List[Produto]:
        """Lista produtos de uma categoria"""
        with self.db.get_session() as session:
            query = session.query(Produto).filter_by(
                categoria_id=categoria_id, ativo=True
            )
            
            if apenas_com_estoque:
                query = query.filter(
                    or_(Produto.estoque > 0, Produto.estoque_ilimitado == True)
                )
            
            return query.order_by(Produto.nome).all()
    
    def listar_todos(self, apenas_ativos: bool = True) -> List[Produto]:
        """Lista todos os produtos"""
        with self.db.get_session() as session:
            query = session.query(Produto)
            if apenas_ativos:
                query = query.filter_by(ativo=True)
            return query.order_by(Produto.nome).all()
    
    def listar_destaques(self, limite: int = 5) -> List[Produto]:
        """Lista produtos em destaque"""
        with self.db.get_session() as session:
            return session.query(Produto).filter_by(
                ativo=True, destaque=True
            ).filter(
                or_(Produto.estoque > 0, Produto.estoque_ilimitado == True)
            ).limit(limite).all()
    
    def listar_promocoes(self) -> List[Produto]:
        """Lista produtos em promoção"""
        with self.db.get_session() as session:
            return session.query(Produto).filter_by(
                ativo=True, em_promocao=True
            ).filter(
                or_(Produto.estoque > 0, Produto.estoque_ilimitado == True)
            ).all()
    
    def buscar_por_id(self, produto_id: int) -> Optional[Produto]:
        """Busca produto por ID"""
        with self.db.get_session() as session:
            return session.query(Produto).get(produto_id)
    
    def buscar_por_nome(self, termo: str) -> List[Produto]:
        """Busca produtos por nome (pesquisa)"""
        with self.db.get_session() as session:
            return session.query(Produto).filter(
                and_(
                    Produto.ativo == True,
                    Produto.nome.ilike(f"%{termo}%")
                )
            ).all()
    
    def get_detalhes(self, produto_id: int) -> Optional[Dict]:
        """Retorna detalhes completos do produto"""
        with self.db.get_session() as session:
            produto = session.query(Produto).get(produto_id)
            
            if not produto:
                return None
            
            # Conta estoque real
            estoque_real = session.query(func.count(EstoqueLogin.id)).filter_by(
                produto_id=produto_id, vendido=False
            ).scalar()
            
            return {
                'id': produto.id,
                'nome': produto.nome,
                'descricao': produto.descricao,
                'valor': produto.valor,
                'valor_promocional': produto.valor_promocional,
                'preco_atual': produto.preco_atual,
                'estoque': estoque_real if not produto.estoque_ilimitado else 999999,
                'estoque_ilimitado': produto.estoque_ilimitado,
                'garantia': produto.garantia,
                'plataforma': produto.plataforma,
                'duracao': produto.duracao_padrao,
                'em_promocao': produto.em_promocao,
                'categoria_id': produto.categoria_id,
                'categoria_nome': produto.categoria.nome if produto.categoria else '',
                'total_vendas': produto.total_vendas,
                'imagem_id': produto.imagem_id
            }
    
    def criar(self, dados: Dict) -> Produto:
        """Cria um novo produto"""
        with self.db.get_session() as session:
            produto = Produto(
                nome=dados.get('nome', ''),
                descricao=dados.get('descricao', ''),
                valor=dados.get('valor', 0.0),
                valor_promocional=dados.get('valor_promocional'),
                categoria_id=dados.get('categoria_id'),
                garantia=dados.get('garantia', '7 dias'),
                plataforma=dados.get('plataforma', ''),
                duracao_padrao=dados.get('duracao', '30 dias'),
                estoque_ilimitado=dados.get('estoque_ilimitado', False),
                imagem_id=dados.get('imagem_id', ''),
                em_promocao=dados.get('em_promocao', False),
                destaque=dados.get('destaque', False)
            )
            session.add(produto)
            session.flush()
            
            # Atualiza contador da categoria
            categoria = session.query(Categoria).get(produto.categoria_id)
            if categoria:
                categoria.total_produtos = (categoria.total_produtos or 0) + 1
            
            logger.info(f"✅ Produto criado: {produto.nome} (ID: {produto.id})")
            return produto
    
    def atualizar(self, produto_id: int, **kwargs) -> bool:
        """Atualiza um produto"""
        with self.db.get_session() as session:
            produto = session.query(Produto).get(produto_id)
            if not produto:
                return False
            
            for key, value in kwargs.items():
                if hasattr(produto, key):
                    setattr(produto, key, value)
            
            produto.data_atualizacao = datetime.now()
            session.flush()
            logger.info(f"✅ Produto atualizado: {produto_id}")
            return True
    
    def remover(self, produto_id: int) -> bool:
        """Remove um produto (soft delete)"""
        with self.db.get_session() as session:
            produto = session.query(Produto).get(produto_id)
            if not produto:
                return False
            
            produto.ativo = False
            session.flush()
            
            # Atualiza contador da categoria
            categoria = session.query(Categoria).get(produto.categoria_id)
            if categoria and categoria.total_produtos > 0:
                categoria.total_produtos -= 1
            
            logger.info(f"✅ Produto removido: {produto_id}")
            return True
    
    def alterar_preco(self, produto_id: int, novo_valor: float, promocional: bool = False) -> bool:
        """Altera o preço de um produto"""
        with self.db.get_session() as session:
            produto = session.query(Produto).get(produto_id)
            if not produto:
                return False
            
            if promocional:
                produto.valor_promocional = novo_valor
                produto.em_promocao = True
            else:
                produto.valor = novo_valor
            
            produto.data_atualizacao = datetime.now()
            session.flush()
            logger.info(f"✅ Preço do produto {produto_id} alterado para {novo_valor}")
            return True
    
    def alterar_precos_em_massa(self, categoria_id: int, porcentagem: float, aumento: bool = True) -> int:
        """Altera preços de todos os produtos de uma categoria"""
        with self.db.get_session() as session:
            produtos = session.query(Produto).filter_by(
                categoria_id=categoria_id, ativo=True
            ).all()
            
            fator = (100 + porcentagem) / 100 if aumento else (100 - porcentagem) / 100
            
            for produto in produtos:
                novo_valor = round(produto.valor * fator, 2)
                produto.valor = novo_valor
                produto.data_atualizacao = datetime.now()
            
            session.flush()
            logger.info(f"✅ {len(produtos)} produtos atualizados com {porcentagem}%")
            return len(produtos)
    
    def get_metricas(self, produto_id: int) -> Dict:
        """Retorna métricas de um produto"""
        with self.db.get_session() as session:
            produto = session.query(Produto).get(produto_id)
            if not produto:
                return {}
            
            total_vendas = session.query(func.count(Compra.id)).filter_by(
                produto_id=produto_id
            ).scalar()
            
            total_faturado = session.query(func.sum(Compra.valor)).filter_by(
                produto_id=produto_id
            ).scalar() or 0.0
            
            alertas_ativos = session.query(func.count(AlertaProduto.id)).filter_by(
                produto_id=produto_id, ativo=True
            ).scalar()
            
            return {
                'total_vendas': total_vendas,
                'total_faturado': float(total_faturado),
                'estoque': produto.estoque,
                'alertas_ativos': alertas_ativos,
                'visualizacoes': produto.visualizacoes,
                'avaliacao_media': produto.avaliacao_media
            }


# ============================================
# SERVIÇO DE ESTOQUE
# ============================================

class EstoqueService:
    """Gerencia estoque de logins"""
    
    def __init__(self, db: Database):
        self.db = db
    
    def get_estoque_disponivel(self, produto_id: int) -> int:
        """Retorna quantidade disponível em estoque"""
        with self.db.get_session() as session:
            return session.query(func.count(EstoqueLogin.id)).filter_by(
                produto_id=produto_id, vendido=False, bloqueado=False
            ).scalar()
    
    def listar_logins(self, produto_id: int, apenas_disponiveis: bool = True) -> List[EstoqueLogin]:
        """Lista logins de um produto"""
        with self.db.get_session() as session:
            query = session.query(EstoqueLogin).filter_by(produto_id=produto_id)
            
            if apenas_disponiveis:
                query = query.filter_by(vendido=False, bloqueado=False)
            
            return query.order_by(EstoqueLogin.data_adicao.desc()).all()
    
    def adicionar_logins(self, produto_id: int, logins: List[Dict]) -> int:
        """Adiciona logins em lote"""
        with self.db.get_session() as session:
            adicionados = 0
            
            for login_data in logins:
                login = EstoqueLogin(
                    produto_id=produto_id,
                    email=login_data.get('email', ''),
                    senha=login_data.get('senha', ''),
                    perfil=login_data.get('perfil', ''),
                    pin=login_data.get('pin', ''),
                    duracao=login_data.get('duracao', '30 dias'),
                    plataforma=login_data.get('plataforma', ''),
                    observacoes=login_data.get('observacoes', '')
                )
                session.add(login)
                adicionados += 1
            
            # Atualiza estoque do produto
            produto = session.query(Produto).get(produto_id)
            if produto and not produto.estoque_ilimitado:
                produto.estoque = self.get_estoque_disponivel(produto_id)
            
            session.flush()
            logger.info(f"✅ {adicionados} logins adicionados ao produto {produto_id}")
            return adicionados
    
    def remover_logins(self, produto_id: int, quantidade: int) -> int:
        """Remove logins não vendidos"""
        with self.db.get_session() as session:
            logins = session.query(EstoqueLogin).filter_by(
                produto_id=produto_id, vendido=False
            ).limit(quantidade).all()
            
            removidos = 0
            for login in logins:
                session.delete(login)
                removidos += 1
            
            # Atualiza estoque do produto
            produto = session.query(Produto).get(produto_id)
            if produto and not produto.estoque_ilimitado:
                produto.estoque = self.get_estoque_disponivel(produto_id)
            
            session.flush()
            logger.info(f"✅ {removidos} logins removidos do produto {produto_id}")
            return removidos
    
    def zerar_estoque(self, produto_id: int) -> int:
        """Remove todos os logins não vendidos"""
        with self.db.get_session() as session:
            logins = session.query(EstoqueLogin).filter_by(
                produto_id=produto_id, vendido=False
            ).all()
            
            removidos = len(logins)
            for login in logins:
                session.delete(login)
            
            produto = session.query(Produto).get(produto_id)
            if produto and not produto.estoque_ilimitado:
                produto.estoque = 0
            
            session.flush()
            logger.info(f"✅ Estoque do produto {produto_id} zerado ({removidos} logins)")
            return removidos
    
    def reservar_login(self, produto_id: int) -> Optional[EstoqueLogin]:
        """Reserva um login para venda"""
        with self.db.get_session() as session:
            login = session.query(EstoqueLogin).filter_by(
                produto_id=produto_id, vendido=False, bloqueado=False
            ).first()
            
            if login:
                login.reservado = True
                session.flush()
            
            return login
    
    def confirmar_venda(self, login_id: int, comprador_id: int, valor: float) -> bool:
        """Confirma venda de um login"""
        with self.db.get_session() as session:
            login = session.query(EstoqueLogin).get(login_id)
            if not login:
                return False
            
            login.vendido = True
            login.reservado = False
            login.comprador_id = comprador_id
            login.data_venda = datetime.now()
            login.valor_venda = valor
            
            # Atualiza estoque do produto
            produto = session.query(Produto).get(login.produto_id)
            if produto:
                if not produto.estoque_ilimitado:
                    produto.estoque = max(0, produto.estoque - 1)
                produto.total_vendas = (produto.total_vendas or 0) + 1
                produto.data_ultima_venda = datetime.now()
            
            session.flush()
            logger.info(f"✅ Login {login_id} vendido para usuário {comprador_id}")
            return True
    
    def liberar_reserva(self, login_id: int) -> bool:
        """Libera reserva de um login"""
        with self.db.get_session() as session:
            login = session.query(EstoqueLogin).get(login_id)
            if not login:
                return False
            
            login.reservado = False
            session.flush()
            return True
    
    def importar_de_txt(self, produto_id: int, conteudo: str) -> int:
        """Importa logins de arquivo TXT (formato: email:senha)"""
        logins = []
        
        for linha in conteudo.strip().split('\n'):
            linha = linha.strip()
            if not linha or linha.startswith('#'):
                continue
            
            partes = linha.split(':')
            if len(partes) >= 2:
                login_data = {
                    'email': partes[0].strip(),
                    'senha': partes[1].strip(),
                    'perfil': partes[2].strip() if len(partes) > 2 else '',
                    'pin': partes[3].strip() if len(partes) > 3 else ''
                }
                logins.append(login_data)
        
        return self.adicionar_logins(produto_id, logins)
    
    def exportar_disponiveis(self, produto_id: int) -> str:
        """Exporta logins disponíveis como texto"""
        with self.db.get_session() as session:
            logins = session.query(EstoqueLogin).filter_by(
                produto_id=produto_id, vendido=False
            ).all()
            
            linhas = []
            for login in logins:
                linha = f"{login.email}:{login.senha}"
                if login.perfil:
                    linha += f":{login.perfil}"
                if login.pin:
                    linha += f":{login.pin}"
                linhas.append(linha)
            
            return '\n'.join(linhas)


# ============================================
# SERVIÇO DE COMPRAS
# ============================================

class CompraService:
    """Gerencia compras e entregas"""
    
    def __init__(self, db: Database):
        self.db = db
        self.estoque_service = EstoqueService(db)
    
    def processar_compra(self, usuario_id: int, produto_id: int) -> Tuple[bool, str, Optional[Dict]]:
        """
        Processa uma compra
        
        Returns:
            Tuple (sucesso, mensagem, dados_da_compra)
        """
        with self.db.get_session() as session:
            # Verifica usuário
            usuario = session.query(Usuario).filter_by(telegram_id=usuario_id).first()
            if not usuario:
                return False, "Usuário não encontrado", None
            
            if usuario.is_banido:
                return False, "Usuário banido", None
            
            # Verifica produto
            produto = session.query(Produto).get(produto_id)
            if not produto or not produto.ativo:
                return False, "Produto indisponível", None
            
            # Verifica estoque
            if not produto.estoque_ilimitado and produto.estoque <= 0:
                return False, "Produto sem estoque", None
            
            # Verifica saldo
            preco = produto.preco_atual
            if usuario.saldo < preco:
                return False, f"Saldo insuficiente. Necessário: {formatar_moeda(preco)}", None
            
            # Verifica requisitos
            if produto.vip_exclusivo and usuario.total_indicacoes < 1:
                return False, "Produto exclusivo para clientes VIP", None
            
            if produto.minimo_compras > 0:
                total_compras = session.query(func.count(Compra.id)).filter_by(
                    usuario_id=usuario.id
                ).scalar()
                if total_compras < produto.minimo_compras:
                    return False, f"Mínimo de {produto.minimo_compras} compras necessárias", None
            
            # Reserva login
            login = None
            if not produto.estoque_ilimitado:
                login = self.estoque_service.reservar_login(produto_id)
                if not login:
                    return False, "Erro ao reservar produto", None
            
            # Debita saldo
            usuario.saldo -= preco
            
            # Registra compra
            compra = Compra(
                usuario_id=usuario.id,
                produto_id=produto_id,
                login_id=login.id if login else None,
                valor=preco,
                valor_original=produto.valor,
                desconto=produto.valor - preco if produto.em_promocao else 0.0,
                status="concluida",
                data=datetime.now(),
                data_entrega=datetime.now()
            )
            session.add(compra)
            session.flush()
            
            # Confirma venda do login
            if login:
                self.estoque_service.confirmar_venda(login.id, usuario.id, preco)
            
            # Processa comissão de afiliado
            if usuario.afiliado_por:
                afiliador = session.query(Usuario).get(usuario.afiliado_por)
                if afiliador:
                    from ..config import config
                    comissao = (preco * config.COMISSAO_AFILIADO) / 100
                    afiliador.comissao_acumulada += comissao
                    afiliador.saldo += comissao
                    compra.comissao_gerada = comissao
                    compra.afiliado_id = afiliador.id
            
            session.flush()
            
            # Prepara dados de entrega
            dados_entrega = {
                'compra_id': compra.id,
                'produto_nome': produto.nome,
                'valor': preco,
                'data': compra.data,
                'garantia': produto.garantia,
                'login': None
            }
            
            if login:
                dados_entrega['login'] = {
                    'email': login.email,
                    'senha': login.senha,
                    'perfil': login.perfil,
                    'pin': login.pin,
                    'duracao': login.duracao
                }
            
            logger.info(f"✅ Compra concluída: User={usuario_id}, Produto={produto_id}, Valor={preco}")
            return True, "Compra realizada com sucesso!", dados_entrega
    
    def listar_compras_usuario(self, telegram_id: int, limite: int = 10) -> List[Compra]:
        """Lista compras de um usuário"""
        with self.db.get_session() as session:
            usuario = session.query(Usuario).filter_by(telegram_id=telegram_id).first()
            if not usuario:
                return []
            
            return session.query(Compra).filter_by(
                usuario_id=usuario.id
            ).order_by(Compra.data.desc()).limit(limite).all()
    
    def get_detalhes_compra(self, compra_id: int) -> Optional[Dict]:
        """Retorna detalhes de uma compra"""
        with self.db.get_session() as session:
            compra = session.query(Compra).get(compra_id)
            if not compra:
                return None
            
            dados = {
                'id': compra.id,
                'produto_nome': compra.produto.nome if compra.produto else 'N/A',
                'valor': compra.valor,
                'desconto': compra.desconto,
                'status': compra.status,
                'data': compra.data,
                'garantia': compra.produto.garantia if compra.produto else 'N/A',
                'reembolsada': compra.reembolsada
            }
            
            if compra.login:
                dados['login'] = {
                    'email': compra.login.email,
                    'senha': compra.login.senha,
                    'perfil': compra.login.perfil,
                    'duracao': compra.login.duracao
                }
            
            return dados
    
    def reembolsar_compra(self, compra_id: int, motivo: str = "") -> Tuple[bool, str]:
        """Reembolsa uma compra"""
        with self.db.get_session() as session:
            compra = session.query(Compra).get(compra_id)
            if not compra:
                return False, "Compra não encontrada"
            
            if compra.reembolsada:
                return False, "Compra já reembolsada"
            
            # Devolve saldo ao usuário
            usuario = session.query(Usuario).get(compra.usuario_id)
            if usuario:
                usuario.saldo += compra.valor
            
            # Marca como reembolsada
            compra.reembolsada = True
            compra.motivo_reembolso = motivo
            compra.data_reembolso = datetime.now()
            compra.status = "reembolsada"
            
            # Libera login se necessário
            if compra.login_id:
                login = session.query(EstoqueLogin).get(compra.login_id)
                if login:
                    login.vendido = False
                    login.comprador_id = None
                    login.data_venda = None
            
            session.flush()
            logger.info(f"✅ Compra {compra_id} reembolsada: {motivo}")
            return True, "Compra reembolsada com sucesso"


# ============================================
# SERVIÇO DE ALERTAS
# ============================================

class AlertaService:
    """Gerencia alertas de reabastecimento"""
    
    def __init__(self, db: Database):
        self.db = db
    
    def ativar_alerta(self, usuario_id: int, produto_id: int) -> bool:
        """Ativa alerta para um produto"""
        with self.db.get_session() as session:
            # Verifica se já existe
            existente = session.query(AlertaProduto).filter_by(
                usuario_id=usuario_id, produto_id=produto_id
            ).first()
            
            if existente:
                existente.ativo = True
                existente.notificado = False
            else:
                alerta = AlertaProduto(
                    usuario_id=usuario_id,
                    produto_id=produto_id,
                    ativo=True
                )
                session.add(alerta)
            
            # Atualiza contador no produto
            produto = session.query(Produto).get(produto_id)
            if produto:
                produto.alertas_ativos = session.query(func.count(AlertaProduto.id)).filter_by(
                    produto_id=produto_id, ativo=True
                ).scalar()
            
            session.flush()
            logger.info(f"✅ Alerta ativado: User={usuario_id}, Produto={produto_id}")
            return True
    
    def desativar_alerta(self, usuario_id: int, produto_id: int) -> bool:
        """Desativa alerta de um produto"""
        with self.db.get_session() as session:
            alerta = session.query(AlertaProduto).filter_by(
                usuario_id=usuario_id, produto_id=produto_id
            ).first()
            
            if alerta:
                alerta.ativo = False
                session.flush()
                logger.info(f"✅ Alerta desativado: User={usuario_id}, Produto={produto_id}")
                return True
            
            return False
    
    def get_usuarios_para_notificar(self, produto_id: int) -> List[int]:
        """Retorna lista de user_ids com alerta ativo"""
        with self.db.get_session() as session:
            alertas = session.query(AlertaProduto).filter_by(
                produto_id=produto_id, ativo=True, notificado=False
            ).all()
            
            return [alerta.usuario_id for alerta in alertas]
    
    def marcar_como_notificados(self, produto_id: int, user_ids: List[int]):
        """Marca alertas como notificados"""
        with self.db.get_session() as session:
            alertas = session.query(AlertaProduto).filter(
                and_(
                    AlertaProduto.produto_id == produto_id,
                    AlertaProduto.usuario_id.in_(user_ids),
                    AlertaProduto.ativo == True
                )
            ).all()
            
            for alerta in alertas:
                alerta.notificado = True
                alerta.data_notificacao = datetime.now()
            
            session.flush()
            logger.info(f"✅ {len(alertas)} alertas notificados para produto {produto_id}")


# ============================================
# EXPORTAÇÕES
# ============================================

__all__ = [
    'CategoriaService',
    'ProdutoService',
    'EstoqueService',
    'CompraService',
    'AlertaService',
]
