"""Empresa ativa da sessão e o papel do usuário nela.

Cada empresa tem dados e visões independentes. O acesso vem dos grupos: um
``AcessoEmpresa`` dá aos membros de um grupo um papel (Limited, Tech ou Master)
numa empresa. O grupo Admin e os superusuários veem todas as empresas, como Admin.
"""

from django.contrib import messages
from django.db.models import Count, QuerySet
from django.http import HttpResponseRedirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from commercial.screens.config.permissions import user_in_groups

from .models import PAPEIS, PAPEL_ADMIN, AcessoEmpresa, Empresa

SESSAO = "empresa_id"
ORDEM_PAPEIS = [papel for papel, _ in PAPEIS] + [PAPEL_ADMIN]


def eh_admin(user) -> bool:
    return user_in_groups(user, [PAPEL_ADMIN])


def empresas_do_usuario(user) -> QuerySet[Empresa]:
    if not getattr(user, "is_authenticated", False):
        return Empresa.objects.none()
    if eh_admin(user):
        return Empresa.objects.filter(ativa=True)
    return Empresa.objects.filter(ativa=True, acessos__grupo__in=user.groups.all()).distinct()


def papel(user, empresa: Empresa | None) -> str | None:
    """Maior papel do usuário na empresa; None se ele não tem acesso a ela."""
    if empresa is None or not getattr(user, "is_authenticated", False):
        return None
    if eh_admin(user):
        return PAPEL_ADMIN
    papeis = AcessoEmpresa.objects.filter(empresa=empresa, grupo__in=user.groups.all()).values_list("papel", flat=True)
    return max(papeis, key=ORDEM_PAPEIS.index, default=None)


def empresa_ativa(request) -> Empresa | None:
    """Empresa escolhida na sessão; sem escolha válida, a com mais propostas a que o usuário tem acesso."""
    if not hasattr(request, "_empresa_ativa"):
        disponiveis = empresas_do_usuario(request.user)
        escolhida = request.session.get(SESSAO)
        empresa = disponiveis.filter(pk=escolhida).first() if escolhida else None
        # Começa pela empresa com mais propostas (ou com SharePoint configurado), não pela primeira do alfabeto.
        padrao = disponiveis.annotate(qtd=Count("propostas", distinct=True)).order_by("-qtd", "-sharepoint_site", "nome")
        empresa = empresa or padrao.first()
        if empresa is not None and empresa.pk != escolhida:
            request.session[SESSAO] = empresa.pk
        request._empresa_ativa = empresa
    return request._empresa_ativa


def papel_ativo(request) -> str | None:
    if not hasattr(request, "_papel_ativo"):
        request._papel_ativo = papel(request.user, empresa_ativa(request))
    return request._papel_ativo


@require_POST
def trocar_empresa(request):
    """Troca a empresa da sessão e volta para a mesma tela (sem os filtros, que são da empresa anterior)."""
    empresa = empresas_do_usuario(request.user).filter(pk=request.POST.get("empresa") or None).first()
    if empresa is None:
        messages.error(request, "Você não tem acesso a esta empresa.")
    else:
        request.session[SESSAO] = empresa.pk
    destino = request.POST.get("next", "")
    if not url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        destino = "/app/"
    return HttpResponseRedirect(destino.split("?", 1)[0])
