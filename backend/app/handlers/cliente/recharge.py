"""
Sistema de Recarga - Geração de Pix e Gateway de Pagamento
"""
import logging
import asyncio
from datetime import datetime, timedelta
from typing import Optional
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
from ...database.models import Transacao, Usuario, StatusTransacao, TipoTransacao
from ...services.pagamento import MercadoPagoService
from ...utils.keyboards import (
    menu_recarga,
    menu_recarga_pix,
    teclado_valores_recarga,
    botao_voltar,
    botoes_confirmacao
)
from ...utils.utils import (
    formatar_moeda,
    formatar_data,
    gerar_qr_code_pix,
    validar_valor,
    get_status_emoji,
    log_com_contexto
)
from ...utils.states import EstadosRecarga
from ...middlewares import somente_chat_privado, log_atividade

logger = logging.getLogger(__name__)

# ============================================
# SERVIÇO DE PAGAMENTO
# ============================================

mp_service = MercadoPagoService()


# ============================================
// ... continua na próxima parte

# ============================================
# HANDLER PRINCIPAL DE RECARGA
# ============================================

@somente_chat_privado
@log_atividade("recarga_iniciada")
async def cmd_recharge(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """
    Comando /pix [valor] - Inicia recarga direta
    """
    user = update.effective_user
    user_id = user.id
    
    # Verifica se tem valor no comando
    if context.args and len(context.args) > 0:
        valor_str = context.args[0]
        valido, valor = validar_valor(valor_str)
        
        if valido:
            # Valida limites
            if valor < config.VALOR_MINIMO_PIX:
                await update.message.reply_text(
                    f"❌ Valor mínimo para recarga: {formatar_moeda(config.VALOR_MINIMO_PIX)}"
                )
                return
            
            if valor > config.VALOR_MAXIMO_PIX:
                await update.message.reply_text(
                    f"❌ Valor máximo para recarga: {formatar_moeda(config.VALOR_MAXIMO_PIX)}"
                )
                return
            
            # Gera Pix diretamente
            await gerar_pix(update, context, db, valor)
            return
    
    # Se não tem valor, mostra menu de recarga
    await mostrar_menu_recarga(update, context, db)


async def mostrar_menu_recarga(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Exibe o menu de recarga"""
    user_id = update.effective_user.id
    db_user = db.get_user(user_id)
    
    if not db_user:
        await update.message.reply_text("❌ Usuário não encontrado. Use /start")
        return
    
    # Mensagem do menu
    texto = f"""
💳 *RECARGA DE SALDO*

👤 *Usuário:* {update.effective_user.first_name}
🆔 *Seu ID:* `{user_id}`
💰 *Saldo Atual:* {formatar_moeda(db_user.saldo)}

📊 *Limites:*
• Mínimo: {formatar_moeda(config.VALOR_MINIMO_PIX)}
• Máximo: {formatar_moeda(config.VALOR_MAXIMO_PIX)}
• Bônus: {config.BONUS_DEPOSITO}% de acréscimo

🎁 *Bônus de recarga ativo!*

🔹 *Selecione um valor ou digite:*
"""
    
    # Se for callback query
    if update.callback_query:
        query = update.callback_query
        await query.edit_message_text(
            text=texto,
            reply_markup=teclado_valores_recarga(),
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            text=texto,
            reply_markup=teclado_valores_recarga(),
            parse_mode="Markdown"
        )
    
    return EstadosRecarga.SELECIONAR_VALOR


# ============================================
// ... continua na próxima parte

# ============================================
# SELEÇÃO DE VALOR
# ============================================

async def selecionar_valor_recarga(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Processa a seleção do valor de recarga"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    valor = None
    
    # Valores pré-definidos
    valores_predefinidos = {
        "recarga_10": 10.0,
        "recarga_20": 20.0,
        "recarga_50": 50.0,
        "recarga_100": 100.0,
        "recarga_200": 200.0,
        "recarga_500": 500.0,
    }
    
    if data in valores_predefinidos:
        valor = valores_predefinidos[data]
    elif data == "recarga_outro":
        # Solicita valor personalizado
        await query.edit_message_text(
            text="""
💎 *DIGITE O VALOR DA RECARGA*

📊 *Limites:*
• Mínimo: {formatar_moeda(config.VALOR_MINIMO_PIX)}
• Máximo: {formatar_moeda(config.VALOR_MAXIMO_PIX)}

✏️ *Digite apenas números:*
Exemplo: 50.00 ou 50
""".format(
                formatar_moeda=formatar_moeda,
                VALOR_MINIMO_PIX=config.VALOR_MINIMO_PIX,
                VALOR_MAXIMO_PIX=config.VALOR_MAXIMO_PIX
            ),
            reply_markup=botao_voltar("menu_recarga"),
            parse_mode="Markdown"
        )
        return EstadosRecarga.DIGITAR_VALOR_PERSONALIZADO
    
    if valor:
        return await confirmar_valor(update, context, db, valor)
    
    return EstadosRecarga.SELECIONAR_VALOR


async def digitar_valor_personalizado(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Recebe o valor personalizado digitado pelo usuário"""
    user_id = update.effective_user.id
    texto = update.message.text
    
    if texto == "🔙 VOLTAR":
        return await mostrar_menu_recarga(update, context, db)
    
    valido, valor = validar_valor(texto)
    
    if not valido:
        await update.message.reply_text(
            "❌ *Valor inválido!*\n\n"
            "Digite apenas números.\n"
            "Exemplo: 50.00 ou 50",
            reply_markup=botao_voltar("menu_recarga"),
            parse_mode="Markdown"
        )
        return EstadosRecarga.DIGITAR_VALOR_PERSONALIZADO
    
    # Valida limites
    if valor < config.VALOR_MINIMO_PIX:
        await update.message.reply_text(
            f"❌ Valor mínimo: {formatar_moeda(config.VALOR_MINIMO_PIX)}",
            reply_markup=botao_voltar("menu_recarga"),
            parse_mode="Markdown"
        )
        return EstadosRecarga.DIGITAR_VALOR_PERSONALIZADO
    
    if valor > config.VALOR_MAXIMO_PIX:
        await update.message.reply_text(
            f"❌ Valor máximo: {formatar_moeda(config.VALOR_MAXIMO_PIX)}",
            reply_markup=botao_voltar("menu_recarga"),
            parse_mode="Markdown"
        )
        return EstadosRecarga.DIGITAR_VALOR_PERSONALIZADO
    
    return await confirmar_valor(update, context, db, valor)


# ============================================
// ... continua na próxima parte

# ============================================
# CONFIRMAÇÃO DO VALOR
# ============================================

async def confirmar_valor(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database, valor: float):
    """Confirma o valor da recarga antes de gerar o Pix"""
    user_id = update.effective_user.id
    
    # Calcula bônus
    bonus = (valor * config.BONUS_DEPOSITO) / 100
    valor_total = valor + bonus
    
    texto = f"""
💳 *CONFIRMAR RECARGA*

💰 *Valor da Recarga:* {formatar_moeda(valor)}
🎁 *Bônus ({config.BONUS_DEPOSITO}%):* {formatar_moeda(bonus)}
💎 *Saldo a Receber:* {formatar_moeda(valor_total)}

🔹 *Confirmar pagamento?*
"""
    
    keyboard = [
        [
            InlineKeyboardButton("✅ CONFIRMAR", callback_data=f"confirmar_recarga_{valor}"),
            InlineKeyboardButton("❌ CANCELAR", callback_data="menu_recarga")
        ]
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
    
    return EstadosRecarga.CONFIRMAR_VALOR


# ============================================
// ... continua na próxima parte

# ============================================
# GERAÇÃO DO PIX
# ============================================

@log_atividade("geracao_pix")
async def gerar_pix(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database, valor: float):
    """
    Gera QR Code Pix via Mercado Pago
    
    Args:
        update: Update do Telegram
        context: Contexto
        db: Database
        valor: Valor da recarga
    """
    user = update.effective_user
    user_id = user.id
    
    # Mensagem de processamento
    if update.callback_query:
        await update.callback_query.edit_message_text("🔄 *Gerando Pix...*", parse_mode="Markdown")
    
    try:
        # Cria transação no banco
        with db.get_session() as session:
            transacao = Transacao(
                usuario_id=user_id,
                tipo=TipoTransacao.PIX.value,
                status=StatusTransacao.PENDENTE.value,
                valor=valor,
                valor_bonus=(valor * config.BONUS_DEPOSITO) / 100,
                valor_total=valor + (valor * config.BONUS_DEPOSITO) / 100,
                gateway="mercado_pago",
                data_criacao=datetime.now(),
                data_expiracao=datetime.now() + timedelta(seconds=config.TEMPO_EXPIRACAO_PIX)
            )
            session.add(transacao)
            session.flush()
            transacao_id = transacao.id
        
        # Gera Pix no Mercado Pago
        pix_data = await mp_service.criar_pix(
            valor=valor,
            descricao=f"Recarga {config.NOME_BOT} - ID: {user_id}",
            external_reference=str(transacao_id)
        )
        
        if not pix_data or 'qr_code' not in pix_data:
            raise Exception("Falha ao gerar QR Code")
        
        # Atualiza transação com dados do Pix
        with db.get_session() as session:
            trans = session.query(Transacao).get(transacao_id)
            trans.qr_code = pix_data.get('qr_code', '')
            trans.qr_code_base64 = pix_data.get('qr_code_base64', '')
            trans.copia_cola = pix_data.get('copia_cola', '')
            trans.gateway_id = pix_data.get('id', '')
            session.flush()
        
        # Exibe QR Code para o usuário
        await exibir_qr_code(update, context, db, transacao_id, pix_data)
        
        # Agenda verificação automática
        asyncio.create_task(verificar_pagamento_automatico(
            context, db, transacao_id, user_id
        ))
        
        log_com_contexto(
            "Pix gerado com sucesso",
            user_id=user_id,
            valor=valor,
            transacao_id=transacao_id
        )
        
    except Exception as e:
        logger.error(f"❌ Erro ao gerar Pix: {e}")
        
        texto_erro = """
❌ *ERRO AO GERAR PIX*

Não foi possível processar sua recarga no momento.
Por favor, tente novamente mais tarde.

Se o problema persistir, contate o suporte.
"""
        if update.callback_query:
            await update.callback_query.edit_message_text(
                text=texto_erro,
                reply_markup=botao_voltar("menu_recarga"),
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                text=texto_erro,
                reply_markup=botao_voltar("menu_recarga"),
                parse_mode="Markdown"
            )
        
        return EstadosRecarga.MENU_RECARGA


# ============================================
// ... continua na próxima parte

# ============================================
# EXIBIÇÃO DO QR CODE
# ============================================

async def exibir_qr_code(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database, 
                         transacao_id: int, pix_data: dict):
    """Exibe o QR Code e informações do Pix"""
    
    user_id = update.effective_user.id
    
    with db.get_session() as session:
        transacao = session.query(Transacao).get(transacao_id)
    
    if not transacao:
        return
    
    # Calcula tempo restante
    tempo_restante = transacao.data_expiracao - datetime.now()
    minutos = tempo_restante.seconds // 60
    segundos = tempo_restante.seconds % 60
    
    texto = f"""
💳 *PIX GERADO COM SUCESSO!*

💰 *Valor:* {formatar_moeda(transacao.valor)}
🎁 *Bônus:* {formatar_moeda(transacao.valor_bonus)}
💎 *Saldo a Receber:* {formatar_moeda(transacao.valor_total)}

⏰ *Expira em:* {minutos}min {segundos}s
📅 *Data:* {formatar_data(transacao.data_criacao)}

🟡 *Status:* AGUARDANDO PAGAMENTO

🔹 *Opções de pagamento:*
• Escaneie o QR Code abaixo
• Ou use o Pix Copia e Cola
"""
    
    keyboard = menu_recarga_pix(
        transacao_id=transacao_id,
        valor=transacao.valor,
        copia_cola=transacao.copia_cola
    )
    
    # Envia QR Code como imagem
    try:
        # Gera QR Code do base64
        import base64
        from io import BytesIO
        
        qr_bytes = base64.b64decode(transacao.qr_code_base64)
        qr_image = BytesIO(qr_bytes)
        qr_image.name = "pix_qrcode.png"
        
        if update.callback_query:
            await update.callback_query.message.reply_photo(
                photo=qr_image,
                caption=texto,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
            await update.callback_query.delete_message()
        else:
            await update.message.reply_photo(
                photo=qr_image,
                caption=texto,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
        
    except Exception as e:
        logger.error(f"Erro ao enviar QR Code: {e}")
        
        # Se falhar, envia apenas texto com copia e cola
        texto += f"\n📋 *Pix Copia e Cola:*\n`{transacao.copia_cola}`"
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                text=texto,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                text=texto,
                reply_markup=keyboard,
                parse_mode="Markdown"
            )
    
    return EstadosRecarga.AGUARDAR_PAGAMENTO


# ============================================
// ... continua na próxima parte

# ============================================
# VERIFICAÇÃO DE PAGAMENTO
# ============================================

async def verificar_pagamento(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Verifica status do pagamento quando usuário clica em 'Já Paguei'"""
    query = update.callback_query
    await query.answer("🔄 Verificando pagamento...")
    
    data = query.data
    transacao_id = int(data.split("_")[-1])
    
    with db.get_session() as session:
        transacao = session.query(Transacao).get(transacao_id)
    
    if not transacao:
        await query.edit_message_text(
            "❌ Transação não encontrada.",
            reply_markup=botao_voltar("menu_recarga")
        )
        return
    
    # Verifica se já não foi processada
    if transacao.status == StatusTransacao.APROVADO.value:
        await processar_pagamento_aprovado(update, context, db, transacao)
        return
    
    if transacao.status == StatusTransacao.EXPIRADO.value:
        await query.edit_message_text(
            "⏰ Este Pix expirou. Gere um novo.",
            reply_markup=botao_voltar("menu_recarga")
        )
        return
    
    # Verifica status no Mercado Pago
    try:
        status_mp = await mp_service.verificar_pagamento(transacao.gateway_id)
        
        if status_mp == "approved":
            await processar_pagamento_aprovado(update, context, db, transacao)
        elif status_mp == "pending":
            # Ainda pendente
            tempo_restante = transacao.data_expiracao - datetime.now()
            minutos = max(0, tempo_restante.seconds // 60)
            
            await query.answer(
                f"⏰ Pagamento ainda não confirmado.\n"
                f"Tempo restante: {minutos}min",
                show_alert=True
            )
        else:
            await query.answer(
                "❌ Pagamento não aprovado. Tente novamente.",
                show_alert=True
            )
            
    except Exception as e:
        logger.error(f"Erro ao verificar pagamento: {e}")
        await query.answer(
            "Erro ao verificar. Tente novamente em instantes.",
            show_alert=True
        )


async def verificar_pagamento_automatico(context: ContextTypes.DEFAULT_TYPE, db: Database,
                                        transacao_id: int, user_id: int, tentativas: int = 30):
    """
    Verifica pagamento automaticamente a cada 10 segundos
    
    Args:
        context: Contexto do bot
        db: Database
        transacao_id: ID da transação
        user_id: ID do usuário
        tentativas: Número máximo de tentativas
    """
    for i in range(tentativas):
        await asyncio.sleep(10)  # Aguarda 10 segundos
        
        with db.get_session() as session:
            transacao = session.query(Transacao).get(transacao_id)
            
            if not transacao:
                break
            
            # Se já foi processada
            if transacao.status != StatusTransacao.PENDENTE.value:
                break
            
            # Se expirou
            if datetime.now() > transacao.data_expiracao:
                transacao.status = StatusTransacao.EXPIRADO.value
                session.flush()
                
                try:
                    await context.bot.send_message(
                        chat_id=user_id,
                        text="⏰ *PIX EXPIRADO*\n\n"
                             "Seu Pix expirou. Gere um novo para continuar.",
                        reply_markup=botao_voltar("menu_recarga"),
                        parse_mode="Markdown"
                    )
                except:
                    pass
                break
            
            # Verifica no Mercado Pago
            try:
                status_mp = await mp_service.verificar_pagamento(transacao.gateway_id)
                
                if status_mp == "approved":
                    # Pagamento aprovado!
                    await aprovar_transacao(session, transacao, db)
                    
                    # Notifica usuário
                    try:
                        texto = f"""
✅ *PAGAMENTO APROVADO!*

💰 *Valor:* {formatar_moeda(transacao.valor)}
🎁 *Bônus:* {formatar_moeda(transacao.valor_bonus)}
💎 *Saldo Adicionado:* {formatar_moeda(transacao.valor_total)}

🔹 Seu saldo já está disponível!
"""
                        await context.bot.send_message(
                            chat_id=user_id,
                            text=texto,
                            parse_mode="Markdown"
                        )
                    except:
                        pass
                    break
                    
            except Exception as e:
                logger.error(f"Erro na verificação automática: {e}")
                continue


# ============================================
// ... continua na próxima parte

# ============================================
# PROCESSAMENTO DE PAGAMENTO
# ============================================

async def aprovar_transacao(session, transacao: Transacao, db: Database):
    """
    Aprova uma transação e adiciona saldo ao usuário
    
    Args:
        session: Sessão do banco
        transacao: Transação a ser aprovada
        db: Database
    """
    # Atualiza status da transação
    transacao.status = StatusTransacao.APROVADO.value
    transacao.data_aprovacao = datetime.now()
    
    # Adiciona saldo ao usuário
    usuario = session.query(Usuario).filter_by(telegram_id=transacao.usuario_id).first()
    
    if usuario:
        valor_total = transacao.valor_total
        usuario.saldo += valor_total
        
        session.flush()
        
        log_com_contexto(
            "Pagamento aprovado",
            user_id=usuario.telegram_id,
            valor=transacao.valor,
            bonus=transacao.valor_bonus,
            transacao_id=transacao.id
        )
        
        # Se usuário foi indicado por afiliado, gera comissão
        if usuario.afiliado_por:
            await gerar_comissao_afiliado(session, usuario, transacao.valor)


async def gerar_comissao_afiliado(session, usuario: Usuario, valor_recarga: float):
    """
    Gera comissão para o afiliado
    
    Args:
        session: Sessão do banco
        usuario: Usuário que fez a recarga
        valor_recarga: Valor da recarga
    """
    afiliador = session.query(Usuario).get(usuario.afiliado_por)
    
    if afiliador and config.SISTEMA_AFILIADOS_ATIVO:
        comissao = (valor_recarga * config.COMISSAO_AFILIADO) / 100
        
        # Adiciona comissão ao afiliador
        afiliador.comissao_acumulada += comissao
        afiliador.saldo += comissao  # Opcional: adiciona direto no saldo
        
        # Registra transação de comissão
        transacao_comissao = Transacao(
            usuario_id=afiliador.telegram_id,
            tipo=TipoTransacao.COMISSAO.value,
            status=StatusTransacao.APROVADO.value,
            valor=comissao,
            valor_total=comissao,
            descricao=f"Comissão sobre recarga de {usuario.nome or usuario.telegram_id}",
            data_criacao=datetime.now(),
            data_aprovacao=datetime.now()
        )
        session.add(transacao_comissao)
        session.flush()
        
        log_com_contexto(
            "Comissão gerada",
            afiliador_id=afiliador.telegram_id,
            valor=comissao,
            origem=usuario.telegram_id
        )


async def processar_pagamento_aprovado(update: Update, context: ContextTypes.DEFAULT_TYPE, 
                                       db: Database, transacao: Transacao):
    """Exibe mensagem de pagamento aprovado"""
    
    texto = f"""
✅ *PAGAMENTO APROVADO!*

💰 *Valor:* {formatar_moeda(transacao.valor)}
🎁 *Bônus:* {formatar_moeda(transacao.valor_bonus)}
💎 *Saldo Adicionado:* {formatar_moeda(transacao.valor_total)}

📅 *Data:* {formatar_data(transacao.data_aprovacao or datetime.now())}

🟢 *Status:* APROVADO

🔹 Seu saldo já está disponível para compras!
"""
    
    # Busca saldo atualizado
    with db.get_session() as session:
        usuario = session.query(Usuario).filter_by(telegram_id=transacao.usuario_id).first()
        if usuario:
            texto += f"\n💰 *Saldo Atual:* {formatar_moeda(usuario.saldo)}"
    
    keyboard = [
        [InlineKeyboardButton("🛒 IR PARA LOJA", callback_data="menu_loja")],
        [InlineKeyboardButton("🔙 MENU PRINCIPAL", callback_data="menu_principal")]
    ]
    
    await update.callback_query.edit_message_text(
        text=texto,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


# ============================================
// ... continua na próxima parte

# ============================================
# COPIAR PIX E CANCELAMENTO
# ============================================

async def copiar_pix(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Copia código Pix"""
    query = update.callback_query
    data = query.data
    transacao_id = int(data.split("_")[-1])
    
    with db.get_session() as session:
        transacao = session.query(Transacao).get(transacao_id)
    
    if transacao and transacao.copia_cola:
        await query.answer(
            "📋 Código Pix copiado!\n\n"
            "Cole no app do seu banco para pagar.",
            show_alert=True
        )
        
        # Envia código como mensagem para facilitar cópia
        await query.message.reply_text(
            f"📋 *CÓDIGO PIX COPIA E COLA*\n\n"
            f"`{transacao.copia_cola}`\n\n"
            f"⚠️ *Válido até:* {formatar_data(transacao.data_expiracao)}",
            parse_mode="Markdown"
        )
    else:
        await query.answer(
            "❌ Erro ao recuperar código Pix.",
            show_alert=True
        )


async def cancelar_pix(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Cancela uma transação Pix pendente"""
    query = update.callback_query
    data = query.data
    transacao_id = int(data.split("_")[-1])
    
    with db.get_session() as session:
        transacao = session.query(Transacao).get(transacao_id)
        
        if transacao and transacao.status == StatusTransacao.PENDENTE.value:
            transacao.status = StatusTransacao.CANCELADO.value
            transacao.data_cancelamento = datetime.now()
            session.flush()
            
            await query.edit_message_text(
                "❌ *PIX CANCELADO*\n\n"
                "Sua recarga foi cancelada.\n"
                "Você pode gerar um novo Pix quando quiser.",
                reply_markup=botao_voltar("menu_recarga"),
                parse_mode="Markdown"
            )
            
            log_com_contexto(
                "Pix cancelado pelo usuário",
                user_id=query.from_user.id,
                transacao_id=transacao_id
            )
        else:
            await query.answer(
                "Não é possível cancelar esta transação.",
                show_alert=True
            )


# ============================================
// ... continua na próxima parte

# ============================================
# HISTÓRICO DE RECARGAS
# ============================================

async def historico_recargas(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Exibe histórico de recargas do usuário"""
    user_id = update.effective_user.id
    
    with db.get_session() as session:
        transacoes = session.query(Transacao).filter_by(
            usuario_id=user_id,
            tipo=TipoTransacao.PIX.value
        ).order_by(Transacao.data_criacao.desc()).limit(10).all()
    
    if not transacoes:
        texto = "📊 *HISTÓRICO DE RECARGAS*\n\n⚠️ Nenhuma recarga encontrada."
    else:
        texto = f"📊 *HISTÓRICO DE RECARGAS*\n\n"
        
        for i, trans in enumerate(transacoes, 1):
            status_emoji = get_status_emoji(trans.status)
            texto += f"{status_emoji} *Recarga #{i}*\n"
            texto += f"   💰 Valor: {formatar_moeda(trans.valor)}\n"
            texto += f"   🎁 Bônus: {formatar_moeda(trans.valor_bonus)}\n"
            texto += f"   📅 Data: {formatar_data(trans.data_criacao)}\n"
            texto += f"   🔹 Status: {trans.status.upper()}\n\n"
    
    keyboard = [[InlineKeyboardButton("🔙 VOLTAR", callback_data="menu_perfil")]]
    
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


# ============================================
// ... continua na próxima parte

# ============================================
# HANDLERS REGISTRATION
# ============================================

def registrar_handlers_recharge(application):
    """Registra todos os handlers de recarga"""
    
    # Conversation Handler para recarga
    recharge_conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler("pix", lambda u, c: cmd_recharge(u, c, None)),
            CallbackQueryHandler(lambda u, c: mostrar_menu_recarga(u, c, None), pattern="^menu_recarga$"),
        ],
        states={
            EstadosRecarga.SELECIONAR_VALOR: [
                CallbackQueryHandler(
                    lambda u, c: selecionar_valor_recarga(u, c, None),
                    pattern="^recarga_"
                ),
            ],
            EstadosRecarga.DIGITAR_VALOR_PERSONALIZADO: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    lambda u, c: digitar_valor_personalizado(u, c, None)
                ),
            ],
            EstadosRecarga.CONFIRMAR_VALOR: [
                CallbackQueryHandler(
                    lambda u, c: gerar_pix_conv(u, c, None),
                    pattern="^confirmar_recarga_"
                ),
            ],
            EstadosRecarga.AGUARDAR_PAGAMENTO: [
                CallbackQueryHandler(
                    lambda u, c: verificar_pagamento(u, c, None),
                    pattern="^verificar_pagamento_"
                ),
                CallbackQueryHandler(
                    lambda u, c: copiar_pix(u, c, None),
                    pattern="^copiar_pix_"
                ),
                CallbackQueryHandler(
                    lambda u, c: cancelar_pix(u, c, None),
                    pattern="^cancelar_pix_"
                ),
            ],
        },
        fallbacks=[
            CallbackQueryHandler(lambda u, c: mostrar_menu_recarga(u, c, None), pattern="^menu_recarga$"),
            CommandHandler("cancel", lambda u, c: mostrar_menu_recarga(u, c, None)),
        ],
        name="recharge_conversation",
        persistent=False,
    )
    
    application.add_handler(recharge_conv_handler)
    
    # Handlers individuais
    application.add_handler(CallbackQueryHandler(
        lambda u, c: historico_recargas(u, c, None),
        pattern="^historico_recargas$"
    ))
    
    application.add_handler(CallbackQueryHandler(
        lambda u, c: mostrar_menu_recarga(u, c, None),
        pattern="^recarga_outro$"
    ))
    
    logger.info("✅ Handlers de recarga registrados!")


async def gerar_pix_conv(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Wrapper para gerar pix dentro da conversa"""
    query = update.callback_query
    data = query.data
    valor = float(data.split("_")[-1])
    await gerar_pix(update, context, db, valor)


# ============================================
// ... continua na próxima parte

# ============================================
# EXPORTAÇÕES
# ============================================

__all__ = [
    'cmd_recharge',
    'mostrar_menu_recarga',
    'registrar_handlers_recharge',
    'historico_recargas',
    'gerar_pix',
    'verificar_pagamento',
    'copiar_pix',
    'cancelar_pix',
]
