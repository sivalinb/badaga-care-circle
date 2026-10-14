from datetime import datetime, timedelta
from functools import wraps
from html import escape
from zoneinfo import ZoneInfo
import inspect
import gradio as gr
from .i18n import TEXT, choices, example_text, tr
from .models import Actor
from .evals import run_evals

CSS = """
.gradio-container { max-width: 1180px !important; font-family: 'Noto Sans Tamil', 'Arial', sans-serif; }
.care-brand { padding: 14px 0 8px; }
.care-brand h1 { margin-bottom: 6px; }
.care-notice { border-left: 4px solid var(--color-accent); padding-left: 14px; }
.care-counter { padding: 12px 0; }
footer { display: none !important; }
"""


class ScopedComponents:
    """Give dynamic components explicit identities; never reuse a different role's type."""
    def __init__(self, scope):
        self.scope = scope
        self.index = 0

    def __getattr__(self, name):
        factory = getattr(gr, name)
        parameters = inspect.signature(factory).parameters
        def create(*args, **kwargs):
            self.index += 1
            if "key" in parameters:
                kwargs.setdefault("key", f"{self.scope}-{name}-{self.index}")
            if "preserved_by_key" in parameters:
                kwargs.setdefault("preserved_by_key", [])
            return factory(*args, **kwargs)
        return create


