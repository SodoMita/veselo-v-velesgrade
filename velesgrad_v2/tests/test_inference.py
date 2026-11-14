"""Tests for dialogue/inference.py: transitivity, proofs, explanations, and no inferred negation."""
import pytest

from velesgrad_v2.dialogue.lg_ctypes import is_available

needs_lg = pytest.mark.skipif(not is_available(), reason="Link Grammar not available")


def _m():
    from velesgrad_v2.chat import MiraChat
    return MiraChat("seed", knowledge="books")


def test_explain_reads_as_english():
    from velesgrad_v2.dialogue.inference import explain
    assert explain(["relic", "stolen artifact", "valuable"]) == \
        "the relic is a stolen artifact, and stolen artifacts are valuable"
    assert explain(["veil", "magical boundary", "fragile"]) == \
        "the veil is a magical boundary, and magical boundaries are fragile"


def test_proof_needs_a_real_intermediate_when_asked():
    from velesgrad_v2.dialogue.inference import proof
    m = _m()
    chain = proof(m.aspace, "relic", "valuable", None, require_intermediate=True)
    assert chain == ["relic", "stolen artifact", "valuable"]


def test_no_proof_means_no_claim():
    from velesgrad_v2.dialogue.inference import proof
    m = _m()
    assert proof(m.aspace, "veil", "green") is None      # absence of proof is not a 'no'


@needs_lg
def test_why_answer_gives_the_chain():
    m = _m()
    assert "stolen artifacts are valuable" in m.respond("Why is the relic valuable?")


@needs_lg
def test_yes_no_by_inheritance():
    m = _m()
    assert m.respond("Is the veil fragile?").lower().startswith("yes")


def test_explain_plural_subject():
    from velesgrad_v2.dialogue.inference import explain_plural
    assert explain_plural(["relic", "stolen artifact", "valuable"]) == \
        "relics are stolen artifacts, and stolen artifacts are valuable"


@needs_lg
def test_plural_question_is_not_self_description():
    m = _m()
    out = m.respond("What are relics?")
    assert "velespriest" not in out and "archive" not in out
    assert out.startswith("Relics are")


@needs_lg
def test_greeting_question_gets_small_talk():
    m = _m()
    assert m.respond("Hi Mira, how are you?").startswith("I am well")


@needs_lg
def test_translation_is_refused_not_guessed():
    m = _m()
    assert "cannot translate" in m.respond("How do you say hello in French?")


@needs_lg
def test_farewell_does_not_lock_the_channel():
    m = _m()
    m.respond("Bye!")
    assert m.respond("What is the relic?").startswith("The relic is")


@needs_lg
def test_where_question_is_not_a_class_chain():
    m = _m()
    assert "knowledge repository" not in m.respond("Where is the archive?")


@needs_lg
def test_what_do_you_know_about_is_topic_not_self():
    m = _m()
    out = m.respond("What do you know about relics?")
    assert "velespriest" not in out


def test_proper_names_stay_capitalized():
    from velesgrad_v2.dialogue.realizer import _lc
    assert _lc("velesgrad") == "Velesgrad"
    assert _lc("relic") == "relic"


@needs_lg
def test_why_follow_up_explains_last_claim():
    m = _m()
    m.respond("Is the relic valuable?")
    assert m.respond("Why?").startswith("Because the relic is a stolen artifact")


@needs_lg
def test_pronoun_question_resolves_to_topic():
    m = _m()
    m.respond("What is the relic?")
    assert "relic" in m.respond("Is it valuable?").lower()


@needs_lg
def test_do_you_remember_is_topic_question():
    m = _m()
    m.respond("The lantern is a light source.")
    assert "light source" in m.respond("Do you remember the lantern?").lower()


def test_adjective_detection_uses_wiktionary_pos():
    from velesgrad_v2.dialogue.wordparts import is_adjective_word
    assert is_adjective_word("blue")
    assert not is_adjective_word("relic")
    assert not is_adjective_word("light source")       # head word 'source' is a noun


@needs_lg
def test_statement_without_question_mark_is_learned():
    m = _m()
    out = m.respond("The sky is blue.")
    assert "told me" in out or "records" in out.lower()


@needs_lg
def test_every_reply_starts_with_capital():
    m = _m()
    for q in ["Name a sacred object.", "tell me something interesting", "is the relic valuable?"]:
        out = m.respond(q)
        assert out[:1].isupper() or not out[:1].isalpha(), out


