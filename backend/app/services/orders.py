"""
Serviço de Pedidos - Compras e Entrega Automática
Gerencia o fluxo completo de compra: validação, pagamento, entrega e pós-venda
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple, List
from sqlalchemy import func, and_

from ..database.connection import Database
from ..database.models import (
    Usuario, Produto, Categoria, EstoqueLogin, 
    Compra, Transacao, Cupom, Avaliacao,
    StatusTransacao, TipoTransacao
)
from ..config import config
from ..utils.utils import (
    formatar_moeda, 
    formatar_data,
    calcular_desconto,
    calcular_comissao_afiliado,
    log_com_contexto
)

logger = logging.getLogger(__name__)


# ============================================
# SERVIÇO PRINCIPAL DE PEDIDOS
# ============================================

class OrderService:
    """
    Serviço completo de pedidos
    
    Fluxo:
    1. Validar compra (saldo, estoque, requisitos)
    2. Reservar produto
    3. Processar pagamento (débito do saldo)
    4. Entregar produto (enviar login/senha)
    5. Pós-venda (garantia, avaliação, reembolso)
    """
    
    def __init__(self, db: Database):
        self.db = db
    
    # ==========================================
    // ... continua na próxima parte

Oops! Desculpe, vou gerar o arquivo completo e correto:

---

## 📄 ARQUIVO: `backend/app/services/orders.py` (COMPLETO)

```python
"""
Serviço de Pedidos - Compras e Entrega Automática
Gerencia o fluxo completo de compra: validação, pagamento, entrega e pós-venda
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple, List
from sqlalchemy import func, and_

from ..database.connection import Database
from ..database.models import (
    Usuario, Produto, Categoria, EstoqueLogin, 
    Compra, Transacao, Cupom, Avaliacao,
    StatusTransacao, TipoTransacao
)
from ..config import config
from ..utils.utils import (
    formatar_moeda, 
    formatar_data,
    calcular_desconto,
    calcular_comissao_afiliado,
    log_com_contexto
)

logger = logging.getLogger(__name__)


# ============================================
# SERVIÇO PRINCIPAL DE PEDIDOS
# ============================================

