"""Etapa 1: realm com as configurações do README_sso.md (1.1–1.7), clients dos apps e as roles de acesso."""
from typing import Any

from django import forms
from django.forms import formset_factory

from keycloak.automacao import realm as servico
from keycloak.automacao.web import api, com_realm, executar
from keycloak.models import Aplicacao


class RealmForm(forms.Form):
    SECOES = [("Realm", ["realm", "nome_exibicao"])]

    realm = forms.SlugField(
        label="Nome do realm", max_length=100,
        help_text="Minúsculas e hífen. Entra nas URLs (/realms/<nome>) e no KEYCLOAK_REALM dos apps. Não muda depois.",
    )
    nome_exibicao = forms.CharField(label="Nome na tela de login", max_length=100, required=False)

    def clean_realm(self) -> str:
        nome = self.cleaned_data["realm"]
        if not servico.NOME_VALIDO.match(nome):
            raise forms.ValidationError("Use só minúsculas, números e hífen.")
        if nome == "master":
            raise forms.ValidationError("O master é o realm do console; crie um realm para os apps.")
        return nome


class AppForm(forms.Form):
    client_id = forms.SlugField(label="Client ID", max_length=100, required=False, help_text="o KEYCLOAK_CLIENT_ID do app")
    nome = forms.CharField(label="Nome", max_length=100, required=False)
    url = forms.URLField(label="URL do app", required=False, assume_scheme="https")
    callback = forms.CharField(label="Callback", max_length=100, required=False, initial=servico.App.callback)

    def clean(self):
        dados = super().clean()
        if dados.get("client_id") and not dados.get("url"):
            self.add_error("url", "Informe a URL pública do app.")
        return dados


AppFormSet = formset_factory(AppForm, extra=1)


@com_realm(exige_realm=False)
def view(context, request, realm) -> dict[str, Any]:
    novo = request.GET.get("novo") == "1" or realm is None
    plano = None
    if request.method == "POST":
        form, apps = RealmForm(request.POST), AppFormSet(request.POST, prefix="apps")
        if form.is_valid() and apps.is_valid():
            nome = form.cleaned_data["realm"]
            lista = [
                servico.App(a["client_id"], a["nome"] or a["client_id"], a["url"], a["callback"] or servico.App.callback)
                for a in apps.cleaned_data if a.get("client_id")
            ]
            plano = executar(
                request, nome, Aplicacao.REALM,
                lambda simular: servico.aplicar(api(), nome, form.cleaned_data["nome_exibicao"], lista, simular),
            )
            if plano is not None and not plano.simular:
                request.session["realm"] = nome
                context["realm"] = nome
            novo = novo and not (plano and not plano.simular)
    elif novo:
        form, apps = RealmForm(), AppFormSet(prefix="apps")
    else:
        dados = servico.ler_realm(api(), realm) or {}
        form = RealmForm(initial={"realm": realm, "nome_exibicao": dados.get("displayName", "")})
        apps = AppFormSet(prefix="apps", initial=[vars(a) for a in servico.ler_apps(api(), realm)])

    if not novo:
        form.fields["realm"].widget.attrs["readonly"] = True
    context.update({"form": form, "apps": apps, "novo": novo, "plano": plano, "config": servico.CONFIG_REALM})
    return {"request": request, "context": context}
