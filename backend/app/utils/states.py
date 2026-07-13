"""
Estados de conversação do bot - Gerenciamento de ForceReply e Conversas
"""
from telegram.ext import ConversationHandler
from enum import IntEnum, auto

# ============================================
# ESTADOS GERAIS
# ============================================

class EstadosConversa(IntEnum):
    """Estados base para conversas"""
    # Estados iniciais
    INICIO = 0
    MENU_PRINCIPAL = 1
    
    # Estados de espera
    AGUARDANDO_INPUT = 10
    AGUARDANDO_CONFIRMACAO = 11
    PROCESSANDO = 12
    
    # Estados finais
    CONCLUIDO = 20
    CANCELADO = 21
    ERRO = 22


# ============================================
# ESTADOS DE RECARGA (PIX)
# ============================================

class EstadosRecarga(IntEnum):
    """Estados para o fluxo de recarga"""
    # Menu inicial de recarga
    MENU_RECARGA = 100
    
    # Seleção de valor
    SELECIONAR_VALOR = 101
    DIGITAR_VALOR_PERSONALIZADO = 102
    CONFIRMAR_VALOR = 103
    
    # Geração do Pix
    GERAR_QR_CODE = 110
    EXIBIR_QR_CODE = 111
    AGUARDAR_PAGAMENTO = 112
    
    # Verificação
    VERIFICAR_PAGAMENTO = 120
    PAGAMENTO_APROVADO = 121
    PAGAMENTO_REJEITADO = 122
    PAGAMENTO_EXPIRADO = 123


# ============================================
// ... continua na próxima parte

# ============================================
# ESTADOS DE COMPRA
# ============================================

class EstadosCompra(IntEnum):
    """Estados para o fluxo de compra"""
    # Navegação da loja
    MENU_LOJA = 200
    LISTAR_CATEGORIAS = 201
    LISTAR_PRODUTOS = 202
    VER_PRODUTO = 203
    
    # Processo de compra
    CONFIRMAR_COMPRA = 210
    PROCESSAR_COMPRA = 211
    ENTREGAR_PRODUTO = 212
    
    # Pós-compra
    COMPRA_CONCLUIDA = 220
    AVALIAR_PRODUTO = 221
    REPORTAR_PROBLEMA = 222
    
    # Estoque insuficiente
    ATIVAR_ALERTA = 230
    ALERTA_ATIVADO = 231


# ============================================
# ESTADOS DE CADASTRO
# ============================================

class EstadosCadastro(IntEnum):
    """Estados para cadastros e edições"""
    # WhatsApp
    SOLICITAR_WHATSAPP = 300
    DIGITAR_WHATSAPP = 301
    CONFIRMAR_WHATSAPP = 302
    
    # Nome
    SOLICITAR_NOME = 310
    DIGITAR_NOME = 311
    
    # Email
    SOLICITAR_EMAIL = 320
    DIGITAR_EMAIL = 321


# ============================================
# ESTADOS DO AFILIADO
# ============================================

class EstadosAfiliado(IntEnum):
    """Estados para o sistema de afiliados"""
    MENU_AFILIADO = 400
    VER_DESEMPENHO = 401
    COPIAR_LINK = 402
    
    # Saque
    SOLICITAR_SAQUE = 410
    CONFIRMAR_SAQUE = 411
    SAQUE_REALIZADO = 412


# ============================================
// ... continua na próxima parte

# ============================================
# ESTADOS DO ADMIN - CONFIGURAÇÕES
# ============================================

class EstadosAdmin(IntEnum):
    """Estados para o painel administrativo"""
    # Menu principal
    MENU_ADMIN = 500
    MENU_CONFIG = 501
    MENU_ACOES = 502
    MENU_TRANSACOES = 503
    
    # Configurações gerais
    CONFIG_GERAL = 510
    EDITAR_LINK_SUPORTE = 511
    EDITAR_LOGS = 512
    EDITAR_SEPARADOR = 513
    ATIVAR_MANUTENCAO = 514
    
    # Gerenciar admins
    ADD_ADMIN = 520
    REMOVER_ADMIN = 521
    LISTAR_ADMINS = 522


