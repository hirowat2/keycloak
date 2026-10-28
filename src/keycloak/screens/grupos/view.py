"""Etapa 2: grupos e as roles de realm de cada um (seções 3.1 e 3.2 do README_sso.md)."""
from typing import Any

from django import forms
from django.forms import formset_factory

from keycloak.automacao import grupos as servico
from keycloak.automacao.realm import clients_dos_apps
from keycloak.automacao.web import api, com_realm, executar
from keycloak.models import Aplicacao


class GrupoForm(forms.Form):
    nome = forms.CharField(label="Grupo", max_length=255, required=False)
    roles = forms.MultipleChoiceField(label="Roles", required=False, widget=forms.CheckboxSelectMultiple)

    def __init__(self, *args, roles: list[str], **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["roles"].choices = [(r, r) for r in roles]

    def clean_nome(self) -> str:
        nome = self.cleaned_data["nome"].strip()
        if "/" in nome:
            raise forms.ValidationError("Sem barra: ela separa subgrupos. Use uma estrutura plana.")
        return nome


GrupoFormSet = formset_factory(GrupoForm, extra=2)


@com_realm()
def view(context, request, realm) -> dict[str, Any]:
    cliente = api()
    roles = servico.roles_do_realm(cliente, realm)
    plano = None
    if request.method == "POST":
        formset = GrupoFormSet(request.POST, prefix="grupos", form_kwargs={"roles": roles})
        if formset.is_valid():
            desejado = {g["nome"]: g["roles"] for g in formset.cleaned_data if g.get("nome")}
            plano = executar(request, realm, Aplicacao.GRUPOS, lambda simular: servico.aplicar(cliente, realm, desejado, simular))
    else:
        atuais = servico.ler_grupos(cliente, realm)
        sugestao = request.GET.get("sugestao") == "1" or not atuais
        if sugestao:
            apps = [c["clientId"] for c in clients_dos_apps(cliente, realm) if c["clientId"] in roles]
            atuais = {**servico.estrutura_sugerida(realm, apps), **atuais}
        context["sugestao"] = sugestao
        formset = GrupoFormSet(
            prefix="grupos", form_kwargs={"roles": roles},
            initial=[{"nome": nome, "roles": r} for nome, r in atuais.items()],
        )
    context.update({"formset": formset, "roles": roles, "plano": plano})
    return {"request": request, "context": context}
