"""
Módulo do Cliente - Sistema Completo de Afiliados
Indicação, comissões, saques e métricas
"""
import logging
from datetime import datetime
from typing import List, Dict, Tuple

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from ...config import config
from ...database import Database
from ...database.models import Usuario, Compra, Transacao, TipoTransacao, StatusTransacao
from ...utils.keyboards import menu_afiliados, botao_voltar, botoes_confirmacao
from ...utils.utils import (
    formatar_moeda, formatar_data, formatar_numero,
    gerar_codigo, calcular_porcentagem, log_com_contexto
)
from ...middlewares import somente_chat_privado

logger = logging.getLogger(__name__)


class AffiliateService:
    """Serviço de afiliados"""
    
    def __init__(self, db: Database):
        self.db = db
    
    def gerar_codigo_afiliado(self, user_id: int) -> str:
        """Gera código de afiliado único"""
        with self.db.get_session() as session:
            usuario = session.query(Usuario).filter_by(telegram_id=user_id).first()
            
            if not usuario:
                return ""
            
            if usuario.codigo_afiliado:
                return usuario.codigo_afiliado
            
            while True:
                codigo = gerar_codigo(8, "alfanumerico")
                existente = session.query(Usuario).filter_by(codigo_afiliado=codigo).first()
                if not existente:
                    usuario.codigo_afiliado = codigo
                    session.flush()
                    return codigo
    
    def get_link_afiliado(self, user_id: int) -> str:
        """Retorna link de afiliado"""
        codigo = self.gerar_codigo_afiliado(user_id)
        if codigo:
            return f"https://t.me/{config.NOME_BOT.replace('@', '')}?start={codigo}"
        return ""
    
    def processar_indicacao(self, indicado_id: int, codigo_afiliador: str) -> Tuple[bool, str]:
        """Processa indicação de afiliado"""
        with self.db.get_session() as session:
            afiliador = session.query(Usuario).filter_by(codigo_afiliado=codigo_afiliador).first()
            
            if not afiliador:
                return False, "Código de afiliado inválido"
            
            if afiliador.telegram_id == indicado_id:
                return False, "Você não pode usar seu próprio código"
            
            indicado = session.query(Usuario).filter_by(telegram_id=indicado_id).first()
            
            if not indicado:
                return False, "Usuário não encontrado"
            
            if indicado.afiliado_por:
                return False, "Usuário já foi indicado por outro afiliado"
            
            indicado.afiliado_por = afiliador.id
            afiliador.total_indicacoes = (afiliador.total_indicacoes or 0) + 1
            
            session.flush()
            
            log_com_contexto(
                "Indicação processada",
                afiliador=afiliador.telegram_id,
                indicado=indicado_id,
                codigo=codigo_afiliador
            )
            
            return True, f"✅ Indicado por {afiliador.nome or afiliador.username}!"
    
    def get_metricas_afiliado(self, user_id: int) -> Dict:
        """Retorna métricas do afiliado"""
        with self.db.get_session() as session:
            usuario = session.query(Usuario).filter_by(telegram_id=user_id).first()
            
            if not usuario:
                return {}
            
            # Total de indicados
            total_indicados = session.query(Usuario).filter_by(
                afiliado_por=usuario.id
            ).count()
            
            # Compras dos indicados
            indicados_ids = session.query(Usuario.id).filter_by(afiliado_por=usuario.id).all()
            indicados_ids = [i[0] for i in indicados_ids]
            
            total_compras_indicados = 0
            total_comissoes = usuario.comissao_acumulada or 0.0
            
            if indicados_ids:
                total_compras_indicados = session.query(Compra).filter(
                    Compra.usuario_id.in_(indicados_ids),
                    Compra.reembolsada == False
                ).count()
            
            return {
                'codigo': usuario.codigo_afiliado or '',
                'link': f"https://t.me/{config.NOME_BOT.replace('@', '')}?start={usuario.codigo_afiliado}",
                'total_indicados': total_indicados,
                'total_compras_indicados': total_compras_indicados,
                'comissao_acumulada': total_comissoes,
                'comissao_disponivel': usuario.saldo or 0.0
            }
    
    def get_top_afiliados(self, limite: int = 10) -> List[Dict]:
        """Retorna top afiliados"""
        with self.db.get_session() as session:
            afiliados = session.query(Usuario).filter(
                Usuario.total_indicacoes > 0
            ).order_by(Usuario.comissao_acumulada.desc()).limit(limite).all()
            
            return [
                {
                    'id': a.telegram_id,
                    'nome': a.nome or f"@{a.username}" or f"User{a.telegram_id}",
                    'indicacoes': a.total_indicacoes or 0,
                    'comissao': float(a.comissao_acumulada or 0)
                }
                for a in afiliados
            ]


