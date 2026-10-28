from django import forms
from django.forms import inlineformset_factory

from commercial.propostas.models import Cliente, Contato


class ClienteForm(forms.ModelForm):
    SECOES = [
        ("Cliente", ["nome", "nome_fantasia", "documento", "segmento", "ativo"]),
        ("Contato e localização", ["email", "telefone", "cidade", "uf", "observacoes"]),
        ("SharePoint", ["nomes_sharepoint"]),
    ]
    # Campos com sugestões (valores já usados pela empresa).
    SUGESTOES = ["segmento", "cidade"]

    class Meta:
        model = Cliente
        fields = [
            "nome", "nome_fantasia", "documento", "segmento", "ativo", "email", "telefone", "cidade", "uf", "observacoes",
            "nomes_sharepoint",
        ]
        widgets = {"observacoes": forms.Textarea(attrs={"rows": 2}), "nomes_sharepoint": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, empresa, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.empresa = empresa
        for nome in self.SUGESTOES:
            self.fields[nome].widget.attrs["list"] = f"sugestoes-{nome}"

    def clean_documento(self) -> str:
        documento = self.cleaned_data["documento"].strip()
        repetido = Cliente.objects.filter(empresa=self.instance.empresa, documento=documento).exclude(pk=self.instance.pk)
        if documento and repetido.exists():
            raise forms.ValidationError(f"Já existe um cliente com este documento: {repetido.first()}.")
        return documento

    def clean_uf(self) -> str:
        return self.cleaned_data["uf"].strip().upper()


ContatosFormSet = inlineformset_factory(
    Cliente, Contato, fields=["nome", "cargo", "email", "telefone", "principal"], extra=1, can_delete=True
)
