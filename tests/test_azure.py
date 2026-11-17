"""Tela "Azure AD dos realms": inventário, comparação com o Azure e ajuste do provedor."""

import pytest

from keycloak.automacao import azure

PROVEDOR = {
    "alias": "Estatcamp", "enabled": True, "providerId": "saml",
    "config": {
        "entityId": "https://keycloak.antigo/realms/cliente",
        "singleSignOnServiceUrl": "https://login.microsoftonline.com/22f0fb2c-0638-4944-be79-9e94ac853bcc/saml2",
        "validateSignature": "false",
    },
}


class Api:
    def __init__(self):
        self.gravado = None

    def get(self, caminho, **_):
        if caminho.endswith("/mappers"):
            return []
        if caminho.endswith("/instances"):
            return [PROVEDOR, {"alias": "google", "providerId": "saml", "config": {"singleSignOnServiceUrl": "https://accounts.google.com/o/saml2"}}]
        return PROVEDOR

    def put(self, caminho, dados):
        self.gravado = dados


def test_inventario_so_azure_com_problemas() -> None:
    itens = azure.inventario(Api(), "https://keycloak.novo", ["cliente"])
    assert [i["alias"] for i in itens] == ["Estatcamp"]
    item = itens[0]
    assert item["tenant"] == "22f0fb2c-0638-4944-be79-9e94ac853bcc"
    assert item["reply"] == "https://keycloak.novo/realms/cliente/broker/Estatcamp/endpoint"
    assert set(item["problemas"]) == {"assinatura não validada", "Entity ID no host antigo"}


def test_comparar_diz_o_que_adicionar_e_remover() -> None:
    item = azure.inventario(Api(), "https://keycloak.novo", ["cliente"])[0]
    linhas = azure.comparar(item, "https://keycloak.antigo/realms/cliente", "https://keycloak.novo/realms/cliente/broker/Estatcamp/endpoint/\nhttps://keycloak.antigo/realms/cliente")
    assert not linhas[0]["ok"] and linhas[0]["sobra"] == ["https://keycloak.antigo/realms/cliente"]
    assert linhas[1]["ok"] and linhas[1]["sobra"] == ["https://keycloak.antigo/realms/cliente"]


def test_aplicar_troca_entity_e_liga_assinatura(monkeypatch) -> None:
    urls = []
    monkeypatch.setattr(azure, "importar_metadata", lambda api, realm, url: urls.append(url) or {"signingCertificate": "MIIC", "idpEntityId": "https://sts.windows.net/x/"})
    api = Api()
    app = "a4571991-0c9b-40c9-b6a7-a48d4353924f"
    plano = azure.aplicar(api, "cliente", "Estatcamp", "https://keycloak.novo", app, True, simular=True)
    assert plano.mudancas == 1 and api.gravado is None  # simulação não grava
    azure.aplicar(api, "cliente", "Estatcamp", "https://keycloak.novo", app, True, simular=False)
    config = api.gravado["config"]
    assert config["entityId"] == "https://keycloak.novo/realms/cliente" and config["validateSignature"] == "true"
    assert config["signingCertificate"] == "MIIC" and urls[0].endswith(f"?appid={app}") and "22f0fb2c" in urls[0]
    with pytest.raises(ValueError):
        azure.aplicar(api, "cliente", "Estatcamp", "https://keycloak.novo", "nao-e-guid", True, simular=True)
