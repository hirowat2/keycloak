"""Azure AD dos realms: os provedores SAML já ligados ao Azure e o que ajustar depois de trocar de host.

1. Inventário de todos os realms: tenant, Entity ID, assinatura e mappers.
2. Para o provedor escolhido (do realm ativo): os valores que o app do Azure precisa ter,
   a comparação com o que está lá (colado da tela do Azure) e a ordem para trocar sem
   derrubar o login.
3. Ajuste do lado do Keycloak (simular → aplicar): Entity ID no host atual e, com o ID do
   Aplicativo, o certificado do app e a validação da assinatura.
"""
from typing import Any

from django import forms

from keycloak.automacao import azure as servico
from keycloak.automacao.api import url_publica
from keycloak.automacao.web import api, com_realm, executar, realms_disponiveis
from keycloak.models import Aplicacao


class AjusteForm(forms.Form):
    alias = forms.CharField(widget=forms.HiddenInput)
    trocar_entity = forms.BooleanField(label="Trocar o Entity ID para o host atual", required=False, initial=True)
    app_id = forms.CharField(label="ID do Aplicativo no Azure", required=False, max_length=36,
                             help_text="Aplicativos empresariais → o app → Propriedades → ID do Aplicativo. "
                                       "Com ele, o Keycloak lê o certificado do app e passa a validar a assinatura.")


@com_realm(exige_realm=False)
def view(context, request, realm) -> dict[str, Any]:
    cliente = api()
    host = url_publica()
    itens = servico.inventario(cliente, host, realms_disponiveis())
    alias = request.POST.get("alias") or request.GET.get("alias") or ""
    item = next((i for i in itens if i["realm"] == realm and i["alias"] == alias), None)
    if item is None and alias == "":
        item = next((i for i in itens if i["realm"] == realm), None)

    plano = None
    form = AjusteForm(initial={"alias": item["alias"]} if item else None)
    if request.method == "POST" and item:
        form = AjusteForm(request.POST)
        if form.is_valid():
            dados = form.cleaned_data
            plano = executar(request, realm, Aplicacao.SSO, lambda simular: servico.aplicar(
                cliente, realm, dados["alias"], host, dados["app_id"].strip(), dados["trocar_entity"], simular))
            if plano and not plano.simular:
                itens = servico.inventario(cliente, host, realms_disponiveis())
                item = next((i for i in itens if i["realm"] == realm and i["alias"] == dados["alias"]), item)

    identificador = request.GET.get("identificador", "")
    resposta = request.GET.get("resposta", "")
    context.update(
        {
            "itens": itens,
            "item": item,
            "host": host,
            "form": form,
            "plano": plano,
            "identificador": identificador,
            "resposta": resposta,
            "comparacao": servico.comparar(item, identificador, resposta) if item else [],
            "com_problema": sum(1 for i in itens if i["problemas"]),
        }
    )
    return {"request": request, "context": context}
