"""
Middlewares do Bot - Controle de acesso, logs, anti-spam e segurança
"""
import time
import logging
from typing import Callable, Dict, Any, Optional
from datetime import datetime, timedelta
from functools import wraps
from collections import defaultdict
from telegram import Update
from telegram.ext import ContextTypes, Application
from telegram.constants import ChatType

from .config import config
from .database.models import Usuario, Blacklist, LogAtividade

logger = logging.getLogger(__name__)

# ============================================
// ... continua na próxima parte

# ============================================
# CONTROLE DE ACESSO
# ============================================

class ControleAcesso:
    """Gerencia permissões de acesso ao bot"""
    
    def __init__(self):
        self.usuarios_bloqueados = set()
        self.modo_manutencao = False
        self.ips_suspeitos = defaultdict(list)
        
    def carregar_blacklist(self, db_session):
        """Carrega lista de usuários banidos do banco"""
        try:
            blacklist = db_session.query(Blacklist).filter_by(ativo=True).all()
            self.usuarios_bloqueados = {b.telegram_id for b in blacklist}
            logger.info(f"✅ Blacklist carregada: {len(self.usuarios_bloqueados)} usuários")
        except Exception as e:
            logger.error(f"❌ Erro ao carregar blacklist: {e}")
    
    def is_bloqueado(self, user_id: int) -> bool:
        """Verifica se usuário está bloqueado"""
        return user_id in self.usuarios_bloqueados
    
    def bloquear_usuario(self, user_id: int, motivo: str = "", admin_id: int = None):
        """Bloqueia um usuário"""
        self.usuarios_bloqueados.add(user_id)
        logger.warning(f"🚫 Usuário {user_id} bloqueado por admin {admin_id}: {motivo}")
    
    def desbloquear_usuario(self, user_id: int):
        """Desbloqueia um usuário"""
        self.usuarios_bloqueados.discard(user_id)
        logger.info(f"✅ Usuário {user_id} desbloqueado")
    
    def ativar_manutencao(self):
        """Ativa modo manutenção"""
        self.modo_manutencao = True
        logger.warning("🔧 MODO MANUTENÇÃO ATIVADO")
    
    def desativar_manutencao(self):
        """Desativa modo manutenção"""
        self.modo_manutencao = False
        logger.info("✅ Modo manutenção desativado")
    
    def is_admin(self, user_id: int) -> bool:
        """Verifica se usuário é administrador"""
        return config.is_admin(user_id)

# Instância global
controle_acesso = ControleAcesso()


# ============================================
// ... continua na próxima parte

# ============================================
# MIDDLEWARE DE AUTENTICAÇÃO
# ============================================

