"""
Módulo do Cliente - Histórico de Compras e Geração de PDF/Excel
"""
import logging
from datetime import datetime
from typing import List, Dict
from io import BytesIO

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from ...config import config
from ...database import Database
from ...services.orders import OrderService
from ...utils.keyboards import botao_voltar
from ...utils.utils import formatar_moeda, formatar_data, get_status_emoji
from ...middlewares import somente_chat_privado

logger = logging.getLogger(__name__)


class RelatorioService:
    """Gerencia geração de relatórios em PDF e Excel"""
    
    @staticmethod
    def gerar_pdf_compras(compras: List[Dict], usuario: Dict) -> BytesIO:
        """Gera PDF com histórico de compras"""
        try:
            from fpdf import FPDF
            
            pdf = FPDF()
            pdf.add_page()
            pdf.set_auto_page_break(auto=True, margin=15)
            
            pdf.set_font("Helvetica", "B", 20)
            pdf.cell(0, 10, config.NOME_BOT, ln=True, align="C")
            pdf.set_font("Helvetica", "", 12)
            pdf.cell(0, 10, "Historico de Compras", ln=True, align="C")
            pdf.ln(5)
            
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(5)
            
            pdf.set_font("Helvetica", "B", 12)
            pdf.cell(0, 8, "Dados do Cliente", ln=True)
            pdf.set_font("Helvetica", "", 10)
            pdf.cell(0, 6, f"Nome: {usuario.get('nome', 'N/A')}", ln=True)
            pdf.cell(0, 6, f"ID: {usuario.get('id', 'N/A')}", ln=True)
            pdf.cell(0, 6, f"Data: {formatar_data(datetime.now())}", ln=True)
            pdf.cell(0, 6, f"Total de Compras: {len(compras)}", ln=True)
            pdf.ln(5)
            
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(5)
            
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_fill_color(240, 240, 240)
            
            colunas = [("ID", 15), ("Produto", 55), ("Data", 35), ("Valor", 30), ("Status", 30), ("Garantia", 25)]
            for nome, largura in colunas:
                pdf.cell(largura, 8, nome, border=1, fill=True, align="C")
            pdf.ln()
            
            pdf.set_font("Helvetica", "", 9)
            total_valor = 0.0
            
            for compra in compras:
                pdf.cell(15, 7, str(compra.get('id', '')), border=1, align="C")
                pdf.cell(55, 7, compra.get('produto_nome', 'N/A')[:30], border=1)
                pdf.cell(35, 7, compra.get('data', 'N/A'), border=1, align="C")
                valor = compra.get('valor', 0)
                total_valor += valor
                pdf.cell(30, 7, formatar_moeda(valor), border=1, align="R")
                pdf.cell(30, 7, compra.get('status', 'N/A').upper(), border=1, align="C")
                pdf.cell(25, 7, compra.get('garantia', 'N/A'), border=1, align="C")
                pdf.ln()
            
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
            pdf.ln(5)
            pdf.set_font("Helvetica", "B", 12)
            pdf.cell(0, 10, f"Total Gasto: {formatar_moeda(total_valor)}", ln=True, align="R")
            
            pdf.ln(10)
            pdf.set_font("Helvetica", "I", 8)
            pdf.cell(0, 5, f"Relatorio gerado em {formatar_data(datetime.now())}", ln=True, align="C")
            pdf.cell(0, 5, f"{config.NOME_BOT} v{config.VERSAO}", ln=True, align="C")
            
            output = BytesIO()
            pdf.output(output)
            output.seek(0)
            return output
            
        except Exception as e:
            logger.error(f"Erro ao gerar PDF: {e}")
            return None
    
    @staticmethod
    def gerar_excel_compras(compras: List[Dict], usuario: Dict) -> BytesIO:
        """Gera arquivo Excel com histórico de compras"""
        try:
            import xlsxwriter
            
            output = BytesIO()
            workbook = xlsxwriter.Workbook(output, {'in_memory': True})
            worksheet = workbook.add_worksheet('Historico')
            
            formato_titulo = workbook.add_format({
                'bold': True, 'font_size': 16, 'align': 'center',
                'bg_color': '#4CAF50', 'font_color': 'white', 'border': 1
            })
            formato_cabecalho = workbook.add_format({
                'bold': True, 'font_size': 11, 'align': 'center',
                'bg_color': '#E0E0E0', 'border': 1
            })
            formato_dados = workbook.add_format({
                'font_size': 10, 'align': 'center', 'border': 1
            })
            formato_valor = workbook.add_format({
                'font_size': 10, 'align': 'right', 'border': 1,
                'num_format': 'R$ #,##0.00'
            })
            
            worksheet.merge_range('A1:F1', f'{config.NOME_BOT} - Historico de Compras', formato_titulo)
            
            bold = workbook.add_format({'bold': True})
            worksheet.write('A3', 'Cliente:', bold)
            worksheet.write('B3', usuario.get('nome', 'N/A'))
            worksheet.write('A4', 'ID:', bold)
            worksheet.write('B4', usuario.get('id', 'N/A'))
            worksheet.write('A5', 'Data:', bold)
            worksheet.write('B5', formatar_data(datetime.now()))
            
            headers = ['ID', 'Produto', 'Data', 'Valor', 'Status', 'Garantia']
            for col, header in enumerate(headers):
                worksheet.write(7, col, header, formato_cabecalho)
            
            worksheet.set_column('A:A', 8)
            worksheet.set_column('B:B', 35)
            worksheet.set_column('C:C', 20)
            worksheet.set_column('D:D', 15)
            worksheet.set_column('E:E', 15)
            worksheet.set_column('F:F', 15)
            
            row = 8
            total_valor = 0.0
            
            for compra in compras:
                worksheet.write(row, 0, compra.get('id', ''), formato_dados)
                worksheet.write(row, 1, compra.get('produto_nome', 'N/A'), formato_dados)
                worksheet.write(row, 2, compra.get('data', 'N/A'), formato_dados)
                valor = compra.get('valor', 0)
                total_valor += valor
                worksheet.write(row, 3, valor, formato_valor)
                worksheet.write(row, 4, compra.get('status', 'N/A').upper(), formato_dados)
                worksheet.write(row, 5, compra.get('garantia', 'N/A'), formato_dados)
                row += 1
            
            formato_total = workbook.add_format({
                'bold': True, 'font_size': 12, 'align': 'right',
                'border': 2, 'num_format': 'R$ #,##0.00', 'bg_color': '#FFF9C4'
            })
            worksheet.merge_range(f'A{row}:C{row}', 'TOTAL GASTO:', formato_total)
            worksheet.write(row, 3, total_valor, formato_total)
            
            workbook.close()
            output.seek(0)
            return output
            
        except Exception as e:
            logger.error(f"Erro ao gerar Excel: {e}")
            return None


