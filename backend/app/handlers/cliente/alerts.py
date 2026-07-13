"""
Módulo do Cliente - Sistema de Alertas de Reposição de Estoque
Notifica usuários quando produtos voltam ao estoque
"""
import logging
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from ...config import config
from ...database import Database
from ...database.models import Produto, AlertaProduto
from ...services.products import AlertaService, ProdutoService
from ...utils.keyboards import botao_voltar, botoes_confirmacao
from ...utils.utils import formatar_data, log_com_contexto
from ...middlewares import somente_chat_privado

logger = logging.getLogger(__name__)


async def cmd_alertas(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Comando /alertas - Lista alertas ativos do usuário"""
    user_id = update.effective_user.id
    
    alerta_service = AlertaService(db)
    produto_service = ProdutoService(db)
    
    with db.get_session() as session:
        alertas = session.query(AlertaProduto).filter_by(
            usuario_id=user_id, ativo=True
        ).all()
    
    if not alertas:
        texto = """
🔔 *SEUS ALERTAS*

⚠️ Você não tem alertas ativos.

💡 *Como ativar:*
Quando um produto estiver sem estoque,
clique em 🔔 ATIVAR ALERTA para ser notificado
quando ele voltar!
"""
        keyboard = [[InlineKeyboardButton("🛍️ IR PARA LOJA", callback_data="menu_loja")]]
        
        await update.message.reply_text(
            text=texto,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        return
    
    texto = "🔔 *SEUS ALERTAS ATIVOS*\n\n"
    texto += f"📊 *Total:* {len(alertas)} alerta(s)\n\n"
    
    keyboard = []
    
    for alerta in alertas:
        produto = session.query(Produto).get(alerta.produto_id) if not alerta.produto else alerta.produto
        
        if produto:
            status = "🟢 Disponível" if produto.estoque > 0 else "🔴 Esgotado"
            texto += f"📦 *{produto.nome}*\n"
            texto += f"   💰 {config.formatar_moeda(produto.valor) if hasattr(config, 'formatar_moeda') else f'R$ {produto.valor:.2f}'}\n"
            texto += f"   📊 Status: {status}\n"
            texto += f"   📅 Ativado em: {formatar_data(alerta.data_criacao, 'dd/mm/aaaa')}\n\n"
            
            keyboard.append([
                InlineKeyboardButton(
                    f"🔕 Desativar - {produto.nome[:25]}",
                    callback_data=f"desativar_alerta_{alerta.id}"
                )
            ])
    
    keyboard.append([InlineKeyboardButton("🔕 DESATIVAR TODOS", callback_data="desativar_todos_alertas")])
    keyboard.append([InlineKeyboardButton("🔙 VOLTAR", callback_data="menu_perfil")])
    
    await update.message.reply_text(
        text=texto,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def ativar_alerta(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Ativa alerta para um produto"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    produto_id = int(query.data.split("_")[-1])
    
    alerta_service = AlertaService(db)
    produto_service = ProdutoService(db)
    
    produto = produto_service.buscar_por_id(produto_id)
    
    if not produto:
        await query.edit_message_text(
            "❌ Produto não encontrado.",
            reply_markup=botao_voltar("menu_loja")
        )
        return
    
    sucesso = alerta_service.ativar_alerta(user_id, produto_id)
    
    if sucesso:
        texto = f"""
🔔 *ALERTA ATIVADO!*

📦 *Produto:* {produto.nome}
💰 *Valor:* {produto.valor if hasattr(produto, 'valor') else 'N/A'}

✅ Você será notificado quando este produto
voltar ao estoque!

📋 Use /alertas para ver seus alertas ativos.
"""
    else:
        texto = "❌ Erro ao ativar alerta. Tente novamente."
    
    keyboard = [[InlineKeyboardButton("🔙 VOLTAR", callback_data=f"ver_prod_{produto_id}")]]
    
    await query.edit_message_text(
        text=texto,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
    log_com_contexto("Alerta ativado", user_id=user_id, produto_id=produto_id)


async def desativar_alerta(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Desativa um alerta específico"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    alerta_id = int(query.data.split("_")[-1])
    
    alerta_service = AlertaService(db)
    
    with db.get_session() as session:
        alerta = session.query(AlertaProduto).get(alerta_id)
        
        if alerta and alerta.usuario_id == user_id:
            alerta.ativo = False
            session.flush()
            
            await query.edit_message_text(
                "✅ Alerta desativado com sucesso!\n"
                "Use /alertas para ver seus alertas.",
                reply_markup=botao_voltar("menu_perfil")
            )
        else:
            await query.edit_message_text(
                "❌ Alerta não encontrado.",
                reply_markup=botao_voltar("menu_perfil")
            )


async def desativar_todos_alertas(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Desativa todos os alertas do usuário"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    with db.get_session() as session:
        alertas = session.query(AlertaProduto).filter_by(
            usuario_id=user_id, ativo=True
        ).all()
        
        for alerta in alertas:
            alerta.ativo = False
        
        session.flush()
    
    await query.edit_message_text(
        f"✅ *{len(alertas)} alerta(s) desativado(s)!*\n\n"
        "Você não receberá mais notificações.",
        reply_markup=botao_voltar("menu_perfil"),
        parse_mode="Markdown"
    )
    
    log_com_contexto("Todos alertas desativados", user_id=user_id)


async def notificar_usuarios_estoque(db: Database, produto_id: int, bot):
    """Notifica usuários com alerta ativo quando produto é reabastecido"""
    alerta_service = AlertaService(db)
    produto_service = ProdutoService(db)
    
    produto = produto_service.buscar_por_id(produto_id)
    
    if not produto or produto.estoque <= 0:
        return 0
    
    usuarios = alerta_service.get_usuarios_para_notificar(produto_id)
    
    if not usuarios:
        return 0
    
    notificados = 0
    
    for user_id in usuarios:
        try:
            texto = f"""
🔔 *PRODUTO DISPONÍVEL!*

📦 *{produto.nome}* voltou ao estoque!

💰 *Valor:* {produto.valor if hasattr(produto, 'valor') else 'N/A'}
📊 *Estoque:* {produto.estoque} un.

⚡ Corra e garanta o seu antes que acabe!
"""
            keyboard = [
                [InlineKeyboardButton("🛒 COMPRAR AGORA", callback_data=f"comprar_{produto_id}")],
                [InlineKeyboardButton("🔕 DESATIVAR ALERTA", callback_data=f"desativar_alerta_prod_{produto_id}")]
            ]
            
            await bot.send_message(
                chat_id=user_id,
                text=texto,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
            notificados += 1
            
        except Exception as e:
            logger.error(f"Erro ao notificar usuário {user_id}: {e}")
    
    alerta_service.marcar_como_notificados(produto_id, usuarios)
    
    logger.info(f"✅ {notificados} usuários notificados sobre produto {produto_id}")
    return notificados


def registrar_handlers_alerts(application):
    """Registra handlers de alertas"""
    application.add_handler(CommandHandler("alertas", lambda u, c: cmd_alertas(u, c, None)))
    application.add_handler(CallbackQueryHandler(lambda u, c: ativar_alerta(u, c, None), pattern="^alerta_"))
    application.add_handler(CallbackQueryHandler(lambda u, c: desativar_alerta(u, c, None), pattern="^desativar_alerta_"))
    application.add_handler(CallbackQueryHandler(lambda u, c: desativar_todos_alertas(u, c, None), pattern="^desativar_todos_alertas$"))
    logger.info("✅ Handlers de alertas registrados!")


__all__ = [
    'cmd_alertas',
    'ativar_alerta',
    'desativar_alerta',
    'desativar_todos_alertas',
    'notificar_usuarios_estoque',
    'registrar_handlers_alerts',
]
