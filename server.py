from flask import Flask, request, jsonify
from flask_cors import CORS
from functools import wraps
import json
import os
import threading
import requests

app = Flask(__name__)
CORS(app)

ARQUIVO_JSON = "numeros.json"
ARQUIVO_TXT = "contagem.txt"

ADMIN_EMAIL = "aquiles.mm.enzo@gmail.com"

lock = threading.Lock()


def carregar():
    if not os.path.exists(ARQUIVO_JSON):
        return {
            "numeros": {},
            "bloqueados": [],
            "mensagem": ""
        }

    try:
        with open(
            ARQUIVO_JSON,
            "r",
            encoding="utf-8"
        ) as arquivo:
            dados = json.load(arquivo)

        if "numeros" not in dados:
            dados = {
                "numeros": dados,
                "bloqueados": [],
                "mensagem": ""
            }

        dados.setdefault("bloqueados", [])
        dados.setdefault("mensagem", "")

        return dados

    except:
        return {
            "numeros": {},
            "bloqueados": [],
            "mensagem": ""
        }


def salvar(dados):
    with open(
        ARQUIVO_JSON,
        "w",
        encoding="utf-8"
    ) as arquivo:
        json.dump(
            dados,
            arquivo,
            ensure_ascii=False,
            indent=4
        )

    atualizar_txt(dados)


def atualizar_txt(dados):
    numeros = dados.get("numeros", {})

    linhas = []

    for numero in range(101):
        chave = str(numero)

        if chave in numeros:
            linhas.append(
                str(numero) +
                "   " +
                numeros[chave]["nome"]
            )

    with open(
        ARQUIVO_TXT,
        "w",
        encoding="utf-8"
    ) as arquivo:
        arquivo.write(
            "\n".join(linhas)
        )


def verificar_google(token):
    try:
        resposta = requests.get(
            "https://oauth2.googleapis.com/tokeninfo",
            params={
                "id_token": token
            },
            timeout=10
        )

        if resposta.status_code != 200:
            return None

        dados = resposta.json()

        email = dados.get("email")

        if not email:
            return None

        if dados.get("email_verified") != "true":
            return None

        return {
            "email": email.lower(),
            "nome": dados.get(
                "name",
                email.split("@")[0]
            )
        }

    except:
        return None


def usuario_autenticado():
    token = request.headers.get(
        "Authorization",
        ""
    )

    if not token.startswith("Bearer "):
        return None

    token = token[7:].strip()

    if not token:
        return None

    return verificar_google(token)


def exigir_login(funcao):
    @wraps(funcao)
    def wrapper(*args, **kwargs):
        usuario = usuario_autenticado()

        if not usuario:
            return jsonify({
                "sucesso": False,
                "erro": "Você precisa entrar com o Google."
            }), 401

        return funcao(
            usuario,
            *args,
            **kwargs
        )

    return wrapper


def exigir_admin(funcao):
    @wraps(funcao)
    def wrapper(usuario, *args, **kwargs):
        if usuario["email"] != ADMIN_EMAIL:
            return jsonify({
                "sucesso": False,
                "erro": "Acesso negado."
            }), 403

        return funcao(
            usuario,
            *args,
            **kwargs
        )

    return wrapper


@app.route("/")
def inicio():
    return "Contagem online funcionando!"


@app.route("/api/lista")
def lista():
    with lock:
        dados = carregar()

    numeros = {}

    for numero, registro in dados["numeros"].items():
        numeros[numero] = registro["nome"]

    return jsonify({
        "numeros": numeros,
        "mensagem": dados["mensagem"]
    })


@app.route("/api/eu")
@exigir_login
def eu(usuario):
    with lock:
        dados = carregar()

    numero_usuario = None

    for numero, registro in dados["numeros"].items():
        if registro["email"] == usuario["email"]:
            numero_usuario = int(numero)
            break

    return jsonify({
        "email": usuario["email"],
        "nome": usuario["nome"],
        "numero": numero_usuario,
        "admin": usuario["email"] == ADMIN_EMAIL
    })


