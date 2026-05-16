# Automação de Envio de Emails

Script em Python para envio automático de emails com anexos PDF, lendo uma lista de clientes em JSON.

## Funcionalidades
- Envio automático de emails via SMTP (SSL)
- Anexa automaticamente todos os PDFs da pasta do cliente
- Modos `TESTE` (envia para um endereço fixo, limitado a 2 envios) e `PRODUCAO`
- Validação de variáveis de ambiente e de cada registro de cliente
- Proteção contra path traversal na resolução das pastas
- Log persistente em `envios.log`

## Estrutura esperada

```
BASE_PATH/
├── Empresa_Exemplo/
│   ├── doc1.pdf
│   └── doc2.pdf
└── Cliente_Demonstracao/
    └── doc1.pdf
```

`BASE_PATH` é configurável via `.env`. Padrão: `~/Desktop/Sefip`.

## Setup

1. Clone o repositório e entre na pasta.
2. (Opcional) Crie um virtualenv:
   ```bash
   python -m venv .venv
   .venv\Scripts\activate    # Windows
   source .venv/bin/activate # Linux/Mac
   ```
3. Instale as dependências:
   ```bash
   pip install -r requirements.txt
   ```
4. Copie `.env.example` para `.env` e preencha as variáveis.
5. Copie `clientes.example.json` para `clientes.json` e ajuste a lista.

## Como executar

```bash
python envio_email.py
```

Em `MODO=PRODUCAO`, o script pede confirmação interativa antes de enviar.

## Variáveis de ambiente

| Variável      | Obrigatória | Descrição                                                  |
|---------------|-------------|------------------------------------------------------------|
| `EMAIL`       | sim         | Endereço remetente                                         |
| `SENHA`       | sim         | Senha (recomenda-se senha de aplicativo)                   |
| `SMTP_SERVER` | sim         | Servidor SMTP (ex.: `smtp.gmail.com`)                      |
| `SMTP_PORT`   | sim         | Porta SMTP (ex.: `465`)                                    |
| `MODO`        | sim         | `TESTE` ou `PRODUCAO`                                      |
| `EMAIL_TESTE` | sim         | Destino usado quando `MODO=TESTE`                          |
| `BASE_PATH`   | não         | Pasta raiz com as subpastas de clientes (padrão `~/Desktop/Sefip`) |

## Formato do `clientes.json`

```json
[
  {
    "empresa": "Empresa Exemplo LTDA",
    "pasta": "Empresa_Exemplo",
    "email": "contato@empresaexemplo.com.br"
  }
]
```
