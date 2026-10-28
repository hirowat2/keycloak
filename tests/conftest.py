import os

import pytest


@pytest.fixture
def usuario(db):
    from django.contrib.auth.models import Group, User

    def criar(*grupos, **extras):
        # Contas do login corporativo (sem senha) só passam pelo middleware com e-mail da lista liberada.
        extras.setdefault("email", "hiro@estatcamp.com.br")
        user = User.objects.create_user(f"u{User.objects.count()}", **extras)
        user.groups.add(*(Group.objects.get_or_create(name=nome)[0] for nome in grupos))
        return user

    return criar


@pytest.fixture
def entrar(usuario):
    """Cliente HTTP logado num grupo do assistente (Admin aplica; Limited só consulta)."""
    from django.test import Client

    def criar(grupo: str = "Admin") -> Client:
        client = Client()
        client.force_login(usuario(grupo, first_name="Hiro"))
        return client

    return criar


@pytest.fixture(autouse=True)
def sem_cache():
    from django.core.cache import cache

    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def keycloak_real(monkeypatch):
    """Admin API de um Keycloak de verdade (KEYCLOAK_TESTE_URL); sem ela, o teste é pulado."""
    url = os.environ.get("KEYCLOAK_TESTE_URL")
    if not url:
        pytest.skip("Defina KEYCLOAK_TESTE_URL (e KEYCLOAK_ADMIN_USER/PASSWORD) para os testes de integração.")
    from keycloak.automacao import web
    from keycloak.automacao.api import KeycloakAdmin

    monkeypatch.setenv("KEYCLOAK_HOST", url)
    api = KeycloakAdmin(
        url, os.environ.get("KEYCLOAK_ADMIN_USER", "admin"), os.environ.get("KEYCLOAK_ADMIN_PASSWORD", "admin"),
        verificar_tls=os.environ.get("KEYCLOAK_VERIFY_TLS", "true").lower() not in ("false", "0"),
    )
    monkeypatch.setattr(web, "_api", api)
    return api
