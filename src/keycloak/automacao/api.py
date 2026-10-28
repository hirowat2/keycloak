"""Cliente da Admin REST API do Keycloak, autenticado no realm master.

Com ``KEYCLOAK_ADMIN_CLIENT_SECRET``, usa um client com service account
(client credentials); senão, o usuário e a senha do admin do console
(``admin-cli``, password grant), os mesmos do ``KC_ADMIN_USER`` do compose.
"""

import time
from os import environ
from urllib.parse import quote

import requests


class ErroKeycloak(Exception):
    """Falha de rede ou resposta de erro da Admin API, com a mensagem do Keycloak."""


def _mensagem(resposta: requests.Response) -> str:
    try:
        corpo = resposta.json()
    except ValueError:
        corpo = {}
    detalhe = corpo.get("errorMessage") or corpo.get("error_description") or corpo.get("error") or resposta.text[:200]
    return f"{resposta.request.method} {resposta.url} → {resposta.status_code}: {detalhe}".strip()


class KeycloakAdmin:
    def __init__(
        self,
        url: str,
        usuario: str = "",
        senha: str = "",
        client_id: str = "admin-cli",
        client_secret: str = "",
        verificar_tls: bool = True,
        timeout: int = 20,
    ):
        self.url = url.rstrip("/")
        self.usuario, self.senha = usuario, senha
        self.client_id, self.client_secret = client_id, client_secret
        self.timeout = timeout
        self.sessao = requests.Session()
        self.sessao.verify = verificar_tls
        self._token, self._expira = "", 0.0

    def token(self) -> str:
        if self._token and time.time() < self._expira:
            return self._token
        if self.client_secret:
            dados = {"grant_type": "client_credentials", "client_id": self.client_id, "client_secret": self.client_secret}
        else:
            dados = {"grant_type": "password", "client_id": self.client_id, "username": self.usuario, "password": self.senha}
        try:
            resposta = self.sessao.post(f"{self.url}/realms/master/protocol/openid-connect/token", data=dados, timeout=self.timeout)
        except requests.RequestException as erro:
            raise ErroKeycloak(f"Sem conexão com o Keycloak em {self.url}: {erro}") from erro
        if resposta.status_code != 200:
            raise ErroKeycloak(f"Login do admin no realm master recusado. {_mensagem(resposta)}")
        corpo = resposta.json()
        self._token = corpo["access_token"]
        self._expira = time.time() + corpo.get("expires_in", 60) - 15
        return self._token

    def requisitar(self, metodo: str, caminho: str, aceitar_404: bool = False, **kwargs) -> requests.Response | None:
        """``caminho`` relativo a /admin/realms (ex.: ``/automateflow/clients``)."""
        try:
            resposta = self.sessao.request(
                metodo,
                f"{self.url}/admin/realms{caminho}",
                headers={"Authorization": f"Bearer {self.token()}"},
                timeout=self.timeout,
                **kwargs,
            )
        except requests.RequestException as erro:
            raise ErroKeycloak(f"Sem conexão com o Keycloak em {self.url}: {erro}") from erro
        if aceitar_404 and resposta.status_code == 404:
            return None
        if resposta.status_code >= 400:
            raise ErroKeycloak(_mensagem(resposta))
        return resposta

    def get(self, caminho: str, **params):
        """JSON da resposta, ou None se o recurso não existe."""
        resposta = self.requisitar("GET", caminho, aceitar_404=True, params=params)
        return resposta.json() if resposta is not None and resposta.content else None

    def post(self, caminho: str, dados=None, **kwargs) -> requests.Response:
        return self.requisitar("POST", caminho, json=dados, **kwargs)

    def put(self, caminho: str, dados) -> requests.Response:
        return self.requisitar("PUT", caminho, json=dados)

    def delete(self, caminho: str, dados=None) -> requests.Response:
        return self.requisitar("DELETE", caminho, json=dados)

    def versao(self) -> str:
        resposta = self.sessao.get(
            f"{self.url}/admin/serverinfo", headers={"Authorization": f"Bearer {self.token()}"}, timeout=self.timeout
        )
        return resposta.json().get("systemInfo", {}).get("version", "") if resposta.ok else ""


def seg(texto: str) -> str:
    """Trecho de URL seguro (nomes de grupo e de role podem ter espaço)."""
    return quote(str(texto), safe="")


def url_publica() -> str:
    """Endereço do Keycloak que o navegador e o SSO enxergam (o ``KC_HOST``)."""
    return environ.get("KEYCLOAK_HOST", "").rstrip("/")


def url_interna() -> str:
    return (environ.get("KEYCLOAK_INTERNAL_URL") or environ.get("KEYCLOAK_HOST", "")).rstrip("/")


def conexao() -> KeycloakAdmin:
    """Admin API pelo endereço interno (no Docker, ``http://keycloak:8080``)."""
    return KeycloakAdmin(
        url_interna(),
        usuario=environ.get("KEYCLOAK_ADMIN_USER", ""),
        senha=environ.get("KEYCLOAK_ADMIN_PASSWORD", ""),
        client_id=environ.get("KEYCLOAK_ADMIN_CLIENT_ID", "admin-cli"),
        client_secret=environ.get("KEYCLOAK_ADMIN_CLIENT_SECRET", ""),
        verificar_tls=environ.get("KEYCLOAK_VERIFY_TLS", "true").lower() not in ("false", "0", "no"),
    )
