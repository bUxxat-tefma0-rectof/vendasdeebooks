"""
Painel Admin - Logs do Sistema
Visualização e gerenciamento de logs de atividades
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict
from io import BytesIO
from sqlalchemy import func, and_, or_

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, ContextTypes

from ...config import config
from ...database import Database
from ...database.models import LogAtividade, Usuario
from ...utils.keyboards import botao_voltar, botoes_paginacao
from ...utils.utils import formatar_data, formatar_numero, log_com_contexto
from ...middlewares import somente_admin, log_atividade

logger = logging.getLogger(__name__)


class LogService:
    """Serviço de logs do sistema"""
    
    def __init__(self, db: Database):
        self.db = db
    
    def get_logs(self, usuario_id: int = None, acao: str = None, 
                 limite: int = 50, pagina: int = 1, dias: int = 7) -> tuple:
        """Busca logs com filtros e paginação"""
        with self.db.get_session() as session:
            query = session.query(LogAtividade)
            
            data_limite = datetime.now() - timedelta(days=dias)
            query = query.filter(LogAtividade.data >= data_limite)
            
            if usuario_id:
                query = query.filter_by(usuario_id=usuario_id)
            
            if acao:
                query = query.filter(LogAtividade.acao.ilike(f"%{acao}%"))
            
            total = query.count()
            total_paginas = max(1, (total + limite - 1) // limite)
            
            logs = query.order_by(LogAtividade.data.desc()
            ).offset((pagina - 1) * limite).limit(limite).all()
            
            dados = []
            for log in logs:
                usuario = session.query(Usuario).filter_by(id=log.usuario_id).first() if log.usuario_id else None
                
                dados.append({
                    'id': log.id,
                    'usuario': usuario.nome or str(usuario.telegram_id) if usuario else 'Sistema',
                    'usuario_id': log.usuario_id,
                    'acao': log.acao,
                    'descricao': log.descricao[:100] if log.descricao else '',
                    'data': formatar_data(log.data, "dd/mm/aaaa HH:MM:SS"),
                    'ip': log.ip or 'N/A'
                })
            
            return dados, total, total_paginas
    
    def get_estatisticas_logs(self) -> Dict:
        """Estatísticas de logs"""
        with self.db.get_session() as session:
            agora = datetime.now()
            hoje = agora.replace(hour=0, minute=0, second=0)
            
            total_logs = session.query(func.count(LogAtividade.id)).scalar() or 0
            logs_hoje = session.query(func.count(LogAtividade.id)).filter(
                LogAtividade.data >= hoje
            ).scalar() or 0
            
            acoes_populares = session.query(
                LogAtividade.acao,
                func.count(LogAtividade.id).label('total')
            ).group_by(LogAtividade.acao
            ).order_by(func.count(LogAtividade.id).desc()
            ).limit(10).all()
            
            return {
                'total': total_logs,
                'hoje': logs_hoje,
                'acoes': [{'acao': a[0], 'total': a[1]} for a in acoes_populares]
            }
    
    def limpar_logs_antigos(self, dias: int = 30) -> int:
        """Limpa logs antigos"""
        with self.db.get_session() as session:
            data_limite = datetime.now() - timedelta(days=dias)
            deletados = session.query(LogAtividade).filter(
                LogAtividade.data < data_limite
            ).delete()
            session.flush()
            
            log_com_contexto("Logs antigos limpos", dias=dias, deletados=deletados)
            return deletados
    
    def exportar_logs(self, dias: int = 7) -> BytesIO:
        """Exporta logs para Excel"""
        try:
            import xlsxwriter
            
            output = BytesIO()
            workbook = xlsxwriter.Workbook(output, {'in_memory': True})
            worksheet = workbook.add_worksheet('Logs')
            
            formato_titulo = workbook.add_format({
                'bold': True, 'font_size': 14, 'align': 'center',
                'bg_color': '#2196F3', 'font_color': 'white'
            })
            formato_cabecalho = workbook.add_format({
                'bold': True, 'bg_color': '#E0E0E0', 'border': 1
            })
            formato_dados = workbook.add_format({'border': 1})
            
            worksheet.merge_range('A1:E1', f'Logs do Sistema - {formatar_data(datetime.now())}', formato_titulo)
            
            headers = ['ID', 'Usuário', 'Ação', 'Descrição', 'Data']
            for col, h in enumerate(headers):
                worksheet.write(2, col, h, formato_cabecalho)
            
            dados, _, _ = self.get_logs(dias=dias, limite=5000)
            
            for row, d in enumerate(dados, 3):
                worksheet.write(row, 0, d['id'], formato_dados)
                worksheet.write(row, 1, d['usuario'], formato_dados)
                worksheet.write(row, 2, d['acao'], formato_dados)
                worksheet.write(row, 3, d['descricao'], formato_dados)
                worksheet.write(row, 4, d['data'], formato_dados)
            
            worksheet.set_column('A:A', 8)
            worksheet.set_column('B:B', 20)
            worksheet.set_column('C:C', 25)
            worksheet.set_column('D:D', 40)
            worksheet.set_column('E:E', 22)
            
            workbook.close()
            output.seek(0)
            return output
            
        except Exception as e:
            logger.error(f"Erro ao exportar logs: {e}")
            return None


log_service = None

def init_service(db: Database):
    global log_service
    log_service = LogService(db)


@somente_admin
@log_atividade("admin_menu_logs")
async def menu_logs(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Menu principal de logs"""
    init_service(db)
    query = update.callback_query
    await query.answer()
    
    stats = log_service.get_estatisticas_logs()
    
    texto = f"""
📋 *LOGS DO SISTEMA*

📊 *Estatísticas:*
• Total de logs: {formatar_numero(stats['total'])}
• Logs hoje: {formatar_numero(stats['hoje'])}

📈 *Ações mais frequentes:*
"""
    
    for acao in stats['acoes'][:5]:
        texto += f"• {acao['acao']}: {formatar_numero(acao['total'])}\n"
    
    texto += "\n🔹 Selecione uma opção:"
    
    keyboard = [
        [InlineKeyboardButton("📋 VER LOGS (7 dias)", callback_data="logs_ver_7")],
        [InlineKeyboardButton("📋 VER LOGS (30 dias)", callback_data="logs_ver_30")],
        [InlineKeyboardButton("📋 VER LOGS HOJE", callback_data="logs_ver_1")],
        [InlineKeyboardButton("🔍 PESQUISAR LOGS", callback_data="logs_pesquisar")],
        [InlineKeyboardButton("📥 EXPORTAR LOGS", callback_data="logs_exportar")],
        [InlineKeyboardButton("🗑️ LIMPAR LOGS ANTIGOS", callback_data="logs_limpar")],
        [InlineKeyboardButton("🔙 VOLTAR", callback_data="admin_menu")]
    ]
    
    await query.edit_message_text(
        text=texto,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


@somente_admin
async def ver_logs(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Visualiza logs"""
    query = update.callback_query
    await query.answer()
    
    dias = int(query.data.split("_")[-1])
    pagina = context.user_data.get('logs_pagina', 1)
    
    dados, total, paginas = log_service.get_logs(dias=dias, pagina=pagina)
    
    texto = f"📋 *LOGS ({dias} dias)*\n\n📊 Total: {formatar_numero(total)} | Página {pagina}/{paginas}\n\n"
    
    for log in dados:
        texto += f"🕐 {log['data']}\n"
        texto += f"👤 {log['usuario']} | 🎯 {log['acao']}\n"
        if log['descricao']:
            texto += f"📝 {log['descricao'][:80]}\n"
        texto += "─" * 30 + "\n"
    
    keyboard = []
    nav = []
    if pagina > 1:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"logs_nav_{pagina - 1}"))
    nav.append(InlineKeyboardButton(f"{pagina}/{paginas}", callback_data="nada"))
    if pagina < paginas:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"logs_nav_{pagina + 1}"))
    if nav:
        keyboard.append(nav)
    
    keyboard.append([InlineKeyboardButton("🔙 VOLTAR", callback_data="admin_logs")])
    
    context.user_data['logs_dias'] = dias
    context.user_data['logs_pagina'] = pagina
    
    await query.edit_message_text(
        text=texto,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


@somente_admin
async def navegar_logs(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Navega entre páginas de logs"""
    query = update.callback_query
    await query.answer()
    
    pagina = int(query.data.split("_")[-1])
    context.user_data['logs_pagina'] = pagina
    dias = context.user_data.get('logs_dias', 7)
    
    dados, total, paginas = log_service.get_logs(dias=dias, pagina=pagina)
    
    texto = f"📋 *LOGS ({dias} dias)*\n\n📊 Total: {formatar_numero(total)} | Página {pagina}/{paginas}\n\n"
    
    for log in dados:
        texto += f"🕐 {log['data']}\n"
        texto += f"👤 {log['usuario']} | 🎯 {log['acao']}\n"
        if log['descricao']:
            texto += f"📝 {log['descricao'][:80]}\n"
        texto += "─" * 30 + "\n"
    
    keyboard = []
    nav = []
    if pagina > 1:
        nav.append(InlineKeyboardButton("⬅️", callback_data=f"logs_nav_{pagina - 1}"))
    nav.append(InlineKeyboardButton(f"{pagina}/{paginas}", callback_data="nada"))
    if pagina < paginas:
        nav.append(InlineKeyboardButton("➡️", callback_data=f"logs_nav_{pagina + 1}"))
    if nav:
        keyboard.append(nav)
    
    keyboard.append([InlineKeyboardButton("🔙 VOLTAR", callback_data="admin_logs")])
    
    await query.edit_message_text(
        text=texto,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


@somente_admin
async def exportar_logs(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Exporta logs para Excel"""
    query = update.callback_query
    await query.answer("📥 Gerando arquivo...")
    
    excel_bytes = log_service.exportar_logs()
    
    if excel_bytes:
        excel_bytes.name = f"logs_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
        await query.message.reply_document(
            document=excel_bytes,
            caption="📋 Logs do sistema"
        )
        await query.answer("✅ Enviado!")
    else:
        await query.answer("❌ Erro ao gerar. Instale: pip install xlsxwriter", show_alert=True)


@somente_admin
@log_atividade("admin_limpar_logs")
async def limpar_logs(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Limpa logs antigos"""
    query = update.callback_query
    await query.answer()
    
    deletados = log_service.limpar_logs_antigos(30)
    
    await query.edit_message_text(
        f"✅ *LOGS LIMPOS!*\n\n"
        f"🗑️ {formatar_numero(deletados)} logs com mais de 30 dias foram removidos.",
        reply_markup=botao_voltar("admin_logs"),
        parse_mode="Markdown"
    )


def registrar_handlers_admin_logs(application):
    """Registra handlers de logs"""
    application.add_handler(CallbackQueryHandler(lambda u, c: menu_logs(u, c, None), pattern="^admin_logs$"))
    application.add_handler(CallbackQueryHandler(lambda u, c: ver_logs(u, c, None), pattern="^logs_ver_"))
    application.add_handler(CallbackQueryHandler(lambda u, c: navegar_logs(u, c, None), pattern="^logs_nav_"))
    application.add_handler(CallbackQueryHandler(lambda u, c: exportar_logs(u, c, None), pattern="^logs_exportar$"))
    application.add_handler(CallbackQueryHandler(lambda u, c: limpar_logs(u, c, None), pattern="^logs_limpar$"))
    logger.info("✅ Handlers de logs registrados!")


__all__ = [
    'menu_logs',
    'ver_logs',
    'navegar_logs',
    'exportar_logs',
    'limpar_logs',
    'registrar_handlers_admin_logs',
]
