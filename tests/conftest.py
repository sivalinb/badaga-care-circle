from datetime import date
import pytest
from badaga_care.config import Settings
from badaga_care.service import CareService


@pytest.fixture
def settings(tmp_path, monkeypatch):
    monkeypatch.setattr(Settings, "today", lambda self: date(2026, 10, 14))
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    return Settings(data_dir=tmp_path)


@pytest.fixture
def svc(settings):
    return CareService(settings)
