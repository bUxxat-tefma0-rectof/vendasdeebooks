"""
Painel Admin - Configurações Gerais do Bot
Gerencia todas as configurações do sistema
"""
import logging
from datetime import datetime
from typing import Dict, Any

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
from ...database.models import ConfiguracaoBot
from ...utils.keyboards import (
    admin_menu_configuracoes,
    botao_voltar,
    botoes_confirmacao
)
from ...utils.utils import formatar_moeda, log_com_contexto
from ...utils.states import EstadosAdmin
from ...middlewares import somente_admin, log_atividade

logger = logging.getLogger(__name__)


class ConfigService:
    """Serviço de configurações do bot"""
    
    def __init__(self, db: Database):
        self.db = db
    
    def get_config(self, chave: str, default: Any = None) -> Any:
        """Obtém uma configuração"""
        with self.db.get_session() as session:
            conf = session.query(ConfiguracaoBot).filter_by(chave=chave).first()
            if conf:
                if conf.tipo == "int":
                    return int(conf.valor)
                elif conf.tipo == "float":
                    return float(conf.valor)
                elif conf.tipo == "bool":
                    return conf.valor.lower() == "true"
                return conf.valor
            return default
    
    def set_config(self, chave: str, valor: Any, tipo: str = "string", descricao: str = "") -> bool:
        """Define uma configuração"""
        with self.db.get_session() as session:
            conf = session.query(ConfiguracaoBot).filter_by(chave=chave).first()
            
            if conf:
                conf.valor = str(valor)
                conf.data_atualizacao = datetime.now()
            else:
                conf = ConfiguracaoBot(
                    chave=chave,
                    valor=str(valor),
                    tipo=tipo,
                    descricao=descricao
                )
                session.add(conf)
            
            session.flush()
            return True
    
    def get_all_configs(self) -> Dict:
        """Retorna todas as configurações"""
        with self.db.get_session() as session:
            configs = session.query(ConfiguracaoBot).all()
            return {c.chave: c.valor for c in configs}
    
    def toggle_manutencao(self) -> bool:
        """Ativa/desativa modo manutenção"""
        atual = self.get_config("modo_manutencao", False)
        self.set_config("modo_manutencao", not atual, "bool", "Modo de manutenção do bot")
        return not atual
    
    def set_link_suporte(self, link: str) -> bool:
        """Define link de suporte"""
        return self.set_config("link_suporte", link, "string", "Link do grupo de suporte")
    
    def set_link_telegram(self, link: str) -> bool:
        """Define link do Telegraph (termos)"""
        return self.set_config("link_telegram", link, "string", "Link dos termos de uso")


config_service = None

def init_config_service(db: Database):
    global config_service
    config_service = ConfigService(db)