# ============================================
# ESTADOS DO ADMIN - USUÁRIOS
# ============================================

class EstadosAdminUsuarios(IntEnum):
    """Estados para gerenciamento de usuários"""
    MENU_USUARIOS = 600
    
    # Pesquisa
    PESQUISAR_USUARIO = 601
    DIGITAR_ID_BUSCA = 602
    EXIBIR_USUARIO = 603
    
    # Editar saldo
    EDITAR_SALDO = 610
    DIGITAR_ID_SALDO = 611
    DIGITAR_VALOR_SALDO = 612
    CONFIRMAR_SALDO = 613
    
    # Banir usuário
    BANIR_USUARIO = 620
    DIGITAR_ID_BAN = 621
    DIGITAR_MOTIVO_BAN = 622
    CONFIRMAR_BAN = 623
    
    # Desbanir
    DESBANIR_USUARIO = 630
    DIGITAR_ID_UNBAN = 631
    CONFIRMAR_UNBAN = 632
    
    # Enviar mensagem (broadcast)
    ENVIAR_MENSAGEM = 640
    DIGITAR_MENSAGEM = 641
    CONFIRMAR_ENVIO = 642
    ENVIANDO = 643
    
    # Bônus em massa
    BONUS_MASSA = 650
    DIGITAR_VALOR_BONUS = 651
    SELECIONAR_FILTRO = 652
    CONFIRMAR_BONUS = 653


# ============================================
// ... continua na próxima parte

# ============================================
# ESTADOS DO ADMIN - PRODUTOS
# ============================================

class EstadosAdminProdutos(IntEnum):
    """Estados para gerenciamento de produtos"""
    MENU_PRODUTOS = 700
    
    # Adicionar produto
    ADD_PRODUTO = 710
    DIGITAR_NOME_PRODUTO = 711
    DIGITAR_DESCRICAO = 712
    DIGITAR_VALOR = 713
    SELECIONAR_CATEGORIA = 714
    DIGITAR_GARANTIA = 715
    ENVIAR_IMAGEM = 716
    CONFIRMAR_PRODUTO = 717
    
    # Editar produto
    EDITAR_PRODUTO = 720
    SELECIONAR_PRODUTO = 721
    EDITAR_CAMPO = 722
    DIGITAR_NOVO_VALOR = 723
    
    # Remover produto
    REMOVER_PRODUTO = 730
    CONFIRMAR_REMOCAO = 731
    
    # Mídias
    MENU_MIDIAS = 740
    ADD_IMAGEM = 741
    REMOVER_IMAGEM = 742


# ============================================
# ESTADOS DO ADMIN - ESTOQUE
# ============================================

class EstadosAdminEstoque(IntEnum):
    """Estados para gerenciamento de estoque"""
    MENU_ESTOQUE = 800
    
    # Adicionar logins
    ADD_LOGINS = 810
    SELECIONAR_PRODUTO_ESTOQUE = 811
    ENVIAR_ARQUIVO_LOGINS = 812
    DIGITAR_LOGINS_MANUAL = 813
    CONFIRMAR_ADD_LOGINS = 814
    
    # Ver estoque
    VER_ESTOQUE = 820
    SELECIONAR_PRODUTO_VER = 821
    EXIBIR_ESTOQUE = 822
    
    # Remover logins
    REMOVER_LOGINS = 830
    DIGITAR_QUANTIDADE = 831
    CONFIRMAR_REMOCAO_LOGINS = 832
    
    # Zerar estoque
    ZERAR_ESTOQUE = 840
    CONFIRMAR_ZERAR = 841
    
    # Alterar preços
    ALTERAR_PRECOS = 850
    DIGITAR_PORCENTAGEM = 851
    SELECIONAR_TIPO_ALTERACAO = 852  # aumento ou redução
    CONFIRMAR_ALTERACAO = 853
    
    # Notificar alertas
    NOTIFICAR_ALERTAS = 860
    SELECIONAR_PRODUTO_ALERTA = 861
    CONFIRMAR_NOTIFICACAO = 862