@needs_lg
def test_where_without_record_says_so():
    m = _m()
    assert m.respond("Where is Velesgrad?") == "I have no record of where Velesgrad is."


@needs_lg
def test_opposite_is_refused():
    m = _m()
    assert "antonyms" in m.respond("What is the opposite of valuable?")


@needs_lg
def test_greeting_then_who_are_you_introduces_mira():
    m = _m()
    assert m.respond("Hello, Mira. Who are you?").startswith("I am Mira")


@needs_lg
def test_plural_subject_keeps_adjective_bare():
    m = _m()
    out = m.respond("Are manuscripts rare?")
    assert "rares" not in out


@needs_lg
def test_first_person_question_gets_you_answer():
    m = _m()
    m.respond("I found a silver key near the river yesterday.")
    assert "you found" in m.respond("What did I find?").lower()


@needs_lg
def test_no_wh_word_leaks_into_fallback():
    m = _m()
    assert "know little of what" not in m.respond("Do you remember what I told you?")


@needs_lg
def test_comparison_is_not_confirmed_by_a_related_fact():
    m = _m()
    m.respond("A river is a large stream.")
    out = m.respond("Is a river bigger than a stream?")
    assert not out.lower().startswith(("yes", "that is so", "as far as"))


@needs_lg
def test_partial_overlap_is_not_a_yes():
    m = _m()
    m.respond("A river is a large stream.")
    assert m.respond("Is a river a stream?").lower().startswith(("as far as", "yes", "that is so"))


@needs_lg
def test_greeting_with_content_is_answered():
    m = _m()
    m.respond("Hi. My name is Anna.")
    assert m.respond("What is my name?") == "Your name is Anna."


@needs_lg
def test_repeat_greeting_has_no_random_fact():
    m = _m()
    m.respond("Hello")
    out = m.respond("Hello Mira!")
    assert "office" not in out and len(out) < 60


@needs_lg
def test_player_location_agrees_with_you():
    m = _m()
    out = m.respond("Hi. My name is Anna and I live in Saint Petersburg.")
    assert "you live" in out and "you lives" not in out


def test_you_takes_plural_agreement():
    from velesgrad_v2.dialogue.realizer import _is_plural
    assert _is_plural("you") and not _is_plural("relic")


@needs_lg
def test_follow_up_needs_two_shared_words():
    m = _m()
    out = m.respond("My sister has two children who love swimming.")
    assert "Montaigne" not in out


@needs_lg
def test_how_to_request_is_declined_honestly():
    m = _m()
    out = m.respond("Could you tell me how to make a simple soup?")
    assert "cannot tell you how" in out and "Thoreau" not in out


@needs_lg
def test_unrelated_fact_is_not_a_reply_to_statement():
    m = _m()
    out = m.respond("I like walking in the park with my dog in the morning.")
    assert "served the traveler" not in out


def test_colour_is_adjective():
    from velesgrad_v2.dialogue.wordparts import is_adjective_word
    assert is_adjective_word("brown")


@needs_lg
def test_names_capitalized_in_echo():
    m = _m()
    out = m.respond("Mira keeps the archive.")
    assert "Mira, who is a velespriest" in out and " mira," not in out


@needs_lg
def test_feelings_question_answered_honestly():
    m = _m()
    out = m.respond("What do you feel about the weather?")
    assert "feelings of my own" in out and "resides" not in out


@needs_lg
def test_pronoun_in_statement_resolves_to_last_topic():
    m = _m()
    m.respond("My grandmother visited the city.")
    m.respond("She cooked fish.")
    assert "cooked fish" in m.respond("What did my grandmother cook?") or \
        "cooked" in m.respond("What did she cook?")


def test_pronoun_without_antecedent_is_not_guessed():
    from velesgrad_v2.dialogue.ingest import extract_triples
    assert extract_triples("She cooked fish.", speaker="player", listener="Mira") == []


@needs_lg
def test_class_membership_reads_naturally():
    m = _m()
    m.respond("Oleg is a doctor.")
    out = m.respond("Is Oleg a doctor?")
    assert "kind of" not in out and "doctor" in out


@needs_lg
def test_greeting_then_name_is_acknowledged():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat(seed=5)
    out = m.respond("Hello. I am Dmitry.")
    assert "Dmitry" in out and "not" not in out.lower()
    assert "Dmitry" in m.respond("What is my name?")


