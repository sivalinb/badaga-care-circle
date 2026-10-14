from dataclasses import dataclass, field
from typing import Literal
from pydantic import BaseModel, Field


@dataclass(frozen=True)
class Actor:
    role: Literal["participant", "volunteer", "clinician"]
    household_id: str


@dataclass
class SafetyDecision:
    route: str = "education"
    reason: str = "general_question"
    message_key: str = ""
    source_ids: list[str] = field(default_factory=list)


@dataclass
class SearchHit:
    doc: dict
    score: float
    lexical_score: float
    semantic_score: float = 0.0


@dataclass
class Answer:
    route: str
    text: str
    source_ids: list[str]
    trace_id: str
    provider: str
    status: str
    review_id: str | None = None
    latency_ms: float = 0.0


class CitedSentence(BaseModel):
    text: str = Field(max_length=500)
    source_ids: list[str]


class EducationDraft(BaseModel):
    sentences: list[CitedSentence] = Field(min_length=1, max_length=5)
    next_step: str = Field(max_length=300)
