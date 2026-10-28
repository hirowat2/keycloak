"""/media/ com DEBUG desligado: layout público, arquivos enviados só com login."""

import pytest
from django.contrib.auth.models import User
from django.test import Client


@pytest.fixture
def media(tmp_path, settings):
    settings.DEBUG = False
    settings.MEDIA_ROOT = str(tmp_path)
    (tmp_path / "css").mkdir()
    (tmp_path / "css" / "app.css").write_text("body{}")
    (tmp_path / "logo.png").write_bytes(b"png")
    (tmp_path / "anexos").mkdir()
    (tmp_path / "anexos" / "proposta.pdf").write_bytes(b"%PDF")
    (tmp_path.parent / "segredo.txt").write_text("nao")
    return tmp_path


@pytest.mark.django_db
def test_layout_e_publico_e_relatorios_exigem_login(media) -> None:
    anonimo = Client()
    assert anonimo.get("/media/css/app.css").status_code == 200
    assert anonimo.get("/media/logo.png").status_code == 200
    resposta = anonimo.get("/media/anexos/proposta.pdf")
    assert resposta.status_code == 302 and resposta["Location"].startswith("/login?next=")

    logado = Client()
    logado.force_login(User.objects.create_user("u", "hiro@estatcamp.com.br"))
    assert logado.get("/media/anexos/proposta.pdf").status_code == 200
    assert logado.get("/media/anexos/nao-existe.pdf").status_code == 404
    assert logado.get("/media/../segredo.txt").status_code in (400, 404)
