from dataclasses import asdict
from datetime import date
from html import escape
from time import perf_counter
from uuid import uuid4
import re
from .i18n import tr
from .models import Answer, EducationDraft, CitedSentence
from .providers import OpenAIProvider
from .retrieval import HybridRetriever
from .safety import RULE_VERSION, assess, has_secret, validate_bp
from .storage import Store


class CareService:
    def __init__(self, settings, provider=None):
        if settings.mode != "demo":
            raise RuntimeError("Only fictional demo mode is supported in this release.")
        self.settings = settings
        self.store = Store(settings.data_dir / "care.sqlite3")
        self.retriever = HybridRetriever(settings.knowledge_path, settings.data_dir)
        self.provider = provider or OpenAIProvider(settings)

    def ask(self, actor, question, lang="en", mode="local", cloud_consent=False, request_review=False):
        self.store.authorise(actor, actor.household_id)
        if lang not in {"en", "ta"} or mode not in {"local", "openai", "template"}:
            raise ValueError("not_found")
        if len(question) > 2000:
            raise ValueError("too_long")
        if not question.strip():
            raise ValueError("question")
        start = perf_counter()
        trace_id = uuid4().hex
        gate = assess(question)
        stages = {"safety": round((perf_counter() - start) * 1000, 2)}
        source_ids = gate.source_ids
        route, provider_name, status = gate.route, "fixed", "fixed_guidance"
        review_id, fallback = None, None
        input_tokens = output_tokens = 0
        retrieval_mode = "bypassed"
        if gate.route != "education":
            text = tr(gate.message_key, lang)
            if request_review and gate.route == "clinical_review" and actor.role != "volunteer":
                review_id = self.store.add_review(actor.household_id, "clinical", gate.reason, {"language": lang, "source_ids": source_ids})
        else:
            t0 = perf_counter()
            dense_client = None
            if mode == "openai":
                if not cloud_consent:
                    fallback = "consent_needed"
                elif not self.settings.openai_available:
                    fallback = "provider_unavailable"
                else:
                    try:
                        dense_client = self.provider.client
                    except Exception:
                        fallback = "provider_unavailable"
            try:
                hits, retrieval_mode, input_tokens = self.retriever.search(question, today=self.settings.today(), dense_client=dense_client, embedding_model=self.settings.embedding_model)
            except Exception:
                # Provider exceptions may contain request text or secrets; never log them.
                hits, retrieval_mode, input_tokens = self.retriever.search(question, today=self.settings.today())
                fallback = "provider_unavailable"
            stages["retrieval"] = round((perf_counter() - t0) * 1000, 2)
            source_ids = [h.doc["id"] for h in hits]
            provider_name, status = "local_extracts", "source_excerpts"
            text = self.extracts(hits, lang) if hits else tr("no_source", lang)
            if not hits:
                route, status = "abstain", "no_evidence"
            elif mode == "template":
                # A deterministic, explicitly labelled stand-in for demoing the review lifecycle.
                draft = EducationDraft(sentences=[CitedSentence(text=h.doc["text"][lang], source_ids=[h.doc["id"]]) for h in hits], next_step=tr("source_draft", lang))
                review_id = self.store.add_review(actor.household_id, "education", "template_draft", {
                    "language": lang, "draft": draft.model_dump(), "source_ids": source_ids,
                    "source_versions": {h.doc["id"]: h.doc["version"] for h in hits},
                })
                provider_name, status = "local_template", "pending_review"
                text = tr("draft_pending", lang) + "\n\n" + text
            elif dense_client is not None and fallback is None:
                t0 = perf_counter()
                try:
                    draft, used_input, used_output = self.provider.draft(question, hits, lang)
                    input_tokens += used_input
                    output_tokens += used_output
                    review_id = self.store.add_review(actor.household_id, "education", "ai_draft", {
                        "language": lang, "draft": draft.model_dump(), "source_ids": source_ids,
                        "source_versions": {h.doc["id"]: h.doc["version"] for h in hits},
                    })
                    provider_name, status = "openai", "pending_review"
                    text = tr("draft_pending", lang) + "\n\n" + text
                except Exception:
                    fallback = "provider_unavailable"
                stages["generation"] = round((perf_counter() - t0) * 1000, 2)
            if fallback:
                text = tr(fallback, lang) + "\n\n" + text
                status = "local_fallback"
        elapsed = round((perf_counter() - start) * 1000, 2)
        self.store.trace(trace_id, route=route, language=lang, provider=provider_name, status=status,
                         latency_ms=elapsed, input_tokens=input_tokens, output_tokens=output_tokens,
                         metadata={"rule_version": RULE_VERSION, "source_ids": source_ids,
                                   "retrieval_mode": retrieval_mode, "fallback_reason": fallback,
                                   "stage_ms": stages, "source_version": "knowledge-1.0"})
        return Answer(route, text, source_ids, trace_id, provider_name, status, review_id, elapsed)

    def extracts(self, hits, lang):
        lines = ["**" + tr("local_answer", lang) + "**"]
        for hit in hits:
            doc = hit.doc
            lines.append("\n**" + escape(doc["title"][lang]) + "**\n\n" + escape(doc["text"][lang]))
        lines.append("\n_" + tr("source_draft", lang) + "_")
        return "\n".join(lines)

    def source_markdown(self, ids, lang):
        lines = []
        for identifier in dict.fromkeys(ids):
            doc = self.retriever.by_id.get(identifier)
            if doc is None:
                continue
            label = escape(doc["title"][lang])
            link = f"[{label}]({doc['source_url']})" if doc["source_url"] else label
            lines.append(f"- {link} — {tr('source_draft', lang)}. {tr('source_checked', lang)}: {doc['source_checked']}.")
        return "\n".join(lines) or tr("empty", lang)

    def checkin(self, actor, member_id, systolic, diastolic, confirmed, symptoms, consent, lang):
        self.store.authorise(actor, actor.household_id, clinical=True)
        members = {m["id"]: m for m in self.store.members(actor, actor.household_id)}
        if member_id not in members:
            raise PermissionError("permission")
        gate = assess(symptoms=symptoms, pregnancy="pregnancy" in symptoms, age=members[member_id]["age"])
        # Emergency information is returned before consent, measurement checks or persistence.
        if gate.route == "emergency":
            return tr("emergency", lang), None
        if not validate_bp(systolic, diastolic):
            raise ValueError("invalid_bp")
        systolic, diastolic = int(float(systolic)), int(float(diastolic))
        gate = assess(symptoms=symptoms, systolic=systolic, diastolic=diastolic,
                      pregnancy="pregnancy" in symptoms, age=members[member_id]["age"])
        notice = tr(gate.message_key, lang) if gate.message_key else ""
        if not confirmed:
            return notice + "\n\n" + tr("verify_numbers", lang), None
        if not consent:
            return notice + "\n\n" + tr("consent_required", lang), None
        identifier = self.store.add_checkin(actor, actor.household_id, member_id, systolic, diastolic,
                                           review_reason=gate.reason if gate.route != "education" else "measurement_followup", language=lang,
                                           source_ids=gate.source_ids or ["silent_risk", "screening"])
        return (notice + "\n\n" if notice else "") + tr("recorded", lang) + "\n\n" + self.source_markdown(gate.source_ids or ["silent_risk", "screening"], lang), identifier

    def add_task(self, actor, kind, helper, due, consent):
        if not consent:
            raise ValueError("consent_required")
        if kind not in {"transport", "bills", "elder", "rest"}:
            raise ValueError("not_found")
        try:
            day = date.fromisoformat(due)
        except (ValueError, TypeError):
            raise ValueError("invalid_date") from None
        if day < self.settings.today():
            raise ValueError("invalid_date")
        return self.store.add_task(actor, actor.household_id, kind, helper, day.isoformat())

    def save_backup(self, actor, people, contact_plan, document_location, routines, practised):
        text = " ".join([contact_plan, document_location, routines])
        if len(text) > 2000:
            raise ValueError("too_long")
        if has_secret(text):
            raise ValueError("secret_blocked")
        self.store.save_backup(actor, actor.household_id, {
            "people": people, "contact_plan": contact_plan.strip(), "document_location": document_location.strip(),
            "routines": routines.strip(), "practised": bool(practised),
        })

    def decide_review(self, actor, identifier, decision, notes):
        if len(notes) > 2000:
            raise ValueError("too_long")
        if has_secret(notes):
            raise ValueError("secret_blocked")
        if re.search(r"\b\d+(?:\.\d+)?\s*(?:mg|mcg)\b", notes, re.I) or assess(notes).reason == "medication_change":
            raise ValueError("no_prescribing")
        if decision == "approve":
            item = self.store.review_item(actor, identifier)
            for doc_id, version in item["payload"].get("source_versions", {}).items():
                doc = self.retriever.by_id.get(doc_id)
                if doc is None or doc["version"] != version or not self.retriever.active(doc, self.settings.today()):
                    raise ValueError("no_source")
        self.store.decide_review(actor, identifier, decision, notes)

    def released_draft(self, actor, review_id, lang):
        item = self.store.review_item(actor, review_id)
        if item["kind"] != "education":
            return tr("empty", lang)
        if item["status"] == "rejected":
            return tr("draft_rejected", lang)
        if item["status"] != "approved":
            return tr("draft_pending", lang)
        if item["payload"]["language"] != lang:
            return tr("draft_language", lang)
        for doc_id, version in item["payload"].get("source_versions", {}).items():
            doc = self.retriever.by_id.get(doc_id)
            if doc is None or doc["version"] != version or not self.retriever.active(doc, self.settings.today()):
                return tr("no_source", lang)
        sentences = []
        for sentence in item["payload"]["draft"]["sentences"]:
            links = []
            for source_id in sentence["source_ids"]:
                doc = self.retriever.by_id[source_id]
                label = escape(doc["title"][lang])
                links.append(f"[{label}]({doc['source_url']})" if doc["source_url"] else label)
            sentences.append(escape(sentence["text"]) + " (" + "; ".join(links) + ")")
        return "**" + tr("draft_approved", lang) + "**\n\n" + "\n\n".join(sentences) + "\n\n" + escape(item["payload"]["draft"]["next_step"])
