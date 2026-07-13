"""
Painel Admin - Atualizações e Transmissões (Broadcast)
Envio de mensagens em massa para usuários
"""
import logging
import asyncio
from datetime import datetime
from typing import List

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler
)
from sqlalchemy import func

from ...config import config
from ...database import Database
from ...database.models import Usuario
from ...utils.keyboards import botao_voltar, botoes_confirmacao
from ...utils.utils import formatar_data, formatar_numero, log_com_contexto
from ...utils.states import EstadosAdminBroadcast
from ...middlewares import somente_admin, log_atividade

logger = logging.getLogger(__name__)


class BroadcastService:
    """Serviço de transmissão em massa"""
    
    def __init__(self, db: Database):
        self.db = db
    
    def get_contagem_usuarios(self, filtro: str = "todos") -> int:
        """Conta usuários por filtro"""
        with self.db.get_session() as session:
            query = session.query(func.count(Usuario.id))
            
            if filtro == "com_saldo":
                query = query.filter(Usuario.saldo > 0)
            elif filtro == "sem_saldo":
                query = query.filter(Usuario.saldo <= 0)
            elif filtro == "afiliados":
                query = query.filter(Usuario.total_indicacoes > 0)
            elif filtro == "admins":
                query = query.filter_by(is_admin=True)
            
            return query.scalar() or 0
    
    def get_usuarios_para_broadcast(self, filtro: str = "todos") -> List[int]:
        """Retorna IDs dos usuários para broadcast"""
        with self.db.get_session() as session:
            query = session.query(Usuario.telegram_id)
            
            if filtro == "com_saldo":
                query = query.filter(Usuario.saldo > 0)
            elif filtro == "sem_saldo":
                query = query.filter(Usuario.saldo <= 0)
            elif filtro == "afiliados":
                query = query.filter(Usuario.total_indicacoes > 0)
            elif filtro == "admins":
                query = query.filter_by(is_admin=True)
            
            return [u[0] for u in query.all()]


broadcast_service = None

def init_service(db: Database):
    global broadcast_service
    broadcast_service = BroadcastService(db)


@somente_admin
@log_atividade("admin_menu_broadcast")
async def menu_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Menu de transmissão"""
    init_service(db)
    query = update.callback_query
    await query.answer()
    
    contagem = {
        'todos': broadcast_service.get_contagem_usuarios('todos'),
        'com_saldo': broadcast_service.get_contagem_usuarios('com_saldo'),
        'afiliados': broadcast_service.get_contagem_usuarios('afiliados'),
        'admins': broadcast_service.get_contagem_usuarios('admins'),
    }
    
    texto = f"""
📢 *TRANSMISSÃO EM MASSA*

👥 *Usuários:*
• Todos: {formatar_numero(contagem['todos'])}
• Com saldo: {formatar_numero(contagem['com_saldo'])}
• Afiliados: {formatar_numero(contagem['afiliados'])}
• Admins: {formatar_numero(contagem['admins'])}

🔹 *Enviar mensagem para:*
"""
    
    keyboard = [
        [InlineKeyboardButton(f"👥 TODOS ({contagem['todos']})", callback_data="broadcast_todos")],
        [InlineKeyboardButton(f"💰 COM SALDO ({contagem['com_saldo']})", callback_data="broadcast_com_saldo")],
        [InlineKeyboardButton(f"🤝 AFILIADOS ({contagem['afiliados']})", callback_data="broadcast_afiliados")],
        [InlineKeyboardButton(f"🛡️ ADMINS ({contagem['admins']})", callback_data="broadcast_admins")],
        [InlineKeyboardButton("🔙 VOLTAR", callback_data="admin_menu")]
    ]
    
    await query.edit_message_text(
        text=texto,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
    return EstadosAdminBroadcast.INICIAR_BROADCAST


@somente_admin
async def broadcast_selecionar_publico(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Seleciona público e solicita mensagem"""
    query = update.callback_query
    await query.answer()
    
    filtro = query.data.split("_")[-1]
    context.user_data['broadcast_filtro'] = filtro
    
    total = broadcast_service.get_contagem_usuarios(filtro)
    context.user_data['broadcast_total'] = total
    
    await query.edit_message_text(
        f"📢 *NOVA TRANSMISSÃO*\n\n"
        f"👥 Público: {filtro.upper().replace('_', ' ')} ({formatar_numero(total)})\n\n"
        "✏️ *Digite a mensagem:*\n\n"
        "💡 Dicas:\n"
        "• Use Markdown para formatar\n"
        "• Envie /cancel para cancelar",
        reply_markup=botao_voltar("admin_menu"),
        parse_mode="Markdown"
    )
    
    return EstadosAdminBroadcast.DIGITAR_TEXTO


