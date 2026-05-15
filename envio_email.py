from dotenv import load_dotenv
import json
import logging
import os
import random
import smtplib
import time
from email.message import EmailMessage
from pathlib import Path

# ─────────────────────────────────────────
# Configuração de log persistente
# ─────────────────────────────────────────
logging.basicConfig(
    filename="envios.log",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

def log(msg: str, level: str = "info"):
    print(msg)
    getattr(logging, level)(msg)


# ─────────────────────────────────────────
# Carregamento e validação do .env
# ─────────────────────────────────────────
load_dotenv()

VARIAVEIS_OBRIGATORIAS = [
    "EMAIL", "SENHA", "SMTP_SERVER", "SMTP_PORT",
    "MODO", "EMAIL_TESTE",
]

ausentes = [v for v in VARIAVEIS_OBRIGATORIAS if not os.getenv(v)]
if ausentes:
    raise EnvironmentError(
        f"Variáveis de ambiente ausentes no .env: {', '.join(ausentes)}"
    )

EMAIL       = os.getenv("EMAIL")
SENHA       = os.getenv("SENHA")
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT   = int(os.getenv("SMTP_PORT"))

# Padrão seguro: TESTE. Só envia em produção se configurado.
MODO        = os.getenv("MODO", "TESTE").upper()
EMAIL_TESTE = os.getenv("EMAIL_TESTE")
LIMITE_TESTE = 2

if MODO not in ("TESTE", "PRODUCAO"):
    raise ValueError(f"MODO inválido: '{MODO}'. Use 'TESTE' ou 'PRODUCAO'.")


# ─────────────────────────────────────────
# Carregamento e validação do clientes.json
# ─────────────────────────────────────────
CAMPOS_OBRIGATORIOS = ["empresa", "pasta", "email"]

try:
    with open("clientes.json", "r", encoding="utf-8") as arquivo:
        clientes_raw = json.load(arquivo)
except FileNotFoundError:
    raise FileNotFoundError("Arquivo 'clientes.json' não encontrado.")
except json.JSONDecodeError as e:
    raise ValueError(f"Erro ao ler 'clientes.json': {e}")

clientes = []
for i, cliente in enumerate(clientes_raw):
    campos_faltando = [c for c in CAMPOS_OBRIGATORIOS if not cliente.get(c)]
    if campos_faltando:
        log(
            f"⚠️  Cliente #{i+1} ignorado — campos ausentes: {', '.join(campos_faltando)}",
            level="warning",
        )
        continue
    clientes.append(cliente)

if not clientes:
    raise ValueError("Nenhum cliente válido encontrado em 'clientes.json'.")


# ─────────────────────────────────────────
# Caminho base (protegido contra path traversal)
# ─────────────────────────────────────────
base_path = (Path.home() / "Desktop" / "Sefip").resolve()


def caminho_seguro(pasta: str) -> Path | None:
    """Retorna o caminho resolvido somente se estiver dentro de base_path."""
    caminho = (base_path / pasta).resolve()
    if not str(caminho).startswith(str(base_path)):
        return None
    return caminho


# ─────────────────────────────────────────
# Confirmação para produção
# ─────────────────────────────────────────
if MODO == "PRODUCAO":
    confirm = input("⚠️  Tem certeza que deseja enviar os e-mails em PRODUÇÃO? (s/n): ")
    if confirm.strip().lower() != "s":
        log("Envios cancelados pelo usuário.")
        exit()


# ─────────────────────────────────────────
# Loop de envios
# ─────────────────────────────────────────
total   = len(clientes)
contador = 1
enviados = 0
erros    = 0

for cliente in clientes:

    # Limite de teste
    if MODO == "TESTE" and contador > LIMITE_TESTE:
        log(f"🔒 Limite de teste atingido ({LIMITE_TESTE}).")
        break

    empresa = cliente["empresa"]
    pasta   = cliente["pasta"]
    email_cliente = cliente["email"]

    # Destino do e-mail
    if MODO == "TESTE":
        destino = EMAIL_TESTE
        log(f"🧪 [{contador}/{total}] TESTE → {empresa}")
    else:
        destino = email_cliente
        log(f"📤 [{contador}/{total}] Enviando → {empresa}")

    # Validação de path traversal
    caminho_pasta = caminho_seguro(pasta)
    if caminho_pasta is None:
        log(f"🚫 Caminho inválido para '{empresa}' (possível path traversal). Ignorado.", level="warning")
        contador += 1
        continue

    # Verifica existência da pasta
    if not caminho_pasta.exists():
        log(f"📁 Pasta não encontrada: {pasta}. Pulando '{empresa}'.", level="warning")
        contador += 1
        continue

    # Coleta PDFs
    pdfs = [
        caminho_pasta / arq
        for arq in os.listdir(caminho_pasta)
        if arq.lower().endswith(".pdf")
    ]

    if not pdfs:
        log(f"📭 Nenhum PDF em '{pasta}'. E-mail não enviado para '{empresa}'.", level="warning")
        contador += 1
        continue

    # Monta o e-mail
    msg = EmailMessage()
    msg["Subject"] = f"Documentos - {empresa}"
    msg["From"]    = EMAIL
    msg["To"]      = destino
    msg.set_content(
        f"Prezados, segue em anexo os documentos da empresa {empresa}."
    )

    for caminho_arquivo in pdfs:
        with open(caminho_arquivo, "rb") as f:
            msg.add_attachment(
                f.read(),
                maintype="application",
                subtype="pdf",
                filename=caminho_arquivo.name,
            )

    # Envio
    try:
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as smtp:
            smtp.login(EMAIL, SENHA)
            smtp.send_message(msg)

        log(f"✅ Enviado com sucesso: {empresa}")
        enviados += 1

    except smtplib.SMTPAuthenticationError:
        log(f"❌ Falha de autenticação SMTP. Verifique EMAIL e SENHA no .env.", level="error")
        break  # Inutíl continuar sem credenciais válidas

    except smtplib.SMTPException as e:
        log(f"❌ Erro SMTP ao enviar para '{empresa}': {e}", level="error")
        erros += 1

    except Exception as e:
        log(f"❌ Erro inesperado ao enviar para '{empresa}': {e}", level="error")
        erros += 1

    # Delay anti-spam
    tempo_espera = random.randint(8, 15)
    log(f"⏳ Aguardando {tempo_espera}s...\n")
    time.sleep(tempo_espera)

    contador += 1


# ─────────────────────────────────────────
# Resumo final
# ─────────────────────────────────────────
log("─" * 40)
log(f"📊 Envio finalizado! Sucesso: {enviados} | Erros: {erros} | Total processado: {contador - 1}")