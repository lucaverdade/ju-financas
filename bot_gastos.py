from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import pandas as pd
import os, re, unicodedata
from datetime import datetime

app = Flask(__name__)
CSV_FILE = "gastos.csv"

if not os.path.exists(CSV_FILE):
    pd.DataFrame(columns=["data", "valor", "setor", "mensagem"]).to_csv(CSV_FILE, index=False)

def remover_acentos(txt):
    return unicodedata.normalize("NFKD", txt).encode("ASCII", "ignore").decode("ASCII")

def classificar_setor(msg):
    msg = remover_acentos(msg.lower())
    if "mercado" in msg or "comida" in msg:
        return "alimentacao"
    elif "uber" in msg or "onibus" in msg:
        return "transporte"
    else:
        return "outros"

def extrair_dados(msg):
    match = re.search(r"(gastei|gasto)\s*R?\$?\s*([\d,.]+).*(no|na|em)?\s*(.*)", msg.lower())
    if match:
        valor = float(match.group(2).replace(",", "."))
        setor = classificar_setor(match.group(4))
        return valor, setor, match.group(4)
    return None, None, None

@app.route("/", methods=["GET"])
def home():
    return "Bot de gastos ativo."

@app.route("/mensagem", methods=["POST"])
def responder():
    msg = request.form.get("Body", "")
    valor, setor, descricao = extrair_dados(msg)
    resposta = MessagingResponse()

    if valor:
        df = pd.read_csv(CSV_FILE)
        df = pd.concat([df, pd.DataFrame([{
            "data": datetime.now().strftime("%Y-%m-%d"),
            "valor": valor,
            "setor": setor,
            "mensagem": descricao
        }])])
        df.to_csv(CSV_FILE, index=False)
        resposta.message(f"✅ Gasto de R$ {valor:.2f} em *{descricao}* registrado em *{setor}*.")
    else:
        resposta.message("❌ Envie algo como: *Gastei 30 no mercado*")
    return str(resposta)
