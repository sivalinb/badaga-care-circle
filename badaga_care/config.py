from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import os

ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    data_dir: Path = ROOT / "var"
    knowledge_path: Path = ROOT / "data" / "knowledge.json"
    timezone: str = "America/Denver"
    model: str = ""
    embedding_model: str = "text-embedding-3-small"
    api_timeout: float = 20.0
    mode: str = "demo"

    @classmethod
    def from_env(cls):
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env", override=False)
        settings = cls(
            data_dir=Path(os.getenv("CARE_DATA_DIR", str(ROOT / "var"))).resolve(),
            timezone=os.getenv("CARE_TIMEZONE", "America/Denver"),
            model=os.getenv("OPENAI_MODEL", ""),
            embedding_model=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
            mode=os.getenv("CARE_MODE", "demo"),
        )
        if settings.mode != "demo":
            raise RuntimeError("This release supports fictional demo data only. See ROADMAP.md for pilot release gates.")
        ZoneInfo(settings.timezone)
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        return settings

    def today(self):
        return datetime.now(ZoneInfo(self.timezone)).date()

    @property
    def openai_available(self):
        return bool(os.getenv("OPENAI_API_KEY") and self.model)
