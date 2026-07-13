"""
Painel Admin - Transações e Financeiro
Visualização de recargas, compras e resumo financeiro
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict
from io import BytesIO
from sqlalchemy import func, and_

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, ContextTypes

from ...config import config
from ...database import Database
from ...database.models import Transacao, Compra, Usuario, TipoTransacao, StatusTransacao
from ...utils.keyboards import admin_menu_transacoes, botao_voltar, botoes_paginacao
from ...utils.utils import (
    formatar_moeda, formatar_data, formatar_numero,
    get_status_emoji, log_com_contexto
)
from ...middlewares import somente_admin, log_atividade

logger = logging.getLogger(__name__)


class TransactionService:
    """Serviço de transações e financeiro"""
    
    def __init__(self, db: Database):
        self.db = db
    
    def get_transacoes(self, tipo: str = None, status: str = None, 
                       limite: int = 20, pagina: int = 1) -> tuple:
        """Lista transações com paginação"""
        with self.db.get_session() as session:
            query = session.query(Transacao)
            
            if tipo:
                query = query.filter_by(tipo=tipo)
            if status:
                query = query.filter_by(status=status)
            
            total = query.count()
            total_paginas = max(1, (total + limite - 1) // limite)
            
            transacoes = query.order_by(Transacao.data_criacao.desc()
            ).offset((pagina - 1) * limite).limit(limite).all()
            
            dados = []
            for t in transacoes:
                usuario = session.query(Usuario).filter_by(telegram_id=t.usuario_id).first()
                dados.append({
                    'id': t.id,
                    'usuario': usuario.nome or str(t.usuario_id) if usuario else str(t.usuario_id),
                    'tipo': t.tipo,
                    'valor': float(t.valor),
                    'valor_total': float(t.valor_total),
                    'status': t.status,
                    'data': formatar_data(t.data_criacao, "dd/mm HH:MM"),
                    'gateway_id': t.gateway_id or ''
                })
            
            return dados, total, total_paginas
    
    def get_compras(self, limite: int = 20, pagina: int = 1) -> tuple:
        """Lista compras com paginação"""
        with self.db.get_session() as session:
            query = session.query(Compra).filter(Compra.reembolsada == False)
            
            total = query.count()
            total_paginas = max(1, (total + limite - 1) // limite)
            
            compras = query.order_by(Compra.data.desc()
            ).offset((pagina - 1) * limite).limit(limite).all()
            
            dados = []
            for c in compras:
                dados.append({
                    'id': c.id,
                    'usuario': c.usuario.nome or str(c.usuario.telegram_id),
                    'produto': c.produto.nome if c.produto else 'N/A',
                    'valor': float(c.valor),
                    'data': formatar_data(c.data, "dd/mm HH:MM"),
                    'status': c.status
                })
            
            return dados, total, total_paginas
    
    def get_resumo_financeiro(self) -> Dict:
        """Resumo financeiro completo"""
        with self.db.get_session() as session:
            agora = datetime.now()
            hoje = agora.replace(hour=0, minute=0, second=0)
            mes_inicio = agora.replace(day=1, hour=0, minute=0, second=0)
            
            recargas_total = session.query(func.sum(Transacao.valor_total)).filter(
                Transacao.tipo == TipoTransacao.PIX.value,
                Transacao.status == StatusTransacao.APROVADO.value
            ).scalar() or 0.0
            
            recargas_hoje = session.query(func.sum(Transacao.valor_total)).filter(
                Transacao.tipo == TipoTransacao.PIX.value,
                Transacao.status == StatusTransacao.APROVADO.value,
                Transacao.data_aprovacao >= hoje
            ).scalar() or 0.0
            
            recargas_mes = session.query(func.sum(Transacao.valor_total)).filter(
                Transacao.tipo == TipoTransacao.PIX.value,
                Transacao.status == StatusTransacao.APROVADO.value,
                Transacao.data_aprovacao >= mes_inicio
            ).scalar() or 0.0
            
            vendas_total = session.query(func.sum(Compra.valor)).filter(
                Compra.reembolsada == False
            ).scalar() or 0.0
            
            vendas_hoje = session.query(func.sum(Compra.valor)).filter(
                Compra.data >= hoje, Compra.reembolsada == False
            ).scalar() or 0.0
            
            vendas_mes = session.query(func.sum(Compra.valor)).filter(
                Compra.data >= mes_inicio, Compra.reembolsada == False
            ).scalar() or 0.0
            
            comissoes_total = session.query(func.sum(Compra.comissao_gerada)).filter(
                Compra.reembolsada == False
            ).scalar() or 0.0
            
            reembolsos = session.query(func.sum(Compra.valor)).filter(
                Compra.reembolsada == True
            ).scalar() or 0.0
            
            saldo_usuarios = session.query(func.sum(Usuario.saldo)).scalar() or 0.0
            
            return {
                'recargas': {'total': float(recargas_total), 'hoje': float(recargas_hoje), 'mes': float(recargas_mes)},
                'vendas': {'total': float(vendas_total), 'hoje': float(vendas_hoje), 'mes': float(vendas_mes)},
                'comissoes': float(comissoes_total),
                'reembolsos': float(reembolsos),
                'saldo_usuarios': float(saldo_usuarios),
                'lucro_liquido': float(vendas_total) - float(comissoes_total) - float(reembolsos)
            }
    
    def exportar_excel(self, tipo: str = "transacoes") -> BytesIO:
        """Exporta dados para Excel"""
        try:
            import xlsxwriter
            
            output = BytesIO()
            workbook = xlsxwriter.Workbook(output, {'in_memory': True})
            worksheet = workbook.add_worksheet('Dados')
            
            formato_titulo = workbook.add_format({
                'bold': True, 'font_size': 14, 'align': 'center',
                'bg_color': '#4CAF50', 'font_color': 'white'
            })
            formato_cabecalho = workbook.add_format({
                'bold': True, 'bg_color': '#E0E0E0', 'border': 1
            })
            formato_dados = workbook.add_format({'border': 1})
            formato_valor = workbook.add_format({'border': 1, 'num_format': 'R$ #,##0.00'})
            
            if tipo == "transacoes":
                dados, _, _ = self.get_transacoes(limite=1000)
                worksheet.merge_range('A1:F1', 'Relatório de Transações', formato_titulo)
                headers = ['ID', 'Usuário', 'Tipo', 'Valor', 'Status', 'Data']
                
                for col, h in enumerate(headers):
                    worksheet.write(1, col, h, formato_cabecalho)
                
                for row, d in enumerate(dados, 2):
                    worksheet.write(row, 0, d['id'], formato_dados)
                    worksheet.write(row, 1, d['usuario'], formato_dados)
                    worksheet.write(row, 2, d['tipo'], formato_dados)
                    worksheet.write(row, 3, d['valor'], formato_valor)
                    worksheet.write(row, 4, d['status'], formato_dados)
                    worksheet.write(row, 5, d['data'], formato_dados)
            
            elif tipo == "compras":
                dados, _, _ = self.get_compras(limite=1000)
                worksheet.merge_range('A1:E1', 'Relatório de Compras', formato_titulo)
                headers = ['ID', 'Usuário', 'Produto', 'Valor', 'Data']
                
                for col, h in enumerate(headers):
                    worksheet.write(1, col, h, formato_cabecalho)
                
                for row, d in enumerate(dados, 2):
                    worksheet.write(row, 0, d['id'], formato_dados)
                    worksheet.write(row, 1, d['usuario'], formato_dados)
                    worksheet.write(row, 2, d['produto'], formato_dados)
                    worksheet.write(row, 3, d['valor'], formato_valor)
                    worksheet.write(row, 4, d['data'], formato_dados)
            
            worksheet.set_column('A:A', 10)
            worksheet.set_column('B:B', 25)
            worksheet.set_column('C:C', 20)
            worksheet.set_column('D:D', 15)
            worksheet.set_column('E:E', 20)
            worksheet.set_column('F:F', 20)
            
            workbook.close()
            output.seek(0)
            return output
            
        except Exception as e:
            logger.error(f"Erro ao exportar Excel: {e}")
            return None


trans_service = None

def init_service(db: Database):
    global trans_service
    trans_service = TransactionService(db)


@somente_admin
@log_atividade("admin_menu_transacoes")
async def menu_transacoes(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Menu de transações"""
    init_service(db)
    query = update.callback_query
    await query.answer()
    
    resumo = trans_service.get_resumo_financeiro()
    
    texto = f"""
💰 *TRANSAÇÕES E FINANCEIRO*

📊 *Resumo Financeiro:*

💎 *Recargas:*
• Total: {formatar_moeda(resumo['recargas']['total'])}
• Hoje: {formatar_moeda(resumo['recargas']['hoje'])}
• Mês: {formatar_moeda(resumo['recargas']['mes'])}

🛒 *Vendas:*
• Total: {formatar_moeda(resumo['vendas']['total'])}
• Hoje: {formatar_moeda(resumo['vendas']['hoje'])}
• Mês: {formatar_moeda(resumo['vendas']['mes'])}

🤝 *Comissões:* {formatar_moeda(resumo['comissoes'])}
🔄 *Reembolsos:* {formatar_moeda(resumo['reembolsos'])}
💵 *Saldo usuários:* {formatar_moeda(resumo['saldo_usuarios'])}

💰 *Lucro Líquido:* {formatar_moeda(resumo['lucro_liquido'])}

🔹 Selecione uma opção:
"""
    
    await query.edit_message_text(
        text=texto,
        reply_markup=admin_menu_transacoes(),
        parse_mode="Markdown"
    )