@somente_admin
@log_atividade("admin_config_menu")
async def menu_configuracoes(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Exibe menu de configurações"""
    init_config_service(db)
    query = update.callback_query
    await query.answer()
    
    modo_manutencao = config_service.get_config("modo_manutencao", False)
    link_suporte = config_service.get_config("link_suporte", config.GRUPO_SUPORTE_LINK)
    
    texto = f"""
⚙️ *CONFIGURAÇÕES GERAIS*

🔧 *Status do Sistema:*
• Modo Manutenção: {'🔴 ATIVADO' if modo_manutencao else '🟢 DESATIVADO'}
• Versão: {config.VERSAO}

📞 *Suporte:*
• Link: {link_suporte or 'Não configurado'}

💰 *Financeiro:*
• Pix Mínimo: {formatar_moeda(config.VALOR_MINIMO_PIX)}
• Pix Máximo: {formatar_moeda(config.VALOR_MAXIMO_PIX)}
• Bônus Depósito: {config.BONUS_DEPOSITO}%
• Expiração Pix: {config.TEMPO_EXPIRACAO_PIX}s

🤝 *Afiliados:*
• Sistema: {'✅ Ativo' if config.SISTEMA_AFILIADOS_ATIVO else '❌ Inativo'}
• Comissão: {config.COMISSAO_AFILIADO}%

🔹 Selecione uma opção:
"""
    
    await query.edit_message_text(
        text=texto,
        reply_markup=admin_menu_configuracoes(),
        parse_mode="Markdown"
    )
    
    return EstadosAdmin.MENU_CONFIG


@somente_admin
async def toggle_manutencao(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Ativa/desativa modo manutenção"""
    query = update.callback_query
    await query.answer()
    
    status = config_service.toggle_manutencao()
    
    texto = f"""
🔧 *MODO MANUTENÇÃO*

Status: {'🔴 ATIVADO' if status else '🟢 DESATIVADO'}

{'⚠️ Apenas administradores podem usar o bot.' if status else '✅ Bot funcionando normalmente.'}
"""
    
    keyboard = [[InlineKeyboardButton("🔙 VOLTAR", callback_data="admin_config")]]
    
    await query.edit_message_text(
        text=texto,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
    
    log_com_contexto("Modo manutenção alterado", status=status)


@somente_admin
async def config_link_suporte(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Solicita novo link de suporte"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "📞 *CONFIGURAR LINK DE SUPORTE*\n\n"
        "✏️ Digite o novo link do grupo de suporte:\n\n"
        "Exemplo: https://t.me/seu_grupo",
        reply_markup=botao_voltar("admin_config"),
        parse_mode="Markdown"
    )
    
    return EstadosAdmin.EDITAR_LINK_SUPORTE


@somente_admin
async def salvar_link_suporte(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Salva novo link de suporte"""
    link = update.message.text.strip()
    
    if not link.startswith("https://t.me/"):
        await update.message.reply_text(
            "❌ Link inválido. Use: https://t.me/seu_grupo",
            reply_markup=botao_voltar("admin_config")
        )
        return EstadosAdmin.EDITAR_LINK_SUPORTE
    
    config_service.set_link_suporte(link)
    config.GRUPO_SUPORTE_LINK = link
    
    await update.message.reply_text(
        f"✅ *Link de suporte atualizado!*\n\n📞 {link}",
        reply_markup=botao_voltar("admin_config"),
        parse_mode="Markdown"
    )
    
    log_com_contexto("Link suporte atualizado", link=link)
    return ConversationHandler.END


@somente_admin
async def config_pix_minimo(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Solicita valor mínimo do Pix"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        f"💰 *VALOR MÍNIMO DO PIX*\n\n"
        f"Atual: {formatar_moeda(config.VALOR_MINIMO_PIX)}\n\n"
        "✏️ Digite o novo valor mínimo:",
        reply_markup=botao_voltar("admin_config"),
        parse_mode="Markdown"
    )
    
    return EstadosAdmin.CONFIG_VALORES


@somente_admin
async def salvar_pix_minimo(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Salva valor mínimo do Pix"""
    try:
        valor = float(update.message.text.replace(",", "."))
        
        if valor < 5:
            await update.message.reply_text("❌ Valor mínimo: R$ 5,00")
            return EstadosAdmin.CONFIG_VALORES
        
        config.VALOR_MINIMO_PIX = valor
        config_service.set_config("pix_minimo", valor, "float")
        
        await update.message.reply_text(
            f"✅ Valor mínimo atualizado: {formatar_moeda(valor)}",
            reply_markup=botao_voltar("admin_config")
        )
        
    except ValueError:
        await update.message.reply_text("❌ Digite um valor válido.")
        return EstadosAdmin.CONFIG_VALORES
    
    return ConversationHandler.END


@somente_admin
async def config_pix_maximo(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Solicita valor máximo do Pix"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        f"💰 *VALOR MÁXIMO DO PIX*\n\n"
        f"Atual: {formatar_moeda(config.VALOR_MAXIMO_PIX)}\n\n"
        "✏️ Digite o novo valor máximo:",
        reply_markup=botao_voltar("admin_config"),
        parse_mode="Markdown"
    )
    
    return EstadosAdmin.DIGITAR_VALOR_MAXIMO


@somente_admin
async def salvar_pix_maximo(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Salva valor máximo do Pix"""
    try:
        valor = float(update.message.text.replace(",", "."))
        config.VALOR_MAXIMO_PIX = valor
        config_service.set_config("pix_maximo", valor, "float")
        
        await update.message.reply_text(
            f"✅ Valor máximo atualizado: {formatar_moeda(valor)}",
            reply_markup=botao_voltar("admin_config")
        )
    except ValueError:
        await update.message.reply_text("❌ Digite um valor válido.")
        return EstadosAdmin.DIGITAR_VALOR_MAXIMO
    
    return ConversationHandler.END


@somente_admin
async def config_bonus_deposito(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Solicita porcentagem de bônus"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        f"🎁 *BÔNUS DE DEPÓSITO*\n\n"
        f"Atual: {config.BONUS_DEPOSITO}%\n\n"
        "✏️ Digite a nova porcentagem (0-100):",
        reply_markup=botao_voltar("admin_config"),
        parse_mode="Markdown"
    )
    
    return EstadosAdmin.CONFIG_BONUS


@somente_admin
async def salvar_bonus_deposito(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Salva porcentagem de bônus"""
    try:
        bonus = float(update.message.text.replace(",", "."))
        
        if bonus < 0 or bonus > 100:
            await update.message.reply_text("❌ Valor entre 0 e 100.")
            return EstadosAdmin.CONFIG_BONUS
        
        config.BONUS_DEPOSITO = bonus
        config_service.set_config("bonus_deposito", bonus, "float")
        
        await update.message.reply_text(
            f"✅ Bônus atualizado: {bonus}%",
            reply_markup=botao_voltar("admin_config")
        )
    except ValueError:
        await update.message.reply_text("❌ Digite um valor válido.")
        return EstadosAdmin.CONFIG_BONUS
    
    return ConversationHandler.END


@somente_admin
async def config_expiracao_pix(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Solicita tempo de expiração do Pix"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        f"⏱️ *TEMPO DE EXPIRAÇÃO DO PIX*\n\n"
        f"Atual: {config.TEMPO_EXPIRACAO_PIX} segundos ({config.TEMPO_EXPIRACAO_PIX // 60} min)\n\n"
        "✏️ Digite o tempo em segundos (mínimo 60):",
        reply_markup=botao_voltar("admin_config"),
        parse_mode="Markdown"
    )
    
    return EstadosAdmin.CONFIG_EXPIRACAO


@somente_admin
async def salvar_expiracao_pix(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Salva tempo de expiração"""
    try:
        tempo = int(update.message.text)
        
        if tempo < 60:
            await update.message.reply_text("❌ Mínimo: 60 segundos.")
            return EstadosAdmin.CONFIG_EXPIRACAO
        
        config.TEMPO_EXPIRACAO_PIX = tempo
        config_service.set_config("expiracao_pix", tempo, "int")
        
        await update.message.reply_text(
            f"✅ Expiração atualizada: {tempo}s ({tempo // 60} min)",
            reply_markup=botao_voltar("admin_config")
        )
    except ValueError:
        await update.message.reply_text("❌ Digite um número válido.")
        return EstadosAdmin.CONFIG_EXPIRACAO
    
    return ConversationHandler.END


@somente_admin
async def config_comissao_afiliado(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Solicita porcentagem de comissão"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        f"🤝 *COMISSÃO DE AFILIADO*\n\n"
        f"Atual: {config.COMISSAO_AFILIADO}%\n\n"
        "✏️ Digite a nova porcentagem (0-50):",
        reply_markup=botao_voltar("admin_config"),
        parse_mode="Markdown"
    )
    
    return EstadosAdmin.DEFINIR_COMISSAO


@somente_admin
async def salvar_comissao_afiliado(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Salva comissão de afiliado"""
    try:
        comissao = float(update.message.text.replace(",", "."))
        
        if comissao < 0 or comissao > 50:
            await update.message.reply_text("❌ Valor entre 0 e 50.")
            return EstadosAdmin.DEFINIR_COMISSAO
        
        config.COMISSAO_AFILIADO = comissao
        config_service.set_config("comissao_afiliado", comissao, "float")
        
        await update.message.reply_text(
            f"✅ Comissão atualizada: {comissao}%",
            reply_markup=botao_voltar("admin_config")
        )
    except ValueError:
        await update.message.reply_text("❌ Digite um valor válido.")
        return EstadosAdmin.DEFINIR_COMISSAO
    
    return ConversationHandler.END


@somente_admin
async def toggle_afiliados(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Ativa/desativa sistema de afiliados"""
    query = update.callback_query
    await query.answer()
    
    config.SISTEMA_AFILIADOS_ATIVO = not config.SISTEMA_AFILIADOS_ATIVO
    config_service.set_config("sistema_afiliados", config.SISTEMA_AFILIADOS_ATIVO, "bool")
    
    status = "✅ ATIVADO" if config.SISTEMA_AFILIADOS_ATIVO else "❌ DESATIVADO"
    
    await query.edit_message_text(
        f"🤝 *SISTEMA DE AFILIADOS*\n\nStatus: {status}",
        reply_markup=botao_voltar("admin_config"),
        parse_mode="Markdown"
    )


def registrar_handlers_admin_settings(application):
    """Registra handlers de configurações"""
    
    settings_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(lambda u, c: menu_configuracoes(u, c, None), pattern="^admin_config$"),
        ],
        states={
            EstadosAdmin.EDITAR_LINK_SUPORTE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: salvar_link_suporte(u, c, None)),
            ],
            EstadosAdmin.CONFIG_VALORES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: salvar_pix_minimo(u, c, None)),
            ],
            EstadosAdmin.DIGITAR_VALOR_MAXIMO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: salvar_pix_maximo(u, c, None)),
            ],
            EstadosAdmin.CONFIG_BONUS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: salvar_bonus_deposito(u, c, None)),
            ],
            EstadosAdmin.CONFIG_EXPIRACAO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: salvar_expiracao_pix(u, c, None)),
            ],
            EstadosAdmin.DEFINIR_COMISSAO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: salvar_comissao_afiliado(u, c, None)),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(lambda u, c: menu_configuracoes(u, c, None), pattern="^admin_config$"),
        ],
        name="admin_settings_conversation",
    )
    
    application.add_handler(settings_conv)
    
    application.add_handler(CallbackQueryHandler(lambda u, c: toggle_manutencao(u, c, None), pattern="^admin_config_manutencao$"))
    application.add_handler(CallbackQueryHandler(lambda u, c: config_link_suporte(u, c, None), pattern="^admin_config_suporte$"))
    application.add_handler(CallbackQueryHandler(lambda u, c: config_pix_minimo(u, c, None), pattern="^admin_config_pix_min$"))
    application.add_handler(CallbackQueryHandler(lambda u, c: config_pix_maximo(u, c, None), pattern="^admin_config_pix_max$"))
    application.add_handler(CallbackQueryHandler(lambda u, c: config_bonus_deposito(u, c, None), pattern="^admin_config_bonus$"))
    application.add_handler(CallbackQueryHandler(lambda u, c: config_expiracao_pix(u, c, None), pattern="^admin_config_expiracao$"))
    application.add_handler(CallbackQueryHandler(lambda u, c: config_comissao_afiliado(u, c, None), pattern="^admin_config_comissao$"))
    application.add_handler(CallbackQueryHandler(lambda u, c: toggle_afiliados(u, c, None), pattern="^admin_toggle_afiliados$"))
    
    logger.info("✅ Handlers de configurações admin registrados!")


__all__ = [
    'menu_configuracoes',
    'toggle_manutencao',
    'config_link_suporte',
    'config_pix_minimo',
    'config_pix_maximo',
    'config_bonus_deposito',
    'config_expiracao_pix',
    'config_comissao_afiliado',
    'toggle_afiliados',
    'registrar_handlers_admin_settings',
    'ConfigService',
]
