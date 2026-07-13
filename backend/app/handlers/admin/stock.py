"""
Painel Admin - Controle de Estoque
Gerencia logins, entrada e saída de produtos
"""
import logging
from datetime import datetime
from typing import Optional, List, Dict
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CallbackQueryHandler,
    MessageHandler,
    CommandHandler,
    filters,
    ContextTypes,
    ConversationHandler
)

from ...config import config
from ...database import Database
from ...database.models import Produto, Categoria, EstoqueLogin, AlertaProduto
from ...services.products import EstoqueService, ProdutoService, AlertaService
from ...utils.keyboards import (
    admin_menu_estoque,
    admin_menu_produtos,
    botao_voltar,
    botoes_confirmacao,
    botoes_paginacao
)
from ...utils.utils import (
    formatar_moeda,
    formatar_data,
    formatar_numero,
    log_com_contexto
)
from ...utils.states import EstadosAdminEstoque
from ...middlewares import somente_admin, log_atividade

logger = logging.getLogger(__name__)

# ============================================
# INICIALIZAÇÃO DOS SERVIÇOS
# ============================================

estoque_service = None
produto_service = None
alerta_service = None

def init_services(db: Database):
    """Inicializa serviços com a instância do banco"""
    global estoque_service, produto_service, alerta_service
    estoque_service = EstoqueService(db)
    produto_service = ProdutoService(db)
    alerta_service = AlertaService(db)


# ============================================
# MENU PRINCIPAL DO ESTOQUE
# ============================================

@somente_admin
@log_atividade("admin_estoque_menu")
async def menu_estoque(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Exibe menu principal de gerenciamento de estoque"""
    query = update.callback_query
    await query.answer()
    
    init_services(db)
    
    texto = """
📦 *GERENCIAMENTO DE ESTOQUE*

🔹 *Opções disponíveis:*
• Adicionar logins em lote
• Visualizar estoque atual
• Remover logins
• Zerar estoque
• Alterar preços
• Notificar alertas

🔹 Selecione uma opção:
"""
    
    await query.edit_message_text(
        text=texto,
        reply_markup=admin_menu_estoque(),
        parse_mode="Markdown"
    )
    
    return EstadosAdminEstoque.MENU_ESTOQUE


# ============================================
# ADICIONAR LOGINS
# ============================================

@somente_admin
async def add_logins_inicio(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Inicia processo de adicionar logins - seleciona produto"""
    query = update.callback_query
    await query.answer()
    
    init_services(db)
    
    produtos = produto_service.listar_todos()
    
    if not produtos:
        await query.edit_message_text(
            "❌ Nenhum produto cadastrado.\n"
            "Cadastre um produto primeiro.",
            reply_markup=botao_voltar("admin_estoque")
        )
        return EstadosAdminEstoque.MENU_ESTOQUE
    
    texto = """
📦 *ADICIONAR LOGINS*

🔹 *Selecione o produto:*
"""
    
    keyboard = []
    for prod in produtos:
        cat_nome = prod.categoria.nome if prod.categoria else "Sem categoria"
        keyboard.append([
            InlineKeyboardButton(
                f"📦 {prod.nome} ({cat_nome}) - {prod.estoque} un.",
                callback_data=f"addlogins_{prod.id}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 VOLTAR", callback_data="admin_estoque")])
    
    await query.edit_message_text(
        text=texto,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
    return EstadosAdminEstoque.SELECIONAR_PRODUTO_ESTOQUE


@somente_admin
async def add_logins_produto_selecionado(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Produto selecionado - solicita envio do arquivo ou texto"""
    query = update.callback_query
    await query.answer()
    
    produto_id = int(query.data.split("_")[1])
    context.user_data['estoque_produto_id'] = produto_id
    
    produto = produto_service.buscar_por_id(produto_id)
    
    if not produto:
        await query.edit_message_text(
            "❌ Produto não encontrado.",
            reply_markup=botao_voltar("admin_estoque")
        )
        return EstadosAdminEstoque.MENU_ESTOQUE
    
    texto = f"""
📦 *ADICIONAR LOGINS*

📝 *Produto:* {produto.nome}
📊 *Estoque atual:* {produto.estoque} un.

🔹 *Envie o arquivo .TXT com os logins*

📋 *Formato do arquivo:*
