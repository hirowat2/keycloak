"""Etapa 4: um mapper por grupo, do grupo do SSO para o grupo do Keycloak (seção 4.4 do README_sso.md)."""
from typing import Any

from django import forms
from django.forms import formset_factory

from keycloak.automacao import saml as servico
from keycloak.automacao.grupos import ler_grupos
from keycloak.automacao.web import api, com_realm, executar
from keycloak.models import Aplicacao


class MapeamentoForm(forms.Form):
    grupo = forms.CharField(widget=forms.HiddenInput)
    ativo = forms.BooleanField(label="Mapear", required=False)
    valor = forms.CharField(label="Valor no SSO", max_length=255, required=False)
    chave = forms.CharField(label="Atributo (Key)", max_length=255, required=False)

    def clean(self):
        dados = super().clean()
        if dados.get("ativo") and not dados.get("valor"):
            self.add_error("valor", "Informe o nome (ou o GUID) do grupo no SSO.")
        if dados.get("ativo") and not dados.get("chave"):
            self.add_error("chave", "Informe o nome do atributo de grupos.")
        return dados


MapeamentoFormSet = formset_factory(MapeamentoForm, extra=0)


@com_realm()
def view(context, request, realm) -> dict[str, Any]:
    cliente = api()
    provedores = servico.listar_provedores(cliente, realm)
    alias = request.GET.get("alias") or (provedores[0]["alias"] if provedores else "")
    if alias not in {p["alias"] for p in provedores}:
        context.update({"provedores": provedores, "formset": None})
        return {"request": request, "context": context}

    grupos = ler_grupos(cliente, realm)
    plano = None
    if request.method == "POST":
        formset = MapeamentoFormSet(request.POST, prefix="map")
        if formset.is_valid():
            itens = [
                servico.MapeamentoGrupo(f["grupo"], f["valor"].strip(), f["chave"].strip() or "groups", f["ativo"])
                for f in formset.cleaned_data if f["grupo"] in grupos
            ]
            plano = executar(request, realm, Aplicacao.MAPEAMENTO,
                             lambda simular: servico.aplicar_mapeamento(cliente, realm, alias, itens, simular))
    else:
        mapeados = servico.ler_mapeamento(cliente, realm, alias)
        chave = request.GET.get("chave") or next((m.chave for m in mapeados.values()), "groups")
        formset = MapeamentoFormSet(
            prefix="map",
            initial=[
                {"grupo": g, "ativo": g in mapeados or not mapeados,
                 "valor": mapeados[g].valor if g in mapeados else g,
                 "chave": mapeados[g].chave if g in mapeados else chave}
                for g in grupos
            ],
        )
    context.update(
        {
            "provedores": provedores,
            "alias": alias,
            "formset": formset,
            "grupos": grupos,
            "plano": plano,
            "chave_longa": servico.CHAVE_GRUPOS_ENTRA_LONGA,
        }
    )
    return {"request": request, "context": context}