async def middleware_autenticacao(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Middleware que verifica autenticação e permissões
    
    Returns:
        bool: True se o usuário pode continuar, False caso contrário
    """
    user = update.effective_user
    if not user:
        return False
    
    user_id = user.id
    
    # Verifica blacklist
    if controle_acesso.is_bloqueado(user_id):
        logger.warning(f"🚫 Acesso negado para usuário bloqueado: {user_id}")
        
        if update.message:
            await update.message.reply_text(
                "⛔ *ACESSO BLOQUEADO*\n\n"
                "Você está banido de usar este bot.\n"
                "Para contestar, entre em contato com o suporte.",
                parse_mode="Markdown"
            )
        return False
    
    # Verifica modo manutenção (exceto admins)
    if controle_acesso.modo_manutencao and not controle_acesso.is_admin(user_id):
        if update.message:
            await update.message.reply_text(
                "🔧 *BOT EM MANUTENÇÃO*\n\n"
                "Estamos realizando melhorias no sistema.\n"
                "Volte em alguns minutos!",
                parse_mode="Markdown"
            )
        return False
    
    # Armazena dados do usuário no context
    context.user_data['user_id'] = user_id
    context.user_data['username'] = user.username
    context.user_data['is_admin'] = controle_acesso.is_admin(user_id)
    context.user_data['timestamp'] = datetime.now()
    
    return True


# ============================================
// ... continua na próxima parte

# ============================================
# MIDDLEWARE DE LOGS
# ============================================

async def middleware_logs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Middleware que registra todas as atividades"""
    user = update.effective_user
    if not user:
        return
    
    user_id = user.id
    username = user.username or "N/A"
    nome = user.first_name or "N/A"
    
    # Identifica o tipo de atualização
    if update.message:
        tipo = "mensagem"
        texto = update.message.text or "[mídia/arquivo]"
        chat_type = update.message.chat.type
        
        logger.info(
            f"📨 [{tipo}] User={user_id} (@{username}) "
            f"Chat={chat_type} | Msg: {texto[:50]}..."
        )
        
    elif update.callback_query:
        tipo = "callback"
        data = update.callback_query.data
        
        logger.info(
            f"🔘 [{tipo}] User={user_id} (@{username}) "
            f"Callback: {data}"
        )
        
    elif update.inline_query:
        tipo = "inline_query"
        query = update.inline_query.query
        
        logger.info(
            f"🔍 [{tipo}] User={user_id} (@{username}) "
            f"Query: {query}"
        )
    
    # Registra atividade no contexto
    if 'atividades' not in context.user_data:
        context.user_data['atividades'] = []
    
    context.user_data['atividades'].append({
        'tipo': tipo,
        'timestamp': datetime.now(),
        'dados': update.to_dict() if update else {}
    })


# ============================================
// ... continua na próxima parte

# ============================================
# MIDDLEWARE ANTI-SPAM
# ============================================

class AntiSpam:
    """Sistema anti-spam e rate limiting"""
    
    def __init__(self):
        # Controle de mensagens por usuário
        self.mensagens_por_usuario = defaultdict(list)
        self.comandos_por_usuario = defaultdict(list)
        
        # Configurações
        self.MAX_MENSAGENS_POR_SEGUNDO = 3
        self.MAX_COMANDOS_POR_MINUTO = 10
        self.JANELA_TEMPO = 60  # segundos
        
        # Usuários em "timeout"
        self.usuarios_em_timeout = {}
        
        # Lista de usuários VIP (sem limite)
        self.usuarios_vip = set()
    
    def verificar_rate_limit(self, user_id: int, is_comando: bool = False) -> bool:
        """
        Verifica se o usuário excedeu o limite de mensagens
        
        Args:
            user_id: ID do usuário
            is_comando: Se é um comando (mais restritivo)
            
        Returns:
            bool: True se pode enviar, False se excedeu limite
        """
        agora = time.time()
        
        # VIPs não têm limite
        if user_id in self.usuarios_vip:
            return True
        
        # Verifica timeout
        if user_id in self.usuarios_em_timeout:
            timeout_ate = self.usuarios_em_timeout[user_id]
            if agora < timeout_ate:
                return False
            else:
                del self.usuarios_em_timeout[user_id]
        
        # Limpa registros antigos
        if is_comando:
            self.comandos_por_usuario[user_id] = [
                t for t in self.comandos_por_usuario[user_id]
                if agora - t < self.JANELA_TEMPO
            ]
            recentes = self.comandos_por_usuario[user_id]
            limite = self.MAX_COMANDOS_POR_MINUTO
        else:
            self.mensagens_por_usuario[user_id] = [
                t for t in self.mensagens_por_usuario[user_id]
                if agora - t < 1  # 1 segundo
            ]
            recentes = self.mensagens_por_usuario[user_id]
            limite = self.MAX_MENSAGENS_POR_SEGUNDO
        
        # Verifica limite
        if len(recentes) >= limite:
            # Aplica timeout
            self.usuarios_em_timeout[user_id] = agora + 30  # 30 segundos
            logger.warning(f"🚨 Rate limit excedido para user {user_id}")
            return False
        
        # Registra mensagem
        if is_comando:
            self.comandos_por_usuario[user_id].append(agora)
        else:
            self.mensagens_por_usuario[user_id].append(agora)
        
        return True
    
    def adicionar_vip(self, user_id: int):
        """Adiciona usuário à lista VIP"""
        self.usuarios_vip.add(user_id)
    
    def remover_vip(self, user_id: int):
        """Remove usuário da lista VIP"""
        self.usuarios_vip.discard(user_id)

# Instância global
anti_spam = AntiSpam()


async def middleware_anti_spam(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Middleware que aplica rate limiting
    
    Returns:
        bool: True se pode continuar, False se bloqueado
    """
    user = update.effective_user
    if not user:
        return False
    
    user_id = user.id
    
    # Admins são VIPs automáticos
    if controle_acesso.is_admin(user_id):
        anti_spam.adicionar_vip(user_id)
    
    # Verifica se é comando
    is_comando = False
    if update.message and update.message.text:
        is_comando = update.message.text.startswith('/')
    
    # Verifica rate limit
    if not anti_spam.verificar_rate_limit(user_id, is_comando):
        if update.message:
            await update.message.reply_text(
                "⚠️ *MUITAS MENSAGENS!*\n\n"
                "Você está enviando mensagens muito rápido.\n"
                "Aguarde 30 segundos e tente novamente.",
                parse_mode="Markdown"
            )
        return False
    
    return True


# ============================================
// ... continua na próxima parte

# ============================================
# MIDDLEWARE DE SEGURANÇA
# ============================================

class Seguranca:
    """Sistema de segurança e detecção de fraudes"""
    
    def __init__(self):
        # Padrões suspeitos
        self.padroes_suspeitos = [
            "hack", "crack", "roubar", "invadir",
            " phishing", "scam", "fraud"
        ]
        
        # Comandos bloqueados
        self.comandos_bloqueados = [
            "/sql", "/inject", "/hack"
        ]
        
        # Tentativas de acesso admin
        self.tentativas_admin = defaultdict(list)
        self.MAX_TENTATIVAS_ADMIN = 5
    
    def detectar_conteudo_suspeito(self, texto: str) -> bool:
        """Verifica se uma mensagem contém conteúdo suspeito"""
        if not texto:
            return False
        
        texto_lower = texto.lower()
        
        for padrao in self.padroes_suspeitos:
            if padrao in texto_lower:
                logger.warning(f"🚨 Conteúdo suspeito detectado: '{texto[:50]}...'")
                return True
        
        return False
    
    def detectar_comando_bloqueado(self, texto: str) -> bool:
        """Verifica se é um comando bloqueado"""
        if not texto:
            return False
        
        for comando in self.comandos_bloqueados:
            if texto.startswith(comando):
                logger.warning(f"🚨 Comando bloqueado detectado: {texto}")
                return True
        
        return False
    
    def registrar_tentativa_admin(self, user_id: int):
        """Registra tentativa de acesso ao admin"""
        agora = time.time()
        self.tentativas_admin[user_id] = [
            t for t in self.tentativas_admin[user_id]
            if agora - t < 300  # 5 minutos
        ]
        self.tentativas_admin[user_id].append(agora)
        
        if len(self.tentativas_admin[user_id]) >= self.MAX_TENTATIVAS_ADMIN:
            logger.warning(f"🚨 Múltiplas tentativas de acesso admin: user {user_id}")
            return True
        
        return False

# Instância global
seguranca = Seguranca()


async def middleware_seguranca(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Middleware de segurança
    
    Returns:
        bool: True se seguro, False se detectou ameaça
    """
    user = update.effective_user
    if not user:
        return False
    
    user_id = user.id
    
    # Verifica conteúdo suspeito em mensagens
    if update.message and update.message.text:
        texto = update.message.text
        
        # Comandos bloqueados
        if seguranca.detectar_comando_bloqueado(texto):
            await update.message.reply_text("🚫 Comando não permitido.")
            return False
        
        # Conteúdo suspeito
        if seguranca.detectar_conteudo_suspeito(texto):
            logger.warning(f"🚨 Conteúdo suspeito de {user_id}: {texto}")
            # Não bloqueia, mas registra
    
    return True


# ============================================
// ... continua na próxima parte

# ============================================
# MIDDLEWARE DE MANUTENÇÃO DE SESSÃO
# ============================================

async def middleware_sessao(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Middleware que mantém dados da sessão do usuário
    """
    user = update.effective_user
    if not user:
        return
    
    user_id = user.id
    
    # Inicializa dados da sessão se necessário
    if 'session_start' not in context.user_data:
        context.user_data['session_start'] = datetime.now()
        context.user_data['message_count'] = 0
        context.user_data['last_activity'] = datetime.now()
        logger.debug(f"🆕 Nova sessão para user {user_id}")
    
    # Atualiza contadores
    context.user_data['message_count'] += 1
    context.user_data['last_activity'] = datetime.now()
    
    # Limpa dados antigos (sessões com mais de 1 hora)
    if datetime.now() - context.user_data['session_start'] > timedelta(hours=1):
        context.user_data.clear()
        context.user_data['session_start'] = datetime.now()
        context.user_data['message_count'] = 1
        logger.debug(f"🔄 Sessão renovada para user {user_id}")


# ============================================
// ... continua na próxima parte

# ============================================
# MIDDLEWARE DE VALIDAÇÃO DE DADOS
# ============================================

async def middleware_validacao(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Middleware que valida dados de entrada
    
    Returns:
        bool: True se dados válidos
    """
    user = update.effective_user
    if not user:
        return False
    
    user_id = user.id
    
    # Valida se o chat é privado (para comandos sensíveis)
    if update.message:
        chat_type = update.message.chat.type
        
        # Comandos financeiros só em chat privado
        if update.message.text and any(cmd in update.message.text for cmd in ['/pix', '/comprar']):
            if chat_type != ChatType.PRIVATE:
                await update.message.reply_text(
                    "⚠️ Por segurança, use este comando apenas no chat privado."
                )
                return False
    
    # Valida tamanho de mensagens
    if update.message and update.message.text:
        if len(update.message.text) > 4096:
            await update.message.reply_text(
                "⚠️ Mensagem muito longa. Limite: 4096 caracteres."
            )
            return False
    
    return True


# ============================================
// ... continua na próxima parte

# ============================================
# MIDDLEWARE DE CACHE
# ============================================

class CacheMiddleware:
    """Sistema de cache simples para middlewares"""
    
    def __init__(self):
        self.cache = {}
        self.cache_timestamps = {}
        self.TTL_PADRAO = 300  # 5 minutos
    
    def get(self, key: str) -> Optional[Any]:
        """Obtém valor do cache"""
        if key in self.cache:
            if time.time() - self.cache_timestamps.get(key, 0) < self.TTL_PADRAO:
                return self.cache[key]
            else:
                del self.cache[key]
                del self.cache_timestamps[key]
        return None
    
    def set(self, key: str, value: Any, ttl: int = None):
        """Armazena valor no cache"""
        self.cache[key] = value
        self.cache_timestamps[key] = time.time()
    
    def invalidate(self, key: str = None):
        """Invalida cache"""
        if key:
            self.cache.pop(key, None)
            self.cache_timestamps.pop(key, None)
        else:
            self.cache.clear()
            self.cache_timestamps.clear()

# Instância global
cache_middleware = CacheMiddleware()


# ============================================
// ... continua na próxima parte

# ============================================
# MIDDLEWARE DE GRUPO
# ============================================

async def middleware_grupo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """
    Middleware específico para grupos
    
    Returns:
        bool: True se pode processar no grupo
    """
    if not update.message:
        return True
    
    chat_type = update.message.chat.type
    
    # Comportamento em grupos
    if chat_type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        user_id = update.effective_user.id
        
        # Verifica se o bot foi mencionado ou é resposta
        bot_username = context.bot.username
        texto = update.message.text or ""
        
        mencionado = f"@{bot_username}" in texto if bot_username else False
        is_reply = update.message.reply_to_message and \
                   update.message.reply_to_message.from_user.id == context.bot.id
        
        # Só responde se mencionado ou em reply
        if not mencionado and not is_reply:
            return False
    
    return True


# ============================================
// ... continua na próxima parte

# ============================================
# FUNÇÃO PRINCIPAL - REGISTRAR TODOS OS MIDDLEWARES
# ============================================

def registrar_middlewares(application: Application):
    """
    Registra todos os middlewares na aplicação
    
    Args:
        application: Aplicação do Telegram Bot
    """
    
    @application.add_handler_wrapper
    async def middleware_chain(update: Update, context: ContextTypes.DEFAULT_TYPE, next_handler: Callable):
        """
        Cadeia completa de middlewares
        Ordem de execução:
        1. Logs
        2. Segurança
        3. Anti-spam
        4. Autenticação
        5. Validação
        6. Grupo
        7. Sessão
        8. Handler final
        """
        
        # 1. Middleware de Logs (sempre executa)
        await middleware_logs(update, context)
        
        # 2. Middleware de Segurança
        if not await middleware_seguranca(update, context):
            return
        
        # 3. Middleware Anti-Spam
        if not await middleware_anti_spam(update, context):
            return
        
        # 4. Middleware de Autenticação
        if not await middleware_autenticacao(update, context):
            return
        
        # 5. Middleware de Validação
        if not await middleware_validacao(update, context):
            return
        
        # 6. Middleware de Grupo
        if not await middleware_grupo(update, context):
            return
        
        # 7. Middleware de Sessão
        await middleware_sessao(update, context)
        
        # 8. Executa o próximo handler
        await next_handler(update, context)
    
    logger.info("✅ Middlewares registrados com sucesso!")


# ============================================
// ... continua na próxima parte

# ============================================
# DECORADORES ÚTEIS
# ============================================

def somente_admin(func: Callable):
    """Decorator para funções que só podem ser executadas por admins"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        
        if not controle_acesso.is_admin(user_id):
            if update.callback_query:
                await update.callback_query.answer("⛔ Acesso restrito a administradores!", show_alert=True)
            elif update.message:
                await update.message.reply_text("⛔ Comando restrito a administradores!")
            return
        
        return await func(update, context, *args, **kwargs)
    return wrapper


def somente_chat_privado(func: Callable):
    """Decorator para funções que só funcionam em chat privado"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if update.message and update.message.chat.type != ChatType.PRIVATE:
            await update.message.reply_text(
                "⚠️ Este comando só pode ser usado no chat privado.\n"
                "Clique aqui para falar comigo: @SeuBot"
            )
            return
        
        return await func(update, context, *args, **kwargs)
    return wrapper


def log_atividade(acao: str):
    """Decorator para logar atividades específicas"""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
            user = update.effective_user
            logger.info(f"📝 [{acao}] User={user.id} (@{user.username})")
            
            # Executa a função
            result = await func(update, context, *args, **kwargs)
            
            return result
        return wrapper
    return decorator


# ============================================
// ... continua na próxima parte

# ============================================
# EXPORTAÇÕES
# ============================================

__all__ = [
    # Classes
    'ControleAcesso',
    'AntiSpam',
    'Seguranca',
    'CacheMiddleware',
    
    # Instâncias
    'controle_acesso',
    'anti_spam',
    'seguranca',
    'cache_middleware',
    
    # Middlewares
    'middleware_autenticacao',
    'middleware_logs',
    'middleware_anti_spam',
    'middleware_seguranca',
    'middleware_sessao',
    'middleware_validacao',
    'middleware_grupo',
    
    # Funções
    'registrar_middlewares',
    
    # Decorators
    'somente_admin',
    'somente_chat_privado',
    'log_atividade',
]