relatorio_service = RelatorioService()


@somente_chat_privado
async def cmd_historico(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Comando /historico - Exibe histórico de compras"""
    user = update.effective_user
    user_id = user.id
    
    order_service = OrderService(db)
    compras = order_service.listar_compras_usuario(user_id)
    
    if not compras:
        await update.message.reply_text(
            "📊 *HISTÓRICO DE COMPRAS*\n\n"
            "⚠️ Você ainda não realizou nenhuma compra.\n\n"
            "🛍️ Use os botões para ver nossos produtos!",
            parse_mode="Markdown",
            reply_markup=botao_voltar("menu_principal")
        )
        return
    
    context.user_data['historico_compras'] = compras
    context.user_data['historico_pagina'] = 0
    await exibir_pagina_historico(update, context, db, 0)


async def exibir_pagina_historico(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database, pagina: int):
    """Exibe uma página do histórico"""
    user = update.effective_user
    user_id = user.id
    
    compras = context.user_data.get('historico_compras', [])
    itens_por_pagina = 5
    total_paginas = max(1, (len(compras) + itens_por_pagina - 1) // itens_por_pagina)
    
    inicio = pagina * itens_por_pagina
    fim = inicio + itens_por_pagina
    pagina_compras = compras[inicio:fim]
    
    db_user = db.get_user(user_id)
    
    texto = f"""
📊 *HISTÓRICO DE COMPRAS*

👤 *Cliente:* {user.first_name}
🆔 *ID:* `{user_id}`
💰 *Saldo:* {formatar_moeda(db_user.saldo) if db_user else 'N/A'}
🛒 *Total de compras:* {len(compras)}

📋 *Página {pagina + 1}/{total_paginas}:*
"""
    
    for i, compra in enumerate(pagina_compras, 1):
        status_emoji = get_status_emoji(compra.get('status', ''))
        texto += f"\n{status_emoji} *Compra #{compra.get('id', 'N/A')}*\n"
        texto += f"📦 {compra.get('produto_nome', 'N/A')}\n"
        texto += f"💰 {formatar_moeda(compra.get('valor', 0))}\n"
        texto += f"📅 {compra.get('data', 'N/A')}\n"
        if compra.get('reembolsada'):
            texto += "🔄 *REEMBOLSADA*\n"
        texto += "─" * 30 + "\n"
    
    keyboard = []
    
    nav_botoes = []
    if pagina > 0:
        nav_botoes.append(InlineKeyboardButton("⬅️ ANTERIOR", callback_data=f"hist_pag_{pagina - 1}"))
    nav_botoes.append(InlineKeyboardButton(f"📄 {pagina + 1}/{total_paginas}", callback_data="nada"))
    if pagina < total_paginas - 1:
        nav_botoes.append(InlineKeyboardButton("PRÓXIMA ➡️", callback_data=f"hist_pag_{pagina + 1}"))
    keyboard.append(nav_botoes)
    
    keyboard.append([
        InlineKeyboardButton("📥 BAIXAR PDF", callback_data="hist_pdf"),
        InlineKeyboardButton("📊 BAIXAR EXCEL", callback_data="hist_excel")
    ])
    
    for compra in pagina_compras:
        keyboard.append([
            InlineKeyboardButton(f"🔍 Ver #{compra.get('id', '')}", callback_data=f"detalhe_compra_{compra.get('id', '')}")
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 VOLTAR", callback_data="menu_perfil")])
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text=texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            text=texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
        )


async def ver_detalhes_compra(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Exibe detalhes de uma compra"""
    query = update.callback_query
    await query.answer()
    
    compra_id = int(query.data.split("_")[-1])
    order_service = OrderService(db)
    detalhes = order_service.get_detalhes_compra(compra_id)
    
    if not detalhes:
        await query.edit_message_text("❌ Compra não encontrada.", reply_markup=botao_voltar("historico_compras"))
        return
    
    status_emoji = get_status_emoji(detalhes.get('status', ''))
    
    texto = f"{status_emoji} *COMPRA #{compra_id}*\n\n"
    texto += f"📦 *Produto:* {detalhes.get('produto_nome', 'N/A')}\n"
    texto += f"💰 *Valor:* {formatar_moeda(detalhes.get('valor', 0))}\n"
    texto += f"📅 *Data:* {detalhes.get('data', 'N/A')}\n"
    texto += f"🛡️ *Garantia:* {detalhes.get('garantia', 'N/A')}\n"
    
    if detalhes.get('login'):
        texto += f"\n🔐 *DADOS DE ACESSO:*\n"
        texto += f"📧 Email: `{detalhes['login'].get('email', 'N/A')}`\n"
        texto += f"🔑 Senha: `{detalhes['login'].get('senha', 'N/A')}`\n"
        if detalhes['login'].get('perfil'):
            texto += f"👤 Perfil: {detalhes['login'].get('perfil', '')}\n"
        texto += f"⏰ Duração: {detalhes['login'].get('duracao', 'N/A')}\n"
    
    keyboard = [
        [InlineKeyboardButton("🔙 VOLTAR", callback_data="historico_compras")]
    ]
    
    await query.edit_message_text(
        text=texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown"
    )


async def baixar_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Gera e envia PDF do histórico"""
    query = update.callback_query
    await query.answer("📥 Gerando PDF...")
    
    user = update.effective_user
    compras = context.user_data.get('historico_compras', [])
    
    usuario_dict = {
        'nome': user.first_name,
        'id': user.id
    }
    
    pdf_bytes = relatorio_service.gerar_pdf_compras(compras, usuario_dict)
    
    if pdf_bytes:
        pdf_bytes.name = f"historico_{user.id}_{datetime.now().strftime('%Y%m%d')}.pdf"
        await query.message.reply_document(
            document=pdf_bytes,
            caption="📄 Seu histórico de compras em PDF"
        )
    else:
        await query.answer("❌ Erro ao gerar PDF. Instale: pip install fpdf2", show_alert=True)


async def baixar_excel(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Gera e envia Excel do histórico"""
    query = update.callback_query
    await query.answer("📊 Gerando Excel...")
    
    user = update.effective_user
    compras = context.user_data.get('historico_compras', [])
    
    usuario_dict = {
        'nome': user.first_name,
        'id': user.id
    }
    
    excel_bytes = relatorio_service.gerar_excel_compras(compras, usuario_dict)
    
    if excel_bytes:
        excel_bytes.name = f"historico_{user.id}_{datetime.now().strftime('%Y%m%d')}.xlsx"
        await query.message.reply_document(
            document=excel_bytes,
            caption="📊 Seu histórico de compras em Excel"
        )
    else:
        await query.answer("❌ Erro ao gerar Excel. Instale: pip install xlsxwriter", show_alert=True)


def registrar_handlers_history(application):
    """Registra handlers de histórico"""
    application.add_handler(CommandHandler("historico", lambda u, c: cmd_historico(u, c, None)))
    application.add_handler(CallbackQueryHandler(lambda u, c: cmd_historico(u, c, None), pattern="^historico_compras$"))
    application.add_handler(CallbackQueryHandler(lambda u, c: exibir_pagina_historico(u, c, None, int(u.callback_query.data.split("_")[-1])), pattern="^hist_pag_"))
    application.add_handler(CallbackQueryHandler(lambda u, c: ver_detalhes_compra(u, c, None), pattern="^detalhe_compra_"))
    application.add_handler(CallbackQueryHandler(lambda u, c: baixar_pdf(u, c, None), pattern="^hist_pdf$"))
    application.add_handler(CallbackQueryHandler(lambda u, c: baixar_excel(u, c, None), pattern="^hist_excel$"))
    logger.info("✅ Handlers de histórico registrados!")


__all__ = [
    'cmd_historico',
    'exibir_pagina_historico',
    'ver_detalhes_compra',
    'baixar_pdf',
    'baixar_excel',
    'registrar_handlers_history',
    'RelatorioService',
    'relatorio_service',
]
