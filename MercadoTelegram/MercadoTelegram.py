import requests
import urllib.parse
import uuid
import mercadopago
import threading
import time
from flask import Flask, request, jsonify
from flask_cors import CORS

# --- 1. CONFIGURAÇÕES ---
TOKEN = '8319089179:AAHNW9vBcm0Dyjd9xBk4Xam3KZzhrf_DHYo'
CHAT_ID = '7704757217'
ACCESS_TOKEN = "APP_USR-2915867478844145-031020-aadd7ff871de57763fd1a06fbbbf33c2-2925892095"

sdk = mercadopago.SDK(ACCESS_TOKEN)
app = Flask(__name__)
CORS(app)

registered_names = ['Ana Silva', 'Carlos Souza']

# --- FUNÇÃO DO TELEGRAM ---
def enviar_mensagem_telegram(mensagem):
    url = f'https://api.telegram.org/bot{TOKEN}/sendMessage'
    dados = {'chat_id': CHAT_ID, 'text': mensagem, 'parse_mode': 'Markdown'}
    try:
        requests.post(url, data=dados)
    except Exception as e:
        print(f'Erro no Telegram: {e}')

# --- MONITOR DE PAGAMENTO (DISPARA APÓS O PIX) ---
def monitorar_pagamento(payment_id, data):
    """Fica vigiando o status do Pix e manda o link do Zap quando aprovado"""
    print(f"🕵️ Monitorando Pix ID {payment_id}...")
    tentativas = 0
    while tentativas < 60:
        time.sleep(5)
        try:
            resultado = sdk.payment().get(payment_id)
            status = resultado["response"]["status"]

            if status == 'approved':
                nome_principal = data.get('attendeeName', '')
                whatsapp_raw = data.get('attendeePhone', '')
                tem_acompanhante = data.get('hasCompanion', False)
                nome_acompanhante = data.get('companionName', '')
                valor = resultado["response"]["transaction_amount"]

                # Monta a mensagem para o seu Telegram
                mensagem_para_bot = f"🚨 *PAGAMENTO CONFIRMADO* 🚨\n\n"
                mensagem_para_bot += f"👤 *Nome:* {nome_principal}\n"
                mensagem_para_bot += f"📞 *WhatsApp:* {whatsapp_raw}\n"
                mensagem_para_bot += f"💰 *Valor Pago:* R$ {valor:.2f}\n"

                if tem_acompanhante and nome_acompanhante:
                    mensagem_para_bot += f"👥 **Acompanhante:** {nome_acompanhante}\n"
                else:
                    mensagem_para_bot += f"👥 **Acompanhante:** Não\n"

                mensagem_para_bot += "\n"

                # Geração do Link do WhatsApp com a sua mensagem exata
                whatsapp_numeros = "55" + "".join(filter(str.isdigit, whatsapp_raw))
                texto_confirmacao = (
                    f"Sua passagem para a escuridão da Hallownight 2.0 foi carimbada! 🎃🔥\n\n"
                    f"Bem-vindo(a), {nome_principal}! Seu pagamento foi confirmado e seu nome já está na lista dos amaldiçoados. "
                    f"Prepare-se para a festa mais insana do ano no **Serjão Lar**! 👻💀\n\n"
                    f"Nos vemos lá... se tiver coragem. -{nome_principal} e {nome_acompanhante if nome_acompanhante else ''}"
                )

                texto_codificado = urllib.parse.quote_plus(texto_confirmacao)
                link_confirmacao_whatsapp = f"https://api.whatsapp.com/send/?phone={whatsapp_numeros}&text={texto_codificado}"

                mensagem_para_bot += f"✅ *PAGAMENTO REALIZADO! Clique no link abaixo para enviar a confirmação para {nome_principal}:*\n"
                mensagem_para_bot += link_confirmacao_whatsapp

                # Manda pro seu celular
                enviar_mensagem_telegram(mensagem_para_bot)
                
                # Adiciona na lista da memória
                registered_names.append(nome_principal)
                return 

        except Exception as e:
            print(f"Erro na consulta: {e}")
        
        tentativas += 1

# --- ROTA 1: GERA O PIX ---
@app.route('/registrar', methods=['POST'])
def registrar_convidado():
    data = request.get_json()
    nome_principal = data.get('attendeeName', '')
    
    if nome_principal.strip().lower() in [name.lower() for name in registered_names]:
        return jsonify({'status': 'xara_found'}), 409

    tem_acompanhante = data.get('hasCompanion', False)
    valor = 40.00 if tem_acompanhante else 20.00

    payment_data = {
        "transaction_amount": float(valor),
        "description": f"Hallownight 2.0 - {nome_principal}",
        "payment_method_id": "pix",
        "payer": {
            "email": "convidado@hallownight.com",
            "first_name": nome_principal,
            "identification": {"type": "CPF", "number": "00000000000"}
        }
    }

    try:
        payment_response = sdk.payment().create(payment_data)
        
        if payment_response.get("status") in [200, 201]:
            res = payment_response["response"]
            payment_id = res["id"]
            qr_code_link = res["point_of_interaction"]["transaction_data"]["ticket_url"]
            
            # Dispara o monitor em background
            threading.Thread(target=monitorar_pagamento, args=(payment_id, data)).start()

            return jsonify({
                'status': 'sucesso', 
                'qr_code_link': qr_code_link
            }), 200
        else:
            return jsonify({'status': 'erro'}), 500
            
    except Exception as e:
        return jsonify({'status': 'erro'}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)

#cmd// ngrok http 5000 // 
#terminal// python -m venv venv // .\venv\Scripts\activate // pip install requests flask flask-cors mercadopago // 
# python MERCADOPAGO\telegram.py