@somente_admin
async def ver_transacoes(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Visualiza transações"""
    query = update.callback_query
    await query.answer()
    
    tipo = None
    if query.data == "admin_trans_pendentes":
        status = "pendente"
        titulo = "PENDENTES"
    elif query.data == "admin_trans_aprovadas":
        status = "aprovado"
        titulo = "APROVADAS"
    else:
        status = None
        titulo = "TODAS"
    
    context.user_data['trans_status'] = status
    context.user_data['trans_pagina'] = 1
    
    dados, total, paginas = trans_service.get_transacoes(status=status)
    
    texto = f"💰 *TRANSAÇÕES {titulo}*\n\n"
    texto += f"📊 Total: {formatar_numero(total)}\n\n"
    
    for t in dados:
        emoji = get_status_emoji(t['status'])
        texto += f"{emoji} #{t['id']} - {t['usuario'][:15]}\n"
        texto += f"   {t['tipo'].upper()} | {formatar_moeda(t['valor'])} | {t['data']}\n\n"
    
    keyboard = []
    if paginas > 1:
        nav = []
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"trans_pag_0"))
        nav.append(InlineKeyboardButton(f"1/{paginas}", callback_data="nada"))
        nav.append(InlineKeyboardButton("➡️", callback_data=f"trans_pag_2"))
        keyboard.append(nav)
    
    keyboard.append([InlineKeyboardButton("📥 EXPORTAR EXCEL", callback_data="exportar_trans")])
    keyboard.append([InlineKeyboardButton("🔙 VOLTAR", callback_data="admin_transacoes")])
    
    await query.edit_message_text(
        text=texto,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


@somente_admin
async def ver_compras(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Visualiza compras"""
    query = update.callback_query
    await query.answer()
    
    dados, total, paginas = trans_service.get_compras()
    
    texto = f"🛒 *COMPRAS REALIZADAS*\n\n📊 Total: {formatar_numero(total)}\n\n"
    
    for c in dados:
        texto += f"🛒 #{c['id']} - {c['usuario'][:15]}\n"
        texto += f"   {c['produto'][:25]} | {formatar_moeda(c['valor'])} | {c['data']}\n\n"
    
    keyboard = [
        [InlineKeyboardButton("📥 EXPORTAR EXCEL", callback_data="exportar_compras")],
        [InlineKeyboardButton("🔙 VOLTAR", callback_data="admin_transacoes")]
    ]
    
    await query.edit_message_text(
        text=texto,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


@somente_admin
async def ver_resumo_financeiro(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Resumo financeiro detalhado"""
    query = update.callback_query
    await query.answer()
    
    resumo = trans_service.get_resumo_financeiro()
    
    texto = f"""
💰 *RESUMO FINANCEIRO COMPLETO*

📅 *Data:* {formatar_data(datetime.now())}

💎 *RECARGAS:*
• Total: {formatar_moeda(resumo['recargas']['total'])}
• Hoje: {formatar_moeda(resumo['recargas']['hoje'])}
• Mês: {formatar_moeda(resumo['recargas']['mes'])}

🛒 *VENDAS:*
• Total: {formatar_moeda(resumo['vendas']['total'])}
• Hoje: {formatar_moeda(resumo['vendas']['hoje'])}
• Mês: {formatar_moeda(resumo['vendas']['mes'])}

━━━━━━━━━━━━━━━━━━

🤝 Comissões: {formatar_moeda(resumo['comissoes'])}
🔄 Reembolsos: {formatar_moeda(resumo['reembolsos'])}
💵 Saldo usuários: {formatar_moeda(resumo['saldo_usuarios'])}

⭐ *LUCRO LÍQUIDO:* {formatar_moeda(resumo['lucro_liquido'])}
"""
    
    keyboard = [
        [InlineKeyboardButton("📥 EXPORTAR TUDO", callback_data="exportar_trans")],
        [InlineKeyboardButton("🔙 VOLTAR", callback_data="admin_transacoes")]
    ]
    
    await query.edit_message_text(
        text=texto,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


@somente_admin
async def exportar_dados(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Exporta dados para Excel"""
    query = update.callback_query
    await query.answer("📥 Gerando arquivo...")
    
    tipo = "compras" if "compras" in query.data else "transacoes"
    
    excel_bytes = trans_service.exportar_excel(tipo)
    
    if excel_bytes:
        excel_bytes.name = f"{tipo}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        await query.message.reply_document(
            document=excel_bytes,
            caption=f"📊 Relatório de {tipo}"
        )
        await query.answer("✅ Enviado!")
    else:
        await query.answer("❌ Erro ao gerar. Instale: pip install xlsxwriter", show_alert=True)


def registrar_handlers_admin_transactions(application):
    """Registra handlers de transações"""
    application.add_handler(CallbackQueryHandler(lambda u, c: menu_transacoes(u, c, None), pattern="^admin_transacoes$"))
    application.add_handler(CallbackQueryHandler(lambda u, c: ver_transacoes(u, c, None), pattern="^admin_trans_"))
    application.add_handler(CallbackQueryHandler(lambda u, c: ver_compras(u, c, None), pattern="^admin_trans_compras$"))
    application.add_handler(CallbackQueryHandler(lambda u, c: ver_resumo_financeiro(u, c, None), pattern="^admin_resumo_financeiro$"))
    application.add_handler(CallbackQueryHandler(lambda u, c: exportar_dados(u, c, None), pattern="^exportar_"))
    logger.info("✅ Handlers de transações registrados!")


__all__ = [
    'menu_transacoes',
    'ver_transacoes',
    'ver_compras',
    'ver_resumo_financeiro',
    'exportar_dados',
    'registrar_handlers_admin_transactions',
]
