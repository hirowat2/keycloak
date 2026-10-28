"""Etapas 3 e 4: provedor SAML (SSO corporativo), mappers de atributo e mappers de grupo.

Segue as seções 2 e 4 do README_sso.md. O Keycloak é o Service Provider; o
Entra ID, o Google Workspace ou o Okta são o Identity Provider.
"""

import json
from dataclasses import dataclass

from .api import KeycloakAdmin, seg
from .plano import ATUALIZAR, CRIAR, OK, REMOVER, Plano, diferencas

CLAIMS_ENTRA = "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/"
# Nome do claim de grupos do Entra sem a customização "Customize the name of the group claim".
CHAVE_GRUPOS_ENTRA_LONGA = "http://schemas.microsoft.com/ws/2008/06/identity/claims/groups"
ATRIBUTOS_SIMPLES = {"email": "email", "firstName": "firstName", "lastName": "lastName"}

# Seção 2.4: nome do atributo na asserção SAML de cada SSO → campo do usuário no Keycloak.
PROVEDORES = {
    "entra": {
        "nome": "Microsoft Entra ID",
        "atributos": {"email": f"{CLAIMS_ENTRA}emailaddress", "firstName": f"{CLAIMS_ENTRA}givenname", "lastName": f"{CLAIMS_ENTRA}surname"},
    },
    "google": {"nome": "Google Workspace", "atributos": ATRIBUTOS_SIMPLES},
    "okta": {"nome": "Okta", "atributos": ATRIBUTOS_SIMPLES},
    "outro": {"nome": "Outro (ADFS, Keycloak…)", "atributos": ATRIBUTOS_SIMPLES},
}

NAMEID = {
    "email": "urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress",
    "persistent": "urn:oasis:names:tc:SAML:2.0:nameid-format:persistent",
}

MAPPER_ATRIBUTO = "saml-user-attribute-idp-mapper"
MAPPER_USERNAME = "saml-username-idp-mapper"
MAPPER_GRUPO = "saml-advanced-group-idp-mapper"
REDIRECTOR = "identity-provider-redirector"


@dataclass
class Provedor:
    alias: str
    tipo: str = "entra"
    nome_exibicao: str = "conta corporativa"
    metadata_url: str = ""
    metadata_xml: str = ""
    nameid: str = "email"
    login_direto: bool = False


@dataclass
class MapeamentoGrupo:
    grupo: str
    valor: str
    chave: str = "groups"
    ativo: bool = True

    @property
    def nome_mapper(self) -> str:
        return f"grupo {self.grupo}"


def urls_sp(host: str, realm: str, alias: str) -> dict[str, str]:
    """Seção 2.1: o que o SSO pede (Entity ID, ACS/Reply URL, logout e metadata do SP)."""
    base = f"{host.rstrip('/')}/realms/{realm}"
    endpoint = f"{base}/broker/{alias or '<alias>'}/endpoint"
    return {"entity_id": base, "acs": endpoint, "logout": endpoint, "descriptor": f"{endpoint}/descriptor"}


def listar_provedores(api: KeycloakAdmin, realm: str) -> list[dict]:
    return [p for p in api.get(f"/{seg(realm)}/identity-provider/instances") or [] if p.get("providerId") == "saml"]


def importar_metadata(api: KeycloakAdmin, realm: str, url: str = "", xml: str = "") -> dict:
    """Lê o metadata do SSO pelo Keycloak (só lê; não grava nada)."""
    caminho = f"/{seg(realm)}/identity-provider/import-config"
    if url:
        return api.post(caminho, {"providerId": "saml", "fromUrl": url}).json()
    return api.requisitar("POST", caminho, data={"providerId": "saml"}, files={"file": ("metadata.xml", xml.encode())}).json()


