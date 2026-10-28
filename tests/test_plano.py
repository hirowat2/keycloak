"""Plano das etapas e as funções que não falam com o Keycloak."""

from keycloak.automacao.conferir import _sem_ids, env_dos_apps
from keycloak.automacao.grupos import estrutura_sugerida
from keycloak.automacao.plano import CRIAR, OK, Plano, diferencas
from keycloak.automacao.realm import App
from keycloak.automacao.saml import MapeamentoGrupo, urls_sp
from keycloak.screens.migracao.view import comandos


def test_diferencas_ignora_ordem_das_listas_e_bool_como_texto() -> None:
    atual = {"supportedLocales": ["en", "pt-BR"], "validateSignature": "true", "sslRequired": "none"}
    desejado = {"supportedLocales": ["pt-BR", "en"], "validateSignature": True, "sslRequired": "external"}
    assert diferencas(atual, desejado) == ["sslRequired"]


def test_simulacao_nao_executa_e_aplicacao_executa() -> None:
    feito = []
    simulado = Plano(simular=True)
    simulado.registrar(CRIAR, "grupo", "a", acao=lambda: feito.append("a"))
    aplicado = Plano(simular=False)
    aplicado.registrar(CRIAR, "grupo", "b", acao=lambda: feito.append("b"))
    aplicado.registrar(OK, "grupo", "c", acao=lambda: feito.append("c"))
    assert feito == ["b"] and simulado.mudancas == 1 and aplicado.mudancas == 1


def test_client_publico_com_pkce_e_callback_do_app() -> None:
    rep = App("atlas-insights", "Atlas Insights", "https://atlas.exemplo/").representacao()
    assert rep["publicClient"] and not rep["directAccessGrantsEnabled"] and not rep["implicitFlowEnabled"]
    assert rep["redirectUris"] == ["https://atlas.exemplo/oidc/callback/"]
    assert rep["webOrigins"] == ["https://atlas.exemplo"]
    assert rep["attributes"] == {"pkce.code.challenge.method": "S256", "post.logout.redirect.uris": "https://atlas.exemplo/*"}


def test_urls_que_o_sso_pede() -> None:
    urls = urls_sp("https://kc.exemplo/", "automateflow", "entra")
    assert urls == {
        "entity_id": "https://kc.exemplo/realms/automateflow",
        "acs": "https://kc.exemplo/realms/automateflow/broker/entra/endpoint",
        "logout": "https://kc.exemplo/realms/automateflow/broker/entra/endpoint",
        "descriptor": "https://kc.exemplo/realms/automateflow/broker/entra/endpoint/descriptor",
    }


def test_estrutura_sugerida_da_secao_3_2() -> None:
    assert estrutura_sugerida("automateflow", ["atlas-insights", "mongo-migrator"]) == {
        "automateflow-admins": ["ADMIN", "atlas-insights", "mongo-migrator"],
        "automateflow-atlas-insights": ["atlas-insights"],
        "automateflow-mongo-migrator": ["mongo-migrator"],
    }


def test_mapper_de_grupo_tem_nome_previsivel() -> None:
    assert MapeamentoGrupo("automateflow-admins", "automateflow-admins").nome_mapper == "grupo automateflow-admins"


def test_env_de_cada_app_exige_a_role_do_app() -> None:
    env = env_dos_apps("https://kc.exemplo", "http://keycloak:8080/", "automateflow", ["atlas-insights"])
    assert env["atlas-insights"].splitlines() == [
        "KEYCLOAK_HOST=https://kc.exemplo/",
        "KEYCLOAK_INTERNAL_URL=http://keycloak:8080",
        "KEYCLOAK_REALM=automateflow",
        "KEYCLOAK_CLIENT_ID=atlas-insights",
        "KEYCLOAK_REQUIRED_ROLE=atlas-insights",
    ]


def test_export_versionavel_sem_ids_nem_secrets() -> None:
    assert _sem_ids({"id": "1", "clients": [{"id": "2", "clientId": "x", "secret": "s", "attributes": {"a": "b"}}]}) == {
        "clients": [{"clientId": "x", "attributes": {"a": "b"}}]
    }


def test_comandos_da_migracao_por_destino() -> None:
    compose = comandos("root@vm", "kc", "compose")
    assert compose["vm"] == ["scp scripts/exportar_vm.sh root@vm:", "ssh root@vm sh exportar_vm.sh kc"]
    assert compose["a"][-1] == "make importar-realms" and compose["b"][-1] == "make restaurar-dump"
    assert comandos("root@vm", "kc", "k8s")["b"][-1] == "make k8s-restaurar-dump"
