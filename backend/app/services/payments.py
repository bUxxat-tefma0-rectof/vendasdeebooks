"""
Serviço de Pagamentos - Integração Mercado Pago e PIX Automático
Versão sem Pillow - usa qrcode puro
"""
import logging
import json
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, Tuple
from io import BytesIO
import base64
import qrcode
import mercadopago

from ..config import config
from ..utils.utils import formatar_moeda, log_com_contexto

logger = logging.getLogger(__name__)


class MercadoPagoService:
    """Serviço de integração com Mercado Pago"""
    
    def __init__(self):
        self.sdk = None
        self.access_token = config.MP_ACCESS_TOKEN
        self.public_key = config.MP_PUBLIC_KEY
        
        if self.access_token:
            try:
                self.sdk = mercadopago.SDK(self.access_token)
                logger.info("✅ Mercado Pago SDK inicializado!")
            except Exception as e:
                logger.error(f"❌ Erro ao inicializar SDK: {e}")
    
    async def criar_pix(
        self,
        valor: float,
        descricao: str = "",
        external_reference: str = ""
    ) -> Optional[Dict[str, Any]]:
        """Cria um pagamento PIX no Mercado Pago"""
        try:
            if not self.sdk:
                logger.error("❌ SDK não inicializado")
                return None
            
            payment_data = {
                "transaction_amount": float(valor),
                "description": descricao or f"Recarga {config.NOME_BOT}",
                "payment_method_id": "pix",
                "external_reference": external_reference,
                "payer": {
                    "email": "cliente@email.com",
                    "first_name": "Cliente"
                }
            }
            
            response = self.sdk.payment().create(payment_data)
            
            if response.get("status") == 201:
                payment = response.get("response", {})
                poi = payment.get("point_of_interaction", {})
                tx_data = poi.get("transaction_data", {})
                
                # Gera QR Code como bytes PNG
                qr_code_text = tx_data.get("qr_code", "")
                qr_image = self._generate_qr_image(qr_code_text)
                
                return {
                    'id': str(payment.get("id")),
                    'qr_code': qr_code_text,
                    'qr_code_base64': qr_image,
                    'copia_cola': qr_code_text,
                    'status': payment.get("status", "pending"),
                    'valor': valor,
                    'data_expiracao': payment.get("date_of_expiration", "")
                }
            
            logger.error(f"❌ Erro ao criar PIX: {response}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Exceção ao criar PIX: {e}")
            return None
    
    def _generate_qr_image(self, data: str) -> str:
        """Gera QR Code como base64 SEM usar Pillow"""
        try:
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(data)
            qr.make(fit=True)
            
            # Usa o método nativo do qrcode para gerar PNG
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Converte para bytes
            buffer = BytesIO()
            img.save(buffer, format='PNG')
            buffer.seek(0)
            
            return base64.b64encode(buffer.read()).decode()
            
        except Exception as e:
            logger.error(f"❌ Erro ao gerar QR Code: {e}")
            return ""
    
    async def verificar_pagamento(self, payment_id: str) -> Optional[str]:
        """Verifica status de um pagamento"""
        try:
            if not self.sdk:
                return None
            
            response = self.sdk.payment().get(payment_id)
            
            if response.get("status") == 200:
                return response.get("response", {}).get("status")
            
            return None
            
        except Exception as e:
            logger.error(f"❌ Erro ao verificar pagamento: {e}")
            return None
    
    async def cancelar_pagamento(self, payment_id: str) -> bool:
        """Cancela um pagamento pendente"""
        try:
            if not self.sdk:
                return False
            
            response = self.sdk.payment().update(payment_id, {"status": "cancelled"})
            return response.get("status") == 200
            
        except Exception as e:
            logger.error(f"❌ Erro ao cancelar: {e}")
            return False


class VerificadorPagamentos:
    """Serviço que verifica pagamentos pendentes periodicamente"""
    
    def __init__(self):
        self.mp_service = MercadoPagoService()
        self.pagamentos_pendentes = {}
        self.verificacao_ativa = False
    
    def adicionar_para_monitorar(
        self,
        payment_id: str,
        user_id: int,
        transacao_id: int,
        callback_aprovado=None,
        callback_expirado=None
    ):
        """Adiciona pagamento para monitoramento"""
        self.pagamentos_pendentes[payment_id] = {
            'user_id': user_id,
            'transacao_id': transacao_id,
            'callback_aprovado': callback_aprovado,
            'callback_expirado': callback_expirado,
            'data_inicio': datetime.now(),
            'tentativas': 0,
            'max_tentativas': 30
        }
        logger.info(f"🔍 Monitorando pagamento {payment_id}")
    
    def remover(self, payment_id: str):
        """Remove pagamento do monitoramento"""
        self.pagamentos_pendentes.pop(payment_id, None)
    
    async def iniciar_verificacao(self, intervalo: int = 10):
        """Inicia verificação automática em background"""
        if self.verificacao_ativa:
            return
        
        self.verificacao_ativa = True
        logger.info("🔄 Verificação automática iniciada")
        
        while self.verificacao_ativa:
            try:
                await self._verificar_todos()
                await asyncio.sleep(intervalo)
            except Exception as e:
                logger.error(f"❌ Erro na verificação: {e}")
                await asyncio.sleep(intervalo * 2)
    
    async def _verificar_todos(self):
        """Verifica todos os pagamentos pendentes"""
        if not self.pagamentos_pendentes:
            return
        
        para_remover = []
        
        for payment_id, dados in self.pagamentos_pendentes.items():
            try:
                dados['tentativas'] += 1
                
                if dados['tentativas'] > dados['max_tentativas']:
                    para_remover.append(payment_id)
                    if dados.get('callback_expirado'):
                        await dados['callback_expirado'](payment_id, dados)
                    continue
                
                status = await self.mp_service.verificar_pagamento(payment_id)
                
                if status == 'approved':
                    para_remover.append(payment_id)
                    if dados.get('callback_aprovado'):
                        await dados['callback_aprovado'](payment_id, dados)
                        
                elif status in ['rejected', 'cancelled', 'refunded']:
                    para_remover.append(payment_id)
                    if dados.get('callback_expirado'):
                        await dados['callback_expirado'](payment_id, dados)
                        
            except Exception as e:
                logger.error(f"❌ Erro ao verificar {payment_id}: {e}")
        
        for payment_id in para_remover:
            self.remover(payment_id)
    
    def parar(self):
        """Para a verificação automática"""
        self.verificacao_ativa = False
        logger.info("⏹️ Verificação automática parada")


mp_service = MercadoPagoService()
verificador = VerificadorPagamentos()


__all__ = [
    'MercadoPagoService',
    'VerificadorPagamentos',
    'mp_service',
    'verificador',
]
