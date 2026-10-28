"""PHARMA / MBRLPROC Sistemas (site actionpharma), Action Stat (criada por configurar_empresas) e sem a Estat Analytics."""

from django.db import migrations

SITE = "https://estatcamp.sharepoint.com/sites"


def reorganizar(apps, schema_editor):
    Empresa = apps.get_model("commercial", "Empresa")
    mbrl = Empresa.objects.filter(slug="mbrlproc-sistemas-ltda").first()
    if mbrl is not None:
        mbrl.nome = "PHARMA / MBRLPROC Sistemas"
        mbrl.razao_social = mbrl.razao_social or "MBRLPROC SISTEMAS LTDA"
        campos = ["nome", "razao_social"]
        if not mbrl.sharepoint_site:
            mbrl.sharepoint_site = f"{SITE}/actionpharma"
            mbrl.sharepoint_pasta = "02 - Propostas Clientes"
            mbrl.sharepoint_controle = "04 - Controle de Propostas"
            mbrl.sharepoint_contratos = "Contratos de Clientes\nCONTRATOS 2022\n01 - Contrato da Parceria"
            mbrl.sharepoint_controle_contratos = "Contratos de Clientes/Controle de Contratos.xlsx"
            mbrl.sharepoint_desde = 2021
            campos += ["sharepoint_site", "sharepoint_pasta", "sharepoint_controle", "sharepoint_contratos",
                       "sharepoint_controle_contratos", "sharepoint_desde"]
        mbrl.save(update_fields=campos)

    analytics = Empresa.objects.filter(slug="estat-analytics").first()
    if analytics is not None:
        tem_dados = any(
            getattr(analytics, relacao).exists()
            for relacao in ("propostas", "clientes", "catalogo", "acervo", "documentos", "contratos")
        )
        if tem_dados:  # não apaga dados: só tira das listas
            analytics.ativa = False
            analytics.save(update_fields=["ativa"])
        else:
            analytics.acessos.all().delete()
            analytics.sincronizacoes.all().delete()
            analytics.delete()


class Migration(migrations.Migration):
    dependencies = [("commercial", "0006_carteira_contratos")]
    operations = [migrations.RunPython(reorganizar, migrations.RunPython.noop)]