@somente_admin
async def broadcast_receber_mensagem(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Recebe mensagem e mostra preview"""
    mensagem = update.message.text
    
    if mensagem == "/cancel":
        await update.message.reply_text("❌ Transmissão cancelada.", reply_markup=botao_voltar("admin_menu"))
        return ConversationHandler.END
    
    context.user_data['broadcast_mensagem'] = mensagem
    
    filtro = context.user_data.get('broadcast_filtro', 'todos')
    total = context.user_data.get('broadcast_total', 0)
    
    texto = f"""
📢 *PRÉ-VISUALIZAÇÃO*

👥 *Público:* {filtro.upper().replace('_', ' ')}
👤 *Total:* {formatar_numero(total)}

📝 *Mensagem:*
{mensagem[:500]}{'...' if len(mensagem) > 500 else ''}

⚠️ Esta mensagem será enviada para {formatar_numero(total)} usuários!

🔹 Confirmar envio?
"""
    
    keyboard = [
        [
            InlineKeyboardButton("✅ ENVIAR", callback_data="broadcast_confirmar"),
            InlineKeyboardButton("❌ CANCELAR", callback_data="admin_menu")
        ]
    ]
    
    await update.message.reply_text(
        text=texto,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
    return EstadosAdminBroadcast.CONFIRMAR_ENVIO_BROADCAST


@somente_admin
@log_atividade("admin_broadcast_enviar")
async def broadcast_executar(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Executa transmissão"""
    query = update.callback_query
    await query.answer()
    
    filtro = context.user_data.get('broadcast_filtro', 'todos')
    mensagem = context.user_data.get('broadcast_mensagem', '')
    
    await query.edit_message_text("📢 *Enviando mensagens...*\n\n⏳ Aguarde...", parse_mode="Markdown")
    
    usuarios = broadcast_service.get_usuarios_para_broadcast(filtro)
    
    enviados = 0
    falhas = 0
    
    for user_id in usuarios:
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"📢 *AVISO IMPORTANTE*\n\n{mensagem}",
                parse_mode="Markdown"
            )
            enviados += 1
            await asyncio.sleep(0.05)  # Evita flood
        except Exception as e:
            falhas += 1
            logger.debug(f"Falha ao enviar para {user_id}: {e}")
    
    texto = f"""
✅ *TRANSMISSÃO CONCLUÍDA!*

📊 *Resultado:*
• ✅ Enviados: {formatar_numero(enviados)}
• ❌ Falhas: {formatar_numero(falhas)}
• 👥 Total: {formatar_numero(len(usuarios))}

📅 *Data:* {formatar_data(datetime.now())}
"""
    
    await query.edit_message_text(
        text=texto,
        reply_markup=botao_voltar("admin_menu"),
        parse_mode="Markdown"
    )
    
    log_com_contexto("Broadcast enviado", filtro=filtro, enviados=enviados, falhas=falhas)
    
    return ConversationHandler.END


def registrar_handlers_admin_updates(application):
    """Registra handlers de transmissão"""
    
    broadcast_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(lambda u, c: menu_broadcast(u, c, None), pattern="^admin_atualizacoes$"),
        ],
        states={
            EstadosAdminBroadcast.INICIAR_BROADCAST: [
                CallbackQueryHandler(lambda u, c: broadcast_selecionar_publico(u, c, None), pattern="^broadcast_"),
            ],
            EstadosAdminBroadcast.DIGITAR_TEXTO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: broadcast_receber_mensagem(u, c, None)),
            ],
            EstadosAdminBroadcast.CONFIRMAR_ENVIO_BROADCAST: [
                CallbackQueryHandler(lambda u, c: broadcast_executar(u, c, None), pattern="^broadcast_confirmar$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(lambda u, c: menu_broadcast(u, c, None), pattern="^admin_menu$"),
        ],
        name="broadcast_conversation",
    )
    
    application.add_handler(broadcast_conv)
    logger.info("✅ Handlers de transmissão registrados!")


__all__ = [
    'menu_broadcast',
    'broadcast_selecionar_publico',
    'broadcast_receber_mensagem',
    'broadcast_executar',
    'registrar_handlers_admin_updates',
]
