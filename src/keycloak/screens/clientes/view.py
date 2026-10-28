"""Clientes: cadastro com contatos e o histórico comercial de cada um."""
from typing import Any

from django.contrib import messages
from django.db import transaction
from django.db.models import Count, OuterRef, Q, Subquery, Sum
from django.shortcuts import redirect

from commercial.propostas.constantes import ETAPAS_ABERTAS, GANHA
from commercial.propostas.models import Cliente, Proposta
from commercial.propostas.web import GRUPOS_EDICAO, com_empresa, exigir, pode

from .forms import ClienteForm, ContatosFormSet

VISOES = [("ativos", "Ativos"), ("inativos", "Inativos"), ("todos", "Todos")]


def _buscar(empresa, pk) -> Cliente | None:
    pk = str(pk or "")
    return Cliente.objects.filter(empresa=empresa, pk=pk).first() if pk.isdigit() else None


def _formularios(request, empresa, cliente: Cliente):
    dados = request.POST if request.method == "POST" else None
    return (
        ClienteForm(dados, instance=cliente, empresa=empresa),
        ContatosFormSet(dados, instance=cliente, prefix="contatos"),
    )


def _post(request, empresa):
    """Salvar, inativar ou reativar. Devolve o redirect ou os formulários com erro."""
    if not exigir(request, GRUPOS_EDICAO):
        return redirect(request.get_full_path()), None
    acao = request.POST.get("action", "")
    pk = request.POST.get("id")
    cliente = _buscar(empresa, pk) if pk else Cliente(empresa=empresa)
    if cliente is None:
        messages.error(request, "Cliente não encontrado.")
        return redirect(request.path), None
    if acao in ("inativar", "reativar") and cliente.pk:
        cliente.ativo = acao == "reativar"
        cliente.save(update_fields=["ativo"])
        messages.success(request, f"{cliente} {'reativado' if cliente.ativo else 'inativado'}.")
        return redirect(request.path), None
    form, contatos = _formularios(request, empresa, cliente)
    if form.is_valid() and contatos.is_valid():
        with transaction.atomic():
            cliente = form.save()
            contatos.instance = cliente
            contatos.save()
        messages.success(request, f"Cliente {cliente} salvo.")
        return redirect(request.path), None
    return None, (form, contatos)


def _sugestoes(empresa) -> dict[str, list[str]]:
    clientes = Cliente.objects.filter(empresa=empresa)
    return {
        campo: list(clientes.exclude(**{campo: ""}).order_by(campo).values_list(campo, flat=True).distinct())
        for campo in ClienteForm.SUGESTOES
    }


def _clientes(empresa, busca: str, ver: str):
    """Clientes do filtro, com a quantidade de propostas (abertas e no total) e o valor ganho."""
    clientes = Cliente.objects.filter(empresa=empresa)
    if ver == "ativos":
        clientes = clientes.filter(ativo=True)
    elif ver == "inativos":
        clientes = clientes.filter(ativo=False)
    if busca:
        clientes = clientes.filter(
            Q(nome__icontains=busca) | Q(nome_fantasia__icontains=busca) | Q(documento__icontains=busca)
            | Q(cidade__icontains=busca) | Q(contatos__nome__icontains=busca)
        ).distinct()
    return clientes.annotate(
        qtd_propostas=Count("propostas", distinct=True),
        abertas=Count("propostas", filter=Q(propostas__etapa__in=ETAPAS_ABERTAS), distinct=True),
        # Subconsulta: a busca por contato junta linhas e somaria a mesma proposta mais de uma vez.
        ganho=Subquery(
            Proposta.objects.filter(cliente=OuterRef("pk"), etapa=GANHA)
            .values("cliente").annotate(total=Sum("valor_total")).values("total")
        ),
    ).prefetch_related("contatos")


@com_empresa
def view(context, request, empresa) -> dict[str, Any]:
    pode_editar = pode(request, GRUPOS_EDICAO)
    forms = None
    if request.method == "POST":
        resposta, forms = _post(request, empresa)
        if resposta is not None:
            return resposta
    elif pode_editar and (request.GET.get("novo") or request.GET.get("editar")):
        cliente = _buscar(empresa, request.GET.get("editar")) if request.GET.get("editar") else Cliente(empresa=empresa)
        if cliente is None:
            messages.error(request, "Cliente não encontrado.")
            return redirect(request.path)
        forms = _formularios(request, empresa, cliente)

    busca = request.GET.get("q", "").strip()
    ver = request.GET.get("ver", "ativos")
    context.update(
        {
            "clientes": _clientes(empresa, busca, ver),
            "busca": busca,
            "ver": ver,
            "visoes": VISOES,
            "pode_editar": pode_editar,
            "form": forms[0] if forms else None,
            "contatos": forms[1] if forms else None,
            "editando": forms[0].instance if forms and forms[0].instance.pk else None,
            "sugestoes": _sugestoes(empresa) if forms else {},
        }
    )
    return {"request": request, "context": context}
