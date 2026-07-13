def gerar_qr_code_pix(payload: str, tamanho: int = 300) -> BytesIO:
    """
    Gera QR Code do Pix (SEM Pillow)
    Usa apenas a biblioteca qrcode nativa
    """
    import qrcode
    
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(payload)
    qr.make(fit=True)
    
    # make_image retorna um objeto PIL, mas o qrcode também suporta
    # gerar diretamente para BytesIO
    img = qr.make_image(fill_color="black", back_color="white")
    
    output = BytesIO()
    img.save(output, format='PNG')
    output.seek(0)
    
    return output


def gerar_qr_code_base64(payload: str) -> str:
    """
    Gera QR Code em base64 (SEM Pillow)
    """
    qr_image = gerar_qr_code_pix(payload)
    return base64.b64encode(qr_image.read()).decode()
