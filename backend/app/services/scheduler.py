"""
Serviço de Tarefas Automáticas (Scheduler)
Expiração de PIX, alertas de estoque, backup e manutenção
"""
import logging
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict
from sqlalchemy import func, and_

from ..database.connection import Database
from ..database.models import Transacao, StatusTransacao, Produto, AlertaProduto, Usuario
from ..config import config
from ..utils.utils import formatar_moeda, log_com_contexto

logger = logging.getLogger(__name__)


class TaskScheduler:
    """Agendador de tarefas automáticas"""
    
    def __init__(self, db: Database, bot=None):
        self.db = db
        self.bot = bot
        self.tasks = []
        self.running = False
    
    async def iniciar(self):
        """Inicia todas as tarefas agendadas"""
        if self.running:
            logger.warning("⚠️ Scheduler já está rodando")
            return
        
        self.running = True
        logger.info("🔄 Iniciando tarefas automáticas...")
        
        self.tasks = [
            asyncio.create_task(self.verificar_pix_expirados()),
            asyncio.create_task(self.limpar_transacoes_antigas()),
            asyncio.create_task(self.verificar_estoque_baixo()),
            asyncio.create_task(self.backup_diario()),
        ]
        
        logger.info(f"✅ {len(self.tasks)} tarefas iniciadas")
    
    async def parar(self):
        """Para todas as tarefas"""
        self.running = False
        
        for task in self.tasks:
            task.cancel()
        
        logger.info("⏹️ Tarefas automáticas paradas")
    
    async def verificar_pix_expirados(self):
        """Verifica e cancela PIX expirados a cada 30 segundos"""
        logger.info("🔄 Monitor de PIX expirados iniciado")
        
        while self.running:
            try:
                with self.db.get_session() as session:
                    agora = datetime.now()
                    
                    expirados = session.query(Transacao).filter(
                        and_(
                            Transacao.status == StatusTransacao.PENDENTE.value,
                            Transacao.data_expiracao < agora,
                            Transacao.tipo == "pix"
                        )
                    ).all()
                    
                    for transacao in expirados:
                        transacao.status = StatusTransacao.EXPIRADO.value
                        
                        # Notifica usuário
                        if self.bot:
                            try:
                                await self.bot.send_message(
                                    chat_id=transacao.usuario_id,
                                    text="⏰ *PIX EXPIRADO*\n\n"
                                         f"Valor: {formatar_moeda(transacao.valor)}\n"
                                         "Gere um novo Pix para continuar.",
                                    parse_mode="Markdown"
                                )
                            except:
                                pass
                    
                    if expirados:
                        session.flush()
                        logger.info(f"⏰ {len(expirados)} PIX expirados cancelados")
                
                await asyncio.sleep(30)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Erro ao verificar PIX expirados: {e}")
                await asyncio.sleep(60)
    
    async def limpar_transacoes_antigas(self):
        """Limpa transações pendentes muito antigas (1 vez por hora)"""
        logger.info("🔄 Limpador de transações antigas iniciado")
        
        while self.running:
            try:
                with self.db.get_session() as session:
                    data_limite = datetime.now() - timedelta(hours=24)
                    
                    deletadas = session.query(Transacao).filter(
                        and_(
                            Transacao.status == StatusTransacao.PENDENTE.value,
                            Transacao.data_criacao < data_limite
                        )
                    ).delete()
                    
                    if deletadas:
                        session.flush()
                        logger.info(f"🗑️ {deletadas} transações pendentes antigas removidas")
                
                await asyncio.sleep(3600)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Erro ao limpar transações: {e}")
                await asyncio.sleep(3600)
    
    async def verificar_estoque_baixo(self):
        """Verifica produtos com estoque baixo a cada 5 minutos"""
        logger.info("🔄 Monitor de estoque baixo iniciado")
        
        while self.running:
            try:
                with self.db.get_session() as session:
                    produtos_baixo = session.query(Produto).filter(
                        and_(
                            Produto.ativo == True,
                            Produto.estoque_ilimitado == False,
                            Produto.estoque <= Produto.estoque_minimo,
                            Produto.estoque > 0
                        )
                    ).all()
                    
                    produtos_zerados = session.query(Produto).filter(
                        and_(
                            Produto.ativo == True,
                            Produto.estoque_ilimitado == False,
                            Produto.estoque <= 0
                        )
                    ).all()
                    
                    if produtos_baixo and self.bot:
                        for admin_id in config.ADMIN_IDS:
                            try:
                                texto = "⚠️ *ESTOQUE BAIXO*\n\n"
                                for p in produtos_baixo[:5]:
                                    texto += f"📦 {p.nome}: {p.estoque} un. (mín: {p.estoque_minimo})\n"
                                
                                if produtos_zerados:
                                    texto += f"\n❌ *SEM ESTOQUE:* {len(produtos_zerados)} produtos\n"
                                
                                await self.bot.send_message(
                                    chat_id=admin_id,
                                    text=texto,
                                    parse_mode="Markdown"
                                )
                            except:
                                pass
                
                await asyncio.sleep(300)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Erro ao verificar estoque: {e}")
                await asyncio.sleep(300)
    
    async def backup_diario(self):
        """Realiza backup do banco a cada 24 horas"""
        logger.info("🔄 Backup diário iniciado")
        
        while self.running:
            try:
                agora = datetime.now()
                
                # Aguarda até 3h da manhã
                proximo_backup = agora.replace(hour=3, minute=0, second=0)
                if agora > proximo_backup:
                    proximo_backup += timedelta(days=1)
                
                espera = (proximo_backup - agora).total_seconds()
                await asyncio.sleep(espera)
                
                # Realiza backup
                from ..database.connection import Database
                nome_arquivo = f"backup_{datetime.now().strftime('%Y%m%d_%H%M')}.db"
                
                try:
                    self.db.backup_database(nome_arquivo)
                    
                    # Notifica admins
                    if self.bot:
                        for admin_id in config.ADMIN_IDS:
                            try:
                                await self.bot.send_message(
                                    chat_id=admin_id,
                                    text=f"✅ *Backup realizado*\n\n📁 {nome_arquivo}",
                                    parse_mode="Markdown"
                                )
                            except:
                                pass
                except Exception as e:
                    logger.error(f"❌ Erro no backup: {e}")
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Erro no agendamento de backup: {e}")
                await asyncio.sleep(3600)
    
    async def notificar_aniversariantes(self):
        """Notifica sobre usuários aniversariantes (placeholder)"""
        pass
    
    async def relatorio_semanal(self):
        """Envia relatório semanal para admins (placeholder)"""
        pass


# Instância global
scheduler = None

def init_scheduler(db: Database, bot=None):
    """Inicializa o scheduler"""
    global scheduler
    scheduler = TaskScheduler(db, bot)
    return scheduler


async def iniciar_tarefas(db: Database, bot=None):
    """Função auxiliar para iniciar tarefas"""
    sched = init_scheduler(db, bot)
    await sched.iniciar()
    return sched


__all__ = [
    'TaskScheduler',
    'scheduler',
    'init_scheduler',
    'iniciar_tarefas',
]
