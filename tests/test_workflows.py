from datetime import date
import json
import pytest
from badaga_care.evals import run_evals
from badaga_care.i18n import TEXT, tr
from badaga_care.models import Actor
from badaga_care.safety import assess, bp_from_text, validate_bp

A = Actor("participant", "HH-001")
B = Actor("participant", "HH-002")
V = Actor("volunteer", "HH-001")
C = Actor("clinician", "HH-001")


def test_regression_suite(settings):
    report = run_evals(settings)
    assert report["passed"] == report["total"], [r for r in report["results"] if not r["passed"]]
    assert report["critical_failures"] == []
    assert report["clinical_release_allowed"] is False


def test_off_topic_question_with_generic_verb_has_no_evidence(svc):
    answer = svc.ask(A, "How does quantum computing work?")
    assert answer.route == "abstain"
    assert answer.source_ids == []
    assert answer.text == tr("no_source")


@pytest.mark.parametrize("query", [
    "எனக்கு இப்போது மார்பில் அழுத்தமும் மூச்சுத்திணறலும் உள்ளது.",
    "என் அப்பாவுக்கு மூச்சு திணறல் உள்ளது.",
    "என் அம்மாவுக்கு மார்பு வலி உள்ளது.",
    "My dad has chest tightness right now.",
    "My mother cannot breathe.",
])
def test_additional_emergency_phrasings(query):
    assert assess(query).route == "emergency"


@pytest.mark.parametrize("top,bottom,valid", [(148,94,True),(120,80,True),(188,125,True),(90,100,False),(0,0,False),(140.5,90,False),(None,90,False),(400,250,False)])
def test_measurement_validation(top, bottom, valid):
    assert validate_bp(top,bottom) is valid


def test_tamil_digit_normalisation():
    assert bp_from_text("ரத்த அழுத்தம் ௧௮௮/௧௨௨") == (188,122)


def test_emergency_bypasses_persistence_and_confirmation(svc):
    text, identifier = svc.checkin(A, "A1", None, None, False, ["chest"], False, "en")
    assert "108" in text and identifier is None
    assert svc.store.checkins(A, "HH-001") == []
    assert svc.store.reviews(C) == []


def test_severe_bp_notice_before_confirmation(svc):
    text, identifier = svc.checkin(A, "A1", 188,122,False,[],False,"en")
    assert "very high" in text and "Confirm" in text and identifier is None


def test_clinical_followup_closes_checkin(svc):
    _, identifier = svc.checkin(A,"A1",148,94,True,[],True,"ta")
    row = svc.store.reviews(C)[0]
    svc.decide_review(C,row["id"],"followup","A fictional clinic review was arranged.")
    assert svc.store.checkins(A,"HH-001")[0]["status"] == "pending"
    svc.decide_review(C,row["id"],"close","Fictional follow-up completed and explained.")
    assert svc.store.checkins(A,"HH-001")[0]["status"] == "completed"
    assert svc.store.checkins(B,"HH-002") == []


def test_consent_is_required_for_checkin(svc):
    text, identifier = svc.checkin(A,"A1",148,94,True,[],False,"en")
    assert "Consent" in text and identifier is None


def test_checkin_and_review_creation_are_atomic(svc,monkeypatch):
    def fail(*args,**kwargs):
        raise RuntimeError("fixture failure")
    monkeypatch.setattr(svc.store,"_insert_review",fail)
    with pytest.raises(RuntimeError):
        svc.checkin(A,"A1",148,94,True,[],True,"en")
    assert svc.store.checkins(A,"HH-001") == []
    assert svc.store.query("SELECT * FROM audits") == []


def test_review_request_is_opt_in(svc):
    svc.ask(A,"Can I stop my tablets?",request_review=False)
    assert svc.store.reviews(C) == []
    answer = svc.ask(A,"Can I stop my tablets?",request_review=True)
    assert answer.review_id and len(svc.store.reviews(C)) == 1


def test_household_isolation_and_volunteer_limits(svc):
    with pytest.raises(PermissionError):
        svc.store.checkins(A,"HH-002")
    with pytest.raises(PermissionError):
        svc.store.backup(V,"HH-001")
    with pytest.raises(PermissionError):
        svc.store.reviews(A)
    with pytest.raises(PermissionError):
        svc.checkin(A,"B1",148,94,True,[],True,"en")
    with pytest.raises(PermissionError):
        svc.store.add_task(A,"HH-002","elder","B1","2026-10-20")
    with pytest.raises(PermissionError):
        svc.checkin(V,"A1",148,94,True,[],True,"en")


