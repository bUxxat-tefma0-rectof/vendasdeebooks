"""
Funções utilitárias do bot - Formatação, validação e helpers
"""
import re
import json
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
from PIL import Image, ImageDraw, ImageFont
import random
import os

logger = logging.getLogger(__name__)

# ============================================
# FORMATAÇÃO DE VALORES E DATAS
# ============================================

def formatar_moeda(valor: float, simbolo: bool = True) -> str:
    """
    Formata um valor para o padrão monetário brasileiro
    
    Args:
        valor: Valor a ser formatado
        simbolo: Se deve incluir o símbolo R$
    
    Returns:
        String formatada
    
    Examples:
        >>> formatar_moeda(50.0)
        'R$ 50,00'
        >>> formatar_moeda(1299.90, simbolo=False)
        '1.299,90'
    """
    if valor is None:
        valor = 0.0
    
    valor_decimal = Decimal(str(valor)).quantize(Decimal('0.01'), rounding=ROUND_DOWN)
    
    # Formata com separadores brasileiros
    valor_str = f"{valor_decimal:,.2f}"
    valor_str = valor_str.replace(",", "X").replace(".", ",").replace("X", ".")
    
    if simbolo:
        return f"R$ {valor_str}"
    return valor_str


def formatar_data(data: datetime, formato: str = "dd/mm/aaaa HH:MM") -> str:
    """
    Formata uma data para o padrão brasileiro
    
    Args:
        data: Objeto datetime
        formato: Formato desejado
    
    Returns:
        String formatada
    
    Examples:
        >>> formatar_data(datetime.now())
        '25/01/2024 14:30'
    """
    if not data:
        return "N/A"
    
    # Converte para timezone brasileiro se necessário
    if data.tzinfo is None:
        data = pytz.UTC.localize(data)
    
    tz_brasil = pytz.timezone('America/Sao_Paulo')
    data_brasil = data.astimezone(tz_brasil)
    
    # Mapeamento de formatos
    formatos = {
        "dd/mm/aaaa": "%d/%m/%Y",
        "dd/mm/aaaa HH:MM": "%d/%m/%Y %H:%M",
        "dd/mm/aaaa HH:MM:SS": "%d/%m/%Y %H:%M:%S",
        "HH:MM": "%H:%M",
        "dd/mm": "%d/%m",
        "extenso": "%d de %B de %Y",
        "dia_semana": "%A, %d/%m/%Y",
    }
    
    formato_python = formatos.get(formato, "%d/%m/%Y %H:%M")
    return data_brasil.strftime(formato_python)


def formatar_tempo(segundos: int) -> str:
    """
    Formata segundos para formato legível
    
    Args:
        segundos: Quantidade de segundos
    
    Returns:
        String formatada
    
    Examples:
        >>> formatar_tempo(3661)
        '1h 1m 1s'
        >>> formatar_tempo(300)
        '5m 0s'
    """
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
    """
    Formata números grandes com separadores
    
    Args:
        numero: Número a ser formatado
    
    Returns:
        String formatada
    
    Examples:
        >>> formatar_numero(1000000)
        '1.000.000'
    """
    return f"{numero:,}".replace(",", ".")


# ============================================
# GERAÇÃO DE QR CODE PIX
# ============================================