class OrderService:
    """Serviço completo de pedidos"""
    
    def __init__(self, db: Database):
        self.db = db
    
    def validar_compra(self, usuario_id: int, produto_id: int, cupom_codigo: str = "") -> Tuple[bool, str, Optional[Dict]]:
        """
        Valida se a compra pode ser realizada
        
        Returns:
            Tuple (pode_comprar, mensagem, dados_validacao)
        """
        with self.db.get_session() as session:
            # Busca usuário
            usuario = session.query(Usuario).filter_by(telegram_id=usuario_id).first()
            if not usuario:
                return False, "❌ Usuário não encontrado", None
            
            if usuario.is_banido:
                return False, "🚫 Você está banido e não pode comprar", None
            
            # Busca produto
            produto = session.query(Produto).get(produto_id)
            if not produto:
                return False, "❌ Produto não encontrado", None
            
            if not produto.ativo:
                return False, "❌ Produto desativado", None
            
            # Verifica estoque
            if not produto.estoque_ilimitado:
                estoque_real = session.query(func.count(EstoqueLogin.id)).filter_by(
                    produto_id=produto_id, vendido=False, bloqueado=False
                ).scalar()
                
                if estoque_real <= 0:
                    return False, "📦 Produto sem estoque no momento", None
            
            # Verifica preço
            preco = produto.preco_atual
            
            # Aplica cupom se fornecido
            desconto = 0.0
            cupom = None
            
            if cupom_codigo:
                cupom = session.query(Cupom).filter_by(
                    codigo=cupom_codigo.upper(), ativo=True
                ).first()
                
                if cupom:
                    # Valida cupom
                    if cupom.quantidade_usada >= cupom.quantidade_maxima:
                        return False, "🎫 Cupom esgotado", None
                    
                    if cupom.data_expiracao and datetime.now() > cupom.data_expiracao:
                        return False, "🎫 Cupom expirado", None
                    
                    if cupom.primeira_compra_apenas:
                        total_compras = session.query(func.count(Compra.id)).filter_by(
                            usuario_id=usuario.id
                        ).scalar()
                        if total_compras > 0:
                            return False, "🎫 Cupom válido apenas para primeira compra", None
                    
                    if preco < cupom.valor_minimo_compra:
                        return False, f"🎫 Valor mínimo para cupom: {formatar_moeda(cupom.valor_minimo_compra)}", None
                    
                    desconto = cupom.valor_desconto if cupom.tipo_desconto == "fixo" else (preco * cupom.valor_desconto / 100)
                    preco = max(0, preco - desconto)
            
            # Verifica saldo
            if usuario.saldo < preco:
                deficit = preco - usuario.saldo
                return False, f"💰 Saldo insuficiente! Faltam {formatar_moeda(deficit)}", None
            
            # Verifica requisitos VIP
            if produto.vip_exclusivo:
                total_compras = session.query(func.count(Compra.id)).filter_by(
                    usuario_id=usuario.id
                ).scalar()
                if total_compras < 1:
                    return False, "👑 Produto exclusivo para clientes", None
            
            # Verifica mínimo de compras
            if produto.minimo_compras > 0:
                total_compras = session.query(func.count(Compra.id)).filter_by(
                    usuario_id=usuario.id
                ).scalar()
                if total_compras < produto.minimo_compras:
                    return False, f"📊 Mínimo de {produto.minimo_compras} compras necessárias", None
            
            # Tudo válido
            dados = {
                'usuario': usuario,
                'produto': produto,
                'preco_original': produto.valor,
                'preco_final': preco,
                'desconto': desconto,
                'cupom': cupom,
                'saldo_usuario': usuario.saldo
            }
            
            return True, "✅ Compra validada", dados
    
    def processar_compra(self, usuario_id: int, produto_id: int, cupom_codigo: str = "") -> Tuple[bool, str, Optional[Dict]]:
        """
        Processa a compra completa
        
        Returns:
            Tuple (sucesso, mensagem, dados_entrega)
        """
        # Valida primeiro
        valido, msg, dados = self.validar_compra(usuario_id, produto_id, cupom_codigo)
        
        if not valido:
            return False, msg, None
        
        with self.db.get_session() as session:
            try:
                usuario = dados['usuario']
                produto = dados['produto']
                preco_final = dados['preco_final']
                desconto = dados['desconto']
                cupom = dados.get('cupom')
                
                # Reserva login do estoque
                login_reservado = None
                if not produto.estoque_ilimitado:
                    login_reservado = session.query(EstoqueLogin).filter_by(
                        produto_id=produto_id, 
                        vendido=False, 
                        bloqueado=False,
                        reservado=False
                    ).first()
                    
                    if not login_reservado:
                        return False, "📦 Produto esgotado durante o processamento", None
                    
                    login_reservado.reservado = True
                    session.flush()
                
                # Debita saldo do usuário
                usuario.saldo -= preco_final
                
                # Registra a compra
                compra = Compra(
                    usuario_id=usuario.id,
                    produto_id=produto_id,
                    login_id=login_reservado.id if login_reservado else None,
                    valor=preco_final,
                    valor_original=produto.valor,
                    desconto=desconto,
                    status="concluida",
                    data=datetime.now(),
                    data_entrega=datetime.now()
                )
                session.add(compra)
                session.flush()
                
                # Confirma venda do login
                dados_login = None
                if login_reservado:
                    login_reservado.vendido = True
                    login_reservado.reservado = False
                    login_reservado.comprador_id = usuario.id
                    login_reservado.data_venda = datetime.now()
                    login_reservado.valor_venda = preco_final
                    
                    dados_login = {
                        'email': login_reservado.email,
                        'senha': login_reservado.senha,
                        'perfil': login_reservado.perfil,
                        'pin': login_reservado.pin,
                        'duracao': login_reservado.duracao,
                        'plataforma': login_reservado.plataforma
                    }
                
                # Atualiza métricas do produto
                produto.total_vendas = (produto.total_vendas or 0) + 1
                produto.data_ultima_venda = datetime.now()
                
                if not produto.estoque_ilimitado:
                    produto.estoque = session.query(func.count(EstoqueLogin.id)).filter_by(
                        produto_id=produto_id, vendido=False
                    ).scalar()
                
                # Atualiza cupom
                if cupom:
                    cupom.quantidade_usada += 1
                
                # Processa comissão de afiliado
                if usuario.afiliado_por and config.SISTEMA_AFILIADOS_ATIVO:
                    afiliador = session.query(Usuario).get(usuario.afiliado_por)
                    if afiliador:
                        comissao = calcular_comissao_afiliado(preco_final, config.COMISSAO_AFILIADO)
                        afiliador.comissao_acumulada += comissao
                        afiliador.saldo += comissao
                        compra.comissao_gerada = comissao
                        compra.afiliado_id = afiliador.id
                        
                        # Registra transação de comissão
                        trans_comissao = Transacao(
                            usuario_id=afiliador.telegram_id,
                            tipo=TipoTransacao.COMISSAO.value,
                            status=StatusTransacao.APROVADO.value,
                            valor=comissao,
                            valor_total=comissao,
                            descricao=f"Comissão sobre compra de {usuario.nome or usuario.telegram_id}",
                            data_criacao=datetime.now(),
                            data_aprovacao=datetime.now()
                        )
                        session.add(trans_comissao)
                
                # Registra transação de compra
                transacao = Transacao(
                    usuario_id=usuario_id,
                    tipo=TipoTransacao.COMPRA.value,
                    status=StatusTransacao.APROVADO.value,
                    valor=preco_final,
                    valor_total=preco_final,
                    descricao=f"Compra: {produto.nome}",
                    data_criacao=datetime.now(),
                    data_aprovacao=datetime.now()
                )
                session.add(transacao)
                
                session.flush()
                
                # Prepara dados de entrega
                dados_entrega = {
                    'compra_id': compra.id,
                    'produto_nome': produto.nome,
                    'produto_descricao': produto.descricao,
                    'valor': preco_final,
                    'valor_original': produto.valor,
                    'desconto': desconto,
                    'data': formatar_data(compra.data),
                    'garantia': produto.garantia,
                    'plataforma': produto.plataforma,
                    'categoria': produto.categoria.nome if produto.categoria else '',
                    'login': dados_login,
                    'saldo_restante': usuario.saldo
                }
                
                log_com_contexto(
                    "Compra processada",
                    user_id=usuario_id,
                    produto=produto.nome,
                    valor=preco_final,
                    compra_id=compra.id
                )
                
                return True, "✅ Compra realizada com sucesso!", dados_entrega
                
            except Exception as e:
                session.rollback()
                logger.error(f"❌ Erro ao processar compra: {e}")
                return False, "❌ Erro interno ao processar compra", None
    
    def get_detalhes_compra(self, compra_id: int) -> Optional[Dict]:
        """Retorna detalhes completos de uma compra"""
        with self.db.get_session() as session:
            compra = session.query(Compra).get(compra_id)
            
            if not compra:
                return None
            
            dados = {
                'id': compra.id,
                'usuario_id': compra.usuario_id,
                'usuario_nome': compra.usuario.nome if compra.usuario else 'N/A',
                'produto_id': compra.produto_id,
                'produto_nome': compra.produto.nome if compra.produto else 'N/A',
                'categoria': compra.produto.categoria.nome if compra.produto and compra.produto.categoria else 'N/A',
                'valor': compra.valor,
                'valor_original': compra.valor_original,
                'desconto': compra.desconto,
                'status': compra.status,
                'data': formatar_data(compra.data),
                'data_entrega': formatar_data(compra.data_entrega) if compra.data_entrega else 'N/A',
                'garantia': compra.produto.garantia if compra.produto else 'N/A',
                'reembolsada': compra.reembolsada,
                'motivo_reembolso': compra.motivo_reembolso,
                'comissao_gerada': compra.comissao_gerada
            }
            
            # Dados do login se disponível
            if compra.login:
                dados['login'] = {
                    'email': compra.login.email,
                    'senha': compra.login.senha,
                    'perfil': compra.login.perfil,
                    'pin': compra.login.pin,
                    'duracao': compra.login.duracao,
                    'plataforma': compra.login.plataforma
                }
            
            return dados
    
    def listar_compras_usuario(self, telegram_id: int, limite: int = 20) -> List[Dict]:
        """Lista compras de um usuário"""
        with self.db.get_session() as session:
            usuario = session.query(Usuario).filter_by(telegram_id=telegram_id).first()
            
            if not usuario:
                return []
            
            compras = session.query(Compra).filter_by(
                usuario_id=usuario.id
            ).order_by(Compra.data.desc()).limit(limite).all()
            
            resultado = []
            for compra in compras:
                resultado.append({
                    'id': compra.id,
                    'produto_nome': compra.produto.nome if compra.produto else 'N/A',
                    'valor': compra.valor,
                    'status': compra.status,
                    'data': formatar_data(compra.data, "dd/mm/aaaa HH:MM"),
                    'reembolsada': compra.reembolsada,
                    'tem_login': compra.login_id is not None
                })
            
            return resultado
    
    def reembolsar_compra(self, compra_id: int, motivo: str = "", admin_id: int = None) -> Tuple[bool, str]:
        """Reembolsa uma compra"""
        with self.db.get_session() as session:
            compra = session.query(Compra).get(compra_id)
            
            if not compra:
                return False, "Compra não encontrada"
            
            if compra.reembolsada:
                return False, "Compra já foi reembolsada"
            
            # Verifica prazo de garantia
            dias_garantia = 7  # padrão
            if compra.produto and compra.produto.garantia:
                try:
                    dias_garantia = int(''.join(filter(str.isdigit, compra.produto.garantia)))
                except:
                    pass
            
            data_limite = compra.data + timedelta(days=dias_garantia)
            
            if datetime.now() > data_limite and admin_id is None:
                return False, f"Garantia de {dias_garantia} dias expirada"
            
            # Devolve saldo
            usuario = session.query(Usuario).get(compra.usuario_id)
            if usuario:
                usuario.saldo += compra.valor
            
            # Atualiza compra
            compra.reembolsada = True
            compra.motivo_reembolso = motivo
            compra.data_reembolso = datetime.now()
            compra.status = "reembolsada"
            
            # Libera login
            if compra.login_id:
                login = session.query(EstoqueLogin).get(compra.login_id)
                if login:
                    login.vendido = False
                    login.comprador_id = None
                    login.data_venda = None
                    login.valor_venda = None
            
            # Registra transação de estorno
            transacao = Transacao(
                usuario_id=usuario.telegram_id,
                tipo=TipoTransacao.ESTORNO.value,
                status=StatusTransacao.APROVADO.value,
                valor=compra.valor,
                valor_total=compra.valor,
                descricao=f"Reembolso compra #{compra_id}: {motivo}",
                data_criacao=datetime.now(),
                data_aprovacao=datetime.now()
            )
            session.add(transacao)
            
            session.flush()
            
            log_com_contexto(
                "Compra reembolsada",
                compra_id=compra_id,
                valor=compra.valor,
                motivo=motivo,
                admin_id=admin_id
            )
            
            return True, f"✅ Compra #{compra_id} reembolsada com sucesso"
    
    def get_metricas_vendas(self, periodo: str = "hoje") -> Dict:
        """Retorna métricas de vendas"""
        with self.db.get_session() as session:
            agora = datetime.now()
            
            if periodo == "hoje":
                inicio = agora.replace(hour=0, minute=0, second=0)
            elif periodo == "semana":
                inicio = agora - timedelta(days=7)
            elif periodo == "mes":
                inicio = agora - timedelta(days=30)
            else:
                inicio = agora - timedelta(days=1)
            
            # Total de vendas
            total_vendas = session.query(func.count(Compra.id)).filter(
                Compra.data >= inicio,
                Compra.reembolsada == False
            ).scalar() or 0
            
            # Faturamento total
            faturamento = session.query(func.sum(Compra.valor)).filter(
                Compra.data >= inicio,
                Compra.reembolsada == False
            ).scalar() or 0.0
            
            # Ticket médio
            ticket_medio = float(faturamento) / total_vendas if total_vendas > 0 else 0.0
            
            # Reembolsos
            reembolsos = session.query(func.count(Compra.id)).filter(
                Compra.data_reembolso >= inicio,
                Compra.reembolsada == True
            ).scalar() or 0
            
            # Top produtos
            top_produtos = session.query(
                Produto.nome,
                func.count(Compra.id).label('total'),
                func.sum(Compra.valor).label('faturamento')
            ).join(Compra).filter(
                Compra.data >= inicio,
                Compra.reembolsada == False
            ).group_by(Produto.id).order_by(func.count(Compra.id).desc()).limit(5).all()
            
            return {
                'periodo': periodo,
                'total_vendas': total_vendas,
                'faturamento': float(faturamento),
                'ticket_medio': round(ticket_medio, 2),
                'reembolsos': reembolsos,
                'taxa_reembolso': round((reembolsos / total_vendas * 100), 2) if total_vendas > 0 else 0,
                'top_produtos': [
                    {
                        'nome': p[0],
                        'vendas': p[1],
                        'faturamento': float(p[2])
                    } for p in top_produtos
                ]
            }
    
    def get_relatorio_vendas(self, data_inicio: datetime = None, data_fim: datetime = None) -> List[Dict]:
        """Gera relatório detalhado de vendas"""
        with self.db.get_session() as session:
            query = session.query(Compra).filter(Compra.reembolsada == False)
            
            if data_inicio:
                query = query.filter(Compra.data >= data_inicio)
            if data_fim:
                query = query.filter(Compra.data <= data_fim)
            
            compras = query.order_by(Compra.data.desc()).all()
            
            relatorio = []
            for compra in compras:
                relatorio.append({
                    'id': compra.id,
                    'data': formatar_data(compra.data),
                    'usuario': compra.usuario.nome or str(compra.usuario.telegram_id),
                    'produto': compra.produto.nome if compra.produto else 'N/A',
                    'categoria': compra.produto.categoria.nome if compra.produto and compra.produto.categoria else 'N/A',
                    'valor': compra.valor,
                    'desconto': compra.desconto,
                    'comissao': compra.comissao_gerada,
                    'status': compra.status
                })
            
            return relatorio


