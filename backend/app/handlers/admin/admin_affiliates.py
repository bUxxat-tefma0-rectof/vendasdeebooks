"""
Painel Admin - Configuração do Sistema de Afiliados
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
from ...database.models import Usuario, Compra
from ...utils.keyboards import admin_menu_afiliados, botao_voltar
from ...utils.utils import (
    formatar_moeda, formatar_numero, get_medalha,
    log_com_contexto
)
from ...utils.states import EstadosAdminAfiliados
from ...middlewares import somente_admin, log_atividade

logger = logging.getLogger(__name__)


class AffiliateAdminService:
    """Serviço de administração de afiliados"""
    
    def __init__(self, db: Database):
        self.db = db
    
    def get_top_afiliados(self, limite: int = 10) -> List[Dict]:
        """Top afiliados"""
        with self.db.get_session() as session:
            afiliados = session.query(Usuario).filter(
                Usuario.total_indicacoes > 0
            ).order_by(Usuario.comissao_acumulada.desc()).limit(limite).all()
            
            return [
                {
                    'id': a.telegram_id,
                    'nome': a.nome or f"@{a.username}" or f"ID:{a.telegram_id}",
                    'indicacoes': a.total_indicacoes or 0,
                    'comissao': float(a.comissao_acumulada or 0),
                    'saldo': float(a.saldo or 0)
                }
                for a in afiliados
            ]
    
    def get_metricas_afiliados(self) -> Dict:
        """Métricas gerais dos afiliados"""
        with self.db.get_session() as session:
            total_afiliados = session.query(Usuario).filter(
                Usuario.total_indicacoes > 0
            ).count()
            
            total_indicacoes = session.query(Usuario).filter(
                Usuario.afiliado_por.isnot(None)
            ).count()
            
            total_comissoes = session.query(Usuario).with_entities(
                func.sum(Usuario.comissao_acumulada)
            ).scalar() or 0.0
            
            return {
                'total_afiliados': total_afiliados,
                'total_indicacoes': total_indicacoes,
                'total_comissoes': float(total_comissoes)
            }


affiliate_admin = None

def init_service(db: Database):
    global affiliate_admin
    affiliate_admin = AffiliateAdminService(db)


@somente_admin
@log_atividade("admin_menu_afiliados")
async def menu_afiliados_admin(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Menu de configuração de afiliados"""
    init_service(db)
    query = update.callback_query
    await query.answer()
    
    metricas = affiliate_admin.get_metricas_afiliados()
    
    texto = f"""
🤝 *CONFIGURAR AFILIADOS*

📊 *Métricas:*
• Afiliados ativos: {formatar_numero(metricas['total_afiliados'])}
• Total indicações: {formatar_numero(metricas['total_indicacoes'])}
• Comissões pagas: {formatar_moeda(metricas['total_comissoes'])}

⚙️ *Configurações:*
• Sistema: {'✅ ATIVO' if config.SISTEMA_AFILIADOS_ATIVO else '❌ INATIVO'}
• Comissão: {config.COMISSAO_AFILIADO}%

🔹 Selecione uma opção:
"""
    
    await query.edit_message_text(
        text=texto,
        reply_markup=admin_menu_afiliados(),
        parse_mode="Markdown"
    )
    
    return EstadosAdminAfiliados.MENU_AFILIADOS


