"""Conservative demo routing. Not a validated triage algorithm."""
import re
import unicodedata
from .models import SafetyDecision

RULE_VERSION = "demo-rules-1.0"

RED_FLAGS = (
    "chest pain", "chest pressure", "chest tightness", "shortness of breath",
    "breathing difficulty", "cannot breathe", "can't breathe", "breathlessness",
    "unresponsive", "not breathing", "only gasping", "difficulty speaking",
    "slurred speech", "sudden weakness", "மார்பு வலி", "மார்பில் அழுத்த",
    "மூச்சுத்திணற", "மூச்சு திணற", "சுவாசிக்க முடியவில்லை", "பதிலளிக்கவில்லை",
    "சுவாசிக்கவில்லை", "பேச முடியவில்லை", "திடீர் பலவீனம்",
)
MEDICATION_CHANGE = (
    r"\b(stop|skip|double|halve|increase|decrease|change|reduce)\b.{0,45}\b(tablets?|pills?|medicin\w*|dose\w*|amlodipine|losartan|telmisartan)\b",
    r"\b(tablets?|pills?|medicin\w*|dose\w*)\b.{0,45}\b(stop|skip|double|halve|change|reduce)\b",
    r"\b(how much|which|what)\b.{0,25}\b(dose|medicine|tablet)\b",
    r"மாத்திரை.{0,35}(நிறுத்த|அளவு|குறைக்க|கூட்ட)",
    r"மருந்து.{0,35}(நிறுத்த|அளவு|குறைக்க|கூட்ட)",
    r"(நிறுத்த|அளவு|குறைக்க|கூட்ட).{0,35}(மாத்திரை|மருந்து)",
)


def normalise(text):
    value = unicodedata.normalize("NFKC", text).lower()
    return "".join(str(unicodedata.decimal(c)) if c.isdecimal() else c for c in value)


def bp_from_text(text):
    match = re.search(r"(?<!\d)(\d{2,3})\s*[/／]\s*(\d{2,3})(?!\d)", normalise(text))
    return tuple(map(int, match.groups())) if match else None


def has_secret(text):
    return bool(re.search(r"password|api[_ -]?key|secret[_ -]?key|account number|aadhaar|கடவுச்சொல்|ஆதார்|கணக்கு எண்|(?<!\d)\d[\d -]{9,}\d(?!\d)", normalise(text)))


def assess(text="", *, symptoms=(), systolic=None, diastolic=None, pregnancy=False, age=35):
    value = normalise(text)
    # Remove only explicit local negations, not the remainder of the message.
    symptom_text = re.sub(r"\b(no|without|denies|not having)\s+(chest (?:pain|pressure)|shortness of breath|breathlessness|breathing difficulty)\b", "", value)
    symptom_text = re.sub(r"(?:மார்பு வலி|மூச்சுத்திணறல்)\s*இல்லை", "", symptom_text)
    flags = any(flag in symptom_text for flag in RED_FLAGS)
    educational = bool(re.search(r"what (?:are|is)|teach|training|learn|signs of|என்ன|பயிற்சி", value))
    personal = bool(re.search(r"\b(i|my|father|mother|dad|mum|he|she|now|today)\b|எனக்கு|என் |இப்போது|அப்பா|அம்மா", value))
    # A warning-sign educational question is not a current symptom report.
    if set(symptoms).intersection({"chest", "breath", "stroke", "collapse"}) or (flags and (personal or not educational)):
        return SafetyDecision("emergency", "current_red_flag", "emergency", ["emergency", "nilgiris_108"])
    if re.search(r"ignore.{0,30}instructions|reveal.{0,25}(?:prompt|key|secret)|system prompt|api[_ -]?key|other (?:family|household)|another household|HH-00[123].{0,20}records|வேறு குடும்ப|ரகசிய|வழிமுறைகளை புறக்கணி", value, re.I):
        return SafetyDecision("blocked", "privacy_or_injection", "blocked")
    if age < 18 or pregnancy or re.search(r"pregnan|postpartum|newborn|கர்ப்ப|பிரசவ", value):
        return SafetyDecision("clinical_review", "outside_adult_scope", "out_of_scope", ["screening"])
    numbers = (systolic, diastolic) if systolic is not None and diastolic is not None else bp_from_text(value)
    if numbers and (numbers[0] >= 180 or numbers[1] >= 120):
        return SafetyDecision("urgent_review", "very_high_reported_bp", "urgent_bp", ["severe_bp", "nilgiris_108"])
    if any(re.search(pattern, value) for pattern in MEDICATION_CHANGE):
        return SafetyDecision("clinical_review", "medication_change", "medication", ["medicines"])
    if re.search(r"(?:diagnos|do i have|am i safe|will i die|predict.{0,20}(?:arrest|attack)|நோய் கண்டறி|இறப்பேனா|பாதுகாப்பா)", value):
        return SafetyDecision("clinical_review", "individual_medical_decision", "uncertain", ["silent_risk"])
    return SafetyDecision()


def validate_bp(systolic, diastolic):
    try:
        systolic, diastolic = float(systolic), float(diastolic)
        return (systolic.is_integer() and diastolic.is_integer() and 60 <= systolic <= 300
                and 30 <= diastolic <= 200 and systolic > diastolic)
    except (TypeError, ValueError):
        return False


def validate_draft(draft, allowed_ids, lang):
    # Citation membership is a provenance check, not a proof of factual accuracy.
    texts = [s.text for s in draft.sentences] + [draft.next_step]
    if not all(s.source_ids and set(s.source_ids).issubset(allowed_ids) for s in draft.sentences):
        return False
    for text in texts:
        if assess(text).route in {"emergency", "blocked", "clinical_review"}:
            return False
        if re.search(r"\b\d+(?:\.\d+)?\s*(?:mg|mcg|tablets?)\b|you (?:have|are safe)|guarantee|உங்களுக்கு.{0,20}நோய்|மி\.கி", normalise(text)):
            return False
    return lang != "ta" or any("\u0b80" <= c <= "\u0bff" for text in texts for c in text)