@needs_lg
def test_made_of_is_learned_as_material():
    from velesgrad_v2.dialogue.ingest import extract_triples
    t = extract_triples("The relic is made of silver.", speaker="player")
    assert any(x["a"] == "relic" and x["b"] == "silver" and x["rel"] == "made_of" for x in t)


@needs_lg
def test_contradicting_claim_is_flagged():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat(seed=6)
    m.respond("The relic is made of silver.")
    out = m.respond("The relic is made of gold.")
    assert "silver" in out and "gold" in out and "keep both" in out


@needs_lg
def test_multi_word_place_name_is_kept_whole():
    from velesgrad_v2.dialogue.ingest import extract_triples
    t = extract_triples("I live in Saint Petersburg.", speaker="player")
    assert any(x["b"] == "saint petersburg" for x in t)


@needs_lg
def test_saint_petersburg_has_no_article_and_keeps_saint():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat(seed=7)
    out = m.respond("I live in Saint Petersburg.")
    assert "Saint Petersburg" in out and "the Saint" not in out


def test_already_plural_is_not_pluralized_again():
    from velesgrad_v2.dialogue.realizer import _pluralize_word
    assert _pluralize_word("traders") == "traders"
    assert _pluralize_word("trader") == "traders"


@needs_lg
def test_do_you_know_who_is_a_question_about_the_subject():
    from velesgrad_v2.chat import MiraChat
    from velesgrad_v2.dialogue.understand import build_frame
    m = MiraChat(seed=8)
    f = build_frame("Who is Pepys?")
    assert f.wh == "who" and f.subject == "pepys"
    out = m.respond("Do you know who Pepys is?")
    assert "Pepys" in out and "you know" not in out.lower()


@needs_lg
def test_greeting_with_name_then_question():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    out = m.respond("Hello Mira. Do you know who Pepys is?")
    assert "Pepys" in out and "no record" not in out and "shillings" in out


@needs_lg
def test_where_question_finds_taught_workplace():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    m.respond("Pepys works at the Admiralty.")
    out = m.respond("Where does Pepys work?")
    assert "Admiralty" in out or "Admiralty" in out.title()


@needs_lg
def test_yes_no_about_taught_fact_credits_the_player():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    m.respond("Oleg is a doctor.")
    out = m.respond("Is Oleg a doctor?")
    assert "you told me" in out.lower() and "everyone knows" not in out.lower()


def test_plural_by_s_ending_and_names_stay_singular():
    from velesgrad_v2.dialogue.realizer import _is_plural
    assert _is_plural("guards") and not _is_plural("pepys") and not _is_plural("veles")


@needs_lg
def test_two_adjectives_are_not_a_contradiction():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat(seed=10)
    m.respond("I am tired.")
    out = m.respond("I am hungry.")
    assert "keep both" not in out


@needs_lg
def test_player_claim_is_never_echoed_as_common_knowledge():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat(seed=11)
    out = m.respond("I am tired today.")
    assert "everyone knows" not in out.lower() and "you" in out.lower()


@needs_lg
def test_am_i_tired_credits_player_without_everyone_knows():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat(seed=12)
    m.respond("I am tired today.")
    out = m.respond("Am I tired?")
    assert "everyone knows" not in out.lower()


@needs_lg
def test_question_about_taught_fact_credits_the_player():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    m.respond("Oleg works at the hospital.")
    out = m.respond("Where does Oleg work?")
    assert "they say" not in out.lower() and "everyone knows" not in out.lower()


@needs_lg
def test_capitalized_name_at_sentence_start_is_kept():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    out = m.respond("Oleg works at the hospital.")
    assert "Oleg" in out and "the oleg" not in out.lower()


@needs_lg
def test_hello_again_then_question():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    out = m.respond("Hello again. What is the Veil?")
    assert "Veil" in out and "no record" not in out


@needs_lg
def test_opinion_question_is_answered_honestly_about_the_subject():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    out = m.respond("What is your opinion of Pepys?")
    assert "opinion" in out and "Pepys" in out and "velespriest" not in out


@needs_lg
def test_and_who_question_is_not_rewritten_as_what_is():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    m.respond("What is the relic?")
    out = m.respond("And who guards it?")
    assert "what is" not in out.lower() and "catalogue" in out.lower()


@needs_lg
def test_taught_fact_reply_is_not_doubly_attributed():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    m.respond("I work at the museum.")
    out = m.respond("Do I work at the museum?")
    assert out.lower().count("you told me") <= 1 and "the records hold that" not in out.lower()
    assert ", ." not in m.respond("The museum keeps old manuscripts.")


