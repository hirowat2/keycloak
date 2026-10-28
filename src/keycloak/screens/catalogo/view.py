"""Produtos e serviços: o catálogo com preço de tabela, referência dos descontos das propostas."""
from typing import Any

from django import forms
from django.contrib import messages
from django.db.models import Count, Q
from django.shortcuts import redirect

from commercial.propostas.constantes import TIPOS_ITEM
from commercial.propostas.models import ItemCatalogo
from commercial.propostas.web import GRUPOS_GESTAO, CampoValor, com_empresa, exigir, pode


class ItemCatalogoForm(forms.ModelForm):
    SECOES = [("Item", ["codigo", "nome", "tipo", "unidade", "preco", "ativo", "descricao"])]

    class Meta:
        model = ItemCatalogo
        fields = ["codigo", "nome", "tipo", "unidade", "preco", "ativo", "descricao"]
        field_classes = {"preco": CampoValor}
        widgets = {"descricao": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, empresa, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.empresa = empresa

    def clean_codigo(self) -> str:
        codigo = self.cleaned_data["codigo"].strip()
        repetido = ItemCatalogo.objects.filter(empresa=self.instance.empresa, codigo=codigo).exclude(pk=self.instance.pk)
        if codigo and repetido.exists():
            raise forms.ValidationError("Já existe um item com este código.")
        return codigo


def _buscar(empresa, pk) -> ItemCatalogo | None:
    pk = str(pk or "")
    return ItemCatalogo.objects.filter(empresa=empresa, pk=pk).first() if pk.isdigit() else None


def _post(request, empresa):
    if not exigir(request, GRUPOS_GESTAO):
        return redirect(request.get_full_path()), None
    pk = request.POST.get("id")
    item = _buscar(empresa, pk) if pk else ItemCatalogo(empresa=empresa)
    if item is None:
        messages.error(request, "Item não encontrado.")
        return redirect(request.path), None
    form = ItemCatalogoForm(request.POST, instance=item, empresa=empresa)
    if form.is_valid():
        item = form.save()
        messages.success(request, f"{item} salvo. Propostas já feitas mantêm o preço de tabela da época.")
        return redirect(request.path), None
    return None, form


@com_empresa
def view(context, request, empresa) -> dict[str, Any]:
    pode_editar = pode(request, GRUPOS_GESTAO)
    form = None
    if request.method == "POST":
        resposta, form = _post(request, empresa)
        if resposta is not None:
            return resposta
    elif pode_editar and (request.GET.get("novo") or request.GET.get("editar")):
        item = _buscar(empresa, request.GET.get("editar")) if request.GET.get("editar") else ItemCatalogo(empresa=empresa)
        if item is None:
            messages.error(request, "Item não encontrado.")
            return redirect(request.path)
        form = ItemCatalogoForm(instance=item, empresa=empresa)

    itens = ItemCatalogo.objects.filter(empresa=empresa).annotate(usos=Count("itens_proposta"))
    tipo = request.GET.get("tipo", "")
    if tipo in dict(TIPOS_ITEM):
        itens = itens.filter(tipo=tipo)
    if request.GET.get("inativos") != "1":
        itens = itens.filter(ativo=True)
    busca = request.GET.get("q", "").strip()
    if busca:
        itens = itens.filter(Q(nome__icontains=busca) | Q(codigo__icontains=busca) | Q(descricao__icontains=busca))

    context.update(
        {
            "itens": itens,
            "tipos": TIPOS_ITEM,
            "tipo": tipo,
            "busca": busca,
            "inativos": request.GET.get("inativos") == "1",
            "form": form,
            "editando": form.instance if form is not None and form.instance.pk else None,
            "pode_editar": pode_editar,
            "desconto_maximo": empresa.desconto_maximo,
        }
    )
    return {"request": request, "context": context}
