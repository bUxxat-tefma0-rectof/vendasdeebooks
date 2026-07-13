"""
Módulo do Cliente - Pesquisa de Serviços
Busca inteligente de produtos com imagens
"""
import logging
from typing import List, Dict

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler
)

from ...config import config
from ...database import Database
from ...database.models import Produto, Categoria
from ...services.products import ProdutoService
from ...utils.keyboards import botao_voltar, botoes_paginacao
from ...utils.utils import formatar_moeda, log_com_contexto
from ...utils.states import EstadosPesquisa
from ...middlewares import somente_chat_privado

logger = logging.getLogger(__name__)


class SearchService:
    """Serviço de pesquisa inteligente"""
    
    @staticmethod
    def pesquisar_produtos(db: Database, termo: str, categoria_id: int = None, 
                           preco_min: float = None, preco_max: float = None,
                           apenas_estoque: bool = True) -> List[Dict]:
        """Pesquisa produtos com filtros"""
        with db.get_session() as session:
            query = session.query(Produto).filter(Produto.ativo == True)
            
            # Filtro por nome/descrição
            if termo:
                search_term = f"%{termo}%"
                query = query.filter(
                    (Produto.nome.ilike(search_term)) |
                    (Produto.descricao.ilike(search_term)) |
                    (Produto.plataforma.ilike(search_term))
                )
            
            # Filtro por categoria
            if categoria_id:
                query = query.filter(Produto.categoria_id == categoria_id)
            
            # Filtro por preço
            if preco_min is not None:
                query = query.filter(Produto.valor >= preco_min)
            if preco_max is not None:
                query = query.filter(Produto.valor <= preco_max)
            
            # Filtro de estoque
            if apenas_estoque:
                query = query.filter(Produto.estoque > 0)
            
            produtos = query.order_by(Produto.nome).limit(20).all()
            
            resultados = []
            for prod in produtos:
                resultados.append({
                    'id': prod.id,
                    'nome': prod.nome,
                    'descricao': prod.descricao[:100] if prod.descricao else '',
                    'valor': prod.valor,
                    'estoque': prod.estoque,
                    'categoria_nome': prod.categoria.nome if prod.categoria else '',
                    'categoria_id': prod.categoria_id,
                    'imagem_id': prod.imagem_id,
                    'em_promocao': prod.em_promocao,
                    'valor_promocional': prod.valor_promocional,
                    'garantia': prod.garantia,
                    'total_vendas': prod.total_vendas or 0
                })
            
            return resultados
    
    @staticmethod
    def get_sugestoes(db: Database, termo: str) -> List[str]:
        """Retorna sugestões de pesquisa"""
        if len(termo) < 2:
            return []
        
        with db.get_session() as session:
            produtos = session.query(Produto.nome).filter(
                Produto.ativo == True,
                Produto.nome.ilike(f"%{termo}%")
            ).limit(5).all()
            
            return [p[0] for p in produtos]


search_service = SearchService()


