"""
Módulo do Cliente - Suporte e Informações
Sistema de tickets, FAQ, termos e contato
"""
import logging
from datetime import datetime
from typing import List, Dict, Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler
)

from ...config import config
from ...database import Database
from ...database.models import Usuario
from ...utils.keyboards import menu_info, botao_voltar, botoes_confirmacao
from ...utils.utils import formatar_data, log_com_contexto
from ...utils.states import EstadosSuporte
from ...middlewares import somente_chat_privado

logger = logging.getLogger(__name__)


class SuporteService:
    """Serviço de suporte e informações"""
    
    FAQ = [
        {
            'pergunta': 'Como faço uma recarga?',
            'resposta': 'Use o comando /pix ou clique em 💳 RECARGA no menu principal. Escolha o valor e pague o QR Code gerado.'
        },
        {
            'pergunta': 'Como comprar um produto?',
            'resposta': 'Acesse a loja pelo menu principal, escolha a categoria, selecione o produto e clique em COMPRAR.'
        },
        {
            'pergunta': 'Qual o prazo de entrega?',
            'resposta': 'A entrega é instantânea! Após a confirmação do pagamento, você recebe os dados de acesso na hora.'
        },
        {
            'pergunta': 'Quanto tempo dura a garantia?',
            'resposta': 'Cada produto tem sua garantia especificada na descrição. Geralmente 7 dias.'
        },
        {
            'pergunta': 'Como funciona o sistema de afiliados?',
            'resposta': 'Compartilhe seu link de afiliado. Você ganha comissão sobre cada compra/recarga de seus indicados.'
        },
        {
            'pergunta': 'Posso pedir reembolso?',
            'resposta': 'Sim, dentro do prazo de garantia do produto. Acesse seu histórico de compras e clique em Reportar Problema.'
        },
        {
            'pergunta': 'Como ativar alertas de estoque?',
            'resposta': 'Quando um produto estiver sem estoque, clique em 🔔 ATIVAR ALERTA. Você será notificado quando reabastecermos.'
        },
        {
            'pergunta': 'O bot é seguro?',
            'resposta': 'Sim! Seus dados são criptografados e não compartilhamos informações com terceiros.'
        },
    ]


suporte_service = SuporteService()


