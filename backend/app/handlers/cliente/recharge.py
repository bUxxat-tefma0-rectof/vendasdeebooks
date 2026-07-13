async def exibir_qr_code(update: Update, context: ContextTypes.DEFAULT_TYPE, db: Database, 
                         transacao_id: int, pix_data: dict):
    """Exibe o QR Code e informações do Pix"""
    
    user_id = update.effective_user.id
    
    with db.get_session() as session:
        transacao = session.query(Transacao).get(transacao_id)
    
    if not transacao:
        return
    
    tempo_restante = transacao.data_expiracao - datetime.now() if transacao.data_expiracao else timedelta(minutes=5)
    minutos = max(0, tempo_restante.seconds // 60)
    segundos = max(0, tempo_restante.seconds % 60)
    
    texto = f"""
💳 *PIX GERADO COM SUCESSO!*

💰 *Valor:* {formatar_moeda(transacao.valor)}
🎁 *Bônus:* {formatar_moeda(transacao.valor_bonus)}
💎 *Saldo a Receber:* {formatar_moeda(transacao.valor_total)}

⏰ *Expira em:* {minutos}min {segundos}s
📅 *Data:* {formatar_data(transacao.data_criacao)}

🟡 *Status:* AGUARDANDO PAGAMENTO

📋 *Pix Copia e Cola:*
`{transacao.copia_cola}`

🔹 Escaneie o QR Code ou copie o código acima
"""
    
    keyboard = menu_recarga_pix(
        transacao_id=transacao_id,
        valor=transacao.valor,
        copia_cola=transacao.copia_cola
    )
    
    # Tenta enviar QR Code como imagem
    try:
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
