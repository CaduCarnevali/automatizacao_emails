from __future__ import annotations

import json
import logging
import os
import random
import smtplib
import sys
import time
from email.message import EmailMessage
from pathlib import Path

from dotenv import load_dotenv


# ─────────────────────────────────────────
# Configuração de log persistente
# ─────────────────────────────────────────
logger = logging.getLogger("envio_email")
logger.setLevel(logging.INFO)

_formatter = logging.Formatter(
    "%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

_file_handler = logging.FileHandler("envios.log", encoding="utf-8")
_file_handler.setFormatter(_formatter)
logger.addHandler(_file_handler)

_stream_handler = logging.StreamHandler()
_stream_handler.setFormatter(logging.Formatter("%(message)s"))
logger.addHandler(_stream_handler)


# ─────────────────────────────────────────
# Configuração
# ─────────────────────────────────────────
VARIAVEIS_OBRIGATORIAS = [
    "EMAIL", "SENHA", "SMTP_SERVER", "SMTP_PORT",
    "MODO", "EMAIL_TESTE",
]
CAMPOS_OBRIGATORIOS = ["empresa", "pasta", "email"]
LIMITE_TESTE = 2


class Config:
    def __init__(self) -> None:
        load_dotenv()

        ausentes = [v for v in VARIAVEIS_OBRIGATORIAS if not os.getenv(v)]
        if ausentes:
            raise EnvironmentError(
                f"Variáveis de ambiente ausentes no .env: {', '.join(ausentes)}"
            )

        self.email = os.getenv("EMAIL", "")
        self.senha = os.getenv("SENHA", "")
        self.smtp_server = os.getenv("SMTP_SERVER", "")

        porta_raw = os.getenv("SMTP_PORT", "").strip()
        try:
            self.smtp_port = int(porta_raw)
        except ValueError:
            raise ValueError(
                f"SMTP_PORT inválido: '{porta_raw}'. Deve ser um número inteiro."
            )

        self.modo = os.getenv("MODO", "TESTE").upper()
        if self.modo not in ("TESTE", "PRODUCAO"):
            raise ValueError(
                f"MODO inválido: '{self.modo}'. Use 'TESTE' ou 'PRODUCAO'."
            )

        self.email_teste = os.getenv("EMAIL_TESTE", "")

        base_path_raw = os.getenv("BASE_PATH") or str(Path.home() / "Desktop" / "Sefip")
        self.base_path = Path(base_path_raw).resolve()


def carregar_clientes(caminho: str = "clientes.json") -> list[dict]:
    try:
        with open(caminho, "r", encoding="utf-8") as arquivo:
            clientes_raw = json.load(arquivo)
    except FileNotFoundError:
        raise FileNotFoundError(f"Arquivo '{caminho}' não encontrado.")
    except json.JSONDecodeError as e:
        raise ValueError(f"Erro ao ler '{caminho}': {e}")

    clientes: list[dict] = []
    for i, cliente in enumerate(clientes_raw, start=1):
        faltando = [c for c in CAMPOS_OBRIGATORIOS if not cliente.get(c)]
        if faltando:
            logger.warning(
                f"⚠️  Cliente #{i} ignorado — campos ausentes: {', '.join(faltando)}"
            )
            continue
        clientes.append(cliente)

    if not clientes:
        raise ValueError("Nenhum cliente válido encontrado em 'clientes.json'.")

    return clientes


def caminho_seguro(base_path: Path, pasta: str) -> Path | None:
    """Retorna o caminho resolvido somente se estiver dentro de base_path."""
    caminho = (base_path / pasta).resolve()
    try:
        caminho.relative_to(base_path)
    except ValueError:
        return None
    return caminho


def coletar_pdfs(pasta: Path) -> list[Path]:
    return sorted(p for p in pasta.iterdir() if p.is_file() and p.suffix.lower() == ".pdf")


def montar_email(
    remetente: str,
    destino: str,
    empresa: str,
    pdfs: list[Path],
    modo_teste: bool,
) -> EmailMessage:
    msg = EmailMessage()
    prefixo = "[TESTE] " if modo_teste else ""
    msg["Subject"] = f"{prefixo}Documentos - {empresa}"
    msg["From"] = remetente
    msg["To"] = destino
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
    return msg


def main() -> int:
    cfg = Config()
    clientes = carregar_clientes()

    if cfg.modo == "PRODUCAO":
        confirm = input("⚠️  Tem certeza que deseja enviar os e-mails em PRODUÇÃO? (s/n): ")
        if confirm.strip().lower() not in ("s", "sim", "y", "yes"):
            logger.info("Envios cancelados pelo usuário.")
            return 0

    total = len(clientes)
    enviados = 0
    erros = 0
    processados = 0

    try:
        with smtplib.SMTP_SSL(cfg.smtp_server, cfg.smtp_port) as smtp:
            smtp.login(cfg.email, cfg.senha)

            for i, cliente in enumerate(clientes, start=1):
                if cfg.modo == "TESTE" and i > LIMITE_TESTE:
                    logger.info(f"🔒 Limite de teste atingido ({LIMITE_TESTE}).")
                    break

                empresa = cliente["empresa"]
                pasta = cliente["pasta"]
                email_cliente = cliente["email"]

                if cfg.modo == "TESTE":
                    destino = cfg.email_teste
                    logger.info(f"🧪 [{i}/{total}] TESTE → {empresa}")
                else:
                    destino = email_cliente
                    logger.info(f"📤 [{i}/{total}] Enviando → {empresa}")

                processados = i

                caminho_pasta = caminho_seguro(cfg.base_path, pasta)
                if caminho_pasta is None:
                    logger.warning(
                        f"🚫 Caminho inválido para '{empresa}' (possível path traversal). Ignorado."
                    )
                    continue

                if not caminho_pasta.exists():
                    logger.warning(f"📁 Pasta não encontrada: {pasta}. Pulando '{empresa}'.")
                    continue

                pdfs = coletar_pdfs(caminho_pasta)
                if not pdfs:
                    logger.warning(
                        f"📭 Nenhum PDF em '{pasta}'. E-mail não enviado para '{empresa}'."
                    )
                    continue

                msg = montar_email(
                    remetente=cfg.email,
                    destino=destino,
                    empresa=empresa,
                    pdfs=pdfs,
                    modo_teste=(cfg.modo == "TESTE"),
                )

                try:
                    smtp.send_message(msg)
                    logger.info(f"✅ Enviado com sucesso: {empresa}")
                    enviados += 1
                except smtplib.SMTPException as e:
                    logger.error(f"❌ Erro SMTP ao enviar para '{empresa}': {e}")
                    erros += 1
                except Exception as e:
                    logger.exception(f"❌ Erro inesperado ao enviar para '{empresa}': {e}")
                    erros += 1

                tempo_espera = random.randint(8, 15)
                logger.info(f"⏳ Aguardando {tempo_espera}s...\n")
                time.sleep(tempo_espera)

    except smtplib.SMTPAuthenticationError:
        logger.error("❌ Falha de autenticação SMTP. Verifique EMAIL e SENHA no .env.")
        return 1

    logger.info("─" * 40)
    logger.info(
        f"📊 Envio finalizado! Sucesso: {enviados} | Erros: {erros} | Total processado: {processados}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
