from django import template

from keycloak.automacao import servidores
from keycloak.screens.config.aside import SECOES
from keycloak.screens.config.permissions import user_in_groups

register = template.Library()


@register.simple_tag(takes_context=True)
def menu_app(context) -> dict:
    """Seções do menu visíveis ao usuário, o item da página atual e os realms.

    O item ativo é o de ``href`` mais longo que prefixa o caminho atual, para
    que ``/app/grupos/?novo=1`` continue marcando "Grupos e roles". Os realms
    vêm do contexto da tela (``com_realm``); telas sem Keycloak não mostram o seletor.
    """
    request = context.get("request")
    user = getattr(request, "user", None)
    caminho = getattr(request, "path", "")
    if not getattr(user, "is_authenticated", False):
        return {"secoes": [], "ativo": None, "realm": "", "realms": [], "servidores": [], "servidor": None}

    secoes = []
    for secao in SECOES:
        itens = [
            dict(item)
            for item in secao["itens"]
            if not item.get("required_groups") or user_in_groups(user, item["required_groups"])
        ]
        if itens:
            secoes.append({"titulo": secao["titulo"], "itens": itens})

    candidatos = [i for s in secoes for i in s["itens"] if caminho.startswith(i["href"])]
    ativo = max(candidatos, key=lambda i: len(i["href"]), default=None)
    if ativo:
        ativo["ativo"] = True
    return {
        "secoes": secoes,
        "ativo": ativo,
        "realm": context.get("realm") or "",
        "realms": context.get("realms") or [],
        # Seletor do Keycloak (tela Servidores): o ativo vem do middleware
        "servidores": servidores.disponiveis(),
        "servidor": getattr(request, "keycloak", None),
    }


@register.filter
def iniciais(usuario) -> str:
    """Iniciais para o avatar: 'Maria Souza' -> 'MS'; sem nome, a 1ª letra do login."""
    nome = (getattr(usuario, "get_full_name", lambda: "")() or "").split()
    if nome:
        return (nome[0][0] + (nome[-1][0] if len(nome) > 1 else "")).upper()
    return (getattr(usuario, "username", "") or "?")[:1].upper()


@register.simple_tag(takes_context=True)
def tour_da_tela(context) -> dict | None:
    """O tour da tela atual (/app/<tela>/), com as figuras já com a URL de /media/; None se a tela não tem tour."""
    from keycloak.screens.config.tours import TOURS
    from keycloak.templatetags.custom_filters import media_url

    request = context.get("request")
    if not getattr(getattr(request, "user", None), "is_authenticated", False):
        return None
    partes = [p for p in getattr(request, "path", "").split("/") if p]
    tela = partes[1] if len(partes) >= 2 and partes[0] == "app" else ("painel" if partes == ["app"] else "")
    tour = TOURS.get(tela)
    if not tour:
        return None
    passos = [{**passo, "figura": media_url(passo["figura"]) if passo.get("figura") else ""} for passo in tour["passos"]]
    return {"tela": tela, "titulo": tour["titulo"], "passos": passos}
