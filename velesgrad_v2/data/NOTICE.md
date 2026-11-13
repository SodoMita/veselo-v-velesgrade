# Data provenance

## NPS Chat Corpus (nps_chat.zip)
- Source: NLTK data package `nps_chat` (nltk_data GitHub, gh-pages)
- Origin: Naval Postgraduate School, released for research use
- Content: 10,567 chat posts, each hand-annotated with a dialogue-act class
  (Statement, Greet, Bye, ynQuestion, whQuestion, Continuer, ...)
- Used for: training the speech-act classifier and mining small-talk phrases.
- License: research use (as distributed by NLTK). Not for commercial redistribution.

Generated artifacts (do not edit by hand — rebuild with
`python -m velesgrad_v2.dialogue.build_chat_assets`):
- speech_act_model.json  — naive-Bayes classifier + evaluation metrics
- chat_phrases.json      — mined greetings / farewells / backchannels / "don't know" stems

## Decisions & measurements (2026-07)

Measured on the corpus (held-out = 3 of 15 session files, disjoint):

| Metric | Value |
|---|---|
| Speech-act model accuracy | **80.5%** (majority baseline 66.8%) |
| per-class | STATEMENT .80 · GREETING .98 · QUESTION .71 · FAREWELL .44 |
| Link Grammar parse rate (sample of 300 posts) | 69% |

Decisions:
1. **COMMAND is not learned.** NPS Chat has no directive class. Imperatives
   stay a heuristic whitelist; we say so instead of pretending.
2. **FAREWELL recall is weak (44%)** because Bye posts are dominated by IRC
   shorthand (brb/tc/hb/afk). Mitigation: corpus-verified parting *patterns*
   ("see you", "good night", "gotta go", "i'm off" — all present in the
   corpus with counts) are matched before the classifier runs.
3. **Realization frames were NOT mined** even though 69% of posts parse.
   The corpus is IRC colloquial — "lol the relic is stolen" is exactly the
   register corruption we refuse to ship. Frames remain hand-written and
   Link-Grammar-validated.
4. Mined small talk passes a register filter before appearing in the game
   ("well", "i see", "not sure" survive; "lmao", usernames don't).
