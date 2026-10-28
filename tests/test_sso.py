"""Login pelo Keycloak: só com token válido e só os e-mails de EMAILS_PERMITIDOS."""

import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from django.contrib.auth.models import User

from proposal.sso import EMAILS_PERMITIDOS, email_permitido

pytestmark = pytest.mark.django_db

CHAVE = rsa.generate_private_key(public_exponent=65537, key_size=2048)
EMISSOR = "https://keycloak.teste/realms/commercialproposal"


@pytest.fixture(autouse=True)
def keycloak(monkeypatch):
    monkeypatch.setenv("KEYCLOAK_HOST", "https://keycloak.teste/")
    monkeypatch.setenv("KEYCLOAK_REALM", "commercialproposal")
    monkeypatch.setenv("KEYCLOAK_CLIENT_ID", "commercialproposal")
    monkeypatch.setattr("proposal.sso._chave_publica", lambda token: CHAVE.public_key())


def token(email="hiro@estatcamp.com.br", nome="Hiro", papeis=("manage-account",), chave=CHAVE, **extra) -> str:
    claims = {
        "iss": EMISSOR,
        "azp": "commercialproposal",
        "exp": int(time.time()) + 300,
        "email": email,
        "name": nome,
        "resource_access": {"account": {"roles": list(papeis)}},
        **extra,
    }
    return jwt.encode(claims, chave, algorithm="RS256")


def entrar(client, valor: str):
    client.cookies["SSOToken"] = valor
    return client.get("/auth/complete/?next=/app")


def test_so_os_emails_fixos_podem_entrar() -> None:
    assert EMAILS_PERMITIDOS == {
        "leao@estatcamp.com.br", "hiro@estatcamp.com.br", "lucas@estatcamp.com.br",
        "rubens@estatcamp.com.br", "victor@estatcamp.com.br", "vitor@estatcamp.com.br",
    }
    # Victor e Vitor são pessoas diferentes: os dois e-mails entram, e nenhum libera o outro por engano.
    assert email_permitido("victor@estatcamp.com.br") and email_permitido("vitor@estatcamp.com.br")
    assert email_permitido(" Hiro@EstatCamp.com.br ")
    assert not email_permitido("hiro@estatcamp.com.br.hacker.io")


def test_admin_local_so_entra_com_debug(client, settings) -> None:
    settings.DEBUG = False
    assert entrar(client, token(email="local-admin@mail.com", nome="admin")).status_code == 403
    settings.DEBUG = True
    assert entrar(client, token(email="local-admin@mail.com", nome="admin")).status_code == 302


@pytest.mark.parametrize("email", sorted(EMAILS_PERMITIDOS))
def test_cada_email_da_lista_entra_sem_debug(client, settings, email) -> None:
    settings.DEBUG = False
    assert entrar(client, token(email=email, nome=email)).status_code == 302


def test_email_da_lista_entra(client) -> None:
    resposta = entrar(client, token())
    assert resposta.status_code == 302 and resposta["Location"] == "/app"
    user = User.objects.get(email="hiro@estatcamp.com.br")
    assert list(user.groups.values_list("name", flat=True)) == ["Master"]
    assert not user.has_usable_password()


def test_email_fora_da_lista_nao_entra(client) -> None:
    resposta = entrar(client, token(email="outro@estatcamp.com.br", nome="Outro"))
    assert resposta.status_code == 403
    assert not User.objects.filter(email="outro@estatcamp.com.br").exists()


def test_cookies_sem_token_valido_nao_entram(client) -> None:
    client.cookies["SSOEmail"] = "hiro@estatcamp.com.br"
    client.cookies["SSOName"] = "Hiro"
    client.cookies["SSOGroups"] = "admin"
    assert client.get("/auth/complete/").status_code == 400
    outra_chave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    assert entrar(client, token(chave=outra_chave, papeis=("admin",))).status_code == 400
    assert not User.objects.exists()


@pytest.mark.parametrize(
    "extra", [{"azp": "outro-client"}, {"iss": "https://outro/realms/commercialproposal"}, {"exp": int(time.time()) - 60}]
)
def test_token_de_outro_client_emissor_ou_vencido_nao_entra(client, extra) -> None:
    assert entrar(client, token(**extra)).status_code == 400


def test_conta_e_a_do_email_mesmo_com_nome_repetido(client) -> None:
    User.objects.create(username="Hiro", email="homonimo@estatcamp.com.br")
    entrar(client, token())
    assert User.objects.get(email="hiro@estatcamp.com.br").username == "hiro@estatcamp.com.br"
    assert User.objects.get(username="Hiro").email == "homonimo@estatcamp.com.br"


def test_quem_sai_da_lista_perde_a_sessao(client, monkeypatch) -> None:
    entrar(client, token())
    assert client.get("/app/").status_code != 403
    monkeypatch.setattr("proposal.sso.EMAILS_PERMITIDOS", frozenset({"vitor@estatcamp.com.br"}))
    assert client.get("/app/").status_code == 403
    assert "_auth_user_id" not in client.session


def test_superusuario_local_nao_depende_da_lista(client) -> None:
    admin = User.objects.create_superuser("estatcamp", "estatcamp@estatcamp.com.br", "senha")
    client.force_login(admin)
    assert client.get("/app/").status_code != 403