def guard(fn, lang):
    @wraps(fn)
    def call(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except (PermissionError, ValueError) as exc:
            key = str(exc)
            raise gr.Error(tr(key if key in TEXT else "uncertain", lang)) from None
    return call


def build_demo(svc):
    def home_choices(lang):
        return [(h["label_" + lang], h["id"]) for h in svc.store.households()]

    def stamp(value):
        return datetime.fromisoformat(value).astimezone(ZoneInfo(svc.settings.timezone)).strftime("%Y-%m-%d %H:%M")

    def counts(lang):
        return tr("summary_counts", lang, **svc.store.counts())

    with gr.Blocks(title="Badaga Care Circle", analytics_enabled=False) as demo:
        with gr.Row():
            language = gr.Dropdown([("English", "en"), ("தமிழ்", "ta")], value="en", label="Language / மொழி", scale=1, min_width=160, elem_id="language-switch", interactive=True)
            household = gr.Dropdown(home_choices("en"), value="HH-001", label=tr("household"), scale=2, elem_id="household-switch", interactive=True)
            role = gr.Dropdown(choices(["participant", "volunteer", "clinician"], "en"), value="participant", label=tr("role"), scale=2, elem_id="role-switch", interactive=True)
        last_answers = gr.State({})

        brand = gr.Markdown("# " + tr("app_title") + "\n" + tr("tagline"), elem_classes="care-brand")
        notice = gr.Markdown(tr("demo_notice"), elem_classes="care-notice")
        translation_notice = gr.Markdown(tr("translation_notice"))
        role_notice = gr.Markdown("_" + tr("role_notice") + " " + tr("switch_notice") + "_")
        active_context = gr.Markdown(tr("participant") + " · " + home_choices("en")[0][0], elem_id="active-context")

        def render_view(view_name, lang, home, actor_role):
            g = ScopedComponents(f"{view_name}-{lang}-{home}-{actor_role}")
            actor = Actor(actor_role, home)
            try:
                members = svc.store.members(actor, home)
            except PermissionError:
                g.Markdown(tr("permission", lang))
                return
            member_choices = [(m["label_" + lang], m["id"]) for m in members]
            member_labels = dict((value, label) for label, value in member_choices)

            def check_rows():
                if actor_role == "volunteer":
                    return []
                return [[r["id"], member_labels.get(r["member_id"], r["member_id"]), r["systolic"], r["diastolic"], tr(r["status"], lang), stamp(r["created_at"])] for r in svc.store.checkins(actor, home)]

            def task_rows():
                return [[r["id"], tr(r["kind"], lang), member_labels.get(r["helper_id"], r["helper_id"]), r["due_date"], tr(r["status"], lang)] for r in svc.store.tasks(actor, home)]

            def task_choices():
                return [(tr(r["kind"], lang) + " · " + r["id"], r["id"]) for r in svc.store.tasks(actor, home)]

            def review_rows():
                if actor_role != "clinician":
                    return tr("permission", lang)
                records = svc.store.reviews(actor)
                if not records:
                    return tr("empty", lang)
                rows = [f"| ID | {tr('household', lang)} | {tr('status', lang)} |", "| --- | --- | --- |"]
                rows.extend(f"| {r['id']} | {r['household_id']} | {tr(r['status'], lang)} |" for r in records)
                return "\n".join(rows)

            def review_choices():
                return [(r["id"] + " · " + r["household_id"], r["id"]) for r in svc.store.reviews(actor)] if actor_role == "clinician" else []

            if view_name == 'overview':
                g.Markdown(tr("welcome", lang))
                refresh_counter = g.Button(tr("refresh", lang))
                refresh_counter.click(lambda: counts(lang), outputs=counter, api_name=False)
                g.Markdown("**" + tr("clinical_gate", lang) + "**")

            if view_name == 'guide':
                with g.Row():
                    example = g.Dropdown([(tr("example_" + k, lang), k) for k in ["sugar", "meds", "emergency", "care", "backup"]], value="sugar", label=tr("example", lang), scale=3, interactive=True)
                    use_example = g.Button(tr("load_example", lang), scale=1)
                question = g.Textbox(label=tr("question", lang), placeholder=tr("question_hint", lang), lines=3, max_lines=6, elem_id="guide-question", interactive=True)
                mode = g.Radio(choices(["local", "template", "openai"], lang), value="local", label=tr("engine", lang), elem_id="answer-mode", interactive=True)
                cloud = g.Checkbox(False, label=tr("cloud_consent", lang), interactive=True)
                review_request = g.Checkbox(False, label=tr("request_review", lang), interactive=True)
                ask_button = g.Button(tr("ask", lang), variant="primary", elem_id="ask-button")
                guide_answer = g.Markdown(tr("empty", lang), elem_id="guide-answer")
                with g.Accordion(tr("sources", lang), open=True):
                    source_display = g.Markdown(tr("empty", lang))
                check_draft = g.Button(tr("draft_status", lang), elem_id="check-draft")

                def ask_callback(q, selected_mode, consent, requested, answers):
                    result = svc.ask(actor, q, lang, selected_mode, consent, requested)
                    updated = dict(answers)
                    updated[home] = {"review_id": result.review_id, "language": lang}
                    text = result.text
                    if result.review_id:
                        text += "\n\n" + tr("review_id", lang) + ": `" + result.review_id + "`"
                    return text, svc.source_markdown(result.source_ids, lang), updated

                def draft_callback(answers):
                    identifier = answers.get(home, {}).get("review_id")
                    if not identifier:
                        return tr("empty", lang), tr("empty", lang)
                    record = svc.store.review_item(actor, identifier)
                    return svc.released_draft(actor, identifier, lang), svc.source_markdown(record["payload"].get("source_ids", []), lang)

                use_example.click(lambda key: example_text(key, lang), example, question, api_name=False)
                ask_button.click(guard(ask_callback, lang), [question, mode, cloud, review_request, last_answers], [guide_answer, source_display, last_answers], api_name=False)
                check_draft.click(guard(draft_callback, lang), last_answers, [guide_answer, source_display], api_name=False)

            if view_name == 'health':
                if actor_role == "volunteer":
                    g.Markdown(tr("permission", lang))
                else:
                    person = g.Dropdown(member_choices, value=members[0]["id"], label=tr("member", lang), interactive=True)
                    current_symptoms = g.CheckboxGroup(choices(["chest", "breath", "stroke", "collapse", "pregnancy"], lang), label=tr("symptoms", lang), elem_id="current-symptoms", interactive=True)
                    with g.Row():
                        systolic = g.Number(value=148, precision=0, label=tr("systolic", lang), elem_id="systolic-input", interactive=True)
                        diastolic = g.Number(value=94, precision=0, label=tr("diastolic", lang), elem_id="diastolic-input", interactive=True)
                    confirmed = g.Checkbox(False, label=tr("confirmed", lang), elem_id="confirm-bp", interactive=True)
                    share_health = g.Checkbox(False, label=tr("share_health", lang), elem_id="consent-health", interactive=True)
                    save_check = g.Button(tr("save_check", lang), variant="primary", elem_id="save-check")
                    check_status = g.Markdown(elem_id="check-status")
                    checks_table = g.Dataframe(value=check_rows(), headers=["ID", tr("member", lang), "mmHg ↑", "mmHg ↓", tr("status", lang), svc.settings.timezone], datatype=["str", "str", "number", "number", "str", "str"], type="array", interactive=False, wrap=True, label=tr("checks", lang))

                    def check_callback(member, top, bottom, verified, symptoms, consent):
                        message, _ = svc.checkin(actor, member, top, bottom, verified, symptoms, consent, lang)
                        return message, check_rows(), counts(lang)
                    save_check.click(guard(check_callback, lang), [person, systolic, diastolic, confirmed, current_symptoms, share_health], [check_status, checks_table, counter], api_name=False)

            if view_name == 'care':
                with g.Row():
                    task_kind = g.Dropdown(choices(["transport", "bills", "elder", "rest"], lang), value="transport", label=tr("task_kind", lang), interactive=True)
                    helper = g.Dropdown(member_choices, value=members[1]["id"], label=tr("helper", lang), interactive=True)
                    due = g.Textbox(value=(svc.settings.today() + timedelta(days=7)).isoformat(), label=tr("due", lang), interactive=True)
                share_consent = g.Checkbox(False, label=tr("share_consent", lang), elem_id="consent-task", interactive=True)
                add_task = g.Button(tr("add_task", lang), variant="primary", elem_id="add-task")
                task_status = g.Markdown(elem_id="task-status")
                tasks_table = g.Dataframe(value=task_rows(), headers=["ID", tr("task_kind", lang), tr("helper", lang), tr("due", lang), tr("status", lang)], type="array", interactive=False, wrap=True, label=tr("tasks", lang))
                with g.Row():
                    task_selector = g.Dropdown(task_choices(), value=None, label=tr("task_id", lang), elem_id="task-selector", interactive=True)
                    task_next = g.Dropdown(choices(["accepted", "completed"], lang), value="accepted", label=tr("task_action", lang), elem_id="task-next", interactive=True)
                    update_task = g.Button(tr("update_task", lang), elem_id="update-task")

                def add_task_callback(kind, helper_id, due_date, consent):
                    identifier = svc.add_task(actor, kind, helper_id, due_date, consent)
                    return tr("task_created", lang), task_rows(), gr.Dropdown(choices=task_choices(), value=identifier, interactive=True), counts(lang)

                def update_task_callback(identifier, status):
                    svc.store.update_task(actor, home, identifier, status)
                    return tr("task_updated", lang) + " " + tr(status, lang), task_rows(), counts(lang)
                add_task.click(guard(add_task_callback, lang), [task_kind, helper, due, share_consent], [task_status, tasks_table, task_selector, counter], api_name=False)
                update_task.click(guard(update_task_callback, lang), [task_selector, task_next], [task_status, tasks_table, counter], api_name=False)

            if view_name == 'backup':
                g.Markdown(tr("backup_intro", lang))
                if actor_role == "volunteer":
                    g.Markdown(tr("permission", lang))
                else:
                    existing = svc.store.backup(actor, home) or {}
                    backup_people = g.CheckboxGroup(member_choices, value=existing.get("people", []), label=tr("backup_people", lang), elem_id="backup-people", interactive=True)
                    contact_plan = g.Textbox(value=existing.get("contact_plan", ""), label=tr("contact_plan", lang), lines=2, elem_id="backup-contacts", interactive=True)
                    document_location = g.Textbox(value=existing.get("document_location", ""), label=tr("document_location", lang), elem_id="backup-documents", interactive=True)
                    routines = g.Textbox(value=existing.get("routines", ""), label=tr("routines", lang), lines=3, elem_id="backup-routines", interactive=True)
                    practised = g.Checkbox(existing.get("practised", False), label=tr("practised", lang), elem_id="backup-practised", interactive=True)
                    save_backup = g.Button(tr("save_backup", lang), variant="primary", elem_id="save-backup")
                    backup_status = g.Markdown(elem_id="backup-status")

                    def backup_callback(people, contacts, location, daily, rehearsed):
                        svc.save_backup(actor, people, contacts, location, daily, rehearsed)
                        return tr("backup_saved", lang), counts(lang)
                    save_backup.click(guard(backup_callback, lang), [backup_people, contact_plan, document_location, routines, practised], [backup_status, counter], api_name=False)

            if view_name == 'review':
                g.Markdown(tr("review_intro", lang))
                if actor_role != "clinician":
                    g.Markdown(tr("permission", lang))
                else:
                    g.Markdown("### " + tr("review_queue", lang))
                    queue_table = g.Markdown(review_rows())
                    with g.Row():
                        item = g.Dropdown(review_choices(), value=None, label=tr("review_case", lang), scale=3, elem_id="review-selector", interactive=True)
                        refresh_review = g.Button(tr("refresh", lang), scale=1)
                        inspect = g.Button(tr("inspect", lang), scale=1, elem_id="inspect-review")
                    details = g.Markdown(elem_id="review-details")
                    notes = g.Textbox(label=tr("review_notes", lang), lines=3, elem_id="review-notes", interactive=True)
                    decision = g.Radio(choices(["followup", "close", "approve", "reject"], lang), value="followup", label=tr("decision", lang), elem_id="review-decision", interactive=True)
                    save_review = g.Button(tr("save_review", lang), variant="primary", elem_id="save-review")
                    review_status = g.Markdown(elem_id="review-status")

                    def refresh_review_callback():
                        return review_rows(), gr.Dropdown(choices=review_choices(), value=None, interactive=True), counts(lang)

                    def inspect_callback(identifier):
                        record = svc.store.review_item(actor, identifier)
                        payload = record["payload"]
                        output = [f"**{record['id']} · {record['household_id']}**", tr("status", lang) + ": " + tr(record["status"], lang)]
                        if record["kind"] == "education":
                            output.extend(escape(s["text"]) for s in payload["draft"]["sentences"])
                            output.append(escape(payload["draft"]["next_step"]))
                        elif payload.get("systolic"):
                            output.append(f"{payload['member_id']}: {payload['systolic']}/{payload['diastolic']} mmHg")
                        else:
                            output.append(tr("medication", lang) if record["reason"] == "medication_change" else tr("uncertain", lang))
                        output.append(svc.source_markdown(payload.get("source_ids", []), lang))
                        return "\n\n".join(output)

                    def decide_callback(identifier, next_decision, note):
                        svc.decide_review(actor, identifier, next_decision, note)
                        return tr("review_saved", lang), review_rows(), counts(lang)
                    refresh_review.click(guard(refresh_review_callback, lang), outputs=[queue_table, item, counter], api_name=False)
                    inspect.click(guard(inspect_callback, lang), item, details, api_name=False)
                    save_review.click(guard(decide_callback, lang), [item, decision, notes], [review_status, queue_table, counter], api_name=False)

            if view_name == 'quality':
                g.Markdown(tr("quality_intro", lang))
                g.Markdown("**" + tr("clinical_gate", lang) + "**")
                with g.Accordion(tr("knowledge", lang), open=True):
                    register = svc.retriever.public_register(lang)
                    g.Dataframe(value=[[r["id"], r["title"], r["version"], r["checked"], r["expires"], tr("source_draft", lang)] for r in register], headers=["ID", tr("sources", lang), "v", tr("source_checked", lang), tr("expires", lang), tr("clinical_review", lang)], type="array", interactive=False, wrap=True)
                eval_button = g.Button(tr("run_evals", lang), variant="primary")
                eval_report = g.JSON(label=tr("eval_report", lang))
                eval_button.click(lambda: run_evals(svc.settings), outputs=eval_report, api_name=False)
                if actor_role == "clinician":
                    with g.Accordion(tr("traces", lang), open=False):
                        trace_display = g.JSON(svc.store.traces(actor), label=tr("traces", lang))
                        refresh_traces = g.Button(tr("refresh", lang))
                        refresh_traces.click(lambda: svc.store.traces(actor), outputs=trace_display, api_name=False)
                    with g.Accordion(tr("metrics", lang), open=False):
                        metrics_display = g.JSON(svc.store.metrics(actor), label=tr("metrics", lang))
                        refresh_metrics = g.Button(tr("refresh", lang))
                        refresh_metrics.click(lambda: svc.store.metrics(actor), outputs=metrics_display, api_name=False)

            if view_name == 'roadmap':
                g.Markdown(tr("roadmap_body", lang))
        tab_names = ["overview", "guide", "health", "care", "backup", "review", "quality", "roadmap"]
        # Permanent bilingual navigation avoids remounting tabs when locale changes.
        nav_labels = ["Home / தொடக்கம்", "Guide / வழிகாட்டி", "Health / உடல்நலம்", "Care / பராமரிப்பு",
                      "Family / குடும்பம்", "Review / ஆய்வு", "Quality / தரம்", "Roadmap / திட்டம்"]
        tab_components = []
        with gr.Tabs(selected="overview"):
            for view_name, nav_label in zip(tab_names, nav_labels):
                with gr.Tab(nav_label, id=view_name) as tab_component:
                    tab_components.append(tab_component)
                    if view_name == "overview":
                        counter = gr.Markdown(counts("en"), elem_classes="care-counter")
                    def bind_view(lang, home, actor_role, selected=view_name):
                        render_view(selected, lang, home, actor_role)
                    gr.render(inputs=[language, household, role], show_progress="hidden")(bind_view)

        def sync_context(lang, home, actor_role):
            label = next(h["label_" + lang] for h in svc.store.households() if h["id"] == home)
            return [gr.update(choices=home_choices(lang), label=tr("household", lang), interactive=True),
                    gr.update(choices=choices(["participant", "volunteer", "clinician"], lang), label=tr("role", lang), interactive=True),
                    "# " + tr("app_title", lang) + "\n" + tr("tagline", lang),
                    tr("demo_notice", lang), tr("translation_notice", lang),
                    "_" + tr("role_notice", lang) + " " + tr("switch_notice", lang) + "_",
                    tr(actor_role, lang) + " · " + label, counts(lang)]
        for control in [language, household, role]:
            control.change(sync_context, [language, household, role],
                           [household, role, brand, notice, translation_notice, role_notice, active_context, counter],
                           queue=False, api_name=False)
    return demo