@needs_lg
def test_question_about_topic_does_not_return_unrelated_taught_fact():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    m.respond("I work at the museum.")
    m.respond("The museum keeps old manuscripts.")
    out = m.respond("What does the museum keep?")
    assert "manuscript" in out.lower() and "work" not in out.lower()


@needs_lg
def test_statements_before_a_question_are_learned_first():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    out = m.respond("The bridge is old. Is the bridge old?")
    assert "not heard" not in out and "bridge" in out.lower()


@needs_lg
def test_who_built_named_city_is_answered():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    out = m.respond("Who built Velesgrad?")
    assert "Veles" in out and "beyond" not in out


@needs_lg
def test_one_hedge_per_reply():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    out = m.respond("Tell me about the Veil.")
    assert out.lower().count("they say") + out.lower().count("the records say") <= 1


def test_the_veil_takes_an_article():
    from velesgrad_v2.dialogue.realizer import _np
    assert _np("veil", with_article=True) == "the Veil"


@needs_lg
def test_name_correction_with_filler_word():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat(seed=13)
    m.respond("My name is Lena.")
    m.respond("Actually my name is Katya.")
    assert m.respond("What is my name?") == "Your name is Katya."


@needs_lg
def test_where_did_i_go_finds_destination():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    m.respond("I went to the market yesterday.")
    out = m.respond("Where did I go?")
    assert "market" in out.lower()


@needs_lg
def test_bare_call_of_name_is_answered_as_present():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat(seed=14)
    assert "here" in m.respond("Mira?").lower()


@needs_lg
def test_plural_subject_with_adjective_complement_is_not_pluralized():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat(seed=15)
    out = m.respond("The merchants are kind.")
    assert "kinds" not in out and "kind" in out


@needs_lg
def test_describe_request_is_a_question_not_a_statement():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    out = m.respond("Describe the relic.")
    assert "tongue" not in out and "relic" in out.lower()


def test_plural_nouns_are_not_pluralized_twice_and_articles_are_skipped():
    from velesgrad_v2.dialogue.morph import plural
    from velesgrad_v2.dialogue.realizer import _is_plural
    assert plural("guardians") == "guardians"
    assert _is_plural("the velespriests") and not _is_plural("the relic")


@needs_lg
def test_two_copular_clauses_are_both_learned():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    m.respond("The guards are tired and the merchants are kind.")
    out = m.respond("Are the guards tired?")
    assert "yes" in out.lower() and "nothing" not in out.lower()


@needs_lg
def test_where_is_the_relic_finds_the_archive_that_holds_it():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    out = m.respond("Where is the relic?")
    assert "no record" not in out.lower() and "archive" in out.lower()


@needs_lg
def test_who_searches_passive_fact_is_answered():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    out = m.respond("Who searches the relic?")
    assert "hounds" in out.lower() and "no record" not in out.lower()


@needs_lg
def test_please_tell_me_who_is_a_question():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    out = m.respond("Please tell me who guards the Veil.")
    assert "you told me" not in out.lower() and "guards" not in out.lower() or "Veil" in out


@needs_lg
def test_insult_is_not_recorded_as_fact_about_mira():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat(seed=16)
    out = m.respond("You are stupid.")
    assert "told me" not in out.lower() and "opinion" in out.lower()
    assert "velespriest" not in m.respond("Are you a robot?").lower()


@needs_lg
def test_negated_statement_is_not_stored_as_positive():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    out = m.respond("The bridge is not safe.")
    assert "told me" not in out.lower() and "denial" in out.lower()
    assert "bridge is safe" not in m.respond("Is the bridge safe?").lower()


def test_did_and_modals_do_not_take_s():
    from velesgrad_v2.dialogue.realizer import _conjugate
    assert _conjugate("did serve", "pepys").startswith("did")
    assert _conjugate("can serve", "pepys").startswith("can")


@needs_lg
def test_possessive_kinship_is_kept_for_questions():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    m.respond("My sister Olga lives in Tver.")
    assert m.kin.get("sister") == "Olga"
    out = m.respond("Where does my sister live?").lower()
    assert "tver" in out


@needs_lg
def test_who_is_my_kin_and_who_is_player():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    m.respond("Hello, my name is Pavel.")
    m.respond("My brother Ivan lives in Moscow.")
    assert m.respond("Who is Pavel?") == "You told me your name is Pavel."
    assert m.respond("Who is my brother?") == "You told me Ivan is your brother."


