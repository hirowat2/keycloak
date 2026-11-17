"""Provedores SAML ligados ao Azure AD (Microsoft Entra ID) já cadastrados nos realms.

Depois de migrar o Keycloak de host (ex.: keycloak.estatcamp.online → keycloak.actionstat.app),
os provedores continuam com o Entity ID do host antigo, e o app do Azure continua
mandando a resposta para a Reply URL antiga. Aqui: o inventário de todos os realms,
o que o app do Azure precisa ter, a comparação com o que está lá, e o ajuste do lado
do Keycloak (Entity ID no host atual e validação da assinatura pelo metadata do app).
"""
import re
from urllib.parse import urlsplit

from .api import KeycloakAdmin, seg
from .plano import ATUALIZAR, OK, Plano
from .saml import importar_metadata, listar_provedores, urls_sp

TENANT = re.compile(r"(?:login\.microsoftonline\.com|sts\.windows\.net)/([0-9a-fA-F-]{36})")
GUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
# Campos que o metadata do app do Azure atualiza no provedor (o resto da configuração fica).
CAMPOS_METADATA = ("signingCertificate", "idpEntityId", "singleSignOnServiceUrl", "singleLogoutServiceUrl")


def tenant(provedor: dict) -> str:
    config = provedor.get("config", {})
    for campo in ("singleSignOnServiceUrl", "idpEntityId", "metadataDescriptorUrl"):
        if achado := TENANT.search(config.get(campo, "")):
            return achado.group(1).lower()
    return ""


def metadata_url(tenant_id: str, app_id: str) -> str:
    """App Federation Metadata Url do Enterprise application (o certificado SAML é do app, não do tenant)."""
    return f"https://login.microsoftonline.com/{tenant_id}/federationmetadata/2007-06/federationmetadata.xml?appid={app_id}"


def _host(url: str) -> str:
    partes = urlsplit(url or "")
    return f"{partes.scheme}://{partes.netloc}".lower() if partes.netloc else ""


def resumo(api: KeycloakAdmin, host: str, realm: str, provedor: dict) -> dict:
    """O provedor visto pelo lado do Azure: o que o app precisa ter e o que está errado no Keycloak."""
    config = provedor.get("config", {})
    alias = provedor["alias"]
    esperado = urls_sp(host, realm, alias)
    entity = config.get("entityId", "")
    mappers = api.get(f"/{seg(realm)}/identity-provider/instances/{seg(alias)}/mappers") or []
    problemas = []
    if config.get("validateSignature") != "true":
        problemas.append("assinatura não validada")
    if entity and _host(entity) != _host(host):
        problemas.append("Entity ID no host antigo")
    if not provedor.get("enabled", True):
        problemas.append("desligado")
    return {
        "realm": realm,
        "alias": alias,
        "nome": provedor.get("displayName") or alias,
        "ativo": provedor.get("enabled", True),
        "tenant": tenant(provedor),
        "entity_atual": entity,
        "entity_esperado": esperado["entity_id"],
        "reply": esperado["acs"],
        "reply_antiga": f"{_host(entity)}{urlsplit(esperado['acs']).path}" if entity and _host(entity) != _host(host) else "",
        "valida_assinatura": config.get("validateSignature") == "true",
        "tem_certificado": bool(config.get("signingCertificate")),
        "nameid": config.get("nameIDPolicyFormat", "").rsplit(":", 1)[-1],
        "mappers": [
            {"nome": m["name"], "tipo": m["identityProviderMapper"], "valor": m.get("config", {}).get("attribute.value", ""),
             "destino": m.get("config", {}).get("role") or m.get("config", {}).get("group", "")}
            for m in mappers
        ],
        "problemas": problemas,
    }


def inventario(api: KeycloakAdmin, host: str, realms: list[str]) -> list[dict]:
    """Todos os provedores SAML que apontam para o Azure, em todos os realms."""
    itens = []
    for realm in realms:
        for provedor in listar_provedores(api, realm):
            if tenant(provedor):
                itens.append(resumo(api, host, realm, provedor))
    return itens


def comparar(item: dict, identificador: str, resposta: str) -> list[dict]:
    """O que está no app do Azure (colado pelo usuário) contra o que o Keycloak manda."""
    linhas = []
    for campo, colado, certo in (
        ("Identificador (ID da Entidade)", identificador, item["entity_esperado"]),
        ("URL de Resposta (ACS)", resposta, item["reply"]),
    ):
        colados = [v.strip().rstrip("/") for v in re.split(r"[\s,;]+", colado or "") if v.strip()]
        if not colados:
            continue
        linhas.append({
            "campo": campo, "colado": colados, "certo": certo, "ok": certo in colados,
            "sobra": [v for v in colados if v != certo],
        })
    return linhas


def aplicar(api: KeycloakAdmin, realm: str, alias: str, host: str, app_id: str, trocar_entity: bool, simular: bool) -> Plano:
    """Entity ID no host atual e, com o ID do Aplicativo, o certificado do app e a validação da assinatura."""
    plano = Plano(simular)
    caminho = f"/{seg(realm)}/identity-provider/instances/{seg(alias)}"
    provedor = api.get(caminho)
    if provedor is None:
        raise ValueError(f"O provedor {alias} não existe no realm {realm}.")
    config = dict(provedor.get("config", {}))
    mudou = []

    certo = urls_sp(host, realm, alias)["entity_id"]
    if trocar_entity and config.get("entityId") != certo:
        mudou.append(f"Entity ID {config.get('entityId') or 'vazio'} → {certo}")
        config["entityId"] = certo

    if app_id:
        if not GUID.match(app_id):
            raise ValueError("O ID do Aplicativo é um GUID (Azure → Aplicativos empresariais → o app → Propriedades).")
        tenant_id = tenant(provedor)
        url = metadata_url(tenant_id, app_id.lower())
        importado = importar_metadata(api, realm, url=url)
        if not importado.get("signingCertificate"):
            raise ValueError(f"O metadata do app não trouxe certificado: confira o ID do Aplicativo e o tenant {tenant_id}.")
        novos = {k: importado[k] for k in CAMPOS_METADATA if importado.get(k)}
        if any(config.get(k) != v for k, v in novos.items()):
            mudou.append("certificado e endereços do metadata do app")
        config.update(novos)
        if config.get("validateSignature") != "true":
            mudou.append("Validate Signatures ligado")
            config["validateSignature"] = "true"

    if mudou:
        plano.registrar(ATUALIZAR, "provedor", alias, "; ".join(mudou), lambda: api.put(caminho, {**provedor, "config": config}))
    else:
        plano.registrar(OK, "provedor", alias, "já está no host atual" + (" e validando a assinatura" if app_id else ""))
    return plano
