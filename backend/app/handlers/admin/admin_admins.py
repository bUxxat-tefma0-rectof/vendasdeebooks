"""
Painel Admin - Gerenciamento de Administradores
Adicionar, remover, listar e configurar permissões
"""
import logging
from datetime import datetime
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
from ...database.models import Usuario
from ...utils.keyboards import botao_voltar, botoes_confirmacao, botoes_paginacao
from ...utils.utils import formatar_data, formatar_numero, log_com_contexto
from ...utils.states import EstadosAdmin
from ...middlewares import somente_admin, log_atividade

logger = logging.getLogger(__name__)


class AdminManagerService:
    """Serviço de gerenciamento de administradores"""
    
    def __init__(self, db: Database):
        self.db = db
    
    def listar_admins(self) -> List[Dict]:
        """Lista todos os administradores"""
        with self.db.get_session() as session:
            admins = session.query(Usuario).filter_by(is_admin=True, is_banido=False).all()
            
            return [
                {
                    'id': a.telegram_id,
                    'nome': a.nome or f"@{a.username}" or f"ID:{a.telegram_id}",
                    'username': a.username or 'N/A',
                    'data_registro': formatar_data(a.data_registro, "dd/mm/aaaa"),
                    'saldo': float(a.saldo)
                }
                for a in admins
            ]
    
    def adicionar_admin(self, user_id: int) -> bool:
        """Adiciona um novo administrador"""
        with self.db.get_session() as session:
            usuario = session.query(Usuario).filter_by(telegram_id=user_id).first()
            
            if not usuario:
                return False
            
            if usuario.is_admin:
                return False
            
            usuario.is_admin = True
            session.flush()
            
            if user_id not in config.ADMIN_IDS:
                config.ADMIN_IDS.append(user_id)
            
            log_com_contexto("Admin adicionado", user_id=user_id)
            return True
    
    def remover_admin(self, user_id: int) -> bool:
        """Remove um administrador"""
        with self.db.get_session() as session:
            usuario = session.query(Usuario).filter_by(telegram_id=user_id).first()
            
            if not usuario:
                return False
            
            if not usuario.is_admin:
                return False
            
            usuario.is_admin = False
            session.flush()
            
            if user_id in config.ADMIN_IDS:
                config.ADMIN_IDS.remove(user_id)
            
            log_com_contexto("Admin removido", user_id=user_id)
            return True
    
    def is_admin(self, user_id: int) -> bool:
        """Verifica se usuário é admin"""
        with self.db.get_session() as session:
            usuario = session.query(Usuario).filter_by(telegram_id=user_id).first()
            return usuario.is_admin if usuario else False


admin_manager = None

def init_admin_manager(db: Database):
    global admin_manager
    admin_manager = AdminManagerService(db)