async def mostrar_menu_info(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Exibe menu de informações"""
    texto = f"""
ℹ️ *INFORMAÇÕES E SUPORTE*

🤖 *{config.NOME_BOT}* v{config.VERSAO}

🔹 *Opções disponíveis:*

📖 Termos de Uso
ℹ️ Sobre o Bot
❓ Perguntas Frequentes (FAQ)
📞 Contato com Suporte
🔍 Pesquisar Serviços

🔹 Selecione uma opção:
"""
    
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            text=texto,
            reply_markup=menu_info(),
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            text=texto,
            reply_markup=menu_info(),
            parse_mode="Markdown"
        )


async def mostrar_termos(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Exibe link dos termos de uso"""
    query = update.callback_query
    await query.answer()
    
    texto = f"""
📖 *TERMOS DE USO*

🔗 Acesse os termos completos:
{config.TERMOS_USO_LINK or 'https://telegra.ph/Termos-de-Uso'}

⚠️ Ao usar este bot, você concorda com os termos.

📋 *Resumo:*
• Não nos responsabilizamos por mau uso
• Reembolsos apenas dentro da garantia
• Contas compartilhadas podem ser banidas
• Proibido revenda sem autorização
"""
    
    keyboard = [[InlineKeyboardButton("🔙 VOLTAR", callback_data="menu_info")]]
    
    await query.edit_message_text(
        text=texto,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
        disable_web_page_preview=True
    )


async def mostrar_sobre(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Exibe informações sobre o bot"""
    query = update.callback_query
    await query.answer()
    
    texto = f"""
ℹ️ *SOBRE O BOT*

🤖 *Nome:* {config.NOME_BOT}
📦 *Versão:* {config.VERSAO}

🛠️ *Funcionalidades:*
• Venda automática de contas
• Recarga via Pix
• Sistema de afiliados
• Ranking de usuários
• Histórico de compras
• Alertas de estoque

👨‍💻 *Desenvolvido para automação completa*

📞 *Suporte:* {config.GRUPO_SUPORTE_LINK or 'Contate um admin'}
"""
    
    keyboard = [[InlineKeyboardButton("🔙 VOLTAR", callback_data="menu_info")]]
    
    await query.edit_message_text(
        text=texto,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def mostrar_faq(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Exibe perguntas frequentes"""
    query = update.callback_query
    
    pagina = context.user_data.get('faq_pagina', 0)
    
    if query.data == "faq":
        await query.answer()
        pagina = 0
    elif query.data == "faq_prox":
        await query.answer()
        pagina += 1
    elif query.data == "faq_ant":
        await query.answer()
        pagina = max(0, pagina - 1)
    else:
        await query.answer()
    
    context.user_data['faq_pagina'] = pagina
    
    total_paginas = (len(suporte_service.FAQ) + 3) // 4
    inicio = pagina * 4
    fim = inicio + 4
    faqs_pagina = suporte_service.FAQ[inicio:fim]
    
    texto = "❓ *PERGUNTAS FREQUENTES (FAQ)*\n\n"
    
    for i, faq in enumerate(faqs_pagina, 1):
        texto += f"*{inicio + i}. {faq['pergunta']}*\n"
        texto += f"💬 {faq['resposta']}\n\n"
    
    texto += f"📄 Página {pagina + 1}/{total_paginas}"
    
    keyboard = []
    
    nav_botoes = []
    if pagina > 0:
        nav_botoes.append(InlineKeyboardButton("⬅️ ANTERIOR", callback_data="faq_ant"))
    if pagina < total_paginas - 1:
        nav_botoes.append(InlineKeyboardButton("PRÓXIMA ➡️", callback_data="faq_prox"))
    if nav_botoes:
        keyboard.append(nav_botoes)
    
    keyboard.append([InlineKeyboardButton("🔙 VOLTAR", callback_data="menu_info")])
    
    await query.edit_message_text(
        text=texto,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def contatar_suporte(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Redireciona para suporte"""
    query = update.callback_query
    await query.answer()
    
    texto = f"""
📞 *SUPORTE*

🔹 *Opções de contato:*

• Grupo de Suporte
• Chamar Administrador

📱 *Link direto:*
{config.GRUPO_SUPORTE_LINK or 'Entre em contato com @admin'}

⏰ *Horário de atendimento:*
Seg a Sáb - 09h às 21h

⚠️ *Antes de chamar:*
• Verifique o FAQ
• Tenha seu ID em mãos
• Descreva bem o problema
"""
    
    keyboard = [
        [InlineKeyboardButton("📱 GRUPO DE SUPORTE", url=config.GRUPO_SUPORTE_LINK or "https://t.me/suporte")],
        [InlineKeyboardButton("📝 ABRIR TICKET", callback_data="abrir_ticket")],
        [InlineKeyboardButton("🔙 VOLTAR", callback_data="menu_info")]
    ]
    
    await query.edit_message_text(
        text=texto,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def pesquisar_servicos(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Sistema de pesquisa de produtos"""
    query = update.callback_query
    
    if query and query.data == "pesquisar":
        await query.answer()
        await query.edit_message_text(
            "🔍 *PESQUISAR SERVIÇOS*\n\n"
            "✏️ Digite o nome do produto que você procura:\n\n"
            "Exemplo: Netflix, Spotify, Prime...",
            reply_markup=botao_voltar("menu_loja"),
            parse_mode="Markdown"
        )
        return EstadosPesquisa.DIGITAR_TERMO
    
    return await mostrar_menu_info(update, context, db)


async def receber_termo_pesquisa(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Recebe termo de pesquisa e mostra resultados"""
    termo = update.message.text.strip()
    
    if not termo or len(termo) < 2:
        await update.message.reply_text(
            "❌ Digite pelo menos 2 caracteres para pesquisar.",
            reply_markup=botao_voltar("menu_loja")
        )
        return EstadosPesquisa.DIGITAR_TERMO
    
    from ...services.products import ProdutoService
    produto_service = ProdutoService(db)
    
    resultados = produto_service.buscar_por_nome(termo)
    
    if not resultados:
        await update.message.reply_text(
            f"🔍 *Nenhum resultado para:* `{termo}`\n\n"
            "Tente outro termo ou volte para a loja.",
            reply_markup=botao_voltar("menu_loja"),
            parse_mode="Markdown"
        )
        return ConversationHandler.END
    
    texto = f"🔍 *RESULTADOS PARA:* `{termo}`\n\n"
    texto += f"📊 {len(resultados)} produto(s) encontrado(s):\n\n"
    
    keyboard = []
    
    for prod in resultados[:10]:
        estoque_emoji = "✅" if prod.estoque > 0 else "❌"
        texto += f"{estoque_emoji} *{prod.nome}*\n"
        texto += f"   💰 {formatar_moeda(prod.valor)} | 📦 {prod.estoque} un.\n"
        texto += f"   📂 {prod.categoria.nome if prod.categoria else 'N/A'}\n\n"
        
        if prod.estoque > 0:
            keyboard.append([
                InlineKeyboardButton(
                    f"🛒 {prod.nome} - {formatar_moeda(prod.valor)}",
                    callback_data=f"ver_prod_{prod.id}"
                )
            ])
    
    keyboard.append([InlineKeyboardButton("🔙 VOLTAR PARA LOJA", callback_data="menu_loja")])
    
    await update.message.reply_text(
        text=texto,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
    return ConversationHandler.END


def registrar_handlers_support(application):
    """Registra handlers de suporte"""
    application.add_handler(CommandHandler("termos", lambda u, c: mostrar_termos(u, c, None)))
    application.add_handler(CommandHandler("faq", lambda u, c: mostrar_faq(u, c, None)))
    application.add_handler(CommandHandler("suporte", lambda u, c: contatar_suporte(u, c, None)))
    
    application.add_handler(CallbackQueryHandler(lambda u, c: mostrar_menu_info(u, c, None), pattern="^menu_info$"))
    application.add_handler(CallbackQueryHandler(lambda u, c: mostrar_termos(u, c, None), pattern="^termos$"))
    application.add_handler(CallbackQueryHandler(lambda u, c: mostrar_sobre(u, c, None), pattern="^sobre_bot$"))
    application.add_handler(CallbackQueryHandler(lambda u, c: mostrar_faq(u, c, None), pattern="^faq$"))
    application.add_handler(CallbackQueryHandler(lambda u, c: mostrar_faq(u, c, None), pattern="^faq_prox$"))
    application.add_handler(CallbackQueryHandler(lambda u, c: mostrar_faq(u, c, None), pattern="^faq_ant$"))
    application.add_handler(CallbackQueryHandler(lambda u, c: contatar_suporte(u, c, None), pattern="^contato_suporte$"))
    application.add_handler(CallbackQueryHandler(lambda u, c: pesquisar_servicos(u, c, None), pattern="^pesquisar$"))
    
    logger.info("✅ Handlers de suporte registrados!")


from ...utils.utils import formatar_moeda
from ...utils.states import EstadosPesquisa

__all__ = [
    'mostrar_menu_info',
    'mostrar_termos',
    'mostrar_sobre',
    'mostrar_faq',
    'contatar_suporte',
    'pesquisar_servicos',
    'receber_termo_pesquisa',
    'registrar_handlers_support',
]
