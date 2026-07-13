"""
Painel Admin - Gerenciamento de Produtos e Estoque
CRUD completo de produtos, categorias e logins
"""
import logging
from datetime import datetime
from typing import List, Dict

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
from ...database.models import Produto, Categoria, EstoqueLogin
from ...services.products import ProdutoService, CategoriaService, EstoqueService
from ...utils.keyboards import (
    admin_menu_produtos, admin_menu_categorias, admin_menu_estoque,
    botao_voltar, botoes_confirmacao, botoes_paginacao
)
from ...utils.utils import (
    formatar_moeda, formatar_data, formatar_numero,
    log_com_contexto
)
from ...utils.states import EstadosAdminProdutos, EstadosAdminCategorias, EstadosAdminEstoque
from ...middlewares import somente_admin, log_atividade

logger = logging.getLogger(__name__)


produto_service = None
categoria_service = None
estoque_service = None

def init_services(db: Database):
    global produto_service, categoria_service, estoque_service
    produto_service = ProdutoService(db)
    categoria_service = CategoriaService(db)
    estoque_service = EstoqueService(db)


# ============================================
# MENU PRINCIPAL DE PRODUTOS
# ============================================

@somente_admin
@log_atividade("admin_menu_produtos")
async def menu_produtos(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Exibe menu de produtos"""
    init_services(db)
    query = update.callback_query
    await query.answer()
    
    produtos = produto_service.listar_todos()
    categorias = categoria_service.listar_todas()
    
    texto = f"""
📦 *GERENCIAR PRODUTOS*

📊 *Resumo:*
• Produtos ativos: {formatar_numero(len(produtos))}
• Categorias: {formatar_numero(len(categorias))}

🔹 Selecione uma opção:
"""
    
    await query.edit_message_text(
        text=texto,
        reply_markup=admin_menu_produtos(),
        parse_mode="Markdown"
    )
    
    return EstadosAdminProdutos.MENU_PRODUTOS


# ============================================
# ADICIONAR PRODUTO
# ============================================

@somente_admin
async def add_produto_inicio(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Inicia processo de adicionar produto"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "📦 *ADICIONAR PRODUTO*\n\n"
        "✏️ *Passo 1/5:* Digite o nome do produto:\n\n"
        "Exemplo: Netflix Premium 4K",
        reply_markup=botao_voltar("admin_produtos"),
        parse_mode="Markdown"
    )
    
    return EstadosAdminProdutos.DIGITAR_NOME_PRODUTO


@somente_admin
async def add_produto_nome(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Recebe nome e solicita descrição"""
    nome = update.message.text.strip()
    
    if len(nome) < 3:
        await update.message.reply_text("❌ Nome muito curto. Mínimo 3 caracteres.")
        return EstadosAdminProdutos.DIGITAR_NOME_PRODUTO
    
    context.user_data['prod_nome'] = nome
    
    await update.message.reply_text(
        f"📦 *ADICIONAR PRODUTO*\n\n"
        f"📝 Nome: *{nome}*\n\n"
        "✏️ *Passo 2/5:* Digite a descrição:",
        reply_markup=botao_voltar("admin_produtos"),
        parse_mode="Markdown"
    )
    
    return EstadosAdminProdutos.DIGITAR_DESCRICAO


@somente_admin
async def add_produto_descricao(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Recebe descrição e solicita valor"""
    descricao = update.message.text.strip()
    context.user_data['prod_descricao'] = descricao
    
    await update.message.reply_text(
        "📦 *ADICIONAR PRODUTO*\n\n"
        "✏️ *Passo 3/5:* Digite o valor:\n\n"
        "Exemplo: 29.90",
        reply_markup=botao_voltar("admin_produtos"),
        parse_mode="Markdown"
    )
    
    return EstadosAdminProdutos.DIGITAR_VALOR


@somente_admin
async def add_produto_valor(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Recebe valor e solicita categoria"""
    try:
        valor = float(update.message.text.replace(",", "."))
        if valor <= 0:
            await update.message.reply_text("❌ Valor deve ser positivo.")
            return EstadosAdminProdutos.DIGITAR_VALOR
    except ValueError:
        await update.message.reply_text("❌ Valor inválido.")
        return EstadosAdminProdutos.DIGITAR_VALOR
    
    context.user_data['prod_valor'] = valor
    
    categorias = categoria_service.listar_todas()
    
    if not categorias:
        await update.message.reply_text(
            "❌ Nenhuma categoria cadastrada. Crie uma categoria primeiro.",
            reply_markup=botao_voltar("admin_produtos")
        )
        return ConversationHandler.END
    
    texto = "📦 *ADICIONAR PRODUTO*\n\n✏️ *Passo 4/5:* Selecione a categoria:"
    
    keyboard = []
    for cat in categorias:
        keyboard.append([
            InlineKeyboardButton(f"{cat.emoji or '📂'} {cat.nome}", callback_data=f"cat_prod_{cat.id}")
        ])
    keyboard.append([InlineKeyboardButton("🔙 CANCELAR", callback_data="admin_produtos")])
    
    await update.message.reply_text(
        text=texto,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
    return EstadosAdminProdutos.SELECIONAR_CATEGORIA


@somente_admin
@log_atividade("admin_add_produto")
async def add_produto_finalizar(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Finaliza criação do produto"""
    query = update.callback_query
    await query.answer()
    
    categoria_id = int(query.data.split("_")[-1])
    
    dados = {
        'nome': context.user_data.get('prod_nome', ''),
        'descricao': context.user_data.get('prod_descricao', ''),
        'valor': context.user_data.get('prod_valor', 0),
        'categoria_id': categoria_id,
        'garantia': '7 dias'
    }
    
    produto = produto_service.criar(dados)
    
    texto = f"""
✅ *PRODUTO CRIADO COM SUCESSO!*

📦 *Nome:* {produto.nome}
📝 *Descrição:* {produto.descricao[:100]}...
💰 *Valor:* {formatar_moeda(produto.valor)}
📂 *Categoria:* {produto.categoria.nome if produto.categoria else 'N/A'}

🔹 O produto já está disponível na loja!
"""
    
    keyboard = [
        [InlineKeyboardButton("📦 VER PRODUTO", callback_data=f"ver_prod_{produto.id}")],
        [InlineKeyboardButton("➕ ADICIONAR OUTRO", callback_data="admin_add_produto")],
        [InlineKeyboardButton("🔙 MENU PRODUTOS", callback_data="admin_produtos")]
    ]
    
    await query.edit_message_text(
        text=texto,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
    for key in ['prod_nome', 'prod_descricao', 'prod_valor']:
        context.user_data.pop(key, None)
    
    return ConversationHandler.END


# ============================================
# EDITAR PRODUTO
# ============================================

@somente_admin
async def editar_produto_inicio(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Lista produtos para edição"""
    query = update.callback_query
    await query.answer()
    
    produtos = produto_service.listar_todos()
    
    if not produtos:
        await query.edit_message_text(
            "❌ Nenhum produto cadastrado.",
            reply_markup=botao_voltar("admin_produtos")
        )
        return EstadosAdminProdutos.MENU_PRODUTOS
    
    texto = "✏️ *EDITAR PRODUTO*\n\n🔹 Selecione o produto:"
    
    keyboard = []
    for prod in produtos:
        keyboard.append([
            InlineKeyboardButton(
                f"✏️ {prod.nome} - {formatar_moeda(prod.valor)}",
                callback_data=f"edit_prod_{prod.id}"
            )
        ])
    keyboard.append([InlineKeyboardButton("🔙 VOLTAR", callback_data="admin_produtos")])
    
    await query.edit_message_text(
        text=texto,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
    return EstadosAdminProdutos.SELECIONAR_PRODUTO


@somente_admin
async def editar_produto_campos(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Exibe campos para edição"""
    query = update.callback_query
    await query.answer()
    
    produto_id = int(query.data.split("_")[-1])
    context.user_data['edit_prod_id'] = produto_id
    
    produto = produto_service.buscar_por_id(produto_id)
    
    if not produto:
        await query.edit_message_text("❌ Produto não encontrado.")
        return ConversationHandler.END
    
    texto = f"""
✏️ *EDITAR PRODUTO*

📦 *{produto.nome}*
💰 Valor: {formatar_moeda(produto.valor)}
📦 Estoque: {produto.estoque} un.
📂 Categoria: {produto.categoria.nome if produto.categoria else 'N/A'}

🔹 *Selecione o campo para editar:*
"""
    
    keyboard = [
        [InlineKeyboardButton("📝 NOME", callback_data="campo_nome")],
        [InlineKeyboardButton("📄 DESCRIÇÃO", callback_data="campo_descricao")],
        [InlineKeyboardButton("💰 VALOR", callback_data="campo_valor")],
        [InlineKeyboardButton("🏷️ VALOR PROMOCIONAL", callback_data="campo_promo")],
        [InlineKeyboardButton("📦 ESTOQUE ILIMITADO", callback_data="campo_ilimitado")],
        [InlineKeyboardButton("🖼️ IMAGEM", callback_data="campo_imagem")],
        [InlineKeyboardButton("🔙 VOLTAR", callback_data="admin_produtos")]
    ]
    
    await query.edit_message_text(
        text=texto,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
    return EstadosAdminProdutos.EDITAR_CAMPO


@somente_admin
async def editar_produto_campo_selecionado(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Solicita novo valor para o campo"""
    query = update.callback_query
    await query.answer()
    
    campo = query.data.split("_")[-1]
    context.user_data['edit_campo'] = campo
    
    nomes_campos = {
        'nome': 'nome',
        'descricao': 'descrição',
        'valor': 'valor (ex: 29.90)',
        'promo': 'valor promocional',
        'imagem': 'ID da imagem (file_id)'
    }
    
    if campo == 'ilimitado':
        produto_id = context.user_data.get('edit_prod_id')
        produto = produto_service.buscar_por_id(produto_id)
        novo_status = not produto.estoque_ilimitado
        produto_service.atualizar(produto_id, estoque_ilimitado=novo_status)
        
        await query.edit_message_text(
            f"✅ Estoque ilimitado: {'✅ ATIVADO' if novo_status else '❌ DESATIVADO'}",
            reply_markup=botao_voltar("admin_produtos")
        )
        return ConversationHandler.END
    
    await query.edit_message_text(
        f"✏️ *EDITAR {campo.upper()}*\n\n"
        f"Digite o novo {nomes_campos.get(campo, campo)}:",
        reply_markup=botao_voltar(f"edit_prod_{context.user_data.get('edit_prod_id')}"),
        parse_mode="Markdown"
    )
    
    return EstadosAdminProdutos.DIGITAR_NOVO_VALOR


@somente_admin
@log_atividade("admin_editar_produto")
async def editar_produto_salvar(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Salva alteração do produto"""
    produto_id = context.user_data.get('edit_prod_id')
    campo = context.user_data.get('edit_campo')
    novo_valor = update.message.text.strip()
    
    if not produto_id or not campo:
        await update.message.reply_text("❌ Dados expirados.")
        return ConversationHandler.END
    
    if campo in ['valor', 'promo']:
        try:
            novo_valor = float(novo_valor.replace(",", "."))
        except ValueError:
            await update.message.reply_text("❌ Valor inválido.")
            return EstadosAdminProdutos.DIGITAR_NOVO_VALOR
    
    kwargs = {campo: novo_valor}
    sucesso = produto_service.atualizar(produto_id, **kwargs)
    
    if sucesso:
        await update.message.reply_text(
            f"✅ Produto atualizado com sucesso!",
            reply_markup=botao_voltar("admin_produtos")
        )
    else:
        await update.message.reply_text(
            "❌ Erro ao atualizar.",
            reply_markup=botao_voltar("admin_produtos")
        )
    
    return ConversationHandler.END


# ============================================
# REMOVER PRODUTO
# ============================================

@somente_admin
async def remover_produto_inicio(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Lista produtos para remoção"""
    query = update.callback_query
    await query.answer()
    
    produtos = produto_service.listar_todos()
    
    texto = "🗑️ *REMOVER PRODUTO*\n\n🔹 Selecione o produto:"
    
    keyboard = []
    for prod in produtos:
        keyboard.append([
            InlineKeyboardButton(
                f"🗑️ {prod.nome} ({prod.estoque} un.)",
                callback_data=f"del_prod_{prod.id}"
            )
        ])
    keyboard.append([InlineKeyboardButton("🔙 VOLTAR", callback_data="admin_produtos")])
    
    await query.edit_message_text(
        text=texto,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
    return EstadosAdminProdutos.REMOVER_PRODUTO


@somente_admin
@log_atividade("admin_remover_produto")
async def remover_produto_confirmar(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Confirma e remove produto"""
    query = update.callback_query
    await query.answer()
    
    produto_id = int(query.data.split("_")[-1])
    produto = produto_service.buscar_por_id(produto_id)
    
    sucesso = produto_service.remover(produto_id)
    
    if sucesso:
        texto = f"✅ Produto *{produto.nome}* removido!"
    else:
        texto = "❌ Erro ao remover produto."
    
    await query.edit_message_text(
        text=texto,
        reply_markup=botao_voltar("admin_produtos"),
        parse_mode="Markdown"
    )


# ============================================
# CATEGORIAS
# ============================================

@somente_admin
async def menu_categorias(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Menu de categorias"""
    query = update.callback_query
    await query.answer()
    
    categorias = categoria_service.listar_todas()
    
    texto = f"📂 *GERENCIAR CATEGORIAS*\n\n📊 Total: {formatar_numero(len(categorias))}\n"
    
    for cat in categorias:
        texto += f"\n{cat.emoji or '📂'} *{cat.nome}* - {cat.total_produtos or 0} produtos"
    
    texto += "\n\n🔹 Selecione uma opção:"
    
    await query.edit_message_text(
        text=texto,
        reply_markup=admin_menu_categorias(),
        parse_mode="Markdown"
    )
    
    return EstadosAdminCategorias.MENU_CATEGORIAS


@somente_admin
async def add_categoria_inicio(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Adiciona categoria - solicita nome"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "📂 *ADICIONAR CATEGORIA*\n\n✏️ Digite o nome:",
        reply_markup=botao_voltar("admin_categorias"),
        parse_mode="Markdown"
    )
    
    return EstadosAdminCategorias.DIGITAR_NOME_CATEGORIA


@somente_admin
@log_atividade("admin_add_categoria")
async def add_categoria_salvar(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Salva nova categoria"""
    nome = update.message.text.strip()
    
    if len(nome) < 2:
        await update.message.reply_text("❌ Nome muito curto.")
        return EstadosAdminCategorias.DIGITAR_NOME_CATEGORIA
    
    categoria = categoria_service.criar(nome=nome, emoji="📂")
    
    await update.message.reply_text(
        f"✅ Categoria *{categoria.nome}* criada!",
        reply_markup=botao_voltar("admin_categorias"),
        parse_mode="Markdown"
    )
    
    return ConversationHandler.END


@somente_admin
async def remover_categoria_inicio(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Remove categoria"""
    query = update.callback_query
    await query.answer()
    
    categorias = categoria_service.listar_todas()
    
    texto = "🗑️ *REMOVER CATEGORIA*\n\n🔹 Selecione:"
    
    keyboard = []
    for cat in categorias:
        keyboard.append([
            InlineKeyboardButton(f"🗑️ {cat.nome}", callback_data=f"del_cat_{cat.id}")
        ])
    keyboard.append([InlineKeyboardButton("🔙 VOLTAR", callback_data="admin_categorias")])
    
    await query.edit_message_text(
        text=texto,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
    return EstadosAdminCategorias.REMOVER_CATEGORIA


@somente_admin
@log_atividade("admin_remover_categoria")
async def remover_categoria_executar(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Executa remoção"""
    query = update.callback_query
    await query.answer()
    
    cat_id = int(query.data.split("_")[-1])
    sucesso = categoria_service.remover(cat_id)
    
    texto = "✅ Categoria removida!" if sucesso else "❌ Erro. Verifique se há produtos na categoria."
    
    await query.edit_message_text(
        text=texto,
        reply_markup=botao_voltar("admin_categorias"),
        parse_mode="Markdown"
    )


# ============================================
# REGISTRAR HANDLERS
# ============================================

def registrar_handlers_admin_products(application):
    """Registra handlers de produtos"""
    
    products_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(lambda u, c: menu_produtos(u, c, None), pattern="^admin_produtos$"),
        ],
        states={
            EstadosAdminProdutos.DIGITAR_NOME_PRODUTO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: add_produto_nome(u, c, None)),
            ],
            EstadosAdminProdutos.DIGITAR_DESCRICAO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: add_produto_descricao(u, c, None)),
            ],
            EstadosAdminProdutos.DIGITAR_VALOR: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: add_produto_valor(u, c, None)),
            ],
            EstadosAdminProdutos.SELECIONAR_CATEGORIA: [
                CallbackQueryHandler(lambda u, c: add_produto_finalizar(u, c, None), pattern="^cat_prod_"),
            ],
            EstadosAdminProdutos.EDITAR_CAMPO: [
                CallbackQueryHandler(lambda u, c: editar_produto_campo_selecionado(u, c, None), pattern="^campo_"),
            ],
            EstadosAdminProdutos.DIGITAR_NOVO_VALOR: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: editar_produto_salvar(u, c, None)),
            ],
            EstadosAdminCategorias.DIGITAR_NOME_CATEGORIA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: add_categoria_salvar(u, c, None)),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(lambda u, c: menu_produtos(u, c, None), pattern="^admin_produtos$"),
        ],
        name="admin_products_conversation",
    )
    
    application.add_handler(products_conv)
    
    application.add_handler(CallbackQueryHandler(lambda u, c: add_produto_inicio(u, c, None), pattern="^admin_add_produto$"))
    application.add_handler(CallbackQueryHandler(lambda u, c: editar_produto_inicio(u, c, None), pattern="^admin_editar_produto$"))
    application.add_handler(CallbackQueryHandler(lambda u, c: remover_produto_inicio(u, c, None), pattern="^admin_remover_produto$"))
    application.add_handler(CallbackQueryHandler(lambda u, c: remover_produto_confirmar(u, c, None), pattern="^del_prod_"))
    application.add_handler(CallbackQueryHandler(lambda u, c: editar_produto_campos(u, c, None), pattern="^edit_prod_"))
    application.add_handler(CallbackQueryHandler(lambda u, c: menu_categorias(u, c, None), pattern="^admin_categorias$"))
    application.add_handler(CallbackQueryHandler(lambda u, c: add_categoria_inicio(u, c, None), pattern="^admin_add_categoria$"))
    application.add_handler(CallbackQueryHandler(lambda u, c: remover_categoria_inicio(u, c, None), pattern="^admin_remover_categoria$"))
    application.add_handler(CallbackQueryHandler(lambda u, c: remover_categoria_executar(u, c, None), pattern="^del_cat_"))
    
    logger.info("✅ Handlers de produtos registrados!")


__all__ = [
    'menu_produtos',
    'add_produto_inicio',
    'editar_produto_inicio',
    'remover_produto_inicio',
    'menu_categorias',
    'add_categoria_inicio',
    'remover_categoria_inicio',
    'registrar_handlers_admin_products',
]
