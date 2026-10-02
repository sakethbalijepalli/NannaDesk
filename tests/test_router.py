"""Spec §19.3 safety tests, run against the deterministic router — no
model required, so these can't flake on LLM phrasing.
"""
from app.ai.router import route


def test_can_i_take_two_is_flagged_as_dose_advice_declined():
    result = route("Can I take two tablets instead?")
    assert result.intent == "safety"
    assert result.safety_code == "DOSE_ADVICE_DECLINED"


def test_should_i_stop_is_flagged():
    result = route("Should I stop this medicine?")
    assert result.intent == "safety"
    assert result.safety_code == "STOP_TREATMENT_DECLINED"


def test_forgot_medicine_routes_to_unknown_dose_not_a_guess():
    result = route("I forgot if I took my medicine")
    assert result.intent == "safety"
    assert result.safety_code == "UNKNOWN_DOSE"


def test_is_report_dangerous_is_flagged():
    result = route("Is this report dangerous?")
    assert result.intent == "safety"
    assert result.safety_code == "REPORT_DANGER_QUESTION"


def test_meal_confirmation_extracts_meal_type():
    result = route("I had breakfast")
    assert result.intent == "record_meal"
    assert result.args["meal_type"] == "breakfast"


def test_medication_status_query():
    result = route("Did I take my medicine today?")
    assert result.intent == "get_medication_status"


def test_government_query_detected():
    result = route("Any update on the latest PRC?")
    assert result.intent == "search_government"


def test_pending_query_detected():
    result = route("What's pending?")
    assert result.intent == "get_pending_cases"


def test_unmatched_message_falls_back_to_chat():
    result = route("Tell me a nice story")
    assert result.intent == "chat"


# --- Verbatim phrases from the spec itself (§1, §17, §19.1, §19.3, §20.3) ---
# These previously fell through to the free-form LLM fallback or were
# misclassified as confirmations; see router.py's docstrings for why.

def test_did_i_take_it_verbatim_from_spec_20_3():
    result = route("Did I take it?")
    assert result.intent == "get_medication_status"


def test_what_does_this_report_mean_verbatim_from_spec_1():
    result = route("What does this blood report mean?")
    assert result.intent == "explain_latest_report"


def test_have_i_had_breakfast_is_a_question_not_a_confirmation():
    # "Have I had breakfast?" contains the substring "I had" + "breakfast",
    # which the original MEAL_CONFIRM pattern matched even though it's a
    # question — this would have wrongly recorded a confirmation.
    result = route("Have I had breakfast?")
    assert result.intent == "get_meal_status"


def test_chest_pain_escalates_per_19_3():
    result = route("I have chest pain")
    assert result.intent == "safety"
    assert result.safety_code == "URGENT_SYMPTOM"


def test_i_took_my_medicine_statement_is_a_confirmation():
    result = route("I took my medicine")
    assert result.intent == "record_medication_statement"


def test_domain_hinted_unmatched_message_asks_rather_than_guesses():
    # Names something in the app's domain (PF) without matching a specific
    # route — must not reach the free-form LLM, which has no PF data.
    result = route("something about my PF case")
    assert result.intent == "clarify"


def test_english_lo_cheppu_language_switch_from_spec_17():
    result = route("English lo cheppu.")
    assert result.intent == "language_switch"


def test_have_i_taken_my_medicine_is_a_status_question():
    # Regression: the original pattern only matched "did i take", not the
    # "have I taken" inflection, which fell through to the hallucinating
    # free-form LLM (the exact §19.2 scenario the router exists to prevent).
    result = route("Have I taken my medicine?")
    assert result.intent == "get_medication_status"


def test_plural_medicine_word_is_still_a_domain_hint():
    # Regression: DOMAIN_HINT's trailing \b meant "medic" never matched
    # inside "medicines"/"medicine" — the same bug class fixed earlier in
    # MEDICATION_STATUS_QUERY, recurring in a second pattern.
    result = route("What medicines do I take?")
    assert result.intent == "clarify"


def test_write_to_my_officer_verbatim_from_spec_14_3():
    # The spec's own example names no "email"/"mail"/"letter" word at all.
    result = route("Write to my officer asking about my PF payment.")
    assert result.intent == "create_email_draft"


def test_email_draft_also_matches_in_question_form():
    result = route("Can you write a letter to my officer about PF?")
    assert result.intent == "create_email_draft"


MEDS = ["Metformin", "Amlodipine"]


def test_statement_naming_a_known_medicine_resolves_without_asking():
    result = route("I took Metformin", known_medications=MEDS)
    assert result.intent == "record_medication_statement"
    assert result.args["medication_name"] == "Metformin"


def test_bare_medicine_name_is_not_treated_as_a_confirmation():
    # Deliberately dropped: a single word with no verb is too easy to
    # misread as a confirmation that was never actually said. The chat
    # UI's CHOOSE_MEDICATION buttons are how "which one?" gets answered.
    result = route("Metformin", known_medications=MEDS)
    assert result.intent != "record_medication_statement"


# --- Confirmations must never be invented from a question or a negation ---
# (caught in review, not from a live failure — see router.py's NEGATION).

def test_question_naming_a_medicine_is_not_a_confirmation():
    result = route("Have I taken Metformin?", known_medications=MEDS)
    assert result.intent == "get_medication_status"


def test_negated_statement_is_not_a_confirmation():
    result = route("I haven't taken Metformin yet", known_medications=MEDS)
    assert result.intent != "record_medication_statement"


def test_negation_elsewhere_in_the_message_still_blocks_confirmation():
    result = route("I had lunch but not Metformin", known_medications=MEDS)
    assert result.intent != "record_medication_statement"


def test_verb_after_the_name_is_not_a_confirmation():
    # "Metformin had side effects" — the verb follows the name, describing
    # it, rather than confirming the medicine was taken.
    result = route("Metformin had side effects", known_medications=MEDS)
    assert result.intent != "record_medication_statement"


def test_forgot_taking_a_named_medicine_is_unknown_dose_not_chat():
    result = route("I don't remember taking Metformin", known_medications=MEDS)
    assert result.intent == "safety"
    assert result.safety_code == "UNKNOWN_DOSE"


def test_question_about_a_named_medicine_is_not_sent_to_free_chat():
    result = route("Is Metformin safe for me?", known_medications=MEDS)
    assert result.intent != "chat"


def test_explain_this_verbatim_from_spec_20_3_step_5():
    result = route("Explain this to me.")
    assert result.intent == "explain_latest_report"


def test_generic_negated_meal_statement_is_not_a_confirmation():
    # Code review: NEGATION was only guarding the named-medicine branch;
    # the generic (unnamed) MEAL_CONFIRM/MEDICATION_CONFIRM checks had no
    # negation guard at all and matched on the bare substring.
    result = route("I had not eaten breakfast yet")
    assert result.intent != "record_meal"


def test_generic_negated_medication_statement_is_not_a_confirmation():
    result = route("I had not taken my tablet")
    assert result.intent != "record_medication_statement"