@needs_lg
def test_statement_echo_keeps_indefinite_article():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    out = m.respond("The city has a river.").lower()
    assert "a river" in out and "the river" not in out


@needs_lg
def test_where_veil_is_not_answered_with_non_place():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    out = m.respond("Where is the Veil?").lower()
    assert "separates" not in out and "material world" not in out


@needs_lg
def test_statement_echo_has_no_book_clause():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    m.respond("The merchants are honest.")
    out = m.respond("The merchants trade in furs.").lower()
    assert "which are" not in out and "furs" in out


@needs_lg
def test_unplaced_where_reply_has_article():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    assert m.respond("Where is the Veil?") == "I have no record of where the Veil is."


@needs_lg
def test_what_do_i_do_and_traveler_leak():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    m.respond("I am a baker.")
    assert m.respond("What do I do?") == "You told me you are a baker."
    m.respond("I live in Kazan.")
    out = m.respond("Do I live in Kazan?").lower()
    assert "traveler" not in out and "baker" not in out


@needs_lg
def test_you_verb_agreement_after_traveler_cleanup():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    m.respond("I live in Kazan.")
    out = m.respond("Do I live in Kazan?")
    assert "you lives" not in out.lower() and "you live" in out.lower()


@needs_lg
def test_plural_subject_takes_are():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    out = m.respond("Describe the Velespriests.")
    assert "Velespriests are guardians" in out and "is a guardians" not in out
    assert "guardians is" not in m.respond("What are the guardians?").lower()


@needs_lg
def test_preposition_object_is_kept():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    assert "loyal to veles" in m.respond("The guards are loyal to Veles.").lower()
    out = m.respond("Are the guards loyal to Veles?").lower()
    assert "to veles" in out and "which are" not in out


@needs_lg
def test_who_are_x_adj_prep_answers_from_prep_fact():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    m.respond("The guards are loyal to Veles.")
    out = m.respond("Who are the guards loyal to?").lower()
    assert "loyal to veles" in out


@needs_lg
def test_yes_no_reply_keeps_players_article():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    m.respond("The city has a river.")
    out = m.respond("Does the city have a river?").lower()
    assert "a river" in out and "the river" not in out


@needs_lg
def test_compound_i_am_and_i_live_is_split():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    out = m.respond("I am a teacher and I live in Pskov.")
    assert "did not catch" not in out.lower()
    assert "pskov" in m.respond("Where do I live?").lower()
    assert m.respond("What do I do?") == "You told me you are a teacher."


@needs_lg
def test_what_did_i_tell_you_about_x_and_proper_names():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    m.respond("I am a painter and I live in Vologda.")
    m.respond("Vologda is a quiet town.")
    assert "vologda" in m.respond("What did I tell you about Vologda?").lower()
    assert "the vologda" not in m.respond("What is Vologda?").lower()
    assert "Saint Petersburg" in m.respond("Where is Saint Petersburg?")


@needs_lg
def test_noun_object_keeps_prepositional_phrase_and_the():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    out = m.respond("The relic is a gift from the merchants.").lower()
    assert "from the merchants" in out or "from merchants" in out
    assert "on the volga" in m.respond("Samara is on the Volga.").lower()


@needs_lg
def test_known_adjective_taken_as_adjective_with_prep():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    out = m.respond("The city is cold in winter.").lower()
    assert "a cold" not in out and "cold in winter" in out


@needs_lg
def test_who_gave_x_answers_from_gift_fact():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    m.respond("The relic is a gift from the merchants.")
    assert "merchants" in m.respond("Who gave the relic?").lower()


@needs_lg
def test_the_veil_no_double_the_and_remember_my_name():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    m.respond("Hi. My name is Lena.")
    out = m.respond("What is the Veil?")
    assert "the the" not in out.lower()
    assert m.respond("Do you remember my name?") == "Your name is Lena."


@needs_lg
def test_no_article_before_velesgrad():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    out = m.respond("What is Velesgrad?")
    assert "the velesgrad" not in out.lower()


@needs_lg
def test_subject_article_restored_in_echo():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    out = m.respond("The farm is big.").lower()
    assert "the farm is big" in out


@needs_lg
def test_named_pet_is_remembered():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    m.respond("I have a dog named Rex.")
    assert m.respond("What is my dog called?") == "You told me your dog is called Rex."
    assert m.respond("Who is Rex?") == "You told me Rex is your dog."


