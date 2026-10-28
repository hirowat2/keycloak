"""Etapa 3: provedor SAML do SSO corporativo (seção 2 do README_sso.md).

Mostra as URLs que o time do SSO precisa, cadastra o provedor a partir do
metadata e cria os mappers de e-mail, nome, sobrenome e username.
"""
from typing import Any

from django import forms

from keycloak.automacao import saml as servico
from keycloak.automacao.api import url_publica
from keycloak.automacao.web import api, com_realm, executar
from keycloak.models import Aplicacao


class ProvedorForm(forms.Form):
    SECOES = [
        ("Provedor", ["tipo", "alias", "nome_exibicao"]),
        ("Metadata do SSO", ["metadata_url", "metadata_xml"]),
        ("Login", ["nameid", "login_direto"]),
    ]

    tipo = forms.ChoiceField(label="SSO", choices=[(k, v["nome"]) for k, v in servico.PROVEDORES.items()],
                             help_text="Define os nomes dos atributos lidos nos mappers (seção 2.4).")
    alias = forms.SlugField(label="Alias", max_length=50, initial="entra",
                            help_text="Entra nas URLs do SSO e não pode ser trocado depois.")
    nome_exibicao = forms.CharField(label="Nome no botão", max_length=100, initial="conta corporativa",
                                    help_text='O Keycloak põe "Entrar com" na frente.')
    metadata_url = forms.URLField(label="URL de metadata", required=False, assume_scheme="https",
                                  help_text="No Entra: App Federation Metadata Url. O Keycloak baixa e acompanha a troca de certificado.")
    metadata_xml = forms.CharField(label="ou o XML de metadata", required=False, widget=forms.Textarea(attrs={"rows": 4}),
                                   help_text="Só se não houver URL (ex.: IdP metadata baixado do Google).")
    nameid = forms.ChoiceField(label="NameID policy format", choices=[("email", "Email (Entra, Google)"), ("persistent", "Persistent (ID fixo)")])
    login_direto = forms.BooleanField(label="Ir direto para o SSO, sem a tela do Keycloak (seção 2.6)", required=False)


def _inicial(cliente, realm: str, provedor: dict) -> dict:
    config = provedor.get("config", {})
    mappers = servico.mappers(cliente, realm, provedor["alias"])
    email = mappers.get("email", {}).get("config", {}).get("attribute.name", "")
    return {
        "tipo": "entra" if email.startswith(servico.CLAIMS_ENTRA) else "google",
        "alias": provedor["alias"],
        "nome_exibicao": provedor.get("displayName", ""),
        "metadata_url": config.get("metadataDescriptorUrl", ""),
        "nameid": "persistent" if config.get("nameIDPolicyFormat") == servico.NAMEID["persistent"] else "email",
        "login_direto": servico.login_direto_atual(cliente, realm) == provedor["alias"],
    }


@com_realm()
def view(context, request, realm) -> dict[str, Any]:
    cliente = api()
    provedores = servico.listar_provedores(cliente, realm)
    atual = next((p for p in provedores if p["alias"] == request.GET.get("alias")), None)
    if atual is None and provedores and request.GET.get("novo") != "1":
        atual = provedores[0]
    plano = None
    if request.method == "POST":
        form = ProvedorForm(request.POST)
        if form.is_valid():
            dados = servico.Provedor(**form.cleaned_data)
            plano = executar(request, realm, Aplicacao.SSO,
                             lambda simular: servico.aplicar_provedor(cliente, realm, url_publica(), dados, simular))
    else:
        form = ProvedorForm(initial=_inicial(cliente, realm, atual) if atual else None)
    if atual:
        form.fields["alias"].widget.attrs["readonly"] = True

    alias = (form["alias"].value() or "").strip()
    context.update(
        {
            "form": form,
            "plano": plano,
            "provedores": provedores,
            "atual": atual,
            "tipo": form["tipo"].value() or "entra",
            "urls": servico.urls_sp(url_publica(), realm, alias),
            "modelo": servico.urls_sp(url_publica(), realm, "__ALIAS__"),
            "atributos": servico.PROVEDORES,
        }
    )
    return {"request": request, "context": context}