def test_task_handover_and_completion(svc):
    identifier = svc.add_task(A,"elder","A2","2026-10-20",True)
    with pytest.raises(ValueError,match="task_transition"):
        svc.store.update_task(A,"HH-001",identifier,"completed")
    svc.store.update_task(V,"HH-001",identifier,"accepted")
    svc.store.update_task(A,"HH-001",identifier,"completed")
    assert svc.store.counts()["tasks"] == 1
    assert svc.store.tasks(B,"HH-002") == []
    with pytest.raises(ValueError,match="not_found"):
        svc.store.update_task(B,"HH-002",identifier,"accepted")


@pytest.mark.parametrize("due", ["2026-01-01","tomorrow","2026-99-99"])
def test_invalid_task_dates(svc,due):
    with pytest.raises(ValueError,match="invalid_date"):
        svc.add_task(A,"transport","A2",due,True)


def test_task_consent_and_helper_scope(svc):
    with pytest.raises(ValueError,match="consent_required"):
        svc.add_task(A,"transport","A2","2026-10-20",False)
    with pytest.raises(PermissionError):
        svc.add_task(A,"transport","B2","2026-10-20",True)


def test_private_backup_and_rehearsal(svc):
    svc.save_backup(A,["A2","A3"],"Printed fictional contact card","Fictional cupboard","Two adults practise the routine",True)
    assert svc.store.backup(A,"HH-001")["practised"] is True
    assert svc.store.counts()["backups"] == 1
    assert svc.store.backup(B,"HH-002") is None
    with pytest.raises(ValueError,match="backup_two"):
        svc.save_backup(A,["A2","A2"],"a","b","c",False)


@pytest.mark.parametrize("secret", ["password: example", "Account number 123456789012", "ஆதார் 123456789012", "API key example", "கடவுச்சொல் எடுத்துக்காட்டு"])
def test_secrets_are_not_saved_in_backup(svc, secret):
    with pytest.raises(ValueError,match="secret_blocked"):
        svc.save_backup(A,["A2","A3"],secret,"location","routine",False)
    assert svc.store.backup(A,"HH-001") is None


def test_template_draft_requires_reviewer_and_stays_private(svc):
    answer = svc.ask(A,"How do we reduce sugar in tea?",mode="template")
    assert answer.provider == "local_template" and answer.status == "pending_review"
    assert "not approved" in svc.released_draft(A,answer.review_id,"en")
    with pytest.raises(PermissionError):
        svc.decide_review(A,answer.review_id,"approve","Reviewed.")
    with pytest.raises(PermissionError):
        svc.released_draft(B,answer.review_id,"en")
    svc.decide_review(C,answer.review_id,"approve","Fictional education checked against sources.")
    assert "Reviewed demo draft" in svc.released_draft(A,answer.review_id,"en")
    assert "மற்ற மொழி" in svc.released_draft(A,answer.review_id,"ta")


def test_rejected_draft_is_not_released(svc):
    answer = svc.ask(A,"How can we share caregiver responsibilities?",mode="template")
    svc.decide_review(C,answer.review_id,"reject","Revise the fictional wording.")
    assert "rejected" in svc.released_draft(A,answer.review_id,"en")


def test_changed_source_invalidates_approved_draft(svc):
    answer = svc.ask(A,"How do we reduce sugar in tea?",mode="template")
    svc.decide_review(C,answer.review_id,"approve","Fictional wording checked.")
    svc.retriever.by_id["sugar"]["version"] = "2.0"
    assert svc.released_draft(A,answer.review_id,"en") == tr("no_source")


def test_expiry_and_production_approval_filter(svc):
    hits, _, _ = svc.retriever.search("sugar tea",today=date(2028,1,1))
    assert hits == []
    hits, _, _ = svc.retriever.search("sugar tea",today=date(2026,10,14),production=True)
    assert hits == []


def test_review_notes_do_not_prescribe(svc):
    answer = svc.ask(A,"Can I stop tablets?",request_review=True)
    with pytest.raises(ValueError,match="no_prescribing"):
        svc.decide_review(C,answer.review_id,"close","Take 10 mg daily.")


def test_traces_do_not_store_query_measurements_or_households(svc):
    text = "UniquePrivateMarker My BP is 188/125"
    answer = svc.ask(A,text)
    traces = json.dumps(svc.store.traces(C))
    assert answer.trace_id in traces
    for prohibited in ["UniquePrivateMarker","188/125","HH-001","OPENAI_API_KEY"]:
        assert prohibited not in traces


def test_every_localised_string_has_both_languages():
    assert all(len(value) == 2 and all(value) for value in TEXT.values())
    assert all(any("\u0b80" <= c <= "\u0bff" for c in value[1]) for value in TEXT.values())
