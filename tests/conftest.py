import pytest

from apps.accounts.models import User

PASSWORD = "kata-sandi-uji-123"


@pytest.fixture
def make_user(db):
    def _make(role, email=None, **extra):
        return User.objects.create_user(
            email=email or f"{role}@example.com",
            password=PASSWORD,
            full_name=f"Uji {role}",
            role=role,
            **extra,
        )

    return _make


@pytest.fixture
def client_as(client, make_user):
    """client_as("admin") -> client yang sudah login sebagai Admin."""

    def _login(role):
        client.force_login(make_user(role))
        return client

    return _login