def gerar_qr_code_pix(payload: str, tamanho: int = 300) -> BytesIO:
    """
    Gera QR Code do Pix
    
    Args:
        payload: Payload PIX
        tamanho: Tamanho da imagem
    
    Returns:
        BytesIO com a imagem do QR Code
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Redimensiona
    img = img.resize((tamanho, tamanho), Image.Resampling.LANCZOS)
    
    # Salva em BytesIO
    output = BytesIO()
    img.save(output, format='PNG')
    output.seek(0)
    
    return output


def gerar_qr_code_base64(payload: str) -> str:
    """
    Gera QR Code em base64
    
    Args:
        payload: Payload PIX
    
    Returns:
        String base64 da imagem
    """
    qr_image = gerar_qr_code_pix(payload)
    return base64.b64encode(qr_image.read()).decode()


def gerar_copia_cola_pix(chave: str, valor: float, descricao: str = "") -> str:
    """
    Gera código copia e cola do Pix (simplificado)
    
    Args:
        chave: Chave PIX
        valor: Valor do pagamento
        descricao: Descrição do pagamento
    
    Returns:
        Código copia e cola
    """
    # Este é um placeholder - você precisará implementar
    # o payload completo do PIX conforme especificação do BACEN
    payload = f"PIX|{chave}|{valor:.2f}|{descricao}"
    return payload


# ============================================
// ... continua na próxima parte

# ============================================
# VALIDAÇÕES
# ============================================

def validar_email(email: str) -> bool:
    """
    Valida formato de email
    
    Args:
        email: Email a ser validado
    
    Returns:
        True se válido
    """
    if not email:
        return False
    
    padrao = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(padrao, email))


def validar_telefone(telefone: str) -> bool:
    """
    Valida formato de telefone brasileiro
    
    Args:
        telefone: Número de telefone
    
    Returns:
        True se válido
    """
    if not telefone:
        return False
    
    # Remove caracteres não numéricos
    numeros = re.sub(r'\D', '', telefone)
    
    # Verifica se tem 10 ou 11 dígitos (com DDD)
    return len(numeros) in [10, 11]


def validar_cpf(cpf: str) -> bool:
    """
    Valida CPF
    
    Args:
        cpf: CPF a ser validado
    
    Returns:
        True se válido
    """
    if not cpf:
        return False
    
    # Remove caracteres não numéricos
    cpf = re.sub(r'\D', '', cpf)
    
    if len(cpf) != 11:
        return False
    
    # Verifica se todos os dígitos são iguais
    if cpf == cpf[0] * 11:
        return False
    
    # Validação dos dígitos verificadores
    for i in range(9, 11):
        soma = sum(int(cpf[num]) * ((i+1) - num) for num in range(0, i))
        digito = (soma * 10) % 11
        if digito == 10:
            digito = 0
        if digito != int(cpf[i]):
            return False
    
    return True


def validar_valor(valor_str: str) -> Tuple[bool, float]:
    """
    Valida e converte string para valor monetário
    
    Args:
        valor_str: String do valor
    
    Returns:
        Tupla (válido, valor_float)
    """
    if not valor_str:
        return False, 0.0
    
    # Remove símbolos e espaços
    valor_str = valor_str.replace('R$', '').replace(' ', '')
    
    # Substitui vírgula por ponto
    valor_str = valor_str.replace('.', '').replace(',', '.')
    
    try:
        valor = float(valor_str)
        if valor <= 0:
            return False, 0.0
        return True, valor
    except ValueError:
        return False, 0.0


def validar_senha(senha: str) -> Tuple[bool, str]:
    """
    Valida força da senha
    
    Args:
        senha: Senha a ser validada
    
    Returns:
        Tupla (válida, mensagem)
    """
    if len(senha) < 8:
        return False, "Senha deve ter no mínimo 8 caracteres"
    
    if not re.search(r'[A-Z]', senha):
        return False, "Senha deve ter pelo menos uma letra maiúscula"
    
    if not re.search(r'[a-z]', senha):
        return False, "Senha deve ter pelo menos uma letra minúscula"
    
    if not re.search(r'\d', senha):
        return False, "Senha deve ter pelo menos um número"
    
    return True, "Senha válida"


# ============================================
// ... continua na próxima parte

# ============================================
# SANITIZAÇÃO E LIMPEZA DE DADOS
# ============================================

def sanitizar_texto(texto: str, max_length: int = 1000) -> str:
    """
    Limpa e sanitiza texto
    
    Args:
        texto: Texto a ser sanitizado
        max_length: Tamanho máximo
    
    Returns:
        Texto sanitizado
    """
    if not texto:
        return ""
    
    # Remove caracteres especiais perigosos
    texto = texto.replace('<', '&lt;').replace('>', '&gt;')
    
    # Remove múltiplos espaços
    texto = ' '.join(texto.split())
    
    # Limita tamanho
    if len(texto) > max_length:
        texto = texto[:max_length-3] + "..."
    
    return texto


def sanitizar_username(username: str) -> str:
    """
    Limpa username do Telegram
    
    Args:
        username: Username a ser sanitizado
    
    Returns:
        Username limpo
    """
    if not username:
        return ""
    
    # Remove @ se existir
    username = username.lstrip('@')
    
    # Mantém apenas caracteres válidos
    username = re.sub(r'[^a-zA-Z0-9_]', '', username)
    
    return username


def escape_markdown(texto: str) -> str:
    """
    Escapa caracteres especiais do Markdown
    
    Args:
        texto: Texto a ser escapado
    
    Returns:
        Texto escapado para Markdown
    """
    if not texto:
        return ""
    
    caracteres_especiais = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    
    for char in caracteres_especiais:
        texto = texto.replace(char, f'\\{char}')
    
    return texto


def escape_html(texto: str) -> str:
    """
    Escapa caracteres HTML
    
    Args:
        texto: Texto a ser escapado
    
    Returns:
        Texto escapado para HTML
    """
    if not texto:
        return ""
    
    escapes = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#x27;',
    }
    
    for char, escape in escapes.items():
        texto = texto.replace(char, escape)
    
    return texto


# ============================================
// ... continua na próxima parte

# ============================================
# GERAÇÃO DE CÓDIGOS E HASHES
# ============================================

def gerar_codigo(tamanho: int = 8, tipo: str = "alfanumerico") -> str:
    """
    Gera código aleatório
    
    Args:
        tamanho: Tamanho do código
        tipo: 'numerico', 'alfabetico', 'alfanumerico'
    
    Returns:
        Código gerado
    """
    if tipo == "numerico":
        caracteres = string.digits
    elif tipo == "alfabetico":
        caracteres = string.ascii_uppercase
    else:
        caracteres = string.ascii_uppercase + string.digits
    
    return ''.join(secrets.choice(caracteres) for _ in range(tamanho))


def gerar_hash(texto: str, algoritmo: str = "sha256") -> str:
    """
    Gera hash de um texto
    
    Args:
        texto: Texto para gerar hash
        algoritmo: Algoritmo de hash
    
    Returns:
        Hash gerado
    """
    if algoritmo == "md5":
        return hashlib.md5(texto.encode()).hexdigest()
    elif algoritmo == "sha1":
        return hashlib.sha1(texto.encode()).hexdigest()
    else:
        return hashlib.sha256(texto.encode()).hexdigest()


def gerar_token(length: int = 32) -> str:
    """
    Gera token seguro
    
    Args:
        length: Tamanho do token
    
    Returns:
        Token hexadecimal
    """
    return secrets.token_hex(length)


# ============================================
// ... continua na próxima parte

# ============================================
# MANIPULAÇÃO DE ARQUIVOS
# ============================================

def criar_diretorio_se_nao_existe(caminho: str) -> bool:
    """
    Cria diretório se não existir
    
    Args:
        caminho: Caminho do diretório
    
    Returns:
        True se criou ou já existe
    """
    try:
        os.makedirs(caminho, exist_ok=True)
        return True
    except Exception as e:
        logger.error(f"Erro ao criar diretório {caminho}: {e}")
        return False


def salvar_arquivo(bytes_io: BytesIO, caminho: str) -> bool:
    """
    Salva BytesIO em arquivo
    
    Args:
        bytes_io: Objeto BytesIO
        caminho: Caminho para salvar
    
    Returns:
        True se salvou com sucesso
    """
    try:
        with open(caminho, 'wb') as f:
            f.write(bytes_io.read())
        return True
    except Exception as e:
        logger.error(f"Erro ao salvar arquivo {caminho}: {e}")
        return False


def ler_arquivo_txt(caminho: str) -> Optional[str]:
    """
    Lê arquivo de texto
    
    Args:
        caminho: Caminho do arquivo
    
    Returns:
        Conteúdo do arquivo
    """
    try:
        with open(caminho, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logger.error(f"Erro ao ler arquivo {caminho}: {e}")
        return None


# ============================================
// ... continua na próxima parte

# ============================================
# CÁLCULOS E FÓRMULAS
# ============================================

def calcular_porcentagem(valor: float, porcentagem: float) -> float:
    """
    Calcula porcentagem de um valor
    
    Args:
        valor: Valor base
        porcentagem: Porcentagem
    
    Returns:
        Valor calculado
    """
    return (valor * porcentagem) / 100


def calcular_desconto(valor: float, desconto: float, tipo: str = "porcentagem") -> float:
    """
    Calcula valor com desconto
    
    Args:
        valor: Valor original
        desconto: Valor do desconto
        tipo: 'porcentagem' ou 'fixo'
    
    Returns:
        Valor com desconto
    """
    if tipo == "porcentagem":
        desconto_valor = calcular_porcentagem(valor, desconto)
    else:
        desconto_valor = desconto
    
    return max(0, valor - desconto_valor)


def calcular_comissao_afiliado(valor_venda: float, porcentagem_comissao: float) -> float:
    """
    Calcula comissão de afiliado
    
    Args:
        valor_venda: Valor da venda
        porcentagem_comissao: Porcentagem de comissão
    
    Returns:
        Valor da comissão
    """
    comissao = calcular_porcentagem(valor_venda, porcentagem_comissao)
    return round(comissao, 2)


# ============================================
// ... continua na próxima parte

# ============================================
# PAGINAÇÃO
# ============================================

class Paginacao:
    """Sistema de paginação para listas"""
    
    def __init__(self, itens: List[Any], itens_por_pagina: int = 10):
        """
        Inicializa paginação
        
        Args:
            itens: Lista de itens
            itens_por_pagina: Quantidade de itens por página
        """
        self.itens = itens
        self.itens_por_pagina = itens_por_pagina
        self.total_paginas = max(1, (len(itens) + itens_por_pagina - 1) // itens_por_pagina)
    
    def get_pagina(self, pagina: int) -> List[Any]:
        """
        Retorna itens de uma página específica
        
        Args:
            pagina: Número da página (começa em 1)
        
        Returns:
            Lista de itens da página
        """
        pagina = max(1, min(pagina, self.total_paginas))
        inicio = (pagina - 1) * self.itens_por_pagina
        fim = inicio + self.itens_por_pagina
        return self.itens[inicio:fim]
    
    def tem_proxima(self, pagina: int) -> bool:
        """Verifica se tem próxima página"""
        return pagina < self.total_paginas
    
    def tem_anterior(self, pagina: int) -> bool:
        """Verifica se tem página anterior"""
        return pagina > 1


# ============================================
// ... continua na próxima parte

# ============================================
# CORES E EMOJIS
# ============================================

# Constantes de emojis
EMOJIS = {
    "sucesso": "✅",
    "erro": "❌",
    "aviso": "⚠️",
    "info": "ℹ️",
    "dinheiro": "💰",
    "carrinho": "🛒",
    "estrela": "⭐",
    "trofeu": "🏆",
    "coroa": "👑",
    "fogo": "🔥",
    "foguete": "🚀",
    "presente": "🎁",
    "loja": "🏪",
    "usuario": "👤",
    "admin": "🛡️",
    "banido": "🚫",
    "relogio": "⏰",
    "grafico": "📊",
    "documento": "📄",
    "link": "🔗",
    "cadeado": "🔒",
    "chave": "🔑",
    "lupa": "🔍",
    "sino": "🔔",
    "coracao": "❤️",
    "mais": "➕",
    "menos": "➖",
    "editar": "✏️",
    "lixeira": "🗑️",
    "voltar": "🔙",
    "proximo": "➡️",
    "anterior": "⬅️",
    "recarregar": "🔄",
    "download": "📥",
    "upload": "📤",
    "compartilhar": "📤",
    "olho": "👁️",
    "olhos": "👀",
    "mao_acenando": "👋",
    "mao_joinha": "👍",
    "mao_negativo": "👎",
    "pensando": "🤔",
    "feliz": "😊",
    "triste": "😢",
    "bravo": "😡",
    "surpreso": "😱",
    "legal": "😎",
    "piscando": "😉",
}

# Ranking emojis
MEDALHAS = ["🥇", "🥈", "🥉"] + ["🏅"] * 7

# Constantes de status
STATUS_EMOJI = {
    "pendente": "🟡",
    "aprovado": "🟢",
    "cancelado": "🔴",
    "expirado": "⚫",
    "reembolsado": "🔵",
}


def get_emoji(categoria: str) -> str:
    """
    Retorna emoji por categoria
    
    Args:
        categoria: Nome da categoria
    
    Returns:
        Emoji correspondente
    """
    return EMOJIS.get(categoria, "📌")


def get_medalha(posicao: int) -> str:
    """
    Retorna emoji de medalha por posição
    
    Args:
        posicao: Posição no ranking (1-indexed)
    
    Returns:
        Emoji da medalha
    """
    if posicao < 1:
        return "👤"
    return MEDALHAS[min(posicao - 1, len(MEDALHAS) - 1)]


def get_status_emoji(status: str) -> str:
    """
    Retorna emoji de status
    
    Args:
        status: Status da transação
    
    Returns:
        Emoji do status
    """
    return STATUS_EMOJI.get(status.lower(), "⚪")


# ============================================
// ... continua na próxima parte

# ============================================
# FUNÇÕES ASSÍNCRONAS AUXILIARES
# ============================================

async def enviar_mensagem_com_delay(bot, chat_id, texto, delay=1.0):
    """
    Envia mensagem com delay (para evitar flood)
    
    Args:
        bot: Instância do bot
        chat_id: ID do chat
        texto: Texto da mensagem
        delay: Delay em segundos
    """
    import asyncio
    await asyncio.sleep(delay)
    await bot.send_message(chat_id=chat_id, text=texto)


async def processar_lote(itens, funcao, tamanho_lote=10, delay=0.5):
    """
    Processa itens em lotes
    
    Args:
        itens: Lista de itens
        funcao: Função async para processar cada item
        tamanho_lote: Tamanho do lote
        delay: Delay entre lotes
    """
    import asyncio
    
    for i in range(0, len(itens), tamanho_lote):
        lote = itens[i:i+tamanho_lote]
        tarefas = [funcao(item) for item in lote]
        await asyncio.gather(*tarefas)
        
        if i + tamanho_lote < len(itens):
            await asyncio.sleep(delay)


# ============================================
// ... continua na próxima parte

# ============================================
# LOGGING PERSONALIZADO
# ============================================

def log_com_contexto(mensagem: str, level: str = "info", **kwargs):
    """
    Log com informações de contexto
    
    Args:
        mensagem: Mensagem de log
        level: Nível do log
        **kwargs: Dados adicionais
    """
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


# ============================================
// ... continua na próxima parte

# ============================================
# FUNÇÕES DE ESTATÍSTICAS
# ============================================

def calcular_media(valores: List[float]) -> float:
    """Calcula média de uma lista de valores"""
    if not valores:
        return 0.0
    return sum(valores) / len(valores)


def calcular_total(valores: List[float]) -> float:
    """Calcula soma total"""
    return sum(valores)


def calcular_taxa_conversao(visitas: int, compras: int) -> float:
    """
    Calcula taxa de conversão
    
    Args:
        visitas: Número de visitas
        compras: Número de compras
    
    Returns:
        Taxa de conversão em porcentagem
    """
    if visitas == 0:
        return 0.0
    return (compras / visitas) * 100


# ============================================
// ... continua na próxima parte

# ============================================
# EXPORTAÇÕES
# ============================================

__all__ = [
    # Formatação
    'formatar_moeda',
    'formatar_data',
    'formatar_tempo',
    'formatar_numero',
    
    # QR Code
    'gerar_qr_code_pix',
    'gerar_qr_code_base64',
    'gerar_copia_cola_pix',
    
    # Validações
    'validar_email',
    'validar_telefone',
    'validar_cpf',
    'validar_valor',
    'validar_senha',
    
    # Sanitização
    'sanitizar_texto',
    'sanitizar_username',
    'escape_markdown',
    'escape_html',
    
    # Geração
    'gerar_codigo',
    'gerar_hash',
    'gerar_token',
    
    # Arquivos
    'criar_diretorio_se_nao_existe',
    'salvar_arquivo',
    'ler_arquivo_txt',
    
    # Cálculos
    'calcular_porcentagem',
    'calcular_desconto',
    'calcular_comissao_afiliado',
    
    # Paginação
    'Paginacao',
    
    # Emojis
    'EMOJIS',
    'MEDALHAS',
    'STATUS_EMOJI',
    'get_emoji',
    'get_medalha',
    'get_status_emoji',
    
    # Async
    'enviar_mensagem_com_delay',
    'processar_lote',
    
    # Logging
    'log_com_contexto',
    
    # Estatísticas
    'calcular_media',
    'calcular_total',
    'calcular_taxa_conversao',
]