# ============================================
// ... continua na próxima parte

# ============================================
# ESTADOS DO ADMIN - CATEGORIAS
# ============================================

class EstadosAdminCategorias(IntEnum):
    """Estados para gerenciamento de categorias"""
    MENU_CATEGORIAS = 900
    
    # Adicionar categoria
    ADD_CATEGORIA = 910
    DIGITAR_NOME_CATEGORIA = 911
    DIGITAR_EMOJI = 912
    DIGITAR_DESCRICAO_CATEGORIA = 913
    DIGITAR_ORDEM = 914
    CONFIRMAR_CATEGORIA = 915
    
    # Editar categoria
    EDITAR_CATEGORIA = 920
    SELECIONAR_CATEGORIA_EDITAR = 921
    DIGITAR_NOVO_NOME = 922
    
    # Remover categoria
    REMOVER_CATEGORIA = 930
    CONFIRMAR_REMOCAO_CATEGORIA = 931
    
    # Reordenar
    REORDENAR_CATEGORIAS = 940
    DIGITAR_NOVA_ORDEM = 941


# ============================================
# ESTADOS DO ADMIN - PAGAMENTOS
# ============================================

class EstadosAdminPagamentos(IntEnum):
    """Estados para configurações de pagamento"""
    MENU_PAGAMENTOS = 1000
    
    # Configurar API
    CONFIG_API = 1010
    DIGITAR_TOKEN = 1011
    DIGITAR_PUBLIC_KEY = 1012
    TESTAR_CONEXAO = 1013
    
    # Valores
    CONFIG_VALORES = 1020
    DIGITAR_VALOR_MINIMO = 1021
    DIGITAR_VALOR_MAXIMO = 1022
    
    # Expiração
    CONFIG_EXPIRACAO = 1030
    DIGITAR_TEMPO_EXPIRACAO = 1031
    
    # Bônus depósito
    CONFIG_BONUS = 1040
    DIGITAR_PORCENTAGEM_BONUS = 1041


# ============================================
// ... continua na próxima parte

# ============================================
# ESTADOS DO ADMIN - AFILIADOS
# ============================================

class EstadosAdminAfiliados(IntEnum):
    """Estados para configurações de afiliados"""
    MENU_AFILIADOS = 1100
    
    # Ativar/Desativar
    TOGGLE_AFILIADOS = 1110
    
    # Definir comissão
    DEFINIR_COMISSAO = 1120
    DIGITAR_PORCENTAGEM_COMISSAO = 1121
    
    # Metas e bônus
    METAS_AFILIADOS = 1130
    DIGITAR_META = 1131
    DIGITAR_BONUS_META = 1132


# ============================================
# ESTADOS DO ADMIN - CUPONS
# ============================================

class EstadosAdminCupons(IntEnum):
    """Estados para gerenciamento de cupons"""
    MENU_CUPONS = 1200
    
    # Criar cupom
    CRIAR_CUPOM = 1210
    DIGITAR_CODIGO_CUPOM = 1211
    DIGITAR_VALOR_DESCONTO = 1212
    SELECIONAR_TIPO_DESCONTO = 1213  # porcentagem ou fixo
    DIGITAR_QUANTIDADE = 1214
    DEFINIR_VALIDADE = 1215
    CONFIRMAR_CUPOM = 1216
    
    # Remover cupom
    REMOVER_CUPOM = 1220
    SELECIONAR_CUPOM = 1221
    CONFIRMAR_REMOCAO_CUPOM = 1222


# ============================================
# ESTADOS DO ADMIN - PESQUISA DE SERVIÇOS
# ============================================

class EstadosAdminPesquisa(IntEnum):
    """Estados para configuração da pesquisa de serviços"""
    MENU_PESQUISA = 1300
    
    # Adicionar imagem
    ADD_IMAGEM_PESQUISA = 1310
    ENVIAR_IMAGEM_PESQUISA = 1311
    DIGITAR_TERMO_BUSCA = 1312
    CONFIRMAR_IMAGEM = 1313
    
    # Remover imagem
    REMOVER_IMAGEM_PESQUISA = 1320
    SELECIONAR_IMAGEM = 1321
    CONFIRMAR_REMOCAO_IMAGEM = 1322


