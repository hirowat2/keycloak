from decimal import Decimal

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

@register.filter(name="brl")
def brl(value):
    """Formata um número como moeda brasileira: 1234.5 -> 'R$ 1.234,50'."""
    if value is None or value == "":
        return "—"
    numero = Decimal(str(value))
    texto = f"{abs(numero):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"-R$ {texto}" if numero < 0 else f"R$ {texto}"


def _br(numero: Decimal, casas: int) -> str:
    return f"{numero:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


@register.filter(name="pct")
def pct(value, casas=1):
    """12.3 -> '12,3%' ({{ v|pct:2 }} -> '12,30%'); None -> '—'."""
    if value is None or value == "":
        return "—"
    return f"{_br(Decimal(str(value)), int(casas))}%"


@register.filter(name="indice")
def indice(value, casas=2):
    """Número com ``casas`` decimais (padrão 2): 1.5 -> '1,50'; None -> '—'."""
    if value is None or value == "":
        return "—"
    return _br(Decimal(str(value)), int(casas))


@register.filter(name="sinal")
def sinal(value):
    """Classe CSS para destacar valores negativos."""
    try:
        return "ct-neg" if Decimal(str(value)) < 0 else ""
    except Exception:
        return ""


@register.filter(name="brl_curto")
def brl_curto(value):
    """Valor abreviado para rótulos de gráfico: 12300 -> 'R$ 12 mil'."""
    from commercial.propostas.valores import valor_curto

    if value is None or value == "":
        return "—"
    return valor_curto(Decimal(str(value)))


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
