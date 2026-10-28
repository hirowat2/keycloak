from django import template

from commercial.propostas.empresas import eh_admin, empresa_ativa, empresas_do_usuario, papel_ativo
from commercial.propostas.models import PAPEL_ADMIN
from commercial.screens.config.aside import SECOES

register = template.Library()


@register.simple_tag(takes_context=True)
def menu_app(context) -> dict:
    """Seções do menu visíveis ao usuário, o item da página atual e as empresas.

    Os itens dependem do papel do usuário na empresa ativa. O item ativo é o
    de ``href`` mais longo que prefixa o caminho atual, para que
    ``/app/propostas/?id=7`` continue marcando "Propostas".
    """
    request = context.get("request")
    user = getattr(request, "user", None)
    caminho = getattr(request, "path", "")
    if not getattr(user, "is_authenticated", False):
        return {"secoes": [], "ativo": None, "empresa": "", "empresas": []}

    empresa = empresa_ativa(request)
    # Admin vê a Administração mesmo antes de existir alguma empresa.
    papel = PAPEL_ADMIN if eh_admin(user) else papel_ativo(request)
    secoes = []
    for secao in SECOES:
        itens = [
            dict(item)
            for item in secao["itens"]
            if not item.get("required_groups") or papel in item["required_groups"]
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
        "empresa": empresa.nome if empresa else "",
        "empresa_id": empresa.pk if empresa else None,
        "empresas": list(empresas_do_usuario(user).order_by("nome")),
    }


@register.filter
def iniciais(usuario) -> str:
    """Iniciais para o avatar: 'Maria Souza' -> 'MS'; sem nome, a 1ª letra do login."""
    nome = (getattr(usuario, "get_full_name", lambda: "")() or "").split()
    if nome:
        return (nome[0][0] + (nome[-1][0] if len(nome) > 1 else "")).upper()
    return (getattr(usuario, "username", "") or "?")[:1].upper()
