"""
Painel Admin - Dashboard Administrativo Completo
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List
from sqlalchemy import func

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from ...config import config
from ...database import Database
from ...database.models import (
    Usuario, Produto, Compra, Transacao,
    AlertaProduto, StatusTransacao, TipoTransacao
)
from ...utils.keyboards import (
    admin_menu_principal, botao_voltar
)
from ...utils.utils import formatar_moeda, formatar_data, formatar_numero
from ...middlewares import somente_admin, log_atividade

logger = logging.getLogger(__name__)


class AdminMetricsService:
    """Serviço de métricas para dashboard"""
    
    def __init__(self, db: Database):
        self.db = db
    
    def get_metricas_gerais(self) -> Dict:
        """Retorna métricas gerais do sistema"""
        with self.db.get_session() as session:
            agora = datetime.now()
            hoje = agora.replace(hour=0, minute=0, second=0, microsecond=0)
            mes_inicio = agora.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            
            total_usuarios = session.query(func.count(Usuario.id)).scalar() or 0
            novos_hoje = session.query(func.count(Usuario.id)).filter(Usuario.data_registro >= hoje).scalar() or 0
            novos_mes = session.query(func.count(Usuario.id)).filter(Usuario.data_registro >= mes_inicio).scalar() or 0
            
            total_vendas = session.query(func.count(Compra.id)).filter(Compra.reembolsada == False).scalar() or 0
            vendas_hoje = session.query(func.count(Compra.id)).filter(Compra.data >= hoje, Compra.reembolsada == False).scalar() or 0
            vendas_mes = session.query(func.count(Compra.id)).filter(Compra.data >= mes_inicio, Compra.reembolsada == False).scalar() or 0
            
            faturamento_total = session.query(func.sum(Compra.valor)).filter(Compra.reembolsada == False).scalar() or 0.0
            faturamento_hoje = session.query(func.sum(Compra.valor)).filter(Compra.data >= hoje, Compra.reembolsada == False).scalar() or 0.0
            faturamento_mes = session.query(func.sum(Compra.valor)).filter(Compra.data >= mes_inicio, Compra.reembolsada == False).scalar() or 0.0
            
            total_recargas = session.query(func.sum(Transacao.valor_total)).filter(
                Transacao.tipo == TipoTransacao.PIX.value,
                Transacao.status == StatusTransacao.APROVADO.value
            ).scalar() or 0.0
            
            recargas_hoje = session.query(func.sum(Transacao.valor_total)).filter(
                Transacao.tipo == TipoTransacao.PIX.value,
                Transacao.status == StatusTransacao.APROVADO.value,
                Transacao.data_aprovacao >= hoje
            ).scalar() or 0.0
            
            total_produtos = session.query(func.count(Produto.id)).filter(Produto.ativo == True).scalar() or 0
            produtos_sem_estoque = session.query(func.count(Produto.id)).filter(
                Produto.ativo == True, Produto.estoque_ilimitado == False, Produto.estoque <= 0
            ).scalar() or 0
            
            ticket_medio = float(faturamento_total) / total_vendas if total_vendas > 0 else 0.0
            usuarios_com_saldo = session.query(func.count(Usuario.id)).filter(Usuario.saldo > 0).scalar() or 0
            saldo_total = session.query(func.sum(Usuario.saldo)).scalar() or 0.0
            total_afiliados = session.query(func.count(Usuario.id)).filter(Usuario.total_indicacoes > 0).scalar() or 0
            alertas_ativos = session.query(func.count(AlertaProduto.id)).filter(AlertaProduto.ativo == True).scalar() or 0
            
            return {
                'usuarios': {'total': total_usuarios, 'novos_hoje': novos_hoje, 'novos_mes': novos_mes},
                'vendas': {'total': total_vendas, 'hoje': vendas_hoje, 'mes': vendas_mes},
                'faturamento': {'total': float(faturamento_total), 'hoje': float(faturamento_hoje), 'mes': float(faturamento_mes), 'ticket_medio': round(ticket_medio, 2)},
                'recargas': {'total': float(total_recargas), 'hoje': float(recargas_hoje)},
                'produtos': {'total': total_produtos, 'sem_estoque': produtos_sem_estoque},
                'financeiro': {'usuarios_com_saldo': usuarios_com_saldo, 'saldo_total': float(saldo_total)},
                'afiliados': {'total': total_afiliados},
                'alertas': {'ativos': alertas_ativos}
            }
    
    def get_ultimas_vendas(self, limite: int = 5) -> List[Dict]:
        """Retorna últimas vendas"""
        with self.db.get_session() as session:
            compras = session.query(Compra).filter(Compra.reembolsada == False).order_by(Compra.data.desc()).limit(limite).all()
            return [{'id': c.id, 'usuario': c.usuario.nome or str(c.usuario.telegram_id), 'produto': c.produto.nome if c.produto else 'N/A', 'valor': c.valor, 'data': formatar_data(c.data, "HH:MM dd/mm")} for c in compras]
    
    def get_ultimos_usuarios(self, limite: int = 5) -> List[Dict]:
        """Retorna últimos usuários"""
        with self.db.get_session() as session:
            usuarios = session.query(Usuario).order_by(Usuario.data_registro.desc()).limit(limite).all()
            return [{'id': u.telegram_id, 'nome': u.nome or f"@{u.username}" or f"ID:{u.telegram_id}", 'saldo': float(u.saldo), 'data': formatar_data(u.data_registro, "dd/mm/aaaa")} for u in usuarios]


metrics_service = None

def init_metrics(db: Database):
    global metrics_service
    metrics_service = AdminMetricsService(db)


@somente_admin
@log_atividade("admin_dashboard")
async def dashboard_admin(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Exibe dashboard principal"""
    init_metrics(db)
    user = update.effective_user
    m = metrics_service.get_metricas_gerais()
    ultimas_vendas = metrics_service.get_ultimas_vendas()
    ultimos_usuarios = metrics_service.get_ultimos_usuarios()
    
    texto = f"""
🛡️ *PAINEL ADMINISTRATIVO*

👑 *Admin:* {user.first_name}
📅 *Data:* {formatar_data(datetime.now())}
🤖 *Bot:* {config.NOME_BOT} v{config.VERSAO}

📊 *MÉTRICAS GERAIS*
━━━━━━━━━━━━━━━━━━
👥 *Usuários:*
• Total: {formatar_numero(m['usuarios']['total'])}
• Hoje: +{formatar_numero(m['usuarios']['novos_hoje'])}
• Mês: +{formatar_numero(m['usuarios']['novos_mes'])}

🛒 *Vendas:*
• Total: {formatar_numero(m['vendas']['total'])}
• Hoje: {formatar_numero(m['vendas']['hoje'])}
• Mês: {formatar_numero(m['vendas']['mes'])}

💰 *Faturamento:*
• Total: {formatar_moeda(m['faturamento']['total'])}
• Hoje: {formatar_moeda(m['faturamento']['hoje'])}
• Mês: {formatar_moeda(m['faturamento']['mes'])}
• Ticket Médio: {formatar_moeda(m['faturamento']['ticket_medio'])}

💎 *Recargas:* Total: {formatar_moeda(m['recargas']['total'])} | Hoje: {formatar_moeda(m['recargas']['hoje'])}
📦 *Produtos:* {m['produtos']['total']} ativos | {m['produtos']['sem_estoque']} sem estoque
💵 *Saldos:* {formatar_numero(m['financeiro']['usuarios_com_saldo'])} usuários | {formatar_moeda(m['financeiro']['saldo_total'])}
🤝 *Afiliados:* {formatar_numero(m['afiliados']['total'])}
🔔 *Alertas:* {formatar_numero(m['alertas']['ativos'])} ativos

📋 *ÚLTIMAS VENDAS:*
"""
    
    for v in ultimas_vendas:
        texto += f"• {v['data']} - {v['usuario'][:12]} comprou {v['produto'][:20]} - {formatar_moeda(v['valor'])}\n"
    
    texto += f"\n👥 *ÚLTIMOS USUÁRIOS:*\n"
    for u in ultimos_usuarios:
        texto += f"• {u['data']} - {u['nome'][:15]} | Saldo: {formatar_moeda(u['saldo'])}\n"
    
    texto += "\n🔹 Selecione uma opção:"
    
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(text=texto, reply_markup=admin_menu_principal(), parse_mode="Markdown")
    else:
        await update.message.reply_text(text=texto, reply_markup=admin_menu_principal(), parse_mode="Markdown")


@somente_admin
async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Comando /admin"""
    await dashboard_admin(update, context, db)


def registrar_handlers_admin(application):
    """Registra handlers do admin"""
    application.add_handler(CommandHandler("admin", lambda u, c: cmd_admin(u, c, None)))
    application.add_handler(CallbackQueryHandler(lambda u, c: dashboard_admin(u, c, None), pattern="^admin_menu$"))
    logger.info("✅ Handlers do admin registrados!")


__all__ = ['dashboard_admin', 'cmd_admin', 'registrar_handlers_admin', 'AdminMetricsService']
