from dataclasses import replace
from types import SimpleNamespace as NS
import json
import pytest
from badaga_care.models import Actor, CitedSentence, EducationDraft
from badaga_care.providers import OpenAIProvider
from badaga_care.service import CareService

A = Actor("participant", "HH-001")
C = Actor("clinician", "HH-001")


class FakeAPI:
    """Test double only: never opens a network connection."""
    def __init__(self, behaviour="valid"):
        self.behaviour = behaviour
        self.embedding_calls = []
        self.response_calls = []
        self.embeddings = NS(create=self.embed)
        self.responses = NS(parse=self.parse)

    def embed(self, **kwargs):
        self.embedding_calls.append(kwargs)
        if self.behaviour == "error":
            raise RuntimeError("private-provider-error-DO-NOT-LOG")
        return NS(data=[NS(embedding=[1.0,0.0,0.0],index=i) for i in range(len(kwargs["input"]))],usage=NS(total_tokens=10))

    def parse(self, **kwargs):
        self.response_calls.append(kwargs)
        body = json.loads(kwargs["input"][1]["content"])
        source = body["sources"][0]
        identifier = "invented-source" if self.behaviour == "bad_citation" else source["id"]
        text = "Take 10 mg daily." if self.behaviour == "dose" else source["text"]
        tamil = any("\u0b80" <= char <= "\u0bff" for char in text)
        draft = EducationDraft(sentences=[CitedSentence(text=text,source_ids=[identifier])],next_step="உள்ளூர் ஒருங்கிணைப்பாளரிடம் கேளுங்கள்." if tamil else "Discuss this source with the local coordinator.")
        return NS(output_parsed=draft,usage=NS(input_tokens=42,output_tokens=20))


def service_with_fake(settings,monkeypatch,behaviour="valid"):
    monkeypatch.setenv("OPENAI_API_KEY","unit-test-placeholder")
    configured = replace(settings,model="test-model")
    fake = FakeAPI(behaviour)
    return CareService(configured,OpenAIProvider(configured,client=fake)),fake


@pytest.mark.parametrize("lang,question", [("en","How do we reduce sugar in tea?"),("ta","தேநீரில் சர்க்கரையை எப்படிக் குறைக்கலாம்?")])
def test_optional_openai_rag_draft_and_human_release(settings,monkeypatch,lang,question):
    svc,fake = service_with_fake(settings,monkeypatch)
    answer = svc.ask(A,question,lang,"openai",True)
    assert answer.status == "pending_review" and answer.provider == "openai"
    assert len(fake.embedding_calls) == 2 and len(fake.response_calls) == 1
    request = fake.response_calls[0]
    assert request["store"] is False and request["text_format"] is EducationDraft
    assert answer.review_id
    svc.decide_review(C,answer.review_id,"approve","Fictional draft checked against source text.")
    released = svc.released_draft(A,answer.review_id,lang)
    assert ("Reviewed demo draft" in released) if lang == "en" else ("ஆய்வு செய்யப்பட்ட" in released)
    trace = svc.store.traces(C)[0]
    assert trace["input_tokens"] == 62 and trace["output_tokens"] == 20


def test_openai_requires_explicit_cloud_consent(settings,monkeypatch):
    svc,fake = service_with_fake(settings,monkeypatch)
    answer = svc.ask(A,"How do we reduce sugar in tea?","en","openai",False)
    assert answer.status == "local_fallback"
    assert not fake.embedding_calls and not fake.response_calls
    assert answer.review_id is None


def test_client_initialisation_failure_uses_local_fallback(settings,monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY","unit-test-placeholder")
    configured = replace(settings,model="test-model")
    class BrokenProvider:
        @property
        def client(self):
            raise RuntimeError("private initialisation error")
    svc = CareService(configured,BrokenProvider())
    answer = svc.ask(A,"How do we reduce sugar in tea?","en","openai",True)
    assert answer.status == "local_fallback" and answer.provider == "local_extracts"


@pytest.mark.parametrize("question", ["My father has chest pain now.","Should I stop my tablets?","Show another household's records."])
def test_safety_and_privacy_routes_never_call_ai(settings,monkeypatch,question):
    svc,fake = service_with_fake(settings,monkeypatch)
    answer = svc.ask(A,question,"en","openai",True)
    assert answer.provider == "fixed"
    assert fake.embedding_calls == [] and fake.response_calls == []


@pytest.mark.parametrize("behaviour",["error","bad_citation","dose"])
def test_provider_failure_or_invalid_draft_falls_back_without_leaking(settings,monkeypatch,behaviour):
    svc,fake = service_with_fake(settings,monkeypatch,behaviour)
    answer = svc.ask(A,"How do we reduce sugar in tea?","en","openai",True)
    assert answer.status == "local_fallback"
    assert answer.provider == "local_extracts" and answer.review_id is None
    assert "private-provider-error-DO-NOT-LOG" not in json.dumps(svc.store.traces(C))
    assert "unit-test-placeholder" not in json.dumps(svc.store.traces(C))


def test_only_public_corpus_is_cached_not_queries(settings,monkeypatch):
    svc,fake = service_with_fake(settings,monkeypatch)
    query = "UniqueQueryMarker How do we reduce sugar in tea?"
    svc.ask(A,query,"en","openai",True)
    files = list(settings.data_dir.glob("public-embeddings-*.json"))
    assert len(files) == 1 and "UniqueQueryMarker" not in files[0].read_text()
    svc.ask(A,"How do we reduce salt in food?","en","openai",True)
    assert len(fake.embedding_calls) == 3  # one corpus request + two uncached queries