# ============================================
# ESTADOS DO ADMIN - TRANSMISSÃO (BROADCAST)
# ============================================

class EstadosAdminBroadcast(IntEnum):
    """Estados para envio de mensagens em massa"""
    INICIAR_BROADCAST = 1400
    
    # Configurar transmissão
    DIGITAR_TITULO = 1401
    DIGITAR_TEXTO = 1402
    ADICIONAR_IMAGEM = 1403
    ADICIONAR_BOTOES = 1404
    SELECIONAR_PUBLICO = 1405  # todos, apenas com saldo, etc.
    
    # Pré-visualização
    PRE_VISUALIZAR = 1410
    CONFIRMAR_ENVIO_BROADCAST = 1411
    
    # Envio
    ENVIANDO_BROADCAST = 1420
    BROADCAST_CONCLUIDO = 1421


# ============================================
// ... continua na próxima parte

# ============================================
# ESTADOS DO CLIENTE - PESQUISA DE SERVIÇOS
# ============================================

class EstadosPesquisa(IntEnum):
    """Estados para pesquisa de serviços pelo cliente"""
    MENU_PESQUISA = 1500
    
    # Pesquisar
    DIGITAR_TERMO = 1501
    EXIBIR_RESULTADOS = 1502
    
    # Filtros
    APLICAR_FILTRO = 1510
    FILTRAR_PRECO = 1511
    FILTRAR_CATEGORIA = 1512


# ============================================
# ESTADOS DO CLIENTE - AVALIAÇÕES
# ============================================

class EstadosAvaliacao(IntEnum):
    """Estados para avaliação de produtos"""
    MENU_AVALIAR = 1600
    
    # Avaliar produto
    SELECIONAR_NOTA = 1601
    DIGITAR_COMENTARIO = 1602
    CONFIRMAR_AVALIACAO = 1603
    
    # Ver avaliações
    VER_AVALIACOES = 1610
    EXIBIR_AVALIACOES = 1611


# ============================================
# ESTADOS DO CLIENTE - SUPORTE
# ============================================

class EstadosSuporte(IntEnum):
    """Estados para suporte ao cliente"""
    MENU_SUPORTE = 1700
    
    # Abrir ticket
    ABRIR_TICKET = 1701
    DESCREVER_PROBLEMA = 1702
    ANEXAR_IMAGEM = 1703
    CONFIRMAR_TICKET = 1704
    TICKET_ABERTO = 1705
    
    # Ver tickets
    VER_TICKETS = 1710
    EXIBIR_TICKET = 1711
    
    # Responder ticket (admin)
    RESPONDER_TICKET = 1720
    DIGITAR_RESPOSTA = 1721
    ENVIAR_RESPOSTA = 1722


# ============================================
// ... continua na próxima parte

# ============================================
# MAPEAMENTO DE ESTADOS
# ============================================

# Mapeamento de callbacks para estados
CALLBACK_PARA_ESTADO = {
    # Menu principal
    "menu_principal": EstadosConversa.MENU_PRINCIPAL,
    "menu_loja": EstadosCompra.MENU_LOJA,
    "menu_perfil": EstadosConversa.MENU_PRINCIPAL,
    "menu_recarga": EstadosRecarga.MENU_RECARGA,
    "menu_ranking": EstadosConversa.MENU_PRINCIPAL,
    "menu_info": EstadosConversa.MENU_PRINCIPAL,
    
    # Admin
    "admin_menu": EstadosAdmin.MENU_ADMIN,
    "admin_config": EstadosAdmin.MENU_CONFIG,
    "admin_acoes": EstadosAdmin.MENU_ACOES,
    "admin_transacoes": EstadosAdmin.MENU_TRANSACOES,
}