@somente_admin
@log_atividade("admin_gerenciar_admins")
async def menu_gerenciar_admins(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Exibe menu de gerenciamento de administradores"""
    init_admin_manager(db)
    query = update.callback_query
    await query.answer()
    
    admins = admin_manager.listar_admins()
    
    texto = f"""
🛡️ *GERENCIAR ADMINISTRADORES*

📊 *Total de admins:* {formatar_numero(len(admins))}

👑 *Administradores atuais:*
"""
    
    for i, admin in enumerate(admins, 1):
        texto += f"""
*{i}.* {admin['nome']}
   🆔 ID: `{admin['id']}`
   📱 @{admin['username']}
   📅 Desde: {admin['data_registro']}
"""
    
    texto += "\n🔹 *Opções:*"
    
    keyboard = [
        [InlineKeyboardButton("➕ ADICIONAR ADMIN", callback_data="admin_add_admin")],
        [InlineKeyboardButton("➖ REMOVER ADMIN", callback_data="admin_remove_admin")],
        [InlineKeyboardButton("📋 LISTAR ADMINS", callback_data="admin_listar_admins")],
        [InlineKeyboardButton("🔙 VOLTAR", callback_data="admin_config")]
    ]
    
    await query.edit_message_text(
        text=texto,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
    return EstadosAdmin.MENU_ADMIN


@somente_admin
async def adicionar_admin_inicio(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Solicita ID do novo admin"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "➕ *ADICIONAR ADMINISTRADOR*\n\n"
        "✏️ *Digite o ID do Telegram do novo admin:*\n\n"
        "💡 *Como encontrar o ID:*\n"
        "• O usuário usa /id no bot\n"
        "• Ou envia uma mensagem e o ID aparece\n\n"
        "📝 Digite o ID numérico:",
        reply_markup=botao_voltar("admin_gerenciar_admins"),
        parse_mode="Markdown"
    )
    
    return EstadosAdmin.ADD_ADMIN


@somente_admin
async def adicionar_admin_confirmar(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Confirma e adiciona novo admin"""
    try:
        user_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text(
            "❌ ID inválido. Digite apenas números.",
            reply_markup=botao_voltar("admin_gerenciar_admins")
        )
        return EstadosAdmin.ADD_ADMIN
    
    # Busca usuário no banco
    db_user = db.get_user(user_id)
    
    if not db_user:
        await update.message.reply_text(
            f"❌ Usuário com ID `{user_id}` não encontrado no bot.\n\n"
            "O usuário precisa iniciar o bot primeiro usando /start.",
            reply_markup=botao_voltar("admin_gerenciar_admins"),
            parse_mode="Markdown"
        )
        return EstadosAdmin.ADD_ADMIN
    
    if db_user.is_admin:
        await update.message.reply_text(
            f"❌ Usuário {db_user.nome or user_id} já é administrador.",
            reply_markup=botao_voltar("admin_gerenciar_admins")
        )
        return EstadosAdmin.ADD_ADMIN
    
    if db_user.is_banido:
        await update.message.reply_text(
            f"❌ Usuário {db_user.nome or user_id} está banido.",
            reply_markup=botao_voltar("admin_gerenciar_admins")
        )
        return EstadosAdmin.ADD_ADMIN
    
    # Armazena para confirmação
    context.user_data['admin_to_add'] = user_id
    context.user_data['admin_nome'] = db_user.nome or f"@{db_user.username}" or str(user_id)
    
    texto = f"""
➕ *CONFIRMAR ADIÇÃO DE ADMIN*

👤 *Usuário:* {context.user_data['admin_nome']}
🆔 *ID:* `{user_id}`

⚠️ *Este usuário terá acesso total ao painel admin!*

🔹 Confirmar?
"""
    
    keyboard = [
        [
            InlineKeyboardButton("✅ SIM, ADICIONAR", callback_data="confirmar_add_admin"),
            InlineKeyboardButton("❌ CANCELAR", callback_data="admin_gerenciar_admins")
        ]
    ]
    
    await update.message.reply_text(
        text=texto,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
    return EstadosAdmin.CONFIRMAR_ADMIN


@somente_admin
@log_atividade("admin_adicionar_admin")
async def adicionar_admin_executar(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Executa adição do admin"""
    query = update.callback_query
    await query.answer()
    
    user_id = context.user_data.get('admin_to_add')
    nome = context.user_data.get('admin_nome', 'Usuário')
    
    if not user_id:
        await query.edit_message_text(
            "❌ Dados expirados. Tente novamente.",
            reply_markup=botao_voltar("admin_gerenciar_admins")
        )
        return ConversationHandler.END
    
    sucesso = admin_manager.adicionar_admin(user_id)
    
    if sucesso:
        texto = f"""
✅ *ADMIN ADICIONADO COM SUCESSO!*

👤 *Usuário:* {nome}
🆔 *ID:* `{user_id}`

🔹 O usuário agora tem acesso ao painel /admin
"""
        # Notifica o novo admin
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="🎉 *Parabéns! Você foi promovido a Administrador!*\n\n"
                     "Use /admin para acessar o painel de controle.",
                parse_mode="Markdown"
            )
        except:
            pass
    else:
        texto = "❌ Erro ao adicionar administrador."
    
    keyboard = [[InlineKeyboardButton("🔙 VOLTAR", callback_data="admin_gerenciar_admins")]]
    
    await query.edit_message_text(
        text=texto,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
    context.user_data.pop('admin_to_add', None)
    context.user_data.pop('admin_nome', None)
    
    return ConversationHandler.END


@somente_admin
async def remover_admin_inicio(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Lista admins para remoção"""
    query = update.callback_query
    await query.answer()
    
    admins = admin_manager.listar_admins()
    
    if not admins:
        await query.edit_message_text(
            "❌ Nenhum administrador cadastrado.",
            reply_markup=botao_voltar("admin_gerenciar_admins")
        )
        return EstadosAdmin.MENU_ADMIN
    
    user_id_atual = query.from_user.id
    
    texto = """
➖ *REMOVER ADMINISTRADOR*

🔹 *Selecione o admin a remover:*
"""
    
    keyboard = []
    
    for admin in admins:
        if admin['id'] == user_id_atual:
            texto += f"\n👑 *{admin['nome']}* (você) - Não pode remover"
            continue
        
        keyboard.append([
            InlineKeyboardButton(
                f"➖ {admin['nome']} (ID: {admin['id']})",
                callback_data=f"remover_admin_{admin['id']}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 VOLTAR", callback_data="admin_gerenciar_admins")])
    
    await query.edit_message_text(
        text=texto,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
    return EstadosAdmin.REMOVER_ADMIN


@somente_admin
async def remover_admin_confirmar(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Confirma remoção de admin"""
    query = update.callback_query
    await query.answer()
    
    user_id = int(query.data.split("_")[-1])
    
    db_user = db.get_user(user_id)
    
    if not db_user:
        await query.edit_message_text(
            "❌ Usuário não encontrado.",
            reply_markup=botao_voltar("admin_gerenciar_admins")
        )
        return ConversationHandler.END
    
    context.user_data['admin_to_remove'] = user_id
    
    texto = f"""
⚠️ *CONFIRMAR REMOÇÃO DE ADMIN*

👤 *Usuário:* {db_user.nome or f'@{db_user.username}' or user_id}
🆔 *ID:* `{user_id}`

⚠️ O usuário perderá acesso ao painel admin.

🔹 Confirmar?
"""
    
    keyboard = [
        [
            InlineKeyboardButton("✅ SIM, REMOVER", callback_data="confirmar_remover_admin"),
            InlineKeyboardButton("❌ CANCELAR", callback_data="admin_gerenciar_admins")
        ]
    ]
    
    await query.edit_message_text(
        text=texto,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
    return EstadosAdmin.CONFIRMAR_REMOVER


@somente_admin
@log_atividade("admin_remover_admin")
async def remover_admin_executar(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Executa remoção do admin"""
    query = update.callback_query
    await query.answer()
    
    user_id = context.user_data.get('admin_to_remove')
    
    if not user_id:
        await query.edit_message_text(
            "❌ Dados expirados.",
            reply_markup=botao_voltar("admin_gerenciar_admins")
        )
        return ConversationHandler.END
    
    if user_id == query.from_user.id:
        await query.edit_message_text(
            "❌ Você não pode remover a si mesmo.",
            reply_markup=botao_voltar("admin_gerenciar_admins")
        )
        return ConversationHandler.END
    
    sucesso = admin_manager.remover_admin(user_id)
    
    if sucesso:
        texto = f"""
✅ *ADMIN REMOVIDO COM SUCESSO!*

🆔 *ID:* `{user_id}`

🔹 O usuário não tem mais acesso ao painel admin.
"""
        # Notifica o admin removido
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="ℹ️ Seu acesso ao painel administrativo foi removido."
            )
        except:
            pass
    else:
        texto = "❌ Erro ao remover administrador."
    
    keyboard = [[InlineKeyboardButton("🔙 VOLTAR", callback_data="admin_gerenciar_admins")]]
    
    await query.edit_message_text(
        text=texto,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
    context.user_data.pop('admin_to_remove', None)
    
    return ConversationHandler.END


@somente_admin
async def listar_admins_detalhado(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Lista admins com detalhes"""
    query = update.callback_query
    await query.answer()
    
    admins = admin_manager.listar_admins()
    
    texto = f"""
🛡️ *LISTA DE ADMINISTRADORES*

📊 *Total:* {formatar_numero(len(admins))}

"""
    
    for i, admin in enumerate(admins, 1):
        coroa = "👑" if i == 1 else "⭐"
        texto += f"{coroa} *{admin['nome']}*\n"
        texto += f"   🆔 `{admin['id']}`\n"
        texto += f"   📱 @{admin['username']}\n"
        texto += f"   📅 {admin['data_registro']}\n"
        texto += f"   💰 Saldo: R$ {admin['saldo']:.2f}\n\n"
    
    keyboard = [[InlineKeyboardButton("🔙 VOLTAR", callback_data="admin_gerenciar_admins")]]
    
    await query.edit_message_text(
        text=texto,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


def registrar_handlers_admin_admins(application):
    """Registra handlers de gerenciamento de admins"""
    
    admins_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(lambda u, c: menu_gerenciar_admins(u, c, None), pattern="^admin_gerenciar_admins$"),
        ],
        states={
            EstadosAdmin.ADD_ADMIN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: adicionar_admin_confirmar(u, c, None)),
            ],
            EstadosAdmin.CONFIRMAR_ADMIN: [
                CallbackQueryHandler(lambda u, c: adicionar_admin_executar(u, c, None), pattern="^confirmar_add_admin$"),
            ],
            EstadosAdmin.REMOVER_ADMIN: [
                CallbackQueryHandler(lambda u, c: remover_admin_confirmar(u, c, None), pattern="^remover_admin_"),
            ],
            EstadosAdmin.CONFIRMAR_REMOVER: [
                CallbackQueryHandler(lambda u, c: remover_admin_executar(u, c, None), pattern="^confirmar_remover_admin$"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(lambda u, c: menu_gerenciar_admins(u, c, None), pattern="^admin_gerenciar_admins$"),
        ],
        name="admin_admins_conversation",
    )
    
    application.add_handler(admins_conv)
    
    application.add_handler(CallbackQueryHandler(lambda u, c: adicionar_admin_inicio(u, c, None), pattern="^admin_add_admin$"))
    application.add_handler(CallbackQueryHandler(lambda u, c: remover_admin_inicio(u, c, None), pattern="^admin_remove_admin$"))
    application.add_handler(CallbackQueryHandler(lambda u, c: listar_admins_detalhado(u, c, None), pattern="^admin_listar_admins$"))
    
    logger.info("✅ Handlers de gerenciamento de admins registrados!")


__all__ = [
    'menu_gerenciar_admins',
    'adicionar_admin_inicio',
    'adicionar_admin_confirmar',
    'adicionar_admin_executar',
    'remover_admin_inicio',
    'remover_admin_confirmar',
    'remover_admin_executar',
    'listar_admins_detalhado',
    'registrar_handlers_admin_admins',
    'AdminManagerService',
]
