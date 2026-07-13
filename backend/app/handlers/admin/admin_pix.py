"""
Painel Admin - Configuração do PIX e Gateway de Pagamento
"""
import logging
from datetime import datetime

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
from ...services.payments import MercadoPagoService
from ...utils.keyboards import admin_menu_pagamentos, botao_voltar
from ...utils.utils import formatar_moeda, log_com_contexto
from ...utils.states import EstadosAdminPagamentos
from ...middlewares import somente_admin, log_atividade

logger = logging.getLogger(__name__)

mp_service = MercadoPagoService()


@somente_admin
@log_atividade("admin_menu_pix")
async def menu_pix(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Menu de configurações do PIX"""
    query = update.callback_query
    await query.answer()
    
    texto = f"""
💳 *CONFIGURAÇÕES DO PIX*

🔑 *API Mercado Pago:*
• Token: {'✅ Configurado' if config.MP_ACCESS_TOKEN else '❌ Não configurado'}
• Public Key: {'✅ Configurada' if config.MP_PUBLIC_KEY else '❌ Não configurada'}

💰 *Valores:*
• Mínimo: {formatar_moeda(config.VALOR_MINIMO_PIX)}
• Máximo: {formatar_moeda(config.VALOR_MAXIMO_PIX)}

⏱️ *Expiração:* {config.TEMPO_EXPIRACAO_PIX}s ({config.TEMPO_EXPIRACAO_PIX // 60} min)

🎁 *Bônus de Depósito:* {config.BONUS_DEPOSITO}%

🔹 Selecione uma opção:
"""
    
    await query.edit_message_text(
        text=texto,
        reply_markup=admin_menu_pagamentos(),
        parse_mode="Markdown"
    )
    
    return EstadosAdminPagamentos.MENU_PAGAMENTOS


@somente_admin
async def configurar_api(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Solicita token do Mercado Pago"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "🔑 *CONFIGURAR API MERCADO PAGO*\n\n"
        "✏️ *Digite o Access Token:*\n\n"
        "💡 Obtenha em: https://www.mercadopago.com.br/settings/account/credentials\n\n"
        "Formato: APP_USR-xxxxxxxxxxxxx",
        reply_markup=botao_voltar("admin_pix"),
        parse_mode="Markdown"
    )
    
    return EstadosAdminPagamentos.DIGITAR_TOKEN


@somente_admin
@log_atividade("admin_config_token")
async def salvar_token(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Salva token do Mercado Pago"""
    token = update.message.text.strip()
    
    if not token.startswith("APP_USR-") and not token.startswith("TEST-"):
        await update.message.reply_text(
            "❌ Token inválido. Deve começar com APP_USR- ou TEST-",
            reply_markup=botao_voltar("admin_pix")
        )
        return EstadosAdminPagamentos.DIGITAR_TOKEN
    
    config.MP_ACCESS_TOKEN = token
    mp_service.access_token = token
    mp_service.inicializar_sdk()
    
    sucesso, msg = mp_service.testar_conexao()
    
    await update.message.reply_text(
        f"{'✅' if sucesso else '❌'} {msg}",
        reply_markup=botao_voltar("admin_pix")
    )
    
    log_com_contexto("Token Mercado Pago atualizado")
    return ConversationHandler.END


@somente_admin
async def testar_api(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Testa conexão com API"""
    query = update.callback_query
    await query.answer("🔄 Testando conexão...")
    
    sucesso, msg = mp_service.testar_conexao()
    
    await query.edit_message_text(
        f"{'✅' if sucesso else '❌'} {msg}",
        reply_markup=botao_voltar("admin_pix"),
        parse_mode="Markdown"
    )


@somente_admin
async def config_valor_minimo(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Solicita valor mínimo do Pix"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        f"💰 *VALOR MÍNIMO DO PIX*\n\n"
        f"Atual: {formatar_moeda(config.VALOR_MINIMO_PIX)}\n\n"
        "✏️ Digite o novo valor mínimo:",
        reply_markup=botao_voltar("admin_pix"),
        parse_mode="Markdown"
    )
    
    return EstadosAdminPagamentos.DIGITAR_VALOR_MINIMO


@somente_admin
async def salvar_valor_minimo(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Salva valor mínimo"""
    try:
        valor = float(update.message.text.replace(",", "."))
        if valor < 5:
            await update.message.reply_text("❌ Mínimo: R$ 5,00")
            return EstadosAdminPagamentos.DIGITAR_VALOR_MINIMO
        
        config.VALOR_MINIMO_PIX = valor
        await update.message.reply_text(
            f"✅ Valor mínimo: {formatar_moeda(valor)}",
            reply_markup=botao_voltar("admin_pix")
        )
    except ValueError:
        await update.message.reply_text("❌ Valor inválido.")
        return EstadosAdminPagamentos.DIGITAR_VALOR_MINIMO
    
    return ConversationHandler.END


@somente_admin
async def config_valor_maximo(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Solicita valor máximo"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        f"💰 *VALOR MÁXIMO DO PIX*\n\n"
        f"Atual: {formatar_moeda(config.VALOR_MAXIMO_PIX)}\n\n"
        "✏️ Digite o novo valor máximo:",
        reply_markup=botao_voltar("admin_pix"),
        parse_mode="Markdown"
    )
    
    return EstadosAdminPagamentos.DIGITAR_VALOR_MAXIMO


@somente_admin
async def salvar_valor_maximo(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Salva valor máximo"""
    try:
        valor = float(update.message.text.replace(",", "."))
        config.VALOR_MAXIMO_PIX = valor
        await update.message.reply_text(
            f"✅ Valor máximo: {formatar_moeda(valor)}",
            reply_markup=botao_voltar("admin_pix")
        )
    except ValueError:
        await update.message.reply_text("❌ Valor inválido.")
        return EstadosAdminPagamentos.DIGITAR_VALOR_MAXIMO
    
    return ConversationHandler.END


@somente_admin
async def config_expiracao(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Solicita tempo de expiração"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        f"⏱️ *TEMPO DE EXPIRAÇÃO*\n\n"
        f"Atual: {config.TEMPO_EXPIRACAO_PIX}s ({config.TEMPO_EXPIRACAO_PIX // 60} min)\n\n"
        "✏️ Digite o tempo em segundos (mínimo 60):",
        reply_markup=botao_voltar("admin_pix"),
        parse_mode="Markdown"
    )
    
    return EstadosAdminPagamentos.DIGITAR_TEMPO_EXPIRACAO


@somente_admin
async def salvar_expiracao(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Salva tempo de expiração"""
    try:
        tempo = int(update.message.text)
        if tempo < 60:
            await update.message.reply_text("❌ Mínimo: 60 segundos")
            return EstadosAdminPagamentos.DIGITAR_TEMPO_EXPIRACAO
        
        config.TEMPO_EXPIRACAO_PIX = tempo
        await update.message.reply_text(
            f"✅ Expiração: {tempo}s ({tempo // 60} min)",
            reply_markup=botao_voltar("admin_pix")
        )
    except ValueError:
        await update.message.reply_text("❌ Valor inválido.")
        return EstadosAdminPagamentos.DIGITAR_TEMPO_EXPIRACAO
    
    return ConversationHandler.END


@somente_admin
async def config_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Solicita bônus de depósito"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        f"🎁 *BÔNUS DE DEPÓSITO*\n\n"
        f"Atual: {config.BONUS_DEPOSITO}%\n\n"
        "✏️ Digite a porcentagem (0-100):",
        reply_markup=botao_voltar("admin_pix"),
        parse_mode="Markdown"
    )
    
    return EstadosAdminPagamentos.DIGITAR_PORCENTAGEM_BONUS


@somente_admin
async def salvar_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Salva bônus"""
    try:
        bonus = float(update.message.text.replace(",", "."))
        if bonus < 0 or bonus > 100:
            await update.message.reply_text("❌ Valor entre 0 e 100")
            return EstadosAdminPagamentos.DIGITAR_PORCENTAGEM_BONUS
        
        config.BONUS_DEPOSITO = bonus
        await update.message.reply_text(
            f"✅ Bônus: {bonus}%",
            reply_markup=botao_voltar("admin_pix")
        )
    except ValueError:
        await update.message.reply_text("❌ Valor inválido.")
        return EstadosAdminPagamentos.DIGITAR_PORCENTAGEM_BONUS
    
    return ConversationHandler.END


def registrar_handlers_admin_pix(application):
    """Registra handlers de configuração PIX"""
    
    pix_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(lambda u, c: menu_pix(u, c, None), pattern="^admin_pix$"),
        ],
        states={
            EstadosAdminPagamentos.DIGITAR_TOKEN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: salvar_token(u, c, None)),
            ],
            EstadosAdminPagamentos.DIGITAR_VALOR_MINIMO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: salvar_valor_minimo(u, c, None)),
            ],
            EstadosAdminPagamentos.DIGITAR_VALOR_MAXIMO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: salvar_valor_maximo(u, c, None)),
            ],
            EstadosAdminPagamentos.DIGITAR_TEMPO_EXPIRACAO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: salvar_expiracao(u, c, None)),
            ],
            EstadosAdminPagamentos.DIGITAR_PORCENTAGEM_BONUS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: salvar_bonus(u, c, None)),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(lambda u, c: menu_pix(u, c, None), pattern="^admin_pix$"),
        ],
        name="admin_pix_conversation",
    )
    
    application.add_handler(pix_conv)
    
    application.add_handler(CallbackQueryHandler(lambda u, c: configurar_api(u, c, None), pattern="^admin_config_api$"))
    application.add_handler(CallbackQueryHandler(lambda u, c: testar_api(u, c, None), pattern="^admin_testar_api$"))
    application.add_handler(CallbackQueryHandler(lambda u, c: config_valor_minimo(u, c, None), pattern="^admin_config_valor_min$"))
    application.add_handler(CallbackQueryHandler(lambda u, c: config_valor_maximo(u, c, None), pattern="^admin_config_valor_max$"))
    application.add_handler(CallbackQueryHandler(lambda u, c: config_expiracao(u, c, None), pattern="^admin_config_expiracao$"))
    application.add_handler(CallbackQueryHandler(lambda u, c: config_bonus(u, c, None), pattern="^admin_config_bonus$"))
    
    logger.info("✅ Handlers de configuração PIX registrados!")


__all__ = [
    'menu_pix',
    'configurar_api',
    'salvar_token',
    'testar_api',
    'config_valor_minimo',
    'config_valor_maximo',
    'config_expiracao',
    'config_bonus',
    'registrar_handlers_admin_pix',
]
