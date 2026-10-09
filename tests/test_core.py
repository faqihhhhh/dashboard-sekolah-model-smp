import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_healthz_ok(client):
    response = client.get(reverse("core:healthz"))
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


def test_home_ok(client):
    response = client.get(reverse("core:home"))
    assert response.status_code == 200
    assert "Setup Fase 1 berhasil" in response.content.decode()
