"""
Sistema de Recarga - Geração de Pix e Gateway de Pagamento
"""
import logging
import asyncio
import base64
from datetime import datetime, timedelta
from io import BytesIO

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
from ...database.models import Transacao, Usuario, StatusTransacao, TipoTransacao
from ...services.payments import MercadoPagoService
from ...utils.keyboards import (
    menu_recarga_pix,
    teclado_valores_recarga,
    botao_voltar,
)
from ...utils.utils import (
    formatar_moeda,
    formatar_data,
    validar_valor,
    get_status_emoji,
    log_com_contexto
)
from ...utils.states import EstadosRecarga
from ...middlewares import somente_chat_privado, log_atividade

logger = logging.getLogger(__name__)

mp_service = MercadoPagoService()


@somente_chat_privado
@log_atividade("recarga_iniciada")
async def cmd_recharge(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Comando /pix [valor]"""
    user_id = update.effective_user.id
    
    if context.args and len(context.args) > 0:
        valido, valor = validar_valor(context.args[0])
        if valido:
            if valor < config.VALOR_MINIMO_PIX:
                await update.message.reply_text(f"❌ Valor mínimo: {formatar_moeda(config.VALOR_MINIMO_PIX)}")
                return
            if valor > config.VALOR_MAXIMO_PIX:
                await update.message.reply_text(f"❌ Valor máximo: {formatar_moeda(config.VALOR_MAXIMO_PIX)}")
                return
            await gerar_pix(update, context, db, valor)
            return
    
    await mostrar_menu_recarga(update, context, db)


async def mostrar_menu_recarga(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Exibe o menu de recarga"""
    user_id = update.effective_user.id
    db_user = db.get_user(user_id)
    
    if not db_user:
        if update.message:
            await update.message.reply_text("❌ Usuário não encontrado. Use /start")
        return
    
    texto = f"""
💳 *RECARGA DE SALDO*

👤 *Usuário:* {update.effective_user.first_name}
🆔 *ID:* `{user_id}`
💰 *Saldo:* {formatar_moeda(db_user.saldo)}

📊 *Limites:*
• Mínimo: {formatar_moeda(config.VALOR_MINIMO_PIX)}
• Máximo: {formatar_moeda(config.VALOR_MAXIMO_PIX)}
• Bônus: {config.BONUS_DEPOSITO}%

🔹 *Selecione um valor:*
"""
    
    if update.callback_query:
        query = update.callback_query
        await query.edit_message_text(text=texto, reply_markup=teclado_valores_recarga(), parse_mode="Markdown")
    else:
        await update.message.reply_text(text=texto, reply_markup=teclado_valores_recarga(), parse_mode="Markdown")
    
    return EstadosRecarga.SELECIONAR_VALOR


async def selecionar_valor_recarga(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Processa seleção de valor"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    valores = {"recarga_10": 10.0, "recarga_20": 20.0, "recarga_50": 50.0, "recarga_100": 100.0, "recarga_200": 200.0, "recarga_500": 500.0}
    
    if data in valores:
        return await confirmar_valor(update, context, db, valores[data])
    elif data == "recarga_outro":
        await query.edit_message_text(
            text=f"💎 *DIGITE O VALOR*\n\nMínimo: {formatar_moeda(config.VALOR_MINIMO_PIX)}\nMáximo: {formatar_moeda(config.VALOR_MAXIMO_PIX)}\n\n✏️ Digite apenas números:",
            reply_markup=botao_voltar("menu_recarga"),
            parse_mode="Markdown"
        )
        return EstadosRecarga.DIGITAR_VALOR_PERSONALIZADO
    
    return EstadosRecarga.SELECIONAR_VALOR


async def digitar_valor_personalizado(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Recebe valor personalizado"""
    valido, valor = validar_valor(update.message.text)
    
    if not valido:
        await update.message.reply_text("❌ Valor inválido!", reply_markup=botao_voltar("menu_recarga"))
        return EstadosRecarga.DIGITAR_VALOR_PERSONALIZADO
    
    if valor < config.VALOR_MINIMO_PIX:
        await update.message.reply_text(f"❌ Mínimo: {formatar_moeda(config.VALOR_MINIMO_PIX)}", reply_markup=botao_voltar("menu_recarga"))
        return EstadosRecarga.DIGITAR_VALOR_PERSONALIZADO
    
    if valor > config.VALOR_MAXIMO_PIX:
        await update.message.reply_text(f"❌ Máximo: {formatar_moeda(config.VALOR_MAXIMO_PIX)}", reply_markup=botao_voltar("menu_recarga"))
        return EstadosRecarga.DIGITAR_VALOR_PERSONALIZADO
    
    return await confirmar_valor(update, context, db, valor)


async def confirmar_valor(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database, valor: float):
    """Confirma valor"""
    bonus = (valor * config.BONUS_DEPOSITO) / 100
    valor_total = valor + bonus
    
    texto = f"""
💳 *CONFIRMAR RECARGA*

💰 Valor: {formatar_moeda(valor)}
🎁 Bônus ({config.BONUS_DEPOSITO}%): {formatar_moeda(bonus)}
💎 Saldo a receber: {formatar_moeda(valor_total)}

🔹 Confirmar?
"""
    
    keyboard = [[InlineKeyboardButton("✅ CONFIRMAR", callback_data=f"confirmar_recarga_{valor}"), InlineKeyboardButton("❌ CANCELAR", callback_data="menu_recarga")]]
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text=texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    else:
        await update.message.reply_text(text=texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")
    
    return EstadosRecarga.CONFIRMAR_VALOR


@log_atividade("geracao_pix")
async def gerar_pix(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database, valor: float):
    """Gera QR Code Pix"""
    user_id = update.effective_user.id
    
    if update.callback_query:
        await update.callback_query.edit_message_text("🔄 Gerando Pix...", parse_mode="Markdown")
    
    try:
        with db.get_session() as session:
            transacao = Transacao(
                usuario_id=user_id, tipo=TipoTransacao.PIX.value, status=StatusTransacao.PENDENTE.value,
                valor=valor, valor_bonus=(valor * config.BONUS_DEPOSITO) / 100,
                valor_total=valor + (valor * config.BONUS_DEPOSITO) / 100,
                gateway="mercado_pago", data_criacao=datetime.now(),
                data_expiracao=datetime.now() + timedelta(seconds=config.TEMPO_EXPIRACAO_PIX)
            )
            session.add(transacao)
            session.flush()
            transacao_id = transacao.id
        
        pix_data = await mp_service.criar_pix(valor=valor, descricao=f"Recarga {config.NOME_BOT}", external_reference=str(transacao_id))
        
        if not pix_data or 'qr_code' not in pix_data:
            raise Exception("Falha ao gerar QR Code")
        
        with db.get_session() as session:
            trans = session.query(Transacao).get(transacao_id)
            trans.qr_code = pix_data.get('qr_code', '')
            trans.qr_code_base64 = pix_data.get('qr_code_base64', '')
            trans.copia_cola = pix_data.get('copia_cola', '')
            trans.gateway_id = pix_data.get('id', '')
            session.flush()
        
        await exibir_qr_code(update, context, db, transacao_id, pix_data)
        asyncio.create_task(verificar_pagamento_automatico(context, db, transacao_id, user_id))
        log_com_contexto("Pix gerado", user_id=user_id, valor=valor)
        
    except Exception as e:
        logger.error(f"Erro ao gerar Pix: {e}")
        if update.callback_query:
            await update.callback_query.edit_message_text("❌ Erro ao gerar Pix. Tente novamente.", reply_markup=botao_voltar("menu_recarga"), parse_mode="Markdown")
        else:
            await update.message.reply_text("❌ Erro ao gerar Pix. Tente novamente.", reply_markup=botao_voltar("menu_recarga"))
        return EstadosRecarga.MENU_RECARGA


async def exibir_qr_code(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database, transacao_id: int, pix_data: dict):
    """Exibe QR Code"""
    with db.get_session() as session:
        transacao = session.query(Transacao).get(transacao_id)
    
    if not transacao:
        return
    
    tempo_restante = transacao.data_expiracao - datetime.now() if transacao.data_expiracao else timedelta(minutes=5)
    minutos = max(0, tempo_restante.seconds // 60)
    segundos = max(0, tempo_restante.seconds % 60)
    
    texto = f"""
💳 *PIX GERADO!*

💰 Valor: {formatar_moeda(transacao.valor)}
🎁 Bônus: {formatar_moeda(transacao.valor_bonus)}
💎 Receber: {formatar_moeda(transacao.valor_total)}

⏰ Expira em: {minutos}min {segundos}s
🟡 Status: AGUARDANDO

📋 *Pix Copia e Cola:*
`{transacao.copia_cola}`
"""
    
    keyboard = menu_recarga_pix(transacao_id=transacao_id, valor=transacao.valor, copia_cola=transacao.copia_cola)
    
    try:
        qr_bytes = base64.b64decode(transacao.qr_code_base64)
        qr_image = BytesIO(qr_bytes)
        qr_image.name = "pix.png"
        
        if update.callback_query:
            await update.callback_query.message.reply_photo(photo=qr_image, caption=texto, reply_markup=keyboard, parse_mode="Markdown")
            await update.callback_query.delete_message()
        else:
            await update.message.reply_photo(photo=qr_image, caption=texto, reply_markup=keyboard, parse_mode="Markdown")
    except:
        if update.callback_query:
            await update.callback_query.edit_message_text(text=texto, reply_markup=keyboard, parse_mode="Markdown")
        else:
            await update.message.reply_text(text=texto, reply_markup=keyboard, parse_mode="Markdown")
    
    return EstadosRecarga.AGUARDAR_PAGAMENTO


async def verificar_pagamento(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Verifica pagamento"""
    query = update.callback_query
    await query.answer("🔄 Verificando...")
    
    transacao_id = int(query.data.split("_")[-1])
    
    with db.get_session() as session:
        transacao = session.query(Transacao).get(transacao_id)
    
    if not transacao:
        await query.edit_message_text("❌ Transação não encontrada.", reply_markup=botao_voltar("menu_recarga"))
        return
    
    if transacao.status == StatusTransacao.APROVADO.value:
        await processar_pagamento_aprovado(update, context, db, transacao)
        return
    
    try:
        status_mp = await mp_service.verificar_pagamento(transacao.gateway_id)
        if status_mp == "approved":
            await processar_pagamento_aprovado(update, context, db, transacao)
        else:
            await query.answer("⏰ Pagamento ainda não confirmado.", show_alert=True)
    except:
        await query.answer("Erro ao verificar.", show_alert=True)


async def verificar_pagamento_automatico(context, db, transacao_id, user_id, tentativas=30):
    """Verificação automática"""
    for i in range(tentativas):
        await asyncio.sleep(10)
        with db.get_session() as session:
            transacao = session.query(Transacao).get(transacao_id)
            if not transacao or transacao.status != StatusTransacao.PENDENTE.value:
                break
            if datetime.now() > transacao.data_expiracao:
                transacao.status = StatusTransacao.EXPIRADO.value
                session.flush()
                try:
                    await context.bot.send_message(chat_id=user_id, text="⏰ Pix expirado.", reply_markup=botao_voltar("menu_recarga"))
                except:
                    pass
                break
            try:
                status_mp = await mp_service.verificar_pagamento(transacao.gateway_id)
                if status_mp == "approved":
                    await aprovar_transacao(session, transacao)
                    try:
                        await context.bot.send_message(chat_id=user_id, text=f"✅ Pagamento aprovado! Saldo: {formatar_moeda(transacao.valor_total)}", parse_mode="Markdown")
                    except:
                        pass
                    break
            except:
                continue


async def aprovar_transacao(session, transacao):
    """Aprova transação"""
    transacao.status = StatusTransacao.APROVADO.value
    transacao.data_aprovacao = datetime.now()
    usuario = session.query(Usuario).filter_by(telegram_id=transacao.usuario_id).first()
    if usuario:
        usuario.saldo += transacao.valor_total
        session.flush()


async def processar_pagamento_aprovado(update, context, db, transacao):
    """Exibe pagamento aprovado"""
    texto = f"""
✅ *PAGAMENTO APROVADO!*

💰 Valor: {formatar_moeda(transacao.valor)}
🎁 Bônus: {formatar_moeda(transacao.valor_bonus)}
💎 Adicionado: {formatar_moeda(transacao.valor_total)}
"""
    keyboard = [[InlineKeyboardButton("🛒 IR PARA LOJA", callback_data="menu_loja")], [InlineKeyboardButton("🔙 MENU", callback_data="menu_principal")]]
    await update.callback_query.edit_message_text(text=texto, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")


async def copiar_pix(update, context, db):
    """Copia Pix"""
    query = update.callback_query
    transacao_id = int(query.data.split("_")[-1])
    with db.get_session() as session:
        transacao = session.query(Transacao).get(transacao_id)
    if transacao and transacao.copia_cola:
        await query.answer("📋 Código copiado!", show_alert=True)
        await query.message.reply_text(f"`{transacao.copia_cola}`", parse_mode="Markdown")


async def cancelar_pix(update, context, db):
    """Cancela Pix"""
    query = update.callback_query
    transacao_id = int(query.data.split("_")[-1])
    with db.get_session() as session:
        transacao = session.query(Transacao).get(transacao_id)
        if transacao and transacao.status == StatusTransacao.PENDENTE.value:
            transacao.status = StatusTransacao.CANCELADO.value
            transacao.data_cancelamento = datetime.now()
            session.flush()
            await query.edit_message_text("❌ Pix cancelado.", reply_markup=botao_voltar("menu_recarga"), parse_mode="Markdown")


def registrar_handlers_recharge(application):
    """Registra handlers"""
    recharge_conv = ConversationHandler(
        entry_points=[
            CommandHandler("pix", lambda u, c: cmd_recharge(u, c, None)),
            CallbackQueryHandler(lambda u, c: mostrar_menu_recarga(u, c, None), pattern="^menu_recarga$"),
        ],
        states={
            EstadosRecarga.SELECIONAR_VALOR: [CallbackQueryHandler(lambda u, c: selecionar_valor_recarga(u, c, None), pattern="^recarga_")],
            EstadosRecarga.DIGITAR_VALOR_PERSONALIZADO: [MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: digitar_valor_personalizado(u, c, None))],
            EstadosRecarga.CONFIRMAR_VALOR: [CallbackQueryHandler(lambda u, c: gerar_pix_conv(u, c, None), pattern="^confirmar_recarga_")],
            EstadosRecarga.AGUARDAR_PAGAMENTO: [
                CallbackQueryHandler(lambda u, c: verificar_pagamento(u, c, None), pattern="^verificar_pagamento_"),
                CallbackQueryHandler(lambda u, c: copiar_pix(u, c, None), pattern="^copiar_pix_"),
                CallbackQueryHandler(lambda u, c: cancelar_pix(u, c, None), pattern="^cancelar_pix_"),
            ],
        },
        fallbacks=[CallbackQueryHandler(lambda u, c: mostrar_menu_recarga(u, c, None), pattern="^menu_recarga$")],
        name="recharge_conversation",
    )
    application.add_handler(recharge_conv)
    logger.info("✅ Handlers de recarga registrados!")


async def gerar_pix_conv(update, context, db):
    """Wrapper"""
    valor = float(update.callback_query.data.split("_")[-1])
    await gerar_pix(update, context, db, valor)


__all__ = ['cmd_recharge', 'mostrar_menu_recarga', 'registrar_handlers_recharge', 'gerar_pix']
