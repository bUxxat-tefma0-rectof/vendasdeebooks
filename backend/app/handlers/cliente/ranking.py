"""
Módulo do Cliente - Sistema de Ranking
Top 10: Serviços, Compras, Recargas e Saldo
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict
from sqlalchemy import func, desc

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from ...config import config
from ...database import Database
from ...database.models import Usuario, Compra, Transacao, TipoTransacao, StatusTransacao
from ...utils.keyboards import menu_ranking, menu_ranking_detalhes, botao_voltar
from ...utils.utils import formatar_moeda, formatar_numero, get_medalha
from ...middlewares import somente_chat_privado

logger = logging.getLogger(__name__)


class RankingService:
    """Serviço de rankings"""
    
    def __init__(self, db: Database):
        self.db = db
    
    def get_ranking_compras(self, limite: int = 10) -> List[Dict]:
        """Top compradores (quantidade de compras)"""
        with self.db.get_session() as session:
            resultados = session.query(
                Usuario.telegram_id,
                Usuario.nome,
                Usuario.username,
                func.count(Compra.id).label('total_compras'),
                func.sum(Compra.valor).label('total_gasto')
            ).join(Compra, Compra.usuario_id == Usuario.id
            ).filter(Compra.reembolsada == False
            ).group_by(Usuario.id
            ).order_by(desc('total_compras')
            ).limit(limite).all()
            
            return [
                {
                    'id': r[0],
                    'nome': r[1] or f"@{r[2]}" or f"User{r[0]}",
                    'total_compras': r[3],
                    'total_gasto': float(r[4] or 0)
                }
                for r in resultados
            ]
    
    def get_ranking_recargas(self, limite: int = 10) -> List[Dict]:
        """Top recarregadores (valor total em recargas)"""
        with self.db.get_session() as session:
            resultados = session.query(
                Usuario.telegram_id,
                Usuario.nome,
                Usuario.username,
                func.count(Transacao.id).label('total_recargas'),
                func.sum(Transacao.valor_total).label('total_valor')
            ).join(Transacao, Transacao.usuario_id == Usuario.id
            ).filter(
                Transacao.tipo == TipoTransacao.PIX.value,
                Transacao.status == StatusTransacao.APROVADO.value
            ).group_by(Usuario.id
            ).order_by(desc('total_valor')
            ).limit(limite).all()
            
            return [
                {
                    'id': r[0],
                    'nome': r[1] or f"@{r[2]}" or f"User{r[0]}",
                    'total_recargas': r[3],
                    'total_valor': float(r[4] or 0)
                }
                for r in resultados
            ]
    
    def get_ranking_servicos(self, limite: int = 10) -> List[Dict]:
        """Top compradores por valor gasto"""
        with self.db.get_session() as session:
            resultados = session.query(
                Usuario.telegram_id,
                Usuario.nome,
                Usuario.username,
                func.count(Compra.id).label('total_compras'),
                func.sum(Compra.valor).label('total_gasto')
            ).join(Compra, Compra.usuario_id == Usuario.id
            ).filter(Compra.reembolsada == False
            ).group_by(Usuario.id
            ).order_by(desc('total_gasto')
            ).limit(limite).all()
            
            return [
                {
                    'id': r[0],
                    'nome': r[1] or f"@{r[2]}" or f"User{r[0]}",
                    'total_compras': r[3],
                    'total_gasto': float(r[4] or 0)
                }
                for r in resultados
            ]
    
    def get_ranking_saldo(self, limite: int = 10) -> List[Dict]:
        """Top usuários por saldo"""
        with self.db.get_session() as session:
            resultados = session.query(
                Usuario.telegram_id,
                Usuario.nome,
                Usuario.username,
                Usuario.saldo
            ).filter(
                Usuario.is_banido == False
            ).order_by(desc(Usuario.saldo)
            ).limit(limite).all()
            
            return [
                {
                    'id': r[0],
                    'nome': r[1] or f"@{r[2]}" or f"User{r[0]}",
                    'saldo': float(r[3] or 0)
                }
                for r in resultados
            ]
    
    def get_posicao_usuario(self, user_id: int, tipo: str) -> int:
        """Retorna a posição do usuário no ranking"""
        rankings = {
            'compras': self.get_ranking_compras(100),
            'recargas': self.get_ranking_recargas(100),
            'servicos': self.get_ranking_servicos(100),
            'saldo': self.get_ranking_saldo(100)
        }
        
        ranking = rankings.get(tipo, [])
        for i, user in enumerate(ranking, 1):
            if user['id'] == user_id:
                return i
        return 0


ranking_service = None

def init_service(db: Database):
    global ranking_service
    ranking_service = RankingService(db)


async def mostrar_menu_ranking(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Exibe menu principal do ranking"""
    init_service(db)
    
    texto = """
🏆 *RANKING DOS TOP 10*

🔹 Escolha uma categoria:

🛒 *Compras* - Quem mais comprou
💎 *Recargas* - Quem mais recarregou
🔧 *Serviços* - Quem mais gastou
💰 *Saldo* - Maiores saldos

🔹 Selecione abaixo:
"""
    
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            text=texto,
            reply_markup=menu_ranking(),
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            text=texto,
            reply_markup=menu_ranking(),
            parse_mode="Markdown"
        )


