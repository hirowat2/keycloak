from django import template

register = template.Library()


@register.simple_tag
def media_url(caminho):
    """/media/<caminho> com a data do arquivo (?v=): o navegador busca de novo quando o arquivo muda."""
    import os

    from django.conf import settings

    try:
        versao = int(os.path.getmtime(os.path.join(settings.MEDIA_ROOT, caminho)))
    except OSError:
        return f"{settings.MEDIA_URL}{caminho}"
    return f"{settings.MEDIA_URL}{caminho}?v={versao}"


@register.filter
def attr(obj, attr_name):
    if isinstance(obj, dict):
        return obj.get(attr_name, None)
    return getattr(obj, attr_name, None)


@register.filter(name="chave")
def chave(dicionario, nome):
    """Valor de um dicionário no template: {{ slots|chave:item.nome }}."""
    return dicionario.get(nome) if isinstance(dicionario, dict) else None


@register.filter(name="campo")
def campo(form, nome):
    """Campo de um formulário pelo nome: {{ form|campo:"valor" }} (para montar seções)."""
    return form[nome] if nome in form.fields else None


@register.filter(name="nome_usuario")
def nome_usuario(usuario, vazio="—"):
    """Nome completo do usuário, o login se não houver nome, ou ``vazio`` sem usuário."""
    if not usuario:
        return vazio
    return usuario.get_full_name() or usuario.username


@register.filter(name="situacao_css")
def situacao_css(situacao):
    """Badge de um passo do plano: criar/atualizar em destaque, remover em alerta."""
    return {"criar": "ct-badge--ok", "atualizar": "ct-badge--ok", "remover": "ct-badge--alerta"}.get(situacao, "")