@app.route("/api/escolher", methods=["POST"])
@exigir_login
def escolher(usuario):
    dados_recebidos = request.get_json()

    if not dados_recebidos:
        return jsonify({
            "sucesso": False,
            "erro": "Dados não enviados."
        }), 400

    numero = dados_recebidos.get("numero")

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

        nome = usuario["nome"].strip()

        nome_baixo = nome.casefold()

        for bloqueado in dados["bloqueados"]:
            if nome_baixo == bloqueado.casefold():
                return jsonify({
                    "sucesso": False,
                    "erro": "Esse nome está bloqueado."
                }), 403

        for registro in dados["numeros"].values():
            if registro["email"] == usuario["email"]:
                return jsonify({
                    "sucesso": False,
                    "erro": "Você já escolheu um número."
                }), 409

        if chave in dados["numeros"]:
            return jsonify({
                "sucesso": False,
                "erro": "Esse número já foi escolhido!"
            }), 409

        dados["numeros"][chave] = {
            "nome": nome,
            "email": usuario["email"]
        }

        salvar(dados)

    return jsonify({
        "sucesso": True,
        "numero": numero,
        "nome": nome
    })


@app.route("/api/admin/mensagem", methods=["POST"])
@exigir_login
@exigir_admin
def alterar_mensagem(usuario):
    dados_recebidos = request.get_json()

    if not dados_recebidos:
        return jsonify({
            "sucesso": False,
            "erro": "Dados não enviados."
        }), 400

    mensagem = str(
        dados_recebidos.get(
            "mensagem",
            ""
        )
    ).strip()

    with lock:
        dados = carregar()

        dados["mensagem"] = mensagem

        salvar(dados)

    return jsonify({
        "sucesso": True,
        "mensagem": mensagem
    })


@app.route("/api/admin/bloquear", methods=["POST"])
@exigir_login
@exigir_admin
def bloquear(usuario):
    dados_recebidos = request.get_json()

    if not dados_recebidos:
        return jsonify({
            "sucesso": False,
            "erro": "Dados não enviados."
        }), 400

    nome = str(
        dados_recebidos.get(
            "nome",
            ""
        )
    ).strip()

    if not nome:
        return jsonify({
            "sucesso": False,
            "erro": "Digite um nome."
        }), 400

    with lock:
        dados = carregar()

        nomes = [
            x.casefold()
            for x in dados["bloqueados"]
        ]

        if nome.casefold() not in nomes:
            dados["bloqueados"].append(nome)

        salvar(dados)

    return jsonify({
        "sucesso": True
    })


@app.route("/api/admin/desbloquear", methods=["POST"])
@exigir_login
@exigir_admin
def desbloquear(usuario):
    dados_recebidos = request.get_json()

    if not dados_recebidos:
        return jsonify({
            "sucesso": False,
            "erro": "Dados não enviados."
        }), 400

    nome = str(
        dados_recebidos.get(
            "nome",
            ""
        )
    ).strip()

    with lock:
        dados = carregar()

        dados["bloqueados"] = [
            x for x in dados["bloqueados"]
            if x.casefold() != nome.casefold()
        ]

        salvar(dados)

    return jsonify({
        "sucesso": True
    })


@app.route("/api/admin/excluir", methods=["POST"])
@exigir_login
@exigir_admin
def excluir(usuario):
    dados_recebidos = request.get_json()

    if not dados_recebidos:
        return jsonify({
            "sucesso": False,
            "erro": "Dados não enviados."
        }), 400

    numero = dados_recebidos.get("numero")

    try:
        numero = int(numero)
    except:
        return jsonify({
            "sucesso": False,
            "erro": "Número inválido."
        }), 400

    with lock:
        dados = carregar()

        chave = str(numero)

        if chave not in dados["numeros"]:
            return jsonify({
                "sucesso": False,
                "erro": "Esse número não está ocupado."
            }), 404

        del dados["numeros"][chave]

        salvar(dados)

    return jsonify({
        "sucesso": True
    })


@app.route("/api/admin")
@exigir_login
@exigir_admin
def painel_admin(usuario):
    with lock:
        dados = carregar()

    return jsonify({
        "bloqueados": dados["bloqueados"],
        "mensagem": dados["mensagem"],
        "numeros": dados["numeros"]
    })


if __name__ == "__main__":
    porta = int(
        os.environ.get(
            "PORT",
            10000
        )
    )

    atualizar_txt(carregar())

    app.run(
        host="0.0.0.0",
        port=porta
    )