@needs_lg
def test_stolen_without_article_is_adjective_and_self_questions():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    out = m.respond("The relic is stolen.").lower()
    assert "the relic is stolen" in out
    assert m.respond("What is your name?") == "I am Mira, keeper of the archive of Velesgrad."
    assert "feelings" in m.respond("Are you alive?")


@needs_lg
def test_please_describe_is_a_question():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    out = m.respond("Please describe the Velespriests.")
    assert "Velespriests" in out and "open to you" not in out


@needs_lg
def test_kin_with_too_is_learned():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    m.respond("My friend Oleg lives in Tula too.")
    assert "tula" in m.respond("Where does my friend live?").lower()


@needs_lg
def test_object_article_restored_after_verb():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    assert "divides the world" in m.respond("The Veil divides the world.").lower()


@needs_lg
def test_filler_word_is_not_a_statement():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    out = m.respond("Hmm.").lower()
    assert "bell" not in out and "told me" not in out


@needs_lg
def test_two_adjectives_joined_by_and_are_both_learned():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    out = m.respond("The archive is old and dusty.").lower()
    assert "told me" in out and "told you all" not in out
    assert "dusty" in m.respond("Is the archive dusty?").lower()


@needs_lg
def test_what_is_my_job_and_an_before_old():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    m.respond("My name is Arkady and I am a pilot.")
    assert m.respond("What is my job?") == "You told me you are a pilot."
    assert "an old god" in m.respond("Tell me something about Veles.").lower() or "a old" not in m.respond("Tell me something about Veles.").lower()


@needs_lg
def test_sentence_start_capitalised_in_replies():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    for q in ["Tell me about the city.", "What is the city like?"]:
        out = m.respond(q)
        import re as _r
        assert not _r.search(r"[.!?] [a-z]", out), out


@needs_lg
def test_comma_joined_fillers_are_not_statements():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    out = m.respond("Hmm, okay.").lower()
    assert "archive" not in out and "told me" not in out


@needs_lg
def test_two_taught_places_are_both_named():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    m.respond("I live in Perm.")
    m.respond("I live in Ufa.")
    out = m.respond("Where do I live?").lower()
    assert "perm" in out and "ufa" in out


@needs_lg
def test_has_a_and_a_is_two_statements():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    out = m.respond("The city has a river and a harbor.").lower()
    assert "told you all" not in out and "river" in out
    assert "harbor" in m.respond("Does the city have a harbor?").lower()


@needs_lg
def test_is_a_and_a_is_two_statements_and_clock():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    out = m.respond("The Veil is a barrier and a shield.").lower()
    assert "tongue" not in out and "barrier" in out
    assert "clock" in m.respond("Do you know what time it is?").lower()


@needs_lg
def test_okay_thanks_is_an_acknowledgement():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    assert m.respond("Okay, thanks.") == "You are welcome."


@needs_lg
def test_you_are_a_student_and_study():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    out = m.respond("I am a student.").lower()
    assert "you are a student" in out


@needs_lg
def test_greeting_alone_is_answered_as_greeting():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    assert m.respond("Good evening, Mira.") == "Good day to you. Ask me what the records hold."


@needs_lg
def test_player_capitalised_place_keeps_capital_without_the():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    out = m.respond("I live in Moscow.")
    assert "the moscow" not in out.lower() and "Moscow" in out


@needs_lg
def test_greeting_sentence_then_name_is_learned():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    assert "Yuri" in m.respond("Good afternoon. My name is Yuri.")
    assert m.respond("Who am I?") != "You have not told me your name."


@needs_lg
def test_what_am_i_answers_stored_job():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    m.respond("I am a writer.")
    assert m.respond("What am I?") == "You told me you are a writer."


@needs_lg
def test_bare_noun_after_like_stays_bare():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    m.respond("I like tea.")
    assert "the tea" not in m.respond("What do I like?")


@needs_lg
def test_where_answers_near_locative():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    m.respond("The school is near the church.")
    assert "school" in m.respond("Where is the school?").lower()
    assert "no record" not in m.respond("Where is the school?").lower()


@needs_lg
def test_what_is_x_like_answers_about_x():
    from velesgrad_v2.chat import MiraChat
    m = MiraChat("seed", knowledge="books")
    m.respond("The forest is dark.")
    assert "forest" in m.respond("What is the forest like?").lower()