@somente_admin
async def toggle_sistema_afiliados(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Ativa/desativa sistema de afiliados"""
    query = update.callback_query
    await query.answer()
    
    config.SISTEMA_AFILIADOS_ATIVO = not config.SISTEMA_AFILIADOS_ATIVO
    status = "✅ ATIVADO" if config.SISTEMA_AFILIADOS_ATIVO else "❌ DESATIVADO"
    
    await query.edit_message_text(
        f"🤝 *SISTEMA DE AFILIADOS*\n\nStatus: {status}",
        reply_markup=botao_voltar("admin_afiliados"),
        parse_mode="Markdown"
    )
    
    log_com_contexto("Sistema afiliados alterado", ativo=config.SISTEMA_AFILIADOS_ATIVO)


@somente_admin
async def configurar_comissao(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Solicita nova porcentagem de comissão"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        f"💎 *DEFINIR COMISSÃO*\n\n"
        f"Atual: {config.COMISSAO_AFILIADO}%\n\n"
        "✏️ Digite a nova porcentagem (0-50):",
        reply_markup=botao_voltar("admin_afiliados"),
        parse_mode="Markdown"
    )
    
    return EstadosAdminAfiliados.DIGITAR_PORCENTAGEM_COMISSAO


@somente_admin
@log_atividade("admin_config_comissao")
async def salvar_comissao(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Salva nova comissão"""
    try:
        comissao = float(update.message.text.replace(",", "."))
        
        if comissao < 0 or comissao > 50:
            await update.message.reply_text("❌ Valor entre 0 e 50.")
            return EstadosAdminAfiliados.DIGITAR_PORCENTAGEM_COMISSAO
        
        config.COMISSAO_AFILIADO = comissao
        
        await update.message.reply_text(
            f"✅ Comissão atualizada: {comissao}%",
            reply_markup=botao_voltar("admin_afiliados")
        )
    except ValueError:
        await update.message.reply_text("❌ Valor inválido.")
        return EstadosAdminAfiliados.DIGITAR_PORCENTAGEM_COMISSAO
    
    return ConversationHandler.END


@somente_admin
async def ver_top_afiliados(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Exibe ranking de afiliados"""
    query = update.callback_query
    await query.answer()
    
    top = affiliate_admin.get_top_afiliados(10)
    
    if not top:
        await query.edit_message_text(
            "🤝 *TOP AFILIADOS*\n\n⚠️ Nenhum afiliado ainda.",
            reply_markup=botao_voltar("admin_afiliados"),
            parse_mode="Markdown"
        )
        return
    
    texto = "🤝 *TOP 10 AFILIADOS*\n\n"
    
    for i, af in enumerate(top, 1):
        medalha = get_medalha(i)
        texto += f"{medalha} *{af['nome'][:20]}*\n"
        texto += f"   👥 {af['indicacoes']} indicados\n"
        texto += f"   💰 {formatar_moeda(af['comissao'])} em comissões\n"
        texto += f"   💵 Saldo: {formatar_moeda(af['saldo'])}\n\n"
    
    await query.edit_message_text(
        text=texto,
        reply_markup=botao_voltar("admin_afiliados"),
        parse_mode="Markdown"
    )


@somente_admin
async def bonificar_afiliados(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Adiciona bônus para afiliados"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "🎁 *BONUS PARA AFILIADOS*\n\n"
        "✏️ Digite o valor do bônus:\n\n"
        "Será adicionado ao saldo de todos os afiliados.",
        reply_markup=botao_voltar("admin_afiliados"),
        parse_mode="Markdown"
    )
    
    return EstadosAdminAfiliados.DIGITAR_BONUS_META


@somente_admin
@log_atividade("admin_bonus_afiliados")
async def salvar_bonus_afiliados(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Salva bônus para afiliados"""
    try:
        valor = float(update.message.text.replace(",", "."))
        
        with db.get_session() as session:
            afiliados = session.query(Usuario).filter(
                Usuario.total_indicacoes > 0
            ).all()
            
            for af in afiliados:
                af.saldo += valor
            
            session.flush()
        
        await update.message.reply_text(
            f"✅ Bônus de {formatar_moeda(valor)} enviado para {len(afiliados)} afiliados!",
            reply_markup=botao_voltar("admin_afiliados")
        )
        
        log_com_contexto("Bônus afiliados", valor=valor, total=len(afiliados))
        
    except ValueError:
        await update.message.reply_text("❌ Valor inválido.")
        return EstadosAdminAfiliados.DIGITAR_BONUS_META
    
    return ConversationHandler.END


def registrar_handlers_admin_affiliates(application):
    """Registra handlers de afiliados admin"""
    
    aff_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(lambda u, c: menu_afiliados_admin(u, c, None), pattern="^admin_afiliados$"),
        ],
        states={
            EstadosAdminAfiliados.DIGITAR_PORCENTAGEM_COMISSAO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: salvar_comissao(u, c, None)),
            ],
            EstadosAdminAfiliados.DIGITAR_BONUS_META: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: salvar_bonus_afiliados(u, c, None)),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(lambda u, c: menu_afiliados_admin(u, c, None), pattern="^admin_afiliados$"),
        ],
        name="admin_affiliates_conversation",
    )
    
    application.add_handler(aff_conv)
    
    application.add_handler(CallbackQueryHandler(lambda u, c: toggle_sistema_afiliados(u, c, None), pattern="^admin_toggle_afiliados$"))
    application.add_handler(CallbackQueryHandler(lambda u, c: configurar_comissao(u, c, None), pattern="^admin_definir_comissao$"))
    application.add_handler(CallbackQueryHandler(lambda u, c: ver_top_afiliados(u, c, None), pattern="^admin_relatorio_afiliados$"))
    application.add_handler(CallbackQueryHandler(lambda u, c: bonificar_afiliados(u, c, None), pattern="^admin_metas_afiliados$"))
    
    logger.info("✅ Handlers de afiliados admin registrados!")


from sqlalchemy import func

__all__ = [
    'menu_afiliados_admin',
    'toggle_sistema_afiliados',
    'configurar_comissao',
    'salvar_comissao',
    'ver_top_afiliados',
    'bonificar_afiliados',
    'registrar_handlers_admin_affiliates',
]