async def exibir_ranking(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database, tipo: str):
    """Exibe ranking específico"""
    query = update.callback_query
    await query.answer()
    
    init_service(db)
    user_id = query.from_user.id
    
    titulos = {
        'compras': ('🛒 Compras', 'compras'),
        'recargas': ('💎 Recargas', 'recargas'),
        'servicos': ('🔧 Serviços', 'servicos'),
        'saldo': ('💰 Saldo', 'saldo')
    }
    
    emoji, nome = titulos.get(tipo, ('🏆', 'Ranking'))
    
    if tipo == 'compras':
        ranking = ranking_service.get_ranking_compras()
    elif tipo == 'recargas':
        ranking = ranking_service.get_ranking_recargas()
    elif tipo == 'servicos':
        ranking = ranking_service.get_ranking_servicos()
    elif tipo == 'saldo':
        ranking = ranking_service.get_ranking_saldo()
    else:
        ranking = []
    
    texto = f"🏆 *TOP 10 - {emoji} {nome}*\n\n"
    
    if not ranking:
        texto += "⚠️ Nenhum dado disponível ainda.\n"
    else:
        for i, user in enumerate(ranking, 1):
            medalha = get_medalha(i)
            nome_user = user.get('nome', 'N/A')
            
            if len(nome_user) > 20:
                nome_user = nome_user[:18] + "..."
            
            texto += f"{medalha} *{i}º* - {nome_user}\n"
            
            if tipo == 'compras':
                texto += f"   🛒 {user.get('total_compras', 0)} compras | 💰 {formatar_moeda(user.get('total_gasto', 0))}\n"
            elif tipo == 'recargas':
                texto += f"   💎 {user.get('total_recargas', 0)} recargas | 💰 {formatar_moeda(user.get('total_valor', 0))}\n"
            elif tipo == 'servicos':
                texto += f"   🛒 {user.get('total_compras', 0)} compras | 💰 {formatar_moeda(user.get('total_gasto', 0))}\n"
            elif tipo == 'saldo':
                texto += f"   💰 {formatar_moeda(user.get('saldo', 0))}\n"
            
            texto += "\n"
    
    # Posição do usuário
    posicao = ranking_service.get_posicao_usuario(user_id, tipo)
    if posicao > 0:
        texto += f"📊 *Sua posição:* {posicao}º lugar\n"
    else:
        texto += "📊 *Sua posição:* Fora do Top 100\n"
    
    keyboard = [
        [
            InlineKeyboardButton("🛒 COMPRAS", callback_data="rank_compras"),
            InlineKeyboardButton("💎 RECARGAS", callback_data="rank_recargas")
        ],
        [
            InlineKeyboardButton("🔧 SERVIÇOS", callback_data="rank_servicos"),
            InlineKeyboardButton("💰 SALDO", callback_data="rank_saldo")
        ],
        [InlineKeyboardButton("🔙 VOLTAR", callback_data="menu_principal")]
    ]
    
    await query.edit_message_text(
        text=texto,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


def registrar_handlers_ranking(application):
    """Registra handlers de ranking"""
    application.add_handler(CommandHandler("ranking", lambda u, c: mostrar_menu_ranking(u, c, None)))
    application.add_handler(CallbackQueryHandler(lambda u, c: mostrar_menu_ranking(u, c, None), pattern="^menu_ranking$"))
    application.add_handler(CallbackQueryHandler(lambda u, c: exibir_ranking(u, c, None, "compras"), pattern="^rank_compras$"))
    application.add_handler(CallbackQueryHandler(lambda u, c: exibir_ranking(u, c, None, "recargas"), pattern="^rank_recargas$"))
    application.add_handler(CallbackQueryHandler(lambda u, c: exibir_ranking(u, c, None, "servicos"), pattern="^rank_servicos$"))
    application.add_handler(CallbackQueryHandler(lambda u, c: exibir_ranking(u, c, None, "saldo"), pattern="^rank_saldo$"))
    logger.info("✅ Handlers de ranking registrados!")


__all__ = [
    'mostrar_menu_ranking',
    'exibir_ranking',
    'registrar_handlers_ranking',
    'RankingService',
]
