"""As etapas pelas telas, contra um Keycloak de verdade (KEYCLOAK_TESTE_URL), num realm descartável.

    KEYCLOAK_TESTE_URL=https://keycloak.docker.localhost KEYCLOAK_VERIFY_TLS=false make test
"""

import json
import os
import uuid

import pytest

from keycloak.automacao import grupos, saml
from keycloak.automacao.realm import ler_realm
from keycloak.models import Aplicacao

pytestmark = pytest.mark.django_db

# O metadata é baixado pelo próprio Keycloak: o descriptor do realm master serve de "SSO corporativo".
METADATA = os.environ.get("KEYCLOAK_TESTE_METADATA", "http://localhost:8080/realms/master/protocol/saml/descriptor")
APPS = [("atlas-insights", "Atlas Insights", "https://atlas.teste"), ("mongo-migrator", "Mongo Migrator", "https://migrator.teste")]


def formset(prefixo: str, linhas: list[dict]) -> dict:
    dados = {f"{prefixo}-TOTAL_FORMS": str(len(linhas)), f"{prefixo}-INITIAL_FORMS": "0",
             f"{prefixo}-MIN_NUM_FORMS": "0", f"{prefixo}-MAX_NUM_FORMS": "1000"}
    for i, linha in enumerate(linhas):
        for campo, valor in linha.items():
            dados[f"{prefixo}-{i}-{campo}"] = valor
    return dados


@pytest.fixture
def realm(keycloak_real):
    nome = f"teste-{uuid.uuid4().hex[:8]}"
    yield nome
    if ler_realm(keycloak_real, nome) is not None:
        keycloak_real.delete(f"/{nome}")


def ultima() -> Aplicacao:
    return Aplicacao.objects.order_by("-pk").first()


def test_etapas_completas_pelas_telas(entrar, keycloak_real, realm) -> None:
    client = entrar("Admin")
    apps = formset("apps", [{"client_id": c, "nome": n, "url": u, "callback": "/oidc/callback/"} for c, n, u in APPS])

    # 1 · realm e apps: simular não grava; aplicar cria tudo e torna o realm ativo
    resposta = client.post("/app/realm/?novo=1", {"realm": realm, "nome_exibicao": "Teste", "acao": "simular", **apps})
    assert resposta.status_code == 200 and ler_realm(keycloak_real, realm) is None
    assert ultima().simulacao and ultima().mudancas == 1 + 1 + 2 * len(APPS)
    client.post("/app/realm/?novo=1", {"realm": realm, "nome_exibicao": "Teste", "acao": "aplicar", **apps})
    assert ler_realm(keycloak_real, realm)["defaultLocale"] == "pt-BR"
    assert client.session["realm"] == realm
    assert "atlas.teste" in client.get("/app/realm/").content.decode()

    # 2 · grupos: a tela sugere a estrutura da seção 3.2
    sugestao = client.get("/app/grupos/").context["formset"].initial
    linhas = [{"nome": g["nome"], "roles": g["roles"]} for g in sugestao]
    client.post("/app/grupos/", {"realm_tela": realm, "acao": "aplicar", **formset("grupos", linhas)})
    assert grupos.ler_grupos(keycloak_real, realm) == {
        f"{realm}-admins": ["ADMIN", "atlas-insights", "mongo-migrator"],
        f"{realm}-atlas-insights": ["atlas-insights"],
        f"{realm}-mongo-migrator": ["mongo-migrator"],
    }

    # 3 · SSO: provedor, mappers de atributo e username, login direto
    sso = {"tipo": "entra", "alias": "entra", "nome_exibicao": "conta corporativa", "metadata_url": METADATA,
           "nameid": "email", "login_direto": "on", "realm_tela": realm}
    client.post("/app/sso/", {**sso, "acao": "aplicar"})
    assert ultima().sucesso, ultima().erro
    assert saml.login_direto_atual(keycloak_real, realm) == "entra"
    html = client.get("/app/sso/").content.decode()
    assert f"/realms/{realm}/broker/entra/endpoint" in html

    # 4 · grupos do SSO: um mapper por grupo
    inicial = client.get("/app/mapeamento/").context["formset"].initial
    client.post("/app/mapeamento/", {"realm_tela": realm, "acao": "aplicar", **formset("map", [
        {"grupo": m["grupo"], "ativo": "on", "valor": m["valor"], "chave": "groups"} for m in inicial
    ])})
    assert set(saml.ler_mapeamento(keycloak_real, realm, "entra")) == {m["grupo"] for m in inicial}

    # 5 · conferir: nada pendente; o export não leva ids nem secrets
    assert client.get("/app/conferir/").context["pendentes"] == 0
    exportado = json.loads(client.get("/app/conferir/?exportar=1").content)
    assert {c["clientId"] for c in exportado["clients"]} == {c for c, _, _ in APPS}
    assert "users" not in exportado and "components" not in exportado and '"id"' not in json.dumps(exportado)
    assert client.get("/app/painel/").status_code == 200

    # Aplicar de novo não muda nada
    client.post("/app/sso/", {**sso, "acao": "aplicar"})
    assert ultima().sucesso and ultima().mudancas == 0
    client.post("/app/grupos/", {"realm_tela": realm, "acao": "aplicar", **formset("grupos", linhas)})
    assert ultima().mudancas == 0

    # Migração: host novo nos clients
    client.post("/app/migracao/", {"realm_tela": realm, "antigo": "https://atlas.teste", "novo": "https://atlas.novo", "acao": "aplicar"})
    atlas = keycloak_real.get(f"/{realm}/clients", clientId="atlas-insights")[0]
    assert atlas["redirectUris"] == ["https://atlas.novo/oidc/callback/"]
    assert client.get("/app/migracao/?incompletos=1").status_code == 200


def test_limited_so_simula(entrar, keycloak_real, realm) -> None:
    apps = formset("apps", [{"client_id": "atlas-insights", "nome": "Atlas", "url": "https://atlas.teste"}])
    entrar("Limited").post("/app/realm/?novo=1", {"realm": realm, "acao": "aplicar", **apps})
    assert ler_realm(keycloak_real, realm) is None and not Aplicacao.objects.exists()