def _garantir_mapper(api: KeycloakAdmin, plano: Plano, realm: str, alias: str, existentes: dict, nome: str, tipo: str, config: dict) -> None:
    caminho = f"/{seg(realm)}/identity-provider/instances/{seg(alias)}/mappers"
    atual = existentes.get(nome)
    if atual is None:
        plano.registrar(
            CRIAR, "mapper", nome, config.get("attribute.name") or config.get("template") or config.get("group", ""),
            lambda: api.post(caminho, {"name": nome, "identityProviderAlias": alias, "identityProviderMapper": tipo, "config": config}),
        )
        return
    mudou = diferencas(atual.get("config", {}), config)
    if atual.get("identityProviderMapper") != tipo:
        mudou.insert(0, "tipo")
    if mudou:
        plano.registrar(
            ATUALIZAR, "mapper", nome, ", ".join(mudou),
            lambda: api.put(f"{caminho}/{atual['id']}", {**atual, "identityProviderMapper": tipo, "config": config}),
        )
    else:
        plano.registrar(OK, "mapper", nome)


def mappers(api: KeycloakAdmin, realm: str, alias: str) -> dict[str, dict]:
    return {m["name"]: m for m in api.get(f"/{seg(realm)}/identity-provider/instances/{seg(alias)}/mappers") or []}


def _redirector(api: KeycloakAdmin, realm: str) -> dict | None:
    execucoes = api.get(f"/{seg(realm)}/authentication/flows/browser/executions") or []
    return next((e for e in execucoes if e.get("providerId") == REDIRECTOR), None)


def login_direto_atual(api: KeycloakAdmin, realm: str) -> str:
    """Alias do provedor para onde o login vai direto (seção 2.6), ou vazio."""
    config_id = (_redirector(api, realm) or {}).get("authenticationConfig")
    config = api.get(f"/{seg(realm)}/authentication/config/{config_id}") if config_id else None
    return (config or {}).get("config", {}).get("defaultProvider", "")


def _login_direto(api: KeycloakAdmin, plano: Plano, realm: str, alias: str, ligar: bool) -> None:
    """Seção 2.6: Identity Provider Redirector do fluxo browser apontando para o provedor."""
    redirector = _redirector(api, realm)
    if redirector is None:
        plano.registrar(OK, "login direto", "browser", "o fluxo browser deste realm não tem o Identity Provider Redirector")
        return
    config_id = redirector.get("authenticationConfig")
    atual = api.get(f"/{seg(realm)}/authentication/config/{config_id}") if config_id else None
    padrao = (atual or {}).get("config", {}).get("defaultProvider")
    if ligar and atual is None:
        plano.registrar(
            CRIAR, "login direto", alias, "Default Identity Provider",
            lambda: api.post(
                f"/{seg(realm)}/authentication/executions/{redirector['id']}/config",
                {"alias": f"sso-direto-{alias}", "config": {"defaultProvider": alias}},
            ),
        )
    elif ligar and padrao != alias:
        plano.registrar(
            ATUALIZAR, "login direto", alias, f"era {padrao or 'vazio'}",
            lambda: api.put(f"/{seg(realm)}/authentication/config/{config_id}", {**atual, "config": {**atual.get("config", {}), "defaultProvider": alias}}),
        )
    elif not ligar and padrao == alias:
        plano.registrar(REMOVER, "login direto", alias, "volta a mostrar a tela de login do Keycloak",
                        lambda: api.delete(f"/{seg(realm)}/authentication/config/{config_id}"))
    else:
        plano.registrar(OK, "login direto", alias, "ligado" if ligar else "desligado")


