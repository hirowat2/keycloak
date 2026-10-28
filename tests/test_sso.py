"""Login pelo Keycloak: só com token válido, só os e-mails de EMAILS_PERMITIDOS, e a role ADMIN vira Admin."""

import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from django.contrib.auth.models import User

from system.sso import EMAILS_PERMITIDOS, email_permitido

pytestmark = pytest.mark.django_db

CHAVE = rsa.generate_private_key(public_exponent=65537, key_size=2048)
EMISSOR = "https://keycloak.teste/realms/automateflow"


@pytest.fixture(autouse=True)
def keycloak(monkeypatch):
    monkeypatch.setenv("KEYCLOAK_HOST", "https://keycloak.teste/")
    monkeypatch.setenv("KEYCLOAK_REALM", "automateflow")
    monkeypatch.setenv("KEYCLOAK_CLIENT_ID", "keycloak-assistente")
    monkeypatch.setattr("system.sso._chave_publica", lambda token: CHAVE.public_key())


def token(email="hiro@estatcamp.com.br", nome="Hiro", roles=("default-roles-automateflow",), chave=CHAVE, **extra) -> str:
    claims = {
        "iss": EMISSOR,
        "azp": "keycloak-assistente",
        "exp": int(time.time()) + 300,
        "email": email,
        "name": nome,
        "realm_access": {"roles": list(roles)},
        **extra,
    }
    return jwt.encode(claims, chave, algorithm="RS256")


def entrar(client, valor: str):
    client.cookies["SSOToken"] = valor
    return client.get("/auth/complete/?next=/app")


def test_so_os_emails_fixos_podem_entrar() -> None:
    assert "hiro@estatcamp.com.br" in EMAILS_PERMITIDOS
    assert email_permitido(" Hiro@EstatCamp.com.br ")
    assert not email_permitido("hiro@estatcamp.com.br.hacker.io")


def test_role_admin_vira_admin_e_superuser(client) -> None:
    assert entrar(client, token(roles=("ADMIN",))).status_code == 302
    user = User.objects.get(email="hiro@estatcamp.com.br")
    assert user.is_superuser and user.is_staff and list(user.groups.values_list("name", flat=True)) == ["Admin"]


def test_sem_role_admin_so_consulta(client) -> None:
    assert entrar(client, token()).status_code == 302
    user = User.objects.get(email="hiro@estatcamp.com.br")
    assert not user.is_superuser and list(user.groups.values_list("name", flat=True)) == ["Limited"]


def test_perder_a_role_admin_tira_o_superuser(client) -> None:
    entrar(client, token(roles=("ADMIN",)))
    client.logout()
    entrar(client, token())
    assert not User.objects.get(email="hiro@estatcamp.com.br").is_superuser


def test_admin_local_so_entra_com_debug(client, settings) -> None:
    settings.DEBUG = False
    assert entrar(client, token(email="admin@automateflow.local", nome="admin")).status_code == 403
    settings.DEBUG = True
    assert entrar(client, token(email="admin@automateflow.local", nome="admin")).status_code == 302


@pytest.mark.parametrize(
    "valor",
    [
        token(email="intruso@empresa.com", nome="Intruso"),
        token(chave=rsa.generate_private_key(public_exponent=65537, key_size=2048)),
        token(azp="outro-client"),
        token(iss="https://outro/realms/automateflow"),
        token(exp=int(time.time()) - 10),
        "lixo",
    ],
)
def test_token_invalido_ou_email_fora_da_lista_nao_entra(client, valor) -> None:
    assert entrar(client, valor).status_code in (400, 403)
    assert not User.objects.filter(email="intruso@empresa.com").exists()


def test_superuser_do_sso_tirado_da_lista_perde_a_sessao(client, monkeypatch) -> None:
    entrar(client, token(roles=("ADMIN",)))
    monkeypatch.setattr("system.sso.EMAILS_PERMITIDOS", frozenset())
    assert client.get("/app/").status_code == 403
