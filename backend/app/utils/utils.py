"""
Funções utilitárias do bot - Formatação, validação e helpers
"""
import re
import hashlib
import secrets
import string
import qrcode
import base64
import logging
from io import BytesIO
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from decimal import Decimal, ROUND_DOWN
import pytz

logger = logging.getLogger(__name__)


def formatar_moeda(valor: float, simbolo: bool = True) -> str:
    if valor is None:
        valor = 0.0
    valor_decimal = Decimal(str(valor)).quantize(Decimal('0.01'), rounding=ROUND_DOWN)
    valor_str = f"{valor_decimal:,.2f}"
    valor_str = valor_str.replace(",", "X").replace(".", ",").replace("X", ".")
    if simbolo:
        return f"R$ {valor_str}"
    return valor_str


def formatar_data(data: datetime, formato: str = "dd/mm/aaaa HH:MM") -> str:
    if not data:
        return "N/A"
    if data.tzinfo is None:
        data = pytz.UTC.localize(data)
    tz_brasil = pytz.timezone('America/Sao_Paulo')
    data_brasil = data.astimezone(tz_brasil)
    formatos = {
        "dd/mm/aaaa": "%d/%m/%Y",
        "dd/mm/aaaa HH:MM": "%d/%m/%Y %H:%M",
        "dd/mm/aaaa HH:MM:SS": "%d/%m/%Y %H:%M:%S",
        "HH:MM": "%H:%M",
        "dd/mm": "%d/%m",
        "HH:MM dd/mm": "%H:%M %d/%m",
    }
    formato_python = formatos.get(formato, "%d/%m/%Y %H:%M")
    return data_brasil.strftime(formato_python)


def formatar_tempo(segundos: int) -> str:
    if segundos < 0:
        return "0s"
    horas = segundos // 3600
    minutos = (segundos % 3600) // 60
    segs = segundos % 60
    partes = []
    if horas > 0:
        partes.append(f"{horas}h")
    if minutos > 0:
        partes.append(f"{minutos}m")
    partes.append(f"{segs}s")
    return " ".join(partes)


def formatar_numero(numero: int) -> str:
    if numero is None:
        return "0"
    return f"{numero:,}".replace(",", ".")


def gerar_qr_code_pix(payload: str, tamanho: int = 300) -> BytesIO:
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    output = BytesIO()
    img.save(output, format='PNG')
    output.seek(0)
    return output


def gerar_qr_code_base64(payload: str) -> str:
    qr_image = gerar_qr_code_pix(payload)
    return base64.b64encode(qr_image.read()).decode()


def validar_email(email: str) -> bool:
    if not email:
        return False
    padrao = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(padrao, email))


def validar_telefone(telefone: str) -> bool:
    if not telefone:
        return False
    numeros = re.sub(r'\D', '', telefone)
    return len(numeros) in [10, 11]


def validar_valor(valor_str: str) -> Tuple[bool, float]:
    if not valor_str:
        return False, 0.0
    valor_str = valor_str.replace('R$', '').replace(' ', '')
    valor_str = valor_str.replace('.', '').replace(',', '.')
    try:
        valor = float(valor_str)
        if valor <= 0:
            return False, 0.0
        return True, valor
    except ValueError:
        return False, 0.0


def sanitizar_texto(texto: str, max_length: int = 1000) -> str:
    if not texto:
        return ""
    texto = texto.replace('<', '&lt;').replace('>', '&gt;')
    texto = ' '.join(texto.split())
    if len(texto) > max_length:
        texto = texto[:max_length-3] + "..."
    return texto


def escape_markdown(texto: str) -> str:
    if not texto:
        return ""
    caracteres = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for char in caracteres:
        texto = texto.replace(char, f'\\{char}')
    return texto


def gerar_codigo(tamanho: int = 8, tipo: str = "alfanumerico") -> str:
    if tipo == "numerico":
        caracteres = string.digits
    elif tipo == "alfabetico":
        caracteres = string.ascii_uppercase
    else:
        caracteres = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(caracteres) for _ in range(tamanho))


def gerar_hash(texto: str, algoritmo: str = "sha256") -> str:
    if algoritmo == "md5":
        return hashlib.md5(texto.encode()).hexdigest()
    elif algoritmo == "sha1":
        return hashlib.sha1(texto.encode()).hexdigest()
    else:
        return hashlib.sha256(texto.encode()).hexdigest()


def gerar_token(length: int = 32) -> str:
    return secrets.token_hex(length)


def calcular_porcentagem(valor: float, porcentagem: float) -> float:
    return (valor * porcentagem) / 100


def calcular_desconto(valor: float, desconto: float, tipo: str = "porcentagem") -> float:
    if tipo == "porcentagem":
        desconto_valor = calcular_porcentagem(valor, desconto)
    else:
        desconto_valor = desconto
    return max(0, valor - desconto_valor)


def calcular_comissao_afiliado(valor_venda: float, porcentagem_comissao: float) -> float:
    comissao = calcular_porcentagem(valor_venda, porcentagem_comissao)
    return round(comissao, 2)


EMOJIS = {
    "sucesso": "✅", "erro": "❌", "aviso": "⚠️", "info": "ℹ️",
    "dinheiro": "💰", "carrinho": "🛒", "estrela": "⭐", "trofeu": "🏆",
    "fogo": "🔥", "foguete": "🚀", "presente": "🎁", "loja": "🏪",
    "usuario": "👤", "admin": "🛡️", "banido": "🚫", "relogio": "⏰",
    "grafico": "📊", "documento": "📄", "link": "🔗", "cadeado": "🔒",
    "chave": "🔑", "lupa": "🔍", "sino": "🔔", "coracao": "❤️",
    "voltar": "🔙", "download": "📥", "upload": "📤",
}

MEDALHAS = ["🥇", "🥈", "🥉"] + ["🏅"] * 7

STATUS_EMOJI = {
    "pendente": "🟡", "aprovado": "🟢", "cancelado": "🔴",
    "expirado": "⚫", "reembolsado": "🔵",
}


def get_emoji(categoria: str) -> str:
    return EMOJIS.get(categoria, "📌")


def get_medalha(posicao: int) -> str:
    if posicao < 1:
        return "👤"
    return MEDALHAS[min(posicao - 1, len(MEDALHAS) - 1)]


def get_status_emoji(status: str) -> str:
    return STATUS_EMOJI.get(status.lower(), "⚪")


def log_com_contexto(mensagem: str, level: str = "info", **kwargs):
    dados_extras = " | ".join([f"{k}={v}" for k, v in kwargs.items()])
    log_msg = f"{mensagem} | {dados_extras}" if dados_extras else mensagem
    if level == "debug":
        logger.debug(log_msg)
    elif level == "warning":
        logger.warning(log_msg)
    elif level == "error":
        logger.error(log_msg)
    else:
        logger.info(log_msg)


def calcular_media(valores: List[float]) -> float:
    if not valores:
        return 0.0
    return sum(valores) / len(valores)


def calcular_total(valores: List[float]) -> float:
    return sum(valores)


def calcular_taxa_conversao(visitas: int, compras: int) -> float:
    if visitas == 0:
        return 0.0
    return (compras / visitas) * 100
