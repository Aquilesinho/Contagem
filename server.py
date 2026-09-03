from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
import threading


app = Flask(__name__)
CORS(app)

ARQUIVO_JSON = "numeros.json"
ARQUIVO_TXT = "contagem.txt"

lock = threading.Lock()


def carregar():
    if not os.path.exists(ARQUIVO_JSON):
        return {}

    try:
        with open(ARQUIVO_JSON, "r", encoding="utf-8") as arquivo:
            return json.load(arquivo)
    except:
        return {}


def salvar(dados):
    with open(ARQUIVO_JSON, "w", encoding="utf-8") as arquivo:
        json.dump(
            dados,
            arquivo,
            ensure_ascii=False,
            indent=4
        )

    atualizar_txt(dados)


def atualizar_txt(dados):
    linhas = []

    for numero in range(101):
        chave = str(numero)

        if chave in dados:
            linhas.append(
                str(numero) + "   " + dados[chave]
            )

    with open(ARQUIVO_TXT, "w", encoding="utf-8") as arquivo:
        arquivo.write("\n".join(linhas))


@app.route("/")
def inicio():
    return "Contagem online funcionando!"


@app.route("/api/lista")
def lista():
    with lock:
        dados = carregar()

    return jsonify(dados)


@app.route("/api/escolher", methods=["POST"])
def escolher():
    dados_recebidos = request.get_json()

    if not dados_recebidos:
        return jsonify({
            "sucesso": False,
            "erro": "Dados não enviados."
        }), 400

    nome = str(dados_recebidos.get("nome", "")).strip()
    numero = dados_recebidos.get("numero")

    if not nome:
        return jsonify({
            "sucesso": False,
            "erro": "Digite um nome."
        }), 400

    try:
        numero = int(numero)
    except:
        return jsonify({
            "sucesso": False,
            "erro": "Número inválido."
        }), 400

    if numero < 0 or numero > 100:
        return jsonify({
            "sucesso": False,
            "erro": "O número precisa estar entre 0 e 100."
        }), 400

    with lock:
        dados = carregar()

        chave = str(numero)

        if chave in dados:
            return jsonify({
                "sucesso": False,
                "erro": "Esse número já foi escolhido!",
                "nome": dados[chave]
            }), 409

        dados[chave] = nome

        salvar(dados)

    return jsonify({
        "sucesso": True,
        "numero": numero,
        "nome": nome
    })


if __name__ == "__main__":
    porta = int(os.environ.get("PORT", 10000))

    atualizar_txt(carregar())

    app.run(
        host="0.0.0.0",
        port=porta
    )
