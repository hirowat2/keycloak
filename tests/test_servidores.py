"""Tela "Servidores Keycloak": cadastro pela interface, segredo cifrado e troca do Keycloak ativo."""

import pytest

from keycloak.automacao import api as modulo_api
from keycloak.automacao import servidores, web
from keycloak.automacao.api import ErroKeycloak
from keycloak.models import Servidor

pytestmark = pytest.mark.django_db

DADOS = {
    "nome": "Produção actionstat",
    "url": "https://keycloak.actionstat.app/",
    "url_interna": "",
    "autenticacao": "senha",
    "usuario": "admin",
    "client_id": "admin-cli",
    "segredo": "s3nha-forte",
    "verificar_tls": "on",
}


@pytest.fixture
def testes(monkeypatch):
    """A conexão de teste: guarda quem foi testado; ``falhar`` simula o Keycloak recusando."""
    estado = {"testados": [], "falhar": False}

    def testar(alvo):
        estado["testados"].append(alvo)
        if estado["falhar"]:
            raise ErroKeycloak("Login do admin no realm master recusado. invalid_grant")
        return {"versao": "21.1.2", "realms": ["master", "cliente-a"]}

    monkeypatch.setattr(servidores, "testar", testar)
    monkeypatch.setenv("KEYCLOAK_HOST", "https://keycloak.docker.localhost/")
    return estado


def test_cadastra_testa_e_ativa(entrar, testes) -> None:
    client = entrar("Admin")
    resposta = client.post("/app/servidores/", {**DADOS, "acao": "salvar"})
    assert resposta.status_code == 302
    servidor = Servidor.objects.get()
    assert servidor.url == "https://keycloak.actionstat.app" and servidor.usuario == "admin"
    assert servidor.segredo and "s3nha" not in servidor.segredo  # cifrado
    alvo = servidores.do_cadastro(servidor)
    assert alvo.senha == "s3nha-forte" and testes["testados"][0].url == "https://keycloak.actionstat.app"
    # O novo vira o ativo da sessão e aparece no seletor do menu
    assert client.session[servidores.CHAVE_SESSAO] == str(servidor.pk)
    html = client.get("/app/servidores/").content.decode()
    assert 'action="/app/servidor-ativo/"' in html and "Produção actionstat" in html and "ativo</span>" in html


def test_falha_no_teste_nao_salva_mas_permite_salvar_mesmo_assim(entrar, testes) -> None:
    testes["falhar"] = True
    client = entrar("Admin")
    html = client.post("/app/servidores/", {**DADOS, "acao": "salvar"}).content.decode()
    assert "invalid_grant" in html and 'value="salvar_sem_testar"' in html and not Servidor.objects.exists()
    assert client.post("/app/servidores/", {**DADOS, "acao": "salvar_sem_testar"}).status_code == 302
    assert Servidor.objects.count() == 1


def test_editar_em_branco_mantem_o_segredo(entrar, testes) -> None:
    client = entrar("Admin")
    client.post("/app/servidores/", {**DADOS, "acao": "salvar"})
    servidor = Servidor.objects.get()
    client.post("/app/servidores/", {**DADOS, "segredo": "", "url_interna": "http://keycloak:8080", "editar": servidor.pk, "acao": "salvar"})
    servidor.refresh_from_db()
    assert servidor.url_interna == "http://keycloak:8080" and servidores.do_cadastro(servidor).senha == "s3nha-forte"


@pytest.mark.parametrize("url", ["ftp://kc.exemplo", "https://kc.exemplo/admin", "https://kc.exemplo/?x=1", "https://u:p@kc.exemplo", "kc.exemplo", "https://kc:porta"])
def test_recusa_url_invalida(entrar, testes, url) -> None:
    html = entrar("Admin").post("/app/servidores/", {**DADOS, "url": url, "acao": "salvar"}).content.decode()
    assert not Servidor.objects.exists() and "ct-neg" in html


def test_service_account(entrar, testes) -> None:
    dados = {**DADOS, "autenticacao": "client", "usuario": "", "client_id": "assistente", "segredo": "abc"}
    entrar("Admin").post("/app/servidores/", {**dados, "acao": "salvar"})
    alvo = servidores.do_cadastro(Servidor.objects.get())
    assert alvo.client_id == "assistente" and alvo.client_secret == "abc" and not alvo.senha


def test_limited_nao_cadastra_mas_escolhe(entrar, testes) -> None:
    Servidor.objects.create(nome="Outro", url="https://kc.exemplo", usuario="admin", segredo=servidores.cifrar("x"))
    client = entrar("Limited")
    client.post("/app/servidores/", {**DADOS, "acao": "salvar"})
    assert Servidor.objects.count() == 1
    chave = str(Servidor.objects.get().pk)
    assert client.post("/app/servidores/", {"acao": "usar", "chave": chave}).status_code == 302
    assert client.session[servidores.CHAVE_SESSAO] == chave


def test_servidor_ativo_vale_para_as_telas(entrar, testes, monkeypatch) -> None:
    """O middleware ativa o escolhido: api() e url_publica() passam a ser os dele, só durante a requisição."""
    servidor = Servidor.objects.create(nome="Prod", url="https://keycloak.actionstat.app", usuario="admin",
                                       segredo=servidores.cifrar("x"))
    vistos = {}

    def painel(context, request, realm):
        vistos.update(url=web.api().url, publica=modulo_api.url_publica())
        return {"request": request, "context": context}

    monkeypatch.setattr(web, "realms_disponiveis", lambda: ["cliente-a"])
    from keycloak.screens.painel import view as painel_view
    monkeypatch.setattr(painel_view, "view", web.com_realm(exige_realm=False)(painel))
    client = entrar("Admin")
    client.post("/app/servidor-ativo/", {"servidor": str(servidor.pk), "next": "/app/painel/"})
    client.get("/app/painel/")
    assert vistos == {"url": "https://keycloak.actionstat.app", "publica": "https://keycloak.actionstat.app"}
    assert modulo_api.ativo() is None  # nada vaza para a próxima requisição da thread


def test_remover_volta_para_o_ambiente(entrar, testes) -> None:
    client = entrar("Admin")
    client.post("/app/servidores/", {**DADOS, "acao": "salvar"})
    pk = Servidor.objects.get().pk
    client.post("/app/servidores/", {"acao": "remover", "chave": pk})
    assert not Servidor.objects.exists() and servidores.CHAVE_SESSAO not in client.session
    assert servidores.escolhido(client.session).ambiente


def test_dica_do_caminho_auth(monkeypatch) -> None:
    class Resposta:
        ok = True

    monkeypatch.setattr(servidores.requests, "get", lambda url, **kw: Resposta())
    alvo = servidores.Alvo("1", "x", "https://kc.antigo")
    assert "https://kc.antigo/auth" in servidores._dica(alvo, "POST https://kc.antigo/realms/master/... → 404: Not Found")
