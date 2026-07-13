"""
Todos os teclados e botões do bot - Módulo Cliente e Admin
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from typing import List, Dict, Optional

# ============================================
# MENU PRINCIPAL DO CLIENTE
# ============================================

def menu_principal(saldo: float = 0.0) -> InlineKeyboardMarkup:
    """Menu inicial do bot"""
    keyboard = [
        [InlineKeyboardButton("🔐 LOGINS | CONTAS PREMIUM", callback_data="menu_loja")],
        [
            InlineKeyboardButton("👤 PERFIL", callback_data="menu_perfil"),
            InlineKeyboardButton("💳 RECARGA", callback_data="menu_recarga")
        ],
        [InlineKeyboardButton("🏆 RANKING", callback_data="menu_ranking")],
        [
            InlineKeyboardButton("📞 SUPORTE", url="https://t.me/suporte"),
            InlineKeyboardButton("ℹ️ INFORMAÇÕES", callback_data="menu_info")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


# ============================================
# MENU DA LOJA
# ============================================

def menu_loja(categorias: List[Dict] = None) -> InlineKeyboardMarkup:
    """Menu da loja com categorias"""
    keyboard = []
    
    if categorias:
        for cat in categorias:
            emoji = cat.get('emoji', '📦')
            nome = cat.get('nome', 'Categoria')
            cat_id = cat.get('id', 0)
            total = cat.get('total_produtos', 0)
            
            keyboard.append([
                InlineKeyboardButton(
                    f"{emoji} {nome} ({total} itens)",
                    callback_data=f"cat_{cat_id}"
                )
            ])
    else:
        keyboard.append([
            InlineKeyboardButton("📦 Nenhuma categoria disponível", callback_data="nada")
        ])
    
    # Botão de pesquisa
    keyboard.append([
        InlineKeyboardButton("🔍 PESQUISAR SERVIÇOS", callback_data="pesquisar")
    ])
    
    # Botão voltar
    keyboard.append([
        InlineKeyboardButton("🔙 VOLTAR", callback_data="menu_principal")
    ])
    
    return InlineKeyboardMarkup(keyboard)


def menu_produtos(produtos: List[Dict] = None, categoria_id: int = 0) -> InlineKeyboardMarkup:
    """Menu de produtos de uma categoria"""
    keyboard = []
    
    if produtos:
        for prod in produtos:
            nome = prod.get('nome', 'Produto')
            valor = prod.get('valor', 0.0)
            estoque = prod.get('estoque', 0)
            prod_id = prod.get('id', 0)
            
            if estoque > 0:
                keyboard.append([
                    InlineKeyboardButton(
                        f"✅ {nome} - R$ {valor:.2f} ({estoque} un.)",
                        callback_data=f"ver_prod_{prod_id}"
                    )
                ])
            else:
                keyboard.append([
                    InlineKeyboardButton(
                        f"❌ {nome} - ESGOTADO",
                        callback_data=f"alerta_{prod_id}"
                    )
                ])
    else:
        keyboard.append([
            InlineKeyboardButton("📦 Nenhum produto disponível", callback_data="nada")
        ])
    
    # Botão voltar
    keyboard.append([
        InlineKeyboardButton("🔙 VOLTAR", callback_data="menu_loja")
    ])
    
    return InlineKeyboardMarkup(keyboard)


def menu_produto_detalhes(produto: Dict) -> InlineKeyboardMarkup:
    """Menu de detalhes do produto"""
    prod_id = produto.get('id', 0)
    estoque = produto.get('estoque', 0)
    
    keyboard = []
    
    if estoque > 0:
        keyboard.append([
            InlineKeyboardButton("🛒 COMPRAR", callback_data=f"comprar_{prod_id}")
        ])
    
    keyboard.append([
        InlineKeyboardButton("🔔 ATIVAR ALERTA", callback_data=f"alerta_{prod_id}")
    ])
    
    keyboard.append([
        InlineKeyboardButton("🔙 VOLTAR", callback_data=f"cat_{produto.get('categoria_id', 0)}")
    ])
    
    return InlineKeyboardMarkup(keyboard)


def menu_compra_confirmacao(produto_id: int, valor: float, saldo: float) -> InlineKeyboardMarkup:
    """Menu de confirmação de compra"""
    keyboard = []
    
    if saldo >= valor:
        keyboard.append([
            InlineKeyboardButton("✅ CONFIRMAR COMPRA", callback_data=f"confirmar_compra_{produto_id}")
        ])
    else:
        keyboard.append([
            InlineKeyboardButton("❌ SALDO INSUFICIENTE", callback_data="saldo_insuficiente")
        ])
    
    keyboard.append([
        InlineKeyboardButton("💳 RECARREGAR", callback_data="menu_recarga"),
        InlineKeyboardButton("🔙 CANCELAR", callback_data=f"ver_prod_{produto_id}")
    ])
    
    return InlineKeyboardMarkup(keyboard)


# ============================================
# MENU DO PERFIL
# ============================================

def menu_perfil() -> InlineKeyboardMarkup:
    """Menu do perfil do usuário"""
    keyboard = [
        [InlineKeyboardButton("📊 HISTÓRICO DE COMPRAS", callback_data="historico_compras")],
        [InlineKeyboardButton("📱 CADASTRAR WHATSAPP", callback_data="add_whatsapp")],
        [InlineKeyboardButton("🔗 AFILIADOS", callback_data="menu_afiliados")],
        [InlineKeyboardButton("⭐ AVALIAÇÕES", callback_data="minhas_avaliacoes")],
        [InlineKeyboardButton("🔙 VOLTAR", callback_data="menu_principal")]
    ]
    return InlineKeyboardMarkup(keyboard)


def menu_historico_compras(compras: List[Dict] = None) -> InlineKeyboardMarkup:
    """Menu de histórico de compras"""
    keyboard = []
    
    if compras:
        for compra in compras[:5]:  # Mostra últimas 5
            nome = compra.get('produto_nome', 'Produto')
            data = compra.get('data', '')
            compra_id = compra.get('id', 0)
            
            keyboard.append([
                InlineKeyboardButton(
                    f"📦 {nome} - {data}",
                    callback_data=f"detalhe_compra_{compra_id}"
                )
            ])
    
    keyboard.append([
        InlineKeyboardButton("📥 BAIXAR RELATÓRIO", callback_data="baixar_relatorio")
    ])
    
    keyboard.append([
        InlineKeyboardButton("🔙 VOLTAR", callback_data="menu_perfil")
    ])
    
    return InlineKeyboardMarkup(keyboard)


# ============================================
# MENU DE RECARGA
# ============================================

def menu_recarga() -> InlineKeyboardMarkup:
    """Menu de recarga"""
    keyboard = [
        [InlineKeyboardButton("💵 R$ 10,00", callback_data="recarga_10")],
        [InlineKeyboardButton("💵 R$ 20,00", callback_data="recarga_20")],
        [InlineKeyboardButton("💵 R$ 50,00", callback_data="recarga_50")],
        [InlineKeyboardButton("💵 R$ 100,00", callback_data="recarga_100")],
        [InlineKeyboardButton("💎 OUTRO VALOR", callback_data="recarga_outro")],
        [InlineKeyboardButton("🔙 VOLTAR", callback_data="menu_principal")]
    ]
    return InlineKeyboardMarkup(keyboard)


def menu_recarga_pix(transacao_id: int, valor: float, qr_code: str = "", copia_cola: str = "") -> InlineKeyboardMarkup:
    """Menu de pagamento Pix"""
    keyboard = [
        [InlineKeyboardButton("📋 COPIAR PIX", callback_data=f"copiar_pix_{transacao_id}")],
        [InlineKeyboardButton("✅ JÁ PAGUEI", callback_data=f"verificar_pagamento_{transacao_id}")],
        [InlineKeyboardButton("❌ CANCELAR", callback_data=f"cancelar_pix_{transacao_id}")],
        [InlineKeyboardButton("🔙 VOLTAR", callback_data="menu_recarga")]
    ]
    return InlineKeyboardMarkup(keyboard)


# ============================================
# MENU DO RANKING
# ============================================

def menu_ranking() -> InlineKeyboardMarkup:
    """Menu principal do ranking"""
    keyboard = [
        [
            InlineKeyboardButton("🛒 COMPRAS", callback_data="rank_compras"),
            InlineKeyboardButton("💎 RECARGAS", callback_data="rank_recargas")
        ],
        [
            InlineKeyboardButton("🔧 SERVIÇOS", callback_data="rank_servicos"),
            InlineKeyboardButton("💰 SALDO", callback_data="rank_saldo")
        ],
        [InlineKeyboardButton("🔙 VOLTAR", callback_data="menu_principal")]
    ]
    return InlineKeyboardMarkup(keyboard)


def menu_ranking_detalhes(top_10: List[Dict] = None, tipo: str = "compras") -> InlineKeyboardMarkup:
    """Menu de detalhes do ranking"""
    keyboard = []
    
    emojis = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
    
    if top_10:
        for i, user in enumerate(top_10[:10]):
            nome = user.get('nome', 'Usuário')
            valor = user.get('valor', 0)
            
            keyboard.append([
                InlineKeyboardButton(
                    f"{emojis[i]} {nome}",
                    callback_data=f"ver_perfil_{user.get('id', 0)}"
                )
            ])
    
    keyboard.append([
        InlineKeyboardButton("🔙 VOLTAR", callback_data="menu_ranking")
    ])
    
    return InlineKeyboardMarkup(keyboard)


# ============================================
# MENU DE AFILIADOS
# ============================================

def menu_afiliados(codigo: str = "", comissao: float = 0.0, indicacoes: int = 0) -> InlineKeyboardMarkup:
    """Menu do sistema de afiliados"""
    keyboard = [
        [InlineKeyboardButton("📊 MEU DESEMPENHO", callback_data="afiliado_desempenho")],
        [InlineKeyboardButton("📋 COPIAR LINK", callback_data=f"copiar_link_{codigo}")],
        [InlineKeyboardButton("💰 SACAR COMISSÃO", callback_data="sacar_comissao")],
        [InlineKeyboardButton("ℹ️ REGRAS", callback_data="regras_afiliado")],
        [InlineKeyboardButton("🔙 VOLTAR", callback_data="menu_perfil")]
    ]
    return InlineKeyboardMarkup(keyboard)


# ============================================
# MENU DE SUPORTE E INFORMAÇÕES
# ============================================

def menu_info() -> InlineKeyboardMarkup:
    """Menu de informações"""
    keyboard = [
        [InlineKeyboardButton("📖 TERMOS DE USO", url="https://telegra.ph/Termos")],
        [InlineKeyboardButton("ℹ️ SOBRE O BOT", callback_data="sobre_bot")],
        [InlineKeyboardButton("❓ PERGUNTAS FREQUENTES", callback_data="faq")],
        [InlineKeyboardButton("🔙 VOLTAR", callback_data="menu_principal")]
    ]
    return InlineKeyboardMarkup(keyboard)


# ============================================
// ... (continua na próxima parte)

# ============================================
# PAINEL ADMIN - MENU PRINCIPAL
# ============================================

def admin_menu_principal() -> InlineKeyboardMarkup:
    """Painel principal do administrador"""
    keyboard = [
        [InlineKeyboardButton("⚙️ CONFIGURAÇÕES", callback_data="admin_config")],
        [InlineKeyboardButton("⚡ AÇÕES RÁPIDAS", callback_data="admin_acoes")],
        [InlineKeyboardButton("💰 TRANSAÇÕES", callback_data="admin_transacoes")],
        [InlineKeyboardButton("🔄 ATUALIZAÇÕES", callback_data="admin_atualizacoes")],
        [InlineKeyboardButton("📊 RELATÓRIOS", callback_data="admin_relatorios")],
        [InlineKeyboardButton("🔙 SAIR", callback_data="menu_principal")]
    ]
    return InlineKeyboardMarkup(keyboard)


# ============================================
// ... (continua na próxima parte)

# ============================================
# ADMIN - MENU CONFIGURAÇÕES
# ============================================

def admin_menu_configuracoes() -> InlineKeyboardMarkup:
    """Menu de configurações do admin"""
    keyboard = [
        [InlineKeyboardButton("👥 USUÁRIOS", callback_data="admin_config_usuarios")],
        [InlineKeyboardButton("📦 PRODUTOS", callback_data="admin_config_produtos")],
        [InlineKeyboardButton("📂 CATEGORIAS", callback_data="admin_config_categorias")],
        [InlineKeyboardButton("🏪 LOJA", callback_data="admin_config_loja")],
        [InlineKeyboardButton("💳 PAGAMENTOS", callback_data="admin_config_pagamentos")],
        [InlineKeyboardButton("🤝 AFILIADOS", callback_data="admin_config_afiliados")],
        [InlineKeyboardButton("🔔 NOTIFICAÇÕES", callback_data="admin_config_notificacoes")],
        [InlineKeyboardButton("🤖 BOT", callback_data="admin_config_bot")],
        [InlineKeyboardButton("🔙 VOLTAR", callback_data="admin_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)


def admin_menu_usuarios() -> InlineKeyboardMarkup:
    """Menu de gerenciamento de usuários"""
    keyboard = [
        [InlineKeyboardButton("🔍 PESQUISAR USUÁRIO", callback_data="admin_buscar_usuario")],
        [InlineKeyboardButton("📋 LISTAR USUÁRIOS", callback_data="admin_listar_usuarios")],
        [InlineKeyboardButton("💰 EDITAR SALDO", callback_data="admin_editar_saldo")],
        [InlineKeyboardButton("🚫 BANIR USUÁRIO", callback_data="admin_banir_usuario")],
        [InlineKeyboardButton("✅ DESBANIR USUÁRIO", callback_data="admin_desbanir_usuario")],
        [InlineKeyboardButton("📨 ENVIAR MENSAGEM", callback_data="admin_enviar_mensagem")],
        [InlineKeyboardButton("🎁 BÔNUS EM MASSA", callback_data="admin_bonus_massa")],
        [InlineKeyboardButton("🔙 VOLTAR", callback_data="admin_config")]
    ]
    return InlineKeyboardMarkup(keyboard)


def admin_menu_produtos() -> InlineKeyboardMarkup:
    """Menu de gerenciamento de produtos"""
    keyboard = [
        [InlineKeyboardButton("➕ ADICIONAR PRODUTO", callback_data="admin_add_produto")],
        [InlineKeyboardButton("📝 EDITAR PRODUTO", callback_data="admin_editar_produto")],
        [InlineKeyboardButton("🗑️ REMOVER PRODUTO", callback_data="admin_remover_produto")],
        [InlineKeyboardButton("📦 GERENCIAR ESTOQUE", callback_data="admin_estoque")],
        [InlineKeyboardButton("🏷️ PROMOÇÕES", callback_data="admin_promocoes")],
        [InlineKeyboardButton("🖼️ MÍDIAS", callback_data="admin_midias")],
        [InlineKeyboardButton("🔙 VOLTAR", callback_data="admin_config")]
    ]
    return InlineKeyboardMarkup(keyboard)


def admin_menu_estoque() -> InlineKeyboardMarkup:
    """Menu de gerenciamento de estoque"""
    keyboard = [
        [InlineKeyboardButton("➕ ADICIONAR LOGINS", callback_data="admin_add_logins")],
        [InlineKeyboardButton("📋 VER ESTOQUE", callback_data="admin_ver_estoque")],
        [InlineKeyboardButton("🗑️ REMOVER LOGINS", callback_data="admin_remover_logins")],
        [InlineKeyboardButton("🔄 ZERAR ESTOQUE", callback_data="admin_zerar_estoque")],
        [InlineKeyboardButton("💰 ALTERAR PREÇOS", callback_data="admin_alterar_precos")],
        [InlineKeyboardButton("🔔 NOTIFICAR ALERTAS", callback_data="admin_notificar_alertas")],
        [InlineKeyboardButton("🔙 VOLTAR", callback_data="admin_config_produtos")]
    ]
    return InlineKeyboardMarkup(keyboard)


def admin_menu_categorias() -> InlineKeyboardMarkup:
    """Menu de gerenciamento de categorias"""
    keyboard = [
        [InlineKeyboardButton("➕ ADICIONAR CATEGORIA", callback_data="admin_add_categoria")],
        [InlineKeyboardButton("✏️ EDITAR CATEGORIA", callback_data="admin_editar_categoria")],
        [InlineKeyboardButton("🗑️ REMOVER CATEGORIA", callback_data="admin_remover_categoria")],
        [InlineKeyboardButton("🔄 REORDENAR", callback_data="admin_reordenar_categorias")],
        [InlineKeyboardButton("🔙 VOLTAR", callback_data="admin_config")]
    ]
    return InlineKeyboardMarkup(keyboard)


def admin_menu_pagamentos() -> InlineKeyboardMarkup:
    """Menu de configurações de pagamento"""
    keyboard = [
        [InlineKeyboardButton("🔑 CONFIGURAR API", callback_data="admin_config_api_pagamento")],
        [InlineKeyboardButton("💰 VALORES MÍN/MÁX", callback_data="admin_config_valores")],
        [InlineKeyboardButton("⏱️ TEMPO EXPIRAÇÃO", callback_data="admin_config_expiracao")],
        [InlineKeyboardButton("🎁 BÔNUS DEPÓSITO", callback_data="admin_config_bonus")],
        [InlineKeyboardButton("📊 TAXAS", callback_data="admin_config_taxas")],
        [InlineKeyboardButton("🔙 VOLTAR", callback_data="admin_config")]
    ]
    return InlineKeyboardMarkup(keyboard)


def admin_menu_afiliados() -> InlineKeyboardMarkup:
    """Menu de configurações de afiliados"""
    keyboard = [
        [InlineKeyboardButton("✅ ATIVAR/DESATIVAR", callback_data="admin_toggle_afiliados")],
        [InlineKeyboardButton("💎 DEFINIR COMISSÃO", callback_data="admin_definir_comissao")],
        [InlineKeyboardButton("🎯 METAS E BÔNUS", callback_data="admin_metas_afiliados")],
        [InlineKeyboardButton("📊 RELATÓRIO", callback_data="admin_relatorio_afiliados")],
        [InlineKeyboardButton("🔙 VOLTAR", callback_data="admin_config")]
    ]
    return InlineKeyboardMarkup(keyboard)


# ============================================
# ADMIN - AÇÕES RÁPIDAS
# ============================================

def admin_menu_acoes() -> InlineKeyboardMarkup:
    """Menu de ações rápidas"""
    keyboard = [
        [InlineKeyboardButton("🔄 ZERAR ESTOQUE", callback_data="admin_acao_zerar_estoque")],
        [InlineKeyboardButton("💰 QUEIMA DE ESTOQUE", callback_data="admin_acao_queima_estoque")],
        [InlineKeyboardButton("📢 AVISO GERAL", callback_data="admin_acao_aviso")],
        [InlineKeyboardButton("🚫 BANIMENTO RÁPIDO", callback_data="admin_acao_banir")],
        [InlineKeyboardButton("🔄 RECARREGAR CONFIGS", callback_data="admin_acao_recarregar")],
        [InlineKeyboardButton("🔙 VOLTAR", callback_data="admin_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)


# ============================================
# ADMIN - TRANSAÇÕES
# ============================================

def admin_menu_transacoes() -> InlineKeyboardMarkup:
    """Menu de transações"""
    keyboard = [
        [InlineKeyboardButton("💰 RECARGAS PENDENTES", callback_data="admin_trans_pendentes")],
        [InlineKeyboardButton("✅ RECARGAS APROVADAS", callback_data="admin_trans_aprovadas")],
        [InlineKeyboardButton("🛒 COMPRAS REALIZADAS", callback_data="admin_trans_compras")],
        [InlineKeyboardButton("📊 RESUMO FINANCEIRO", callback_data="admin_resumo_financeiro")],
        [InlineKeyboardButton("📥 EXPORTAR DADOS", callback_data="admin_exportar_trans")],
        [InlineKeyboardButton("🔙 VOLTAR", callback_data="admin_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)


# ============================================
# ADMIN - RELATÓRIOS
# ============================================

def admin_menu_relatorios() -> InlineKeyboardMarkup:
    """Menu de relatórios"""
    keyboard = [
        [InlineKeyboardButton("📊 VENDAS DIÁRIAS", callback_data="admin_rel_vendas")],
        [InlineKeyboardButton("👥 NOVOS USUÁRIOS", callback_data="admin_rel_usuarios")],
        [InlineKeyboardButton("💰 FATURAMENTO", callback_data="admin_rel_faturamento")],
        [InlineKeyboardButton("🏷️ PRODUTOS MAIS VENDIDOS", callback_data="admin_rel_top_produtos")],
        [InlineKeyboardButton("🤝 AFILIADOS TOP", callback_data="admin_rel_top_afiliados")],
        [InlineKeyboardButton("📥 EXPORTAR RELATÓRIO", callback_data="admin_exportar_relatorio")],
        [InlineKeyboardButton("🔙 VOLTAR", callback_data="admin_menu")]
    ]
    return InlineKeyboardMarkup(keyboard)


# ============================================
// ... (continua na próxima parte)

# ============================================
# BOTÕES AUXILIARES
# ============================================

def botao_voltar(callback_data: str = "menu_principal", texto: str = "🔙 VOLTAR") -> InlineKeyboardMarkup:
    """Botão voltar genérico"""
    keyboard = [[InlineKeyboardButton(texto, callback_data=callback_data)]]
    return InlineKeyboardMarkup(keyboard)


def botoes_confirmacao(callback_sim: str = "confirmar", callback_nao: str = "cancelar") -> InlineKeyboardMarkup:
    """Botões de confirmação Sim/Não"""
    keyboard = [
        [
            InlineKeyboardButton("✅ SIM", callback_data=callback_sim),
            InlineKeyboardButton("❌ NÃO", callback_data=callback_nao)
        ]
    ]
    return InlineKeyboardMarkup(keyboard)


def botoes_paginacao(pagina_atual: int, total_paginas: int, callback_prefix: str = "pagina") -> InlineKeyboardMarkup:
    """Botões de paginação"""
    keyboard = []
    
    botoes = []
    
    if pagina_atual > 1:
        botoes.append(
            InlineKeyboardButton("⬅️ ANTERIOR", callback_data=f"{callback_prefix}_{pagina_atual - 1}")
        )
    
    botoes.append(
        InlineKeyboardButton(f"📄 {pagina_atual}/{total_paginas}", callback_data="nada")
    )
    
    if pagina_atual < total_paginas:
        botoes.append(
            InlineKeyboardButton("PRÓXIMA ➡️", callback_data=f"{callback_prefix}_{pagina_atual + 1}")
        )
    
    keyboard.append(botoes)
    keyboard.append([InlineKeyboardButton("🔙 VOLTAR", callback_data="menu_principal")])
    
    return InlineKeyboardMarkup(keyboard)


def teclado_valores_recarga() -> InlineKeyboardMarkup:
    """Teclado com valores sugeridos para recarga"""
    keyboard = [
        [
            InlineKeyboardButton("R$ 10", callback_data="recarga_10"),
            InlineKeyboardButton("R$ 20", callback_data="recarga_20"),
            InlineKeyboardButton("R$ 50", callback_data="recarga_50")
        ],
        [
            InlineKeyboardButton("R$ 100", callback_data="recarga_100"),
            InlineKeyboardButton("R$ 200", callback_data="recarga_200"),
            InlineKeyboardButton("R$ 500", callback_data="recarga_500")
        ],
        [InlineKeyboardButton("💎 OUTRO VALOR", callback_data="recarga_outro")],
        [InlineKeyboardButton("🔙 VOLTAR", callback_data="menu_principal")]
    ]
    return InlineKeyboardMarkup(keyboard)


# ============================================
# KEYBOARDS REMOVÍVEIS (TECLADO FIXO)
# ============================================

def teclado_comandos_rapidos() -> ReplyKeyboardMarkup:
    """Teclado com comandos rápidos (aparece abaixo do chat)"""
    keyboard = [
        ["/start", "/saldo", "/id"],
        ["/pix", "/historico", "/ranking"],
        ["/afiliados", "/termos", "/alertas"]
    ]
    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        input_field_placeholder="Digite um comando ou use os botões..."
    )


def teclado_admin_rapido() -> ReplyKeyboardMarkup:
    """Teclado rápido para administradores"""
    keyboard = [
        ["/admin", "/stats"],
        ["/add_saldo", "/remover_saldo"],
        ["/ban", "/unban"]
    ]
    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        input_field_placeholder="Comandos admin..."
    )


# ============================================
# FUNÇÕES UTILITÁRIAS PARA KEYBOARDS
# ============================================

def criar_keyboard_em_grade(botoes: List[str], colunas: int = 2, callback_prefix: str = "") -> InlineKeyboardMarkup:
    """
    Cria um keyboard com botões em grade
    
    Args:
        botoes: Lista de textos dos botões
        colunas: Número de colunas
        callback_prefix: Prefixo para os callbacks
    """
    keyboard = []
    linha = []
    
    for i, texto in enumerate(botoes, 1):
        callback_data = f"{callback_prefix}_{i}" if callback_prefix else f"btn_{i}"
        linha.append(InlineKeyboardButton(texto, callback_data=callback_data))
        
        if len(linha) == colunas:
            keyboard.append(linha)
            linha = []
    
    if linha:
        keyboard.append(linha)
    
    return InlineKeyboardMarkup(keyboard)


def criar_keyboard_lista(
    itens: List[Dict],
    texto_key: str = "nome",
    callback_key: str = "id",
    callback_prefix: str = "item",
    emoji: str = "📌"
) -> InlineKeyboardMarkup:
    """
    Cria keyboard a partir de uma lista de dicionários
    
    Args:
        itens: Lista de dicionários com os dados
        texto_key: Chave para o texto do botão
        callback_key: Chave para o ID
        callback_prefix: Prefixo do callback
        emoji: Emoji padrão
    """
    keyboard = []
    
    for item in itens:
        texto = item.get(texto_key, "Item")
        id_valor = item.get(callback_key, 0)
        
        keyboard.append([
            InlineKeyboardButton(
                f"{emoji} {texto}",
                callback_data=f"{callback_prefix}_{id_valor}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 VOLTAR", callback_data="menu_principal")])
    
    return InlineKeyboardMarkup(keyboard)