affiliate_service = None

def init_service(db: Database):
    global affiliate_service
    affiliate_service = AffiliateService(db)


async def menu_afiliado(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Exibe menu principal de afiliados"""
    init_service(db)
    user_id = update.effective_user.id
    
    metricas = affiliate_service.get_metricas_afiliado(user_id)
    
    if not metricas.get('codigo'):
        codigo = affiliate_service.gerar_codigo_afiliado(user_id)
        metricas = affiliate_service.get_metricas_afiliado(user_id)
    
    texto = f"""
🤝 *SISTEMA DE AFILIADOS*

💎 *Seu Código:* `{metricas.get('codigo', 'N/A')}`

📊 *Suas Métricas:*
👥 Indicados: {formatar_numero(metricas.get('total_indicados', 0))}
🛒 Compras: {formatar_numero(metricas.get('total_compras_indicados', 0))}
💰 Comissão Total: {formatar_moeda(metricas.get('comissao_acumulada', 0))}

🎯 *Comissão por venda:* {config.COMISSAO_AFILIADO}%

🔹 *Como funciona:*
1. Compartilhe seu link
2. Usuários se registram com seu código
3. Você ganha {config.COMISSAO_AFILIADO}% sobre compras e recargas
4. Saldo disponível para saque

🔹 Selecione uma opção:
"""
    
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(
            text=texto,
            reply_markup=menu_afiliados(metricas.get('codigo', '')),
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            text=texto,
            reply_markup=menu_afiliados(metricas.get('codigo', '')),
            parse_mode="Markdown"
        )


async def cmd_afiliados(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Comando /afiliados"""
    await menu_afiliado(update, context, db)


async def copiar_link(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Copia link de afiliado"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    link = affiliate_service.get_link_afiliado(user_id)
    
    if link:
        await query.message.reply_text(
            f"🔗 *SEU LINK DE AFILIADO*\n\n"
            f"`{link}`\n\n"
            f"📋 Copie e compartilhe com seus amigos!\n"
            f"💰 Ganhe {config.COMISSAO_AFILIADO}% sobre cada venda!",
            parse_mode="Markdown"
        )
        await query.answer("✅ Link copiado!", show_alert=True)
    else:
        await query.answer("❌ Erro ao gerar link", show_alert=True)


async def ver_desempenho(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Exibe desempenho detalhado"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    metricas = affiliate_service.get_metricas_afiliado(user_id)
    
    texto = f"""
📊 *DESEMPENHO DE AFILIADO*

💎 *Código:* `{metricas.get('codigo', 'N/A')}`

📈 *Métricas:*
👥 Total de indicados: {formatar_numero(metricas.get('total_indicados', 0))}
🛒 Compras dos indicados: {formatar_numero(metricas.get('total_compras_indicados', 0))}
💰 Comissão acumulada: {formatar_moeda(metricas.get('comissao_acumulada', 0))}
💵 Saldo disponível: {formatar_moeda(metricas.get('comissao_disponivel', 0))}

🎯 *Taxa de comissão:* {config.COMISSAO_AFILIADO}%

📋 *Dicas:*
• Compartilhe em grupos e canais
• Crie conteúdo sobre os produtos
• Use suas redes sociais
"""
    
    keyboard = [
        [InlineKeyboardButton("📋 COPIAR LINK", callback_data=f"copiar_link_{metricas.get('codigo', '')}")],
        [InlineKeyboardButton("🔙 VOLTAR", callback_data="menu_afiliados")]
    ]
    
    await query.edit_message_text(
        text=texto,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def sacar_comissao(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Saque de comissão"""
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    metricas = affiliate_service.get_metricas_afiliado(user_id)
    
    saldo = metricas.get('comissao_disponivel', 0)
    
    if saldo < config.VALOR_MINIMO_PIX:
        texto = f"""
💰 *SAQUE DE COMISSÃO*

❌ Saldo insuficiente para saque.

💵 *Seu saldo:* {formatar_moeda(saldo)}
📊 *Mínimo para saque:* {formatar_moeda(config.VALOR_MINIMO_PIX)}

Continue indicando para acumular mais!
"""
        keyboard = [[InlineKeyboardButton("🔙 VOLTAR", callback_data="menu_afiliados")]]
    else:
        texto = f"""
💰 *SAQUE DE COMISSÃO*

💵 *Saldo disponível:* {formatar_moeda(saldo)}

🔹 Deseja sacar qual valor?

📊 *Limites:*
• Mínimo: {formatar_moeda(config.VALOR_MINIMO_PIX)}
• Máximo: {formatar_moeda(saldo)}
"""
        keyboard = [
            [
                InlineKeyboardButton(f"Sacar {formatar_moeda(saldo)}", callback_data=f"sacar_tudo_{saldo}"),
            ],
            [
                InlineKeyboardButton("💎 Outro valor", callback_data="sacar_outro"),
            ],
            [InlineKeyboardButton("🔙 VOLTAR", callback_data="menu_afiliados")]
        ]
    
    await query.edit_message_text(
        text=texto,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def regras_afiliado(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database):
    """Exibe regras do programa"""
    query = update.callback_query
    await query.answer()
    
    texto = f"""
📋 *REGRAS DO AFILIADO*

1️⃣ *Comissão:* {config.COMISSAO_AFILIADO}% sobre compras e recargas

2️⃣ *Pagamento:* Saldo fica disponível na hora

3️⃣ *Saque:* Mínimo de {formatar_moeda(config.VALOR_MINIMO_PIX)}

4️⃣ *Proibido:*
• Usar o próprio link
• Spam em grupos
• Informações falsas
• Auto-indicação

5️⃣ *Bônus:* Indicados que compram aumentam seu nível

⚠️ O descumprimento das regras pode levar ao banimento.
"""
    
    keyboard = [[InlineKeyboardButton("🔙 VOLTAR", callback_data="menu_afiliados")]]
    
    await query.edit_message_text(
        text=texto,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


def registrar_handlers_affiliates(application):
    """Registra handlers de afiliados"""
    application.add_handler(CommandHandler("afiliados", lambda u, c: cmd_afiliados(u, c, None)))
    application.add_handler(CallbackQueryHandler(lambda u, c: menu_afiliado(u, c, None), pattern="^menu_afiliados$"))
    application.add_handler(CallbackQueryHandler(lambda u, c: copiar_link(u, c, None), pattern="^copiar_link_"))
    application.add_handler(CallbackQueryHandler(lambda u, c: ver_desempenho(u, c, None), pattern="^afiliado_desempenho$"))
    application.add_handler(CallbackQueryHandler(lambda u, c: sacar_comissao(u, c, None), pattern="^sacar_comissao$"))
    application.add_handler(CallbackQueryHandler(lambda u, c: regras_afiliado(u, c, None), pattern="^regras_afiliado$"))
    logger.info("✅ Handlers de afiliados registrados!")


__all__ = [
    'menu_afiliado',
    'cmd_afiliados',
    'copiar_link',
    'ver_desempenho',
    'sacar_comissao',
    'regras_afiliado',
    'registrar_handlers_affiliates',
    'AffiliateService',
]
