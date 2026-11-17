"""Os Keycloaks que o assistente administra.

Cadastrados na tela Servidores (modelo ``Servidor``, com a senha ou o secret
cifrados) e, se as variáveis ``KEYCLOAK_*`` existirem, o do ambiente. O
escolhido no menu fica na sessão; o middleware o ativa em cada requisição.

O login no assistente não muda: continua no Keycloak e no realm do ambiente.
"""
import base64
import hashlib
from dataclasses import dataclass
from os import environ
from threading import Lock

import requests
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings

from .api import ErroKeycloak, KeycloakAdmin, usar

AMBIENTE = "ambiente"
CHAVE_SESSAO = "servidor"


def _cifra() -> Fernet:
    chave = hashlib.sha256(f"servidor-keycloak:{settings.SECRET_KEY}".encode()).digest()
    return Fernet(base64.urlsafe_b64encode(chave))


def cifrar(texto: str) -> str:
    return _cifra().encrypt(texto.encode()).decode() if texto else ""


def decifrar(texto: str) -> str:
    """Vazio se o segredo não abre (SECRET_KEY trocada): a tela pede para digitar de novo."""
    try:
        return _cifra().decrypt(texto.encode()).decode() if texto else ""
    except InvalidToken:
        return ""


@dataclass(frozen=True)
class Alvo:
    """Os dados de conexão de um Keycloak, já com o segredo aberto."""

    chave: str  # "ambiente" ou o id do cadastro
    nome: str
    url: str
    url_interna: str = ""
    usuario: str = ""
    senha: str = ""
    client_id: str = "admin-cli"
    client_secret: str = ""
    verificar_tls: bool = True
    revisao: str = ""  # muda quando o cadastro é salvo: descarta a conexão antiga

    @property
    def ambiente(self) -> bool:
        return self.chave == AMBIENTE

    @property
    def endereco_api(self) -> str:
        return (self.url_interna or self.url).rstrip("/")

    def cliente(self, timeout: int = 20) -> KeycloakAdmin:
        return KeycloakAdmin(
            self.endereco_api, usuario=self.usuario, senha=self.senha, client_id=self.client_id,
            client_secret=self.client_secret, verificar_tls=self.verificar_tls, timeout=timeout,
            publica=self.url.rstrip("/"),
        )


def do_ambiente() -> Alvo | None:
    url = environ.get("KEYCLOAK_HOST", "").rstrip("/")
    if not url:
        return None
    return Alvo(
        AMBIENTE, "Do ambiente", url, environ.get("KEYCLOAK_INTERNAL_URL", "").rstrip("/"),
        environ.get("KEYCLOAK_ADMIN_USER", ""), environ.get("KEYCLOAK_ADMIN_PASSWORD", ""),
        environ.get("KEYCLOAK_ADMIN_CLIENT_ID", "admin-cli"), environ.get("KEYCLOAK_ADMIN_CLIENT_SECRET", ""),
        environ.get("KEYCLOAK_VERIFY_TLS", "true").lower() not in ("false", "0", "no"),
    )


def do_cadastro(servidor) -> Alvo:
    segredo = decifrar(servidor.segredo)
    return Alvo(
        str(servidor.pk), servidor.nome, servidor.url.rstrip("/"), servidor.url_interna.rstrip("/"),
        "" if servidor.usa_client else servidor.usuario,
        "" if servidor.usa_client else segredo,
        servidor.client_id if servidor.usa_client else "admin-cli",
        segredo if servidor.usa_client else "",
        servidor.verificar_tls, servidor.atualizado_em.isoformat() if servidor.atualizado_em else "",
    )


def disponiveis() -> list[Alvo]:
    from keycloak.models import Servidor

    ambiente = do_ambiente()
    return ([ambiente] if ambiente else []) + [do_cadastro(s) for s in Servidor.objects.all()]


def escolhido(sessao) -> Alvo | None:
    """O do menu; sem escolha (ou se ele foi removido), o do ambiente ou o primeiro cadastrado."""
    lista = disponiveis()
    chave = sessao.get(CHAVE_SESSAO)
    return next((a for a in lista if a.chave == chave), lista[0] if lista else None)


# Uma conexão por cadastro e por processo, para reaproveitar o token do admin entre as requisições.
_clientes: dict[tuple[str, str], KeycloakAdmin] = {}
_trava = Lock()


def cliente(alvo: Alvo) -> KeycloakAdmin:
    with _trava:
        for chave in [c for c in _clientes if c[0] == alvo.chave and c[1] != alvo.revisao]:
            del _clientes[chave]
        return _clientes.setdefault((alvo.chave, alvo.revisao), alvo.cliente())


def esquecer(chave: str) -> None:
    with _trava:
        for c in [c for c in _clientes if c[0] == chave]:
            del _clientes[c]


def ativar(sessao) -> Alvo | None:
    """Põe o Keycloak escolhido como o desta requisição (o do ambiente usa a conexão padrão)."""
    alvo = escolhido(sessao)
    usar(None if alvo is None or alvo.ambiente else cliente(alvo))
    return alvo


def testar(alvo: Alvo) -> dict:
    """Login do admin no master, versão e realms. Erros com uma dica do que acertar."""
    api = alvo.cliente(timeout=10)
    try:
        api.token()
    except ErroKeycloak as erro:
        raise ErroKeycloak(f"{erro}{_dica(alvo, str(erro))}") from erro
    realms = api.get("") or []
    return {"versao": api.versao(), "realms": sorted(r["realm"] for r in realms)}


def _dica(alvo: Alvo, erro: str) -> str:
    if "→ 404" in erro and not alvo.endereco_api.endswith("/auth"):
        try:
            com_auth = requests.get(f"{alvo.endereco_api}/auth/realms/master", timeout=5, verify=alvo.verificar_tls)
        except requests.RequestException:
            com_auth = None
        if com_auth is not None and com_auth.ok:
            return f" Este Keycloak usa o caminho /auth: cadastre {alvo.endereco_api}/auth."
        return " Confira a URL: ela é a raiz do Keycloak, a que tem /realms/master."
    if "invalid_grant" in erro or "Invalid user credentials" in erro:
        return " Usuário ou senha do admin do master errados."
    if "unauthorized_client" in erro or "invalid_client" in erro:
        return " Client ID ou secret errados, ou o client não tem service account habilitada."
    if "CERTIFICATE_VERIFY_FAILED" in erro or "SSLError" in erro:
        return " O certificado não foi aceito: corrija-o ou desmarque Verificar o certificado (só em teste)."
    return ""
