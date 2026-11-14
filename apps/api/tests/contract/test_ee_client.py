"""Validación de la clave de cuenta de servicio, sin red ni claves reales (claves FALSAS de prueba)."""

import json

import pytest

from app.core.config import REPO_ROOT
from app.services.earth_engine.client import EarthEngineUnavailable, load_service_account_key

EMAIL = "earth-trend-backend@nasa-pizzia.iam.gserviceaccount.com"


def fake_key(path, **over):
    data = {"type": "service_account", "project_id": "nasa-pizzia", "client_email": EMAIL,
            "private_key": "-----BEGIN PRIVATE KEY-----\nFAKE-TEST-ONLY\n-----END PRIVATE KEY-----\n"}
    data.update(over)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_valid_key_outside_repo(tmp_path):
    assert load_service_account_key(str(fake_key(tmp_path / "k.json")), EMAIL, "nasa-pizzia") == EMAIL


def test_wrong_email_rejected(tmp_path):
    k = fake_key(tmp_path / "k.json", client_email="otra@nasa-pizzia.iam.gserviceaccount.com")
    with pytest.raises(EarthEngineUnavailable, match="se esperaba"):
        load_service_account_key(str(k), EMAIL, "nasa-pizzia")


def test_wrong_project_rejected(tmp_path):
    with pytest.raises(EarthEngineUnavailable, match="proyecto"):
        load_service_account_key(str(fake_key(tmp_path / "k.json", project_id="otro")), EMAIL, "nasa-pizzia")


def test_not_a_service_account_key(tmp_path):
    with pytest.raises(EarthEngineUnavailable, match="no es una clave"):
        load_service_account_key(str(fake_key(tmp_path / "k.json", type="authorized_user")), None, None)


def test_missing_file(tmp_path):
    with pytest.raises(EarthEngineUnavailable, match="no existe"):
        load_service_account_key(str(tmp_path / "nada.json"), None, None)


def test_key_inside_repo_rejected():
    inside = REPO_ROOT / ".cache" / "_test_key_inside_repo.json"
    inside.parent.mkdir(exist_ok=True)
    try:
        fake_key(inside)
        with pytest.raises(EarthEngineUnavailable, match="dentro del repositorio"):
            load_service_account_key(str(inside), EMAIL, "nasa-pizzia")
    finally:
        inside.unlink(missing_ok=True)
