from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
import pandas as pd
import os, re, json, unicodedata
from datetime import datetime, timedelta

DEBUG_VERSION = "vDEBUG 1.4"
print(f"✅ Bot de gastos iniciado — {DEBUG_VERSION}")

app = Flask(__name__)
CSV_FILE = "gastos.csv"
JSON_FILE = "categorias.json"

# Inicializa arquivos
if not os.path.exists(CSV_FILE):
    print("📁 Criando novo arquivo de gastos.csv")
    pd.DataFrame(columns=["data", "valor", "setor", "mensagem"]).to_csv(CSV_FILE, index=False)

if not os.path.exists(JSON_FILE):
    print("📁 Criando novo arquivo categorias.json")
    categorias_iniciais = {
        "alimentacao": ["mc", "mcdonald", "burger", "pizza", "lanche", "restaurante", "madeiro",
                        "ifood", "habib", "comida", "padaria", "mercado", "supermercado", "pao",
                        "cafe", "açai", "outback", "pao de queijo"],
        "lazer": ["cinema", "filme", "show", "shopping", "bar", "balada", "festa", "parque",
                  "netflix", "spotify", "napraia", "festa da ana"],
        "transporte": ["uber", "99", "onibus", "gasolina", "combustivel", "metro", "transporte", "passagem"],
        "casa": ["aluguel", "condominio", "energia", "luz", "agua", "internet", "net", "claro"],
        "outros": []
    }
    with open(JSON_FILE, "w") as f:
        json.dump(categorias_iniciais, f, indent=2)

# Funções auxiliares
def remover_acentos(txt):
    return unicodedata.normalize("NFKD", txt).encode("ASCII", "ignore").decode("ASCII")

def carregar_categorias():
    with open(JSON_FILE, "r") as f:
        return json.load(f)

def salvar_categorias(categorias):
    with open(JSON_FILE, "w") as f:
        json.dump(categorias, f, indent=2)

def classificar_setor(texto):
    texto_limpo = remover_acentos(texto.lower())
    categorias = carregar_categorias()

    for setor, palavras in categorias.items():
        for palavra in palavras:
            palavra_limpa = remover_acentos(palavra.lower())
            if palavra_limpa in texto_limpo:
                print(f"✅ Palavra '{palavra}' encontrada → setor '{setor}'")
                return setor
    print("❌ Nenhuma palavra-chave reconhecida. Retornando 'outros'")
    return "outros"

def extrair_dados(msg):
    match = re.search(r"(gastei|gasto)\s*R?\$?\s*([\d,.]+)\s*(no|na|em)?\s*(.*)", msg.lower())
    if match:
        valor = float(match.group(2).replace(",", "."))
        descricao = match.group(4).strip()
        print(f"🟡 Mensagem: '{msg}' → Descrição: '{descricao}'")
        setor = classificar_setor(descricao)
        return valor, setor, descricao
    print("❗ Mensagem não reconhecida:", msg)
    return None, None, None

def total_por_periodo(df, dias):
    limite = datetime.now() - timedelta(days=dias)
    df["data"] = pd.to_datetime(df["data"])
    return df[df["data"] >= limite]["valor"].sum()

# Rotas
@app.route("/", methods=["GET"])
def home():
    return f"Bot de gastos ativo — {DEBUG_VERSION}"

@app.route("/mensagem", methods=["POST"])
def responder():
    msg = request.form.get("Body", "").strip()
    resposta = MessagingResponse()
    df = pd.read_csv(CSV_FILE)
    texto = remover_acentos(msg.lower())

    if "relatorio" in texto:
        if df.empty:
            resposta.message("📭 Nenhum gasto registrado ainda.")
        else:
            relatorio = df.groupby("setor")["valor"].sum().reset_index()
            total = df["valor"].sum()
            texto_resp = "📊 *Relatório por setor:*\n"
            for _, row in relatorio.iterrows():
                texto_resp += f"• {row['setor'].capitalize()}: R$ {row['valor']:.2f}\n"
            texto_resp += f"\n💰 *Total:* R$ {total:.2f}"
            resposta.message(texto_resp)
        return str(resposta)

    if "total hoje" in texto:
        total = total_por_periodo(df, 0)
        resposta.message(f"📅 Total de hoje: R$ {total:.2f}")
        return str(resposta)

    if "total semana" in texto:
        total = total_por_periodo(df, 7)
        resposta.message(f"🗓️ Total da semana: R$ {total:.2f}")
        return str(resposta)

    if "total mes" in texto:
        total = total_por_periodo(df, 30)
        resposta.message(f"📆 Total do mês: R$ {total:.2f}")
        return str(resposta)

    if "listar categorias" in texto:
        categorias = carregar_categorias()
        msg_cat = "📚 *Categorias cadastradas:*\n"
        for setor, palavras in categorias.items():
            msg_cat += f"• *{setor}*: {', '.join(palavras) if palavras else 'Nenhuma palavra associada'}\n"
        resposta.message(msg_cat)
        return str(resposta)

    match_cat = re.search(r"nova categoria (\w+) com (.+)", texto)
    if match_cat:
        nova_cat = match_cat.group(1).strip()
        palavras = [p.strip() for p in match_cat.group(2).split(",")]
        categorias = carregar_categorias()
        if nova_cat in categorias:
            resposta.message("⚠️ Essa categoria já existe.")
        else:
            categorias[nova_cat] = palavras
            salvar_categorias(categorias)
            resposta.message(f"✅ Categoria *{nova_cat}* criada com: {', '.join(palavras)}")
        return str(resposta)

    if texto.startswith("editar"):
        partes = texto.split()
        if len(partes) >= 4:
            try:
                indice = int(partes[1]) - 1
                campo = partes[2]
                novo_valor = " ".join(partes[3:])
                if campo in ["valor", "setor", "mensagem"] and 0 <= indice < len(df):
                    df.loc[indice, campo] = float(novo_valor) if campo == "valor" else novo_valor
                    df.to_csv(CSV_FILE, index=False)
                    resposta.message(f"✏️ Gasto #{indice+1} atualizado.")
                else:
                    resposta.message("❌ Campo inválido ou índice fora do alcance.")
            except:
                resposta.message("❌ Comando inválido. Ex: editar 1 valor 50")
        else:
            resposta.message("❌ Comando incompleto. Ex: editar 1 valor 50")
        return str(resposta)

    valor, setor, descricao = extrair_dados(msg)
    if valor:
        nova_linha = {
            "data": datetime.now().strftime("%Y-%m-%d"),
            "valor": valor,
            "setor": setor,
            "mensagem": descricao
        }
        df = pd.concat([df, pd.DataFrame([nova_linha])])
        df.to_csv(CSV_FILE, index=False)
        resposta.message(f"✅ Gasto de R$ {valor:.2f} em *{descricao}* registrado na categoria *{setor}*.")
    else:
        resposta.message("❌ Tente algo como: *gastei 30 no mercado*, *relatorio*, *total hoje*, *nova categoria lazer com praia, bar*")
    return str(resposta)

# Início da aplicação
if __name__ == "__main__":
    porta = int(os.environ.get("PORT", 10000))
    print(f"🚀 Servidor Flask rodando na porta {porta} — {DEBUG_VERSION}")
    app.run(host="0.0.0.0", port=porta)