async def iniciar_pesquisa(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Inicia modo de pesquisa"""
    query = update.callback_query
    
    if query:
        await query.answer()
        await query.edit_message_text(
            "🔍 *PESQUISAR SERVIÇOS*\n\n"
            "✏️ *Digite o nome do produto:*\n\n"
            "💡 *Dicas:*\n"
            "• Nome do serviço (Netflix, Spotify)\n"
            "• Tipo (Premium, Familia)\n"
            "• Plataforma (Android, PC)\n\n"
            "📝 Digite sua pesquisa:",
            reply_markup=botao_voltar("menu_loja"),
            parse_mode="Markdown"
        )
        return EstadosPesquisa.DIGITAR_TERMO
    
    return ConversationHandler.END


async def receber_pesquisa(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Recebe termo e exibe resultados"""
    termo = update.message.text.strip()
    
    if not termo or len(termo) < 2:
        await update.message.reply_text(
            "❌ Digite pelo menos 2 caracteres.",
            reply_markup=botao_voltar("menu_loja")
        )
        return EstadosPesquisa.DIGITAR_TERMO
    
    context.user_data['ultimo_termo'] = termo
    context.user_data['pagina_pesquisa'] = 0
    
    return await exibir_resultados(update, context, db, termo, 0)


async def exibir_resultados(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database, 
                           termo: str = None, pagina: int = 0):
    """Exibe página de resultados"""
    if not termo:
        termo = context.user_data.get('ultimo_termo', '')
    
    resultados = search_service.pesquisar_produtos(db, termo)
    
    itens_por_pagina = 5
    total_paginas = max(1, (len(resultados) + itens_por_pagina - 1) // itens_por_pagina)
    
    inicio = pagina * itens_por_pagina
    fim = inicio + itens_por_pagina
    pagina_resultados = resultados[inicio:fim]
    
    if not resultados:
        texto = f"""
🔍 *PESQUISA: `{termo}`*

❌ Nenhum resultado encontrado.

💡 *Sugestões:*
• Verifique a ortografia
• Use termos mais genéricos
• Tente outra categoria
"""
        keyboard = [
            [InlineKeyboardButton("🔍 NOVA PESQUISA", callback_data="pesquisar")],
            [InlineKeyboardButton("🛍️ VER LOJA COMPLETA", callback_data="menu_loja")],
            [InlineKeyboardButton("🔙 VOLTAR", callback_data="menu_principal")]
        ]
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                text=texto,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                text=texto,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
        return ConversationHandler.END
    
    texto = f"""
🔍 *RESULTADOS PARA: `{termo}`*

📊 *{len(resultados)} produto(s) encontrado(s)*

📄 *Página {pagina + 1}/{total_paginas}:*
"""
    
    keyboard = []
    
    for i, prod in enumerate(pagina_resultados, 1):
        num = inicio + i
        
        preco = prod.get('valor_promocional') if prod.get('em_promocao') else prod.get('valor')
        
        texto += f"\n*{num}. {prod.get('nome', 'N/A')}*"
        if prod.get('em_promocao'):
            texto += " 🔥"
        texto += f"\n   💰 {formatar_moeda(prod.get('valor', 0))}"
        if prod.get('em_promocao') and prod.get('valor_promocional'):
            texto += f" | 🏷️ {formatar_moeda(prod.get('valor_promocional', 0))}"
        texto += f"\n   📦 {prod.get('estoque', 0)} un. | 🛒 {prod.get('total_vendas', 0)} vendas"
        texto += f"\n   📂 {prod.get('categoria_nome', 'N/A')}"
        texto += "\n"
        
        if prod.get('estoque', 0) > 0:
            keyboard.append([
                InlineKeyboardButton(
                    f"🛒 {prod.get('nome', '')} - {formatar_moeda(prod.get('valor', 0))}",
                    callback_data=f"ver_prod_{prod.get('id', 0)}"
                )
            ])
        else:
            keyboard.append([
                InlineKeyboardButton(
                    f"🔔 {prod.get('nome', '')} - Esgotado",
                    callback_data=f"alerta_{prod.get('id', 0)}"
                )
            ])
    
    # Paginação
    nav_botoes = []
    if pagina > 0:
        nav_botoes.append(InlineKeyboardButton("⬅️", callback_data=f"search_pag_{pagina - 1}"))
    nav_botoes.append(InlineKeyboardButton(f"{pagina + 1}/{total_paginas}", callback_data="nada"))
    if pagina < total_paginas - 1:
        nav_botoes.append(InlineKeyboardButton("➡️", callback_data=f"search_pag_{pagina + 1}"))
    
    if nav_botoes:
        keyboard.append(nav_botoes)
    
    keyboard.append([
        InlineKeyboardButton("🔍 NOVA PESQUISA", callback_data="pesquisar"),
        InlineKeyboardButton("🎯 FILTROS", callback_data="search_filtros")
    ])
    keyboard.append([InlineKeyboardButton("🛍️ LOJA COMPLETA", callback_data="menu_loja")])
    keyboard.append([InlineKeyboardButton("🔙 MENU PRINCIPAL", callback_data="menu_principal")])
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            text=texto,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            text=texto,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
    
    return EstadosPesquisa.EXIBIR_RESULTADOS


async def navegar_pagina_pesquisa(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Navega entre páginas da pesquisa"""
    query = update.callback_query
    await query.answer()
    
    pagina = int(query.data.split("_")[-1])
    termo = context.user_data.get('ultimo_termo', '')
    
    await exibir_resultados(update, context, db, termo, pagina)


async def aplicar_filtros(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Exibe menu de filtros"""
    query = update.callback_query
    await query.answer()
    
    with db.get_session() as session:
        categorias = session.query(Categoria).filter_by(ativo=True).all()
    
    texto = """
🎯 *FILTROS DE PESQUISA*

🔹 Selecione um filtro:
"""
    
    keyboard = []
    
    # Filtro por categoria
    for cat in categorias[:8]:
        keyboard.append([
            InlineKeyboardButton(
                f"{cat.emoji or '📂'} {cat.nome}",
                callback_data=f"filtro_cat_{cat.id}"
            )
        ])
    
    # Filtro por preço
    keyboard.append([
        InlineKeyboardButton("💰 Até R$ 20", callback_data="filtro_preco_0_20"),
        InlineKeyboardButton("💰 R$ 20-50", callback_data="filtro_preco_20_50"),
    ])
    keyboard.append([
        InlineKeyboardButton("💰 R$ 50-100", callback_data="filtro_preco_50_100"),
        InlineKeyboardButton("💰 Acima R$ 100", callback_data="filtro_preco_100_0"),
    ])
    
    keyboard.append([InlineKeyboardButton("🔄 LIMPAR FILTROS", callback_data="search_limpar_filtros")])
    keyboard.append([InlineKeyboardButton("🔙 VOLTAR", callback_data="search_voltar")])
    
    await query.edit_message_text(
        text=texto,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
    return EstadosPesquisa.APLICAR_FILTRO


async def filtrar_por_categoria(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Filtra resultados por categoria"""
    query = update.callback_query
    await query.answer()
    
    categoria_id = int(query.data.split("_")[-1])
    
    termo = context.user_data.get('ultimo_termo', '')
    resultados = search_service.pesquisar_produtos(db, termo, categoria_id=categoria_id)
    
    await exibir_resultados_filtrados(update, context, db, resultados, f"Categoria")


async def filtrar_por_preco(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Filtra resultados por faixa de preço"""
    query = update.callback_query
    await query.answer()
    
    partes = query.data.split("_")
    preco_min = float(partes[2]) if partes[2] != '0' else None
    preco_max = float(partes[3]) if partes[3] != '0' else None
    
    termo = context.user_data.get('ultimo_termo', '')
    resultados = search_service.pesquisar_produtos(db, termo, preco_min=preco_min, preco_max=preco_max)
    
    faixa = f"R$ {partes[2]}-{partes[3]}" if partes[3] != '0' else f"Acima R$ {partes[2]}"
    await exibir_resultados_filtrados(update, context, db, resultados, f"Preço: {faixa}")


async def exibir_resultados_filtrados(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database,
                                     resultados: List[Dict], filtro: str):
    """Exibe resultados filtrados"""
    if not resultados:
        await update.callback_query.edit_message_text(
            f"🔍 *Filtro: {filtro}*\n\n"
            "❌ Nenhum resultado encontrado.\n\n"
            "Tente outro filtro ou limpe os filtros.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 LIMPAR FILTROS", callback_data="search_limpar_filtros")],
                [InlineKeyboardButton("🔙 VOLTAR", callback_data="search_voltar")]
            ]),
            parse_mode="Markdown"
        )
        return
    
    texto = f"🔍 *RESULTADOS FILTRADOS - {filtro}*\n\n"
    texto += f"📊 {len(resultados)} produto(s)\n\n"
    
    keyboard = []
    
    for prod in resultados[:10]:
        preco = prod.get('valor_promocional') if prod.get('em_promocao') else prod.get('valor')
        texto += f"📦 *{prod.get('nome', 'N/A')}*\n"
        texto += f"   💰 {formatar_moeda(prod.get('valor', 0))}"
        if prod.get('em_promocao'):
            texto += f" | 🏷️ {formatar_moeda(prod.get('valor_promocional', 0))}"
        texto += f"\n   📦 {prod.get('estoque', 0)} un. | 📂 {prod.get('categoria_nome', '')}\n\n"
        
        keyboard.append([
            InlineKeyboardButton(
                f"🛒 {prod.get('nome', '')}",
                callback_data=f"ver_prod_{prod.get('id', 0)}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 VOLTAR AOS FILTROS", callback_data="search_filtros")])
    keyboard.append([InlineKeyboardButton("🛍️ LOJA COMPLETA", callback_data="menu_loja")])
    
    await update.callback_query.edit_message_text(
        text=texto,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


def registrar_handlers_search(application):
    """Registra handlers de pesquisa"""
    search_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(lambda u, c: iniciar_pesquisa(u, c, None), pattern="^pesquisar$"),
        ],
        states={
            EstadosPesquisa.DIGITAR_TERMO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: receber_pesquisa(u, c, None)),
            ],
            EstadosPesquisa.EXIBIR_RESULTADOS: [
                CallbackQueryHandler(lambda u, c: navegar_pagina_pesquisa(u, c, None), pattern="^search_pag_"),
                CallbackQueryHandler(lambda u, c: aplicar_filtros(u, c, None), pattern="^search_filtros$"),
                CallbackQueryHandler(lambda u, c: iniciar_pesquisa(u, c, None), pattern="^pesquisar$"),
            ],
            EstadosPesquisa.APLICAR_FILTRO: [
                CallbackQueryHandler(lambda u, c: filtrar_por_categoria(u, c, None), pattern="^filtro_cat_"),
                CallbackQueryHandler(lambda u, c: filtrar_por_preco(u, c, None), pattern="^filtro_preco_"),
                CallbackQueryHandler(lambda u, c: iniciar_pesquisa(u, c, None), pattern="^search_limpar_filtros$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(lambda u, c: iniciar_pesquisa(u, c, None), pattern="^menu_loja$"),
        ],
        name="search_conversation",
    )
    
    application.add_handler(search_conv)
    logger.info("✅ Handlers de pesquisa registrados!")


__all__ = [
    'iniciar_pesquisa',
    'receber_pesquisa',
    'exibir_resultados',
    'aplicar_filtros',
    'registrar_handlers_search',
    'SearchService',
]