# ============================================
// ... continua na próxima parte

# ============================================
# SERVIÇO DE CUPONS
# ============================================

class CupomService:
    """Gerencia cupons de desconto"""
    
    def __init__(self, db: Database):
        self.db = db
    
    def criar_cupom(self, dados: Dict) -> Cupom:
        """Cria um novo cupom"""
        with self.db.get_session() as session:
            cupom = Cupom(
                codigo=dados.get('codigo', '').upper(),
                tipo_desconto=dados.get('tipo_desconto', 'porcentagem'),
                valor_desconto=dados.get('valor_desconto', 0),
                quantidade_maxima=dados.get('quantidade_maxima', 100),
                valor_minimo_compra=dados.get('valor_minimo_compra', 0),
                data_expiracao=dados.get('data_expiracao'),
                primeira_compra_apenas=dados.get('primeira_compra_apenas', False),
                aplica_todos_produtos=dados.get('aplica_todos_produtos', True),
                categorias_aplicaveis=dados.get('categorias_aplicaveis', '')
            )
            session.add(cupom)
            session.flush()
            
            logger.info(f"✅ Cupom criado: {cupom.codigo}")
            return cupom
    
    def validar_cupom(self, codigo: str, usuario_id: int, valor_compra: float) -> Tuple[bool, str, float]:
        """
        Valida e aplica cupom
        
        Returns:
            Tuple (valido, mensagem, valor_desconto)
        """
        with self.db.get_session() as session:
            cupom = session.query(Cupom).filter_by(
                codigo=codigo.upper(), ativo=True
            ).first()
            
            if not cupom:
                return False, "Cupom não encontrado", 0
            
            if cupom.quantidade_usada >= cupom.quantidade_maxima:
                return False, "Cupom esgotado", 0
            
            if cupom.data_expiracao and datetime.now() > cupom.data_expiracao:
                return False, "Cupom expirado", 0
            
            if valor_compra < cupom.valor_minimo_compra:
                return False, f"Valor mínimo: {formatar_moeda(cupom.valor_minimo_compra)}", 0
            
            # Calcula desconto
            if cupom.tipo_desconto == "porcentagem":
                desconto = (valor_compra * cupom.valor_desconto) / 100
            else:
                desconto = min(cupom.valor_desconto, valor_compra)
            
            return True, "Cupom válido", desconto
    
    def listar_cupons(self) -> List[Cupom]:
        """Lista todos os cupons"""
        with self.db.get_session() as session:
            return session.query(Cupom).order_by(Cupom.data_inicio.desc()).all()
    
    def remover_cupom(self, cupom_id: int) -> bool:
        """Remove um cupom"""
        with self.db.get_session() as session:
            cupom = session.query(Cupom).get(cupom_id)
            if cupom:
                cupom.ativo = False
                session.flush()
                return True
            return False