# Estados que requerem ForceReply
ESTADOS_FORCE_REPLY = [
    EstadosRecarga.DIGITAR_VALOR_PERSONALIZADO,
    EstadosCadastro.DIGITAR_WHATSAPP,
    EstadosCadastro.DIGITAR_NOME,
    EstadosAdminUsuarios.DIGITAR_ID_BUSCA,
    EstadosAdminUsuarios.DIGITAR_VALOR_SALDO,
    EstadosAdminUsuarios.DIGITAR_MOTIVO_BAN,
    EstadosAdminUsuarios.DIGITAR_MENSAGEM,
    EstadosAdminProdutos.DIGITAR_NOME_PRODUTO,
    EstadosAdminProdutos.DIGITAR_DESCRICAO,
    EstadosAdminProdutos.DIGITAR_VALOR,
    EstadosAdminEstoque.DIGITAR_LOGINS_MANUAL,
    EstadosAdminCategorias.DIGITAR_NOME_CATEGORIA,
    EstadosAdminPagamentos.DIGITAR_TOKEN,
    EstadosAdminCupons.DIGITAR_CODIGO_CUPOM,
    EstadosPesquisa.DIGITAR_TERMO,
    EstadosAvaliacao.DIGITAR_COMENTARIO,
    EstadosSuporte.DESCREVER_PROBLEMA,
]

# Estados que aceitam upload de arquivo
ESTADOS_UPLOAD = [
    EstadosAdminProdutos.ENVIAR_IMAGEM,
    EstadosAdminEstoque.ENVIAR_ARQUIVO_LOGINS,
    EstadosAdminPesquisa.ENVIAR_IMAGEM_PESQUISA,
    EstadosAdminBroadcast.ADICIONAR_IMAGEM,
    EstadosSuporte.ANEXAR_IMAGEM,
]


# ============================================
# FUNÇÕES AUXILIARES
# ============================================

def get_estado_por_callback(callback_data: str):
    """Retorna o estado correspondente a um callback"""
    return CALLBACK_PARA_ESTADO.get(callback_data, EstadosConversa.MENU_PRINCIPAL)


def is_force_reply(estado: int) -> bool:
    """Verifica se um estado requer ForceReply"""
    return estado in ESTADOS_FORCE_REPLY


def is_upload_state(estado: int) -> bool:
    """Verifica se um estado aceita upload de arquivo"""
    return estado in ESTADOS_UPLOAD


def get_conversation_timeout(estado: int) -> int:
    """
    Retorna o timeout para cada estado de conversa
    
    Args:
        estado: Estado atual da conversa
        
    Returns:
        Tempo em segundos
    """
    timeouts = {
        EstadosRecarga.AGUARDAR_PAGAMENTO: 300,  # 5 minutos
        EstadosAdminBroadcast.ENVIANDO_BROADCAST: 600,  # 10 minutos
        EstadosAdminUsuarios.ENVIANDO: 300,  # 5 minutos
    }
    
    return timeouts.get(estado, 120)  # 2 minutos padrão


def get_estado_nome(estado: int) -> str:
    """
    Retorna o nome amigável de um estado
    
    Args:
        estado: Estado da conversa
        
    Returns:
        Nome do estado
    """
    nomes = {
        EstadosConversa.MENU_PRINCIPAL: "Menu Principal",
        EstadosRecarga.MENU_RECARGA: "Recarga",
        EstadosCompra.MENU_LOJA: "Loja",
        EstadosAdmin.MENU_ADMIN: "Painel Admin",
        EstadosCadastro.SOLICITAR_WHATSAPP: "Cadastro WhatsApp",
    }
    
    return nomes.get(estado, f"Estado {estado}")


# ============================================
# CONSTANTES DE CONVERSATION HANDLER
# ============================================

# Estados finais para encerrar conversas
ESTADOS_FINAIS = {
    EstadosConversa.CONCLUIDO,
    EstadosConversa.CANCELADO,
    EstadosConversa.ERRO,
}

# Timeout padrão para conversas (em segundos)
TIMEOUT_PADRAO = 120

# Timeout estendido (para operações demoradas)
TIMEOUT_ESTENDIDO = 300