def aplicar_provedor(api: KeycloakAdmin, realm: str, host: str, provedor: Provedor, simular: bool) -> Plano:
    plano = Plano(simular)
    alias = provedor.alias
    atual = api.get(f"/{seg(realm)}/identity-provider/instances/{seg(alias)}")
    if not (provedor.metadata_url or provedor.metadata_xml) and atual is None:
        raise ValueError("Informe a URL de metadata do SSO (ou cole o XML) para cadastrar o provedor.")

    importado = importar_metadata(api, realm, provedor.metadata_url, provedor.metadata_xml) if (provedor.metadata_url or provedor.metadata_xml) else {}
    config = {
        **(atual or {}).get("config", {}),
        **importado,
        # Seção 2.3: Entity ID do Keycloak, NameID, assinaturas e Sync mode Force
        "entityId": urls_sp(host, realm, alias)["entity_id"],
        "nameIDPolicyFormat": NAMEID[provedor.nameid],
        "principalType": "SUBJECT",
        "wantAuthnRequestsSigned": "true",
        "wantAssertionsSigned": "true",
        "validateSignature": "true",
        "syncMode": "FORCE",
    }
    if provedor.metadata_url:
        # "Use entity descriptor": o Keycloak relê o metadata e acompanha a troca de certificado do SSO.
        config.update({"metadataDescriptorUrl": provedor.metadata_url, "useMetadataDescriptorUrl": "true"})
    desejado = {
        "alias": alias,
        "displayName": provedor.nome_exibicao,
        "providerId": "saml",
        "enabled": True,
        "trustEmail": True,
        "firstBrokerLoginFlowAlias": "first broker login",
        "config": config,
    }
    caminho = f"/{seg(realm)}/identity-provider/instances"
    if atual is None:
        plano.registrar(CRIAR, "provedor SAML", alias, PROVEDORES[provedor.tipo]["nome"], lambda: api.post(caminho, desejado))
    else:
        topo = {k: v for k, v in desejado.items() if k != "config"}
        mudou = diferencas(atual, topo) + [f"config.{c}" for c in diferencas(atual.get("config", {}), config)]
        if mudou:
            plano.registrar(ATUALIZAR, "provedor SAML", alias, ", ".join(mudou), lambda: api.put(f"{caminho}/{seg(alias)}", {**atual, **desejado}))
        else:
            plano.registrar(OK, "provedor SAML", alias)

    existentes = {} if (atual is None) else mappers(api, realm, alias)
    for campo, atributo in PROVEDORES[provedor.tipo]["atributos"].items():
        config_mapper = {"syncMode": "INHERIT", "attribute.name": atributo, "user.attribute": campo}
        _garantir_mapper(api, plano, realm, alias, existentes, campo, MAPPER_ATRIBUTO, config_mapper)
    # O username vira o preferred_username e o username no Django.
    _garantir_mapper(api, plano, realm, alias, existentes, "username", MAPPER_USERNAME,
                     {"syncMode": "INHERIT", "template": "${ATTRIBUTE.email}", "target": "LOCAL"})
    _login_direto(api, plano, realm, alias, provedor.login_direto)
    return plano


def ler_mapeamento(api: KeycloakAdmin, realm: str, alias: str) -> dict[str, MapeamentoGrupo]:
    """Mappers de grupo já cadastrados, pelo nome do grupo do Keycloak."""
    mapeados = {}
    for mapper in mappers(api, realm, alias).values():
        if mapper.get("identityProviderMapper") != MAPPER_GRUPO:
            continue
        config = mapper.get("config", {})
        atributo = next(iter(json.loads(config.get("attributes") or "[]")), {})
        grupo = config.get("group", "").lstrip("/")
        mapeados[grupo] = MapeamentoGrupo(grupo, atributo.get("value", ""), atributo.get("key", "groups"))
    return mapeados


def aplicar_mapeamento(api: KeycloakAdmin, realm: str, alias: str, itens: list[MapeamentoGrupo], simular: bool) -> Plano:
    """Seção 4.4: um mapper "Advanced Attribute to Group" por grupo, com Sync mode Force."""
    plano = Plano(simular)
    existentes = mappers(api, realm, alias)
    caminho = f"/{seg(realm)}/identity-provider/instances/{seg(alias)}/mappers"
    for item in itens:
        if not item.ativo:
            if item.nome_mapper in existentes:
                mapper_id = existentes[item.nome_mapper]["id"]
                plano.registrar(REMOVER, "mapper", item.nome_mapper, "", lambda mapper_id=mapper_id: api.delete(f"{caminho}/{mapper_id}"))
            continue
        config = {
            "syncMode": "FORCE",
            # Mesmo formato que o console grava, para a comparação não acusar mudança à toa
            "attributes": json.dumps([{"key": item.chave, "value": item.valor}], separators=(",", ":")),
            "are.attribute.values.regex": "false",
            "group": f"/{item.grupo}",
        }
        _garantir_mapper(api, plano, realm, alias, existentes, item.nome_mapper, MAPPER_GRUPO, config)
    return plano