# ============================================
# SERVIÇO DE AVALIAÇÕES
# ============================================

class AvaliacaoService:
    """Gerencia avaliações de produtos"""
    
    def __init__(self, db: Database):
        self.db = db
    
    def avaliar(self, usuario_id: int, produto_id: int, compra_id: int, nota: int, comentario: str = "") -> Tuple[bool, str]:
        """Registra avaliação de um produto"""
        with self.db.get_session() as session:
            # Verifica se já avaliou
            existente = session.query(Avaliacao).filter_by(
                usuario_id=usuario_id, compra_id=compra_id
            ).first()
            
            if existente:
                return False, "Você já avaliou esta compra"
            
            # Valida nota
            if nota < 1 or nota > 5:
                return False, "Nota deve ser entre 1 e 5"
            
            avaliacao = Avaliacao(
                usuario_id=usuario_id,
                produto_id=produto_id,
                compra_id=compra_id,
                nota=nota,
                comentario=comentario
            )
            session.add(avaliacao)
            
            # Atualiza média do produto
            media = session.query(func.avg(Avaliacao.nota)).filter_by(
                produto_id=produto_id
            ).scalar()
            
            produto = session.query(Produto).get(produto_id)
            if produto:
                produto.avaliacao_media = round(float(media), 1) if media else 5.0
            
            session.flush()
            
            logger.info(f"✅ Avaliação registrada: {nota} estrelas - Produto {produto_id}")
            return True, "Avaliação registrada com sucesso!"
    
    def get_avaliacoes_produto(self, produto_id: int) -> List[Dict]:
        """Retorna avaliações de um produto"""
        with self.db.get_session() as session:
            avaliacoes = session.query(Avaliacao).filter_by(
                produto_id=produto_id
            ).order_by(Avaliacao.data.desc()).limit(20).all()
            
            resultado = []
            for av in avaliacoes:
                resultado.append({
                    'id': av.id,
                    'usuario_nome': av.usuario.nome or "Anônimo",
                    'nota': av.nota,
                    'comentario': av.comentario,
                    'data': formatar_data(av.data, "dd/mm/aaaa"),
                    'estrelas': '⭐' * av.nota
                })
            
            return resultado


# ============================================
# EXPORTAÇÕES
# ============================================

__all__ = [
    'OrderService',
    'CupomService',
    'AvaliacaoService',
]
