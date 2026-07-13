"""
Painel Admin - Gerenciamento de Usuários
Pesquisar, editar saldo, banir, enviar mensagens e bônus em massa
"""
import logging
from datetime import datetime
from typing import List, Dict, Optional

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
from ...database.models import Usuario, Blacklist, Transacao, TipoTransacao, StatusTransacao
from ...utils.keyboards import (
    admin_menu_usuarios, botao_voltar, botoes_confirmacao, botoes_paginacao
)
from ...utils.utils import (
    formatar_moeda, formatar_data, formatar_numero,
    log_com_contexto
)
from ...utils.states import EstadosAdminUsuarios
from ...middlewares import somente_admin, log_atividade

logger = logging.getLogger(__name__)


class UserManagerService:
    """Serviço de gerenciamento de usuários"""
    
    def __init__(self, db: Database):
        self.db = db
    
    def buscar_usuario(self, user_id: int) -> Optional[Dict]:
        """Busca usuário por ID"""
        with self.db.get_session() as session:
            usuario = session.query(Usuario).filter_by(telegram_id=user_id).first()
            
            if not usuario:
                return None
            
            total_compras = len(usuario.compras) if hasattr(usuario, 'compras') else 0
            
            return {
                'id': usuario.telegram_id,
                'nome': usuario.nome or 'N/A',
                'username': usuario.username or 'N/A',
                'saldo': float(usuario.saldo),
                'whatsapp': usuario.whatsapp or 'N/A',
                'is_admin': usuario.is_admin,
                'is_banido': usuario.is_banido,
                'data_registro': formatar_data(usuario.data_registro),
                'total_compras': total_compras,
                'comissao': float(usuario.comissao_acumulada or 0),
                'indicacoes': usuario.total_indicacoes or 0,
                'codigo_afiliado': usuario.codigo_afiliado or 'N/A'
            }
    
    def listar_usuarios(self, pagina: int = 1, limite: int = 10, filtro: str = "todos") -> tuple:
        """Lista usuários com paginação"""
        with self.db.get_session() as session:
            query = session.query(Usuario)
            
            if filtro == "admins":
                query = query.filter_by(is_admin=True)
            elif filtro == "banidos":
                query = query.filter_by(is_banido=True)
            elif filtro == "com_saldo":
                query = query.filter(Usuario.saldo > 0)
            elif filtro == "afiliados":
                query = query.filter(Usuario.total_indicacoes > 0)
            
            total = query.count()
            total_paginas = max(1, (total + limite - 1) // limite)
            
            usuarios = query.order_by(Usuario.data_registro.desc()).offset((pagina - 1) * limite).limit(limite).all()
            
            dados = []
            for u in usuarios:
                dados.append({
                    'id': u.telegram_id,
                    'nome': u.nome or f"@{u.username}" or f"ID:{u.telegram_id}",
                    'saldo': float(u.saldo),
                    'is_admin': u.is_admin,
                    'is_banido': u.is_banido,
                    'data': formatar_data(u.data_registro, "dd/mm/aaaa")
                })
            
            return dados, total, total_paginas
    
    def editar_saldo(self, user_id: int, valor: float, operacao: str = "add", admin_id: int = None) -> tuple:
        """Edita saldo do usuário"""
        with self.db.get_session() as session:
            usuario = session.query(Usuario).filter_by(telegram_id=user_id).first()
            
            if not usuario:
                return False, "Usuário não encontrado", 0
            
            saldo_anterior = usuario.saldo
            
            if operacao == "add":
                usuario.saldo += valor
            elif operacao == "sub":
                if usuario.saldo < valor:
                    return False, "Saldo insuficiente", saldo_anterior
                usuario.saldo -= valor
            elif operacao == "set":
                usuario.saldo = valor
            
            novo_saldo = usuario.saldo
            
            # Registra transação
            transacao = Transacao(
                usuario_id=user_id,
                tipo=TipoTransacao.AJUSTE.value,
                status=StatusTransacao.APROVADO.value,
                valor=valor,
                valor_total=valor,
                descricao=f"Ajuste de saldo por admin {admin_id}: {operacao} {valor}",
                data_criacao=datetime.now(),
                data_aprovacao=datetime.now()
            )
            session.add(transacao)
            session.flush()
            
            log_com_contexto(
                "Saldo editado",
                user_id=user_id,
                operacao=operacao,
                valor=valor,
                anterior=saldo_anterior,
                novo=novo_saldo,
                admin_id=admin_id
            )
            
            return True, "Saldo atualizado", novo_saldo
    
    def banir_usuario(self, user_id: int, motivo: str = "", admin_id: int = None) -> tuple:
        """Bane um usuário"""
        with self.db.get_session() as session:
            usuario = session.query(Usuario).filter_by(telegram_id=user_id).first()
            
            if not usuario:
                return False, "Usuário não encontrado"
            
            if usuario.is_banido:
                return False, "Usuário já está banido"
            
            usuario.is_banido = True
            usuario.motivo_ban = motivo
            usuario.data_ban = datetime.now()
            
            # Adiciona à blacklist
            blacklist = Blacklist(
                telegram_id=user_id,
                motivo=motivo,
                banido_por=admin_id
            )
            session.add(blacklist)
            session.flush()
            
            log_com_contexto("Usuário banido", user_id=user_id, motivo=motivo, admin_id=admin_id)
            return True, f"Usuário {user_id} banido"
    
    def desbanir_usuario(self, user_id: int) -> tuple:
        """Desbane um usuário"""
        with self.db.get_session() as session:
            usuario = session.query(Usuario).filter_by(telegram_id=user_id).first()
            
            if not usuario:
                return False, "Usuário não encontrado"
            
            if not usuario.is_banido:
                return False, "Usuário não está banido"
            
            usuario.is_banido = False
            usuario.motivo_ban = ""
            usuario.data_ban = None
            
            # Remove da blacklist
            session.query(Blacklist).filter_by(telegram_id=user_id, ativo=True).update({"ativo": False})
            session.flush()
            
            log_com_contexto("Usuário desbanido", user_id=user_id)
            return True, f"Usuário {user_id} desbanido"
    
    def get_contagem_usuarios(self) -> Dict:
        """Retorna contagem de usuários por categoria"""
        with self.db.get_session() as session:
            total = session.query(Usuario).count()
            admins = session.query(Usuario).filter_by(is_admin=True).count()
            banidos = session.query(Usuario).filter_by(is_banido=True).count()
            com_saldo = session.query(Usuario).filter(Usuario.saldo > 0).count()
            afiliados = session.query(Usuario).filter(Usuario.total_indicacoes > 0).count()
            
            return {
                'total': total,
                'admins': admins,
                'banidos': banidos,
                'com_saldo': com_saldo,
                'afiliados': afiliados
            }


user_manager = None

def init_user_manager(db: Database):
    global user_manager
    user_manager = UserManagerService(db)


@somente_admin
@log_atividade("admin_menu_usuarios")
async def menu_usuarios(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Exibe menu de gerenciamento de usuários"""
    init_user_manager(db)
    query = update.callback_query
    await query.answer()
    
    contagem = user_manager.get_contagem_usuarios()
    
    texto = f"""
👥 *GERENCIAR USUÁRIOS*

📊 *Estatísticas:*
• Total: {formatar_numero(contagem['total'])}
• Admins: {formatar_numero(contagem['admins'])}
• Banidos: {formatar_numero(contagem['banidos'])}
• Com saldo: {formatar_numero(contagem['com_saldo'])}
• Afiliados: {formatar_numero(contagem['afiliados'])}

🔹 Selecione uma opção:
"""
    
    await query.edit_message_text(
        text=texto,
        reply_markup=admin_menu_usuarios(),
        parse_mode="Markdown"
    )
    
    return EstadosAdminUsuarios.MENU_USUARIOS


@somente_admin
async def pesquisar_usuario_inicio(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Solicita ID para pesquisa"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "🔍 *PESQUISAR USUÁRIO*\n\n"
        "✏️ *Digite o ID do Telegram:*\n\n"
        "💡 O ID aparece no comando /id\n"
        "ou no início de cada mensagem.",
        reply_markup=botao_voltar("admin_usuarios"),
        parse_mode="Markdown"
    )
    
    return EstadosAdminUsuarios.DIGITAR_ID_BUSCA


@somente_admin
async def pesquisar_usuario_exibir(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Exibe dados do usuário pesquisado"""
    try:
        user_id = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text(
            "❌ ID inválido. Digite apenas números.",
            reply_markup=botao_voltar("admin_usuarios")
        )
        return EstadosAdminUsuarios.DIGITAR_ID_BUSCA
    
    dados = user_manager.buscar_usuario(user_id)
    
    if not dados:
        await update.message.reply_text(
            f"❌ Usuário `{user_id}` não encontrado.",
            reply_markup=botao_voltar("admin_usuarios"),
            parse_mode="Markdown"
        )
        return EstadosAdminUsuarios.DIGITAR_ID_BUSCA
    
    texto = f"""
👤 *DADOS DO USUÁRIO*

🆔 *ID:* `{dados['id']}`
👤 *Nome:* {dados['nome']}
📱 *Username:* @{dados['username']}
📞 *WhatsApp:* {dados['whatsapp']}

💰 *Saldo:* {formatar_moeda(dados['saldo'])}
🛒 *Compras:* {dados['total_compras']}
🤝 *Indicações:* {dados['indicacoes']}
💎 *Comissão:* {formatar_moeda(dados['comissao'])}

🛡️ *Admin:* {'✅ Sim' if dados['is_admin'] else '❌ Não'}
🚫 *Banido:* {'⚠️ Sim' if dados['is_banido'] else '✅ Não'}
📅 *Registro:* {dados['data_registro']}

🔗 *Código Afiliado:* `{dados['codigo_afiliado']}`
"""
    
    keyboard = [
        [
            InlineKeyboardButton("💰 EDITAR SALDO", callback_data=f"editar_saldo_{user_id}"),
            InlineKeyboardButton("📨 ENVIAR MSG", callback_data=f"enviar_msg_{user_id}")
        ],
        [
            InlineKeyboardButton("🚫 BANIR" if not dados['is_banido'] else "✅ DESBANIR",
                                callback_data=f"{'banir' if not dados['is_banido'] else 'desbanir'}_{user_id}")
        ],
        [InlineKeyboardButton("🔙 VOLTAR", callback_data="admin_usuarios")]
    ]
    
    await update.message.reply_text(
        text=texto,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
    return ConversationHandler.END


@somente_admin
async def editar_saldo_inicio(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Inicia edição de saldo"""
    query = update.callback_query
    await query.answer()
    
    user_id = int(query.data.split("_")[-1])
    context.user_data['saldo_user_id'] = user_id
    
    dados = user_manager.buscar_usuario(user_id)
    
    texto = f"""
💰 *EDITAR SALDO*

👤 *Usuário:* {dados['nome']}
🆔 *ID:* `{user_id}`
💰 *Saldo atual:* {formatar_moeda(dados['saldo'])}

🔹 *Escolha a operação:*
"""
    
    keyboard = [
        [InlineKeyboardButton("➕ ADICIONAR", callback_data="saldo_op_add")],
        [InlineKeyboardButton("➖ REMOVER", callback_data="saldo_op_sub")],
        [InlineKeyboardButton("🔄 DEFINIR", callback_data="saldo_op_set")],
        [InlineKeyboardButton("🔙 CANCELAR", callback_data="admin_usuarios")]
    ]
    
    await query.edit_message_text(
        text=texto,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
    return EstadosAdminUsuarios.EDITAR_SALDO


@somente_admin
async def editar_saldo_valor(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Define operação e solicita valor"""
    query = update.callback_query
    await query.answer()
    
    operacao = query.data.split("_")[-1]
    context.user_data['saldo_operacao'] = operacao
    
    user_id = context.user_data.get('saldo_user_id')
    dados = user_manager.buscar_usuario(user_id) if user_id else None
    
    op_nomes = {'add': 'ADICIONAR', 'sub': 'REMOVER', 'set': 'DEFINIR'}
    
    await query.edit_message_text(
        f"💰 *{op_nomes.get(operacao, 'EDITAR')} SALDO*\n\n"
        f"👤 Usuário: {dados['nome'] if dados else 'N/A'}\n"
        f"💰 Saldo atual: {formatar_moeda(dados['saldo']) if dados else 'N/A'}\n\n"
        "✏️ *Digite o valor:*",
        reply_markup=botao_voltar("admin_usuarios"),
        parse_mode="Markdown"
    )
    
    return EstadosAdminUsuarios.DIGITAR_VALOR_SALDO


@somente_admin
async def editar_saldo_confirmar(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Confirma e executa edição de saldo"""
    try:
        valor = float(update.message.text.replace(",", "."))
        
        if valor <= 0:
            await update.message.reply_text("❌ Digite um valor positivo.")
            return EstadosAdminUsuarios.DIGITAR_VALOR_SALDO
        
    except ValueError:
        await update.message.reply_text("❌ Valor inválido.")
        return EstadosAdminUsuarios.DIGITAR_VALOR_SALDO
    
    user_id = context.user_data.get('saldo_user_id')
    operacao = context.user_data.get('saldo_operacao', 'add')
    admin_id = update.effective_user.id
    
    sucesso, msg, novo_saldo = user_manager.editar_saldo(user_id, valor, operacao, admin_id)
    
    if sucesso:
        texto = f"""
✅ *SALDO ATUALIZADO!*

👤 *Usuário:* `{user_id}`
💰 *Operação:* {operacao.upper()}
💵 *Valor:* {formatar_moeda(valor)}
💎 *Novo saldo:* {formatar_moeda(novo_saldo)}
"""
    else:
        texto = f"❌ {msg}"
    
    keyboard = [
        [InlineKeyboardButton("🔄 NOVA EDIÇÃO", callback_data=f"editar_saldo_{user_id}")],
        [InlineKeyboardButton("🔙 MENU USUÁRIOS", callback_data="admin_usuarios")]
    ]
    
    await update.message.reply_text(
        text=texto,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
    return ConversationHandler.END


@somente_admin
async def banir_usuario_inicio(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Inicia processo de banimento"""
    query = update.callback_query
    await query.answer()
    
    user_id = int(query.data.split("_")[-1])
    context.user_data['ban_user_id'] = user_id
    
    dados = user_manager.buscar_usuario(user_id)
    
    texto = f"""
🚫 *BANIR USUÁRIO*

👤 *Usuário:* {dados['nome'] if dados else 'N/A'}
🆔 *ID:* `{user_id}`

✏️ *Digite o motivo do banimento:*
"""
    
    await query.edit_message_text(
        text=texto,
        reply_markup=botao_voltar("admin_usuarios"),
        parse_mode="Markdown"
    )
    
    return EstadosAdminUsuarios.DIGITAR_MOTIVO_BAN


@somente_admin
@log_atividade("admin_banir_usuario")
async def banir_usuario_executar(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Executa banimento"""
    user_id = context.user_data.get('ban_user_id')
    motivo = update.message.text.strip()
    admin_id = update.effective_user.id
    
    if not user_id:
        await update.message.reply_text("❌ Dados expirados.")
        return ConversationHandler.END
    
    sucesso, msg = user_manager.banir_usuario(user_id, motivo, admin_id)
    
    if sucesso:
        texto = f"""
✅ *USUÁRIO BANIDO!*

🆔 *ID:* `{user_id}`
📝 *Motivo:* {motivo}

🔹 O usuário não pode mais usar o bot.
"""
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"🚫 *VOCÊ FOI BANIDO*\n\n📝 Motivo: {motivo}\n\nPara contestar, entre em contato com o suporte.",
                parse_mode="Markdown"
            )
        except:
            pass
    else:
        texto = f"❌ {msg}"
    
    keyboard = [[InlineKeyboardButton("🔙 MENU USUÁRIOS", callback_data="admin_usuarios")]]
    
    await update.message.reply_text(
        text=texto,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
    context.user_data.pop('ban_user_id', None)
    return ConversationHandler.END


@somente_admin
async def desbanir_usuario_executar(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Executa desbanimento"""
    query = update.callback_query
    await query.answer()
    
    user_id = int(query.data.split("_")[-1])
    
    sucesso, msg = user_manager.desbanir_usuario(user_id)
    
    if sucesso:
        texto = f"✅ *USUÁRIO DESBANIDO!*\n\n🆔 `{user_id}`\n\n🔹 O usuário pode voltar a usar o bot."
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text="✅ Seu banimento foi removido! Você pode usar o bot novamente."
            )
        except:
            pass
    else:
        texto = f"❌ {msg}"
    
    await query.edit_message_text(
        text=texto,
        reply_markup=botao_voltar("admin_usuarios"),
        parse_mode="Markdown"
    )


@somente_admin
async def enviar_mensagem_inicio(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Inicia envio de mensagem para usuário específico"""
    query = update.callback_query
    await query.answer()
    
    user_id = int(query.data.split("_")[-1])
    context.user_data['msg_user_id'] = user_id
    
    dados = user_manager.buscar_usuario(user_id)
    
    await query.edit_message_text(
        f"📨 *ENVIAR MENSAGEM*\n\n"
        f"👤 Para: {dados['nome'] if dados else 'N/A'} (`{user_id}`)\n\n"
        "✏️ *Digite a mensagem:*",
        reply_markup=botao_voltar("admin_usuarios"),
        parse_mode="Markdown"
    )
    
    return EstadosAdminUsuarios.DIGITAR_MENSAGEM


@somente_admin
async def enviar_mensagem_executar(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Envia mensagem para o usuário"""
    user_id = context.user_data.get('msg_user_id')
    mensagem = update.message.text
    
    if not user_id:
        await update.message.reply_text("❌ Dados expirados.")
        return ConversationHandler.END
    
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"📨 *Mensagem da Administração:*\n\n{mensagem}",
            parse_mode="Markdown"
        )
        
        await update.message.reply_text(
            f"✅ Mensagem enviada para `{user_id}`!",
            reply_markup=botao_voltar("admin_usuarios"),
            parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(
            f"❌ Erro ao enviar: {e}",
            reply_markup=botao_voltar("admin_usuarios")
        )
    
    context.user_data.pop('msg_user_id', None)
    return ConversationHandler.END


@somente_admin
async def bonus_em_massa_inicio(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Inicia bônus em massa"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "🎁 *BÔNUS EM MASSA*\n\n"
        "✏️ *Digite o valor do bônus:*\n\n"
        "💡 Este valor será adicionado ao saldo de todos os usuários\n"
        "que atendem ao filtro selecionado.",
        reply_markup=botao_voltar("admin_usuarios"),
        parse_mode="Markdown"
    )
    
    return EstadosAdminUsuarios.DIGITAR_VALOR_BONUS


@somente_admin
async def bonus_em_massa_filtro(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Seleciona filtro para bônus"""
    try:
        valor = float(update.message.text.replace(",", "."))
        context.user_data['bonus_valor'] = valor
    except ValueError:
        await update.message.reply_text("❌ Valor inválido.")
        return EstadosAdminUsuarios.DIGITAR_VALOR_BONUS
    
    texto = f"""
🎁 *BÔNUS EM MASSA*

💰 *Valor:* {formatar_moeda(valor)}

👥 *Selecione o público:*
"""
    
    keyboard = [
        [InlineKeyboardButton("👥 TODOS USUÁRIOS", callback_data="bonus_filtro_todos")],
        [InlineKeyboardButton("💰 COM SALDO", callback_data="bonus_filtro_com_saldo")],
        [InlineKeyboardButton("🤝 AFILIADOS", callback_data="bonus_filtro_afiliados")],
        [InlineKeyboardButton("🔙 CANCELAR", callback_data="admin_usuarios")]
    ]
    
    await update.message.reply_text(
        text=texto,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
    return EstadosAdminUsuarios.SELECIONAR_FILTRO


@somente_admin
@log_atividade("admin_bonus_massa")
async def bonus_em_massa_executar(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Executa bônus em massa"""
    query = update.callback_query
    await query.answer()
    
    valor = context.user_data.get('bonus_valor', 0)
    filtro = query.data.split("_")[-1]
    
    with db.get_session() as session:
        query_users = session.query(Usuario)
        
        if filtro == "com_saldo":
            query_users = query_users.filter(Usuario.saldo > 0)
        elif filtro == "afiliados":
            query_users = query_users.filter(Usuario.total_indicacoes > 0)
        
        usuarios = query_users.all()
        total = len(usuarios)
        
        for usuario in usuarios:
            usuario.saldo += valor
        
        session.flush()
    
    texto = f"""
✅ *BÔNUS EM MASSA APLICADO!*

💰 *Valor:* {formatar_moeda(valor)}
👥 *Usuários beneficiados:* {formatar_numero(total)}
💵 *Total distribuído:* {formatar_moeda(valor * total)}
"""
    
    await query.edit_message_text(
        text=texto,
        reply_markup=botao_voltar("admin_usuarios"),
        parse_mode="Markdown"
    )
    
    context.user_data.pop('bonus_valor', None)
    return ConversationHandler.END


def registrar_handlers_admin_users(application):
    """Registra handlers de gerenciamento de usuários"""
    
    users_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(lambda u, c: menu_usuarios(u, c, None), pattern="^admin_usuarios$"),
        ],
        states={
            EstadosAdminUsuarios.DIGITAR_ID_BUSCA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: pesquisar_usuario_exibir(u, c, None)),
            ],
            EstadosAdminUsuarios.EDITAR_SALDO: [
                CallbackQueryHandler(lambda u, c: editar_saldo_valor(u, c, None), pattern="^saldo_op_"),
            ],
            EstadosAdminUsuarios.DIGITAR_VALOR_SALDO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: editar_saldo_confirmar(u, c, None)),
            ],
            EstadosAdminUsuarios.DIGITAR_MOTIVO_BAN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: banir_usuario_executar(u, c, None)),
            ],
            EstadosAdminUsuarios.DIGITAR_MENSAGEM: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: enviar_mensagem_executar(u, c, None)),
            ],
            EstadosAdminUsuarios.DIGITAR_VALOR_BONUS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: bonus_em_massa_filtro(u, c, None)),
            ],
            EstadosAdminUsuarios.SELECIONAR_FILTRO: [
                CallbackQueryHandler(lambda u, c: bonus_em_massa_executar(u, c, None), pattern="^bonus_filtro_"),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(lambda u, c: menu_usuarios(u, c, None), pattern="^admin_usuarios$"),
        ],
        name="admin_users_conversation",
    )
    
    application.add_handler(users_conv)
    
    application.add_handler(CallbackQueryHandler(lambda u, c: pesquisar_usuario_inicio(u, c, None), pattern="^admin_buscar_usuario$"))
    application.add_handler(CallbackQueryHandler(lambda u, c: editar_saldo_inicio(u, c, None), pattern="^editar_saldo_"))
    application.add_handler(CallbackQueryHandler(lambda u, c: banir_usuario_inicio(u, c, None), pattern="^banir_"))
    application.add_handler(CallbackQueryHandler(lambda u, c: desbanir_usuario_executar(u, c, None), pattern="^desbanir_"))
    application.add_handler(CallbackQueryHandler(lambda u, c: enviar_mensagem_inicio(u, c, None), pattern="^enviar_msg_"))
    application.add_handler(CallbackQueryHandler(lambda u, c: bonus_em_massa_inicio(u, c, None), pattern="^admin_bonus_massa$"))
    
    logger.info("✅ Handlers de gerenciamento de usuários registrados!")


__all__ = [
    'menu_usuarios',
    'pesquisar_usuario_inicio',
    'pesquisar_usuario_exibir',
    'editar_saldo_inicio',
    'editar_saldo_valor',
    'editar_saldo_confirmar',
    'banir_usuario_inicio',
    'banir_usuario_executar',
    'desbanir_usuario_executar',
    'enviar_mensagem_inicio',
    'enviar_mensagem_executar',
    'bonus_em_massa_inicio',
    'bonus_em_massa_filtro',
    'bonus_em_massa_executar',
    'registrar_handlers_admin_users',
    'UserManagerService',
]
