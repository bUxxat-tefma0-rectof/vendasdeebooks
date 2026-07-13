import mercadopago
from app.config import Config

sdk = mercadopago.SDK(Config.MP_ACCESS_TOKEN)

async def create_pix_payment(user_id: int, amount: float, description: str = "Recarga"):
    payment_data = {
        "transaction_amount": amount,
        "description": description,
        "payment_method_id": "pix",
        "payer": {
            "email": f"user{user_id}@bot.com",
        }
    }

    result = sdk.payment().create(payment_data)
    payment = result["response"]

    if result["status"] == 201:
        pix_data = payment["point_of_interaction"]["transaction_data"]
        return {
            "payment_id": payment["id"],
            "qr_code": pix_data["qr_code"],
            "qr_code_base64": pix_data["qr_code_base64"],
            "status": payment["status"]
        }
    else:
        raise Exception(f"Erro ao criar pagamento: {payment}")

async def check_payment_status(payment_id: str):
    result = sdk.payment().get(payment_id)
    payment = result["response"]
    return payment["status"]  # pending, approved, rejected
