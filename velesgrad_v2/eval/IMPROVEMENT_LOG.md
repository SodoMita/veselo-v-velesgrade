# Improvement log — understanding round

Each entry: what was broken, what changed, commit.

## Fixed this round
1. "why is X adj?" returned the direct fact → chains through intermediates now (inference.proof). `6dbcb55`
2. Plurals in chains: "stolens artifact" → "stolen artifacts" (head noun pluralized). `6dbcb55`
3. ancestors() dropped routes via a global seen-set → per-route cycle guard. `6dbcb55`
4. "What is the relic?" → full chain, not one stored class. `6dbcb55`
5. "How are you?" was answered with a fact about Mira → small-talk reply. `873d535`
6. "How do you say hello in French?" → keyword nonsense → honest refusal. `873d535`
7. "What are relics?" answered with where Mira lives (self-branch matched any "what are") → self-answer only for "you". `873d535`
8. "Word is pepys gives…" ungrammatical template → "The records hold that …". `873d535`
9. Function words (you, how, say…) counted as unknown words. `873d535`
10. "Bye!" locked the channel forever → a later message reopens it. `a5129b7`
11. "What do you know about X?" self-description → topic question. `a5129b7`
12. "Where is the archive?" gave a class chain → chains answer "what/who" only; no record → says so. `eca4e06`
13. Proper names lowercased ("velesgrad is") → capitalized. `a5129b7`
14. "relicness" split as re- + licness → suffix-first split. `70109b0`
15. Wiktionary headwords (fragilely, stolenness) treated as known → still split when Mira lacks them. `70109b0`
16. "What is a fragilely?" → word-part answer. `70109b0`
17. "The lantern is a light source" learned as "source" → noun compounds kept (A/AN links). `edb4964`
18. "The veil is fragile" not learned (Pa link ignored) → Pa handled. `edb4964`
19. "Why?" after an answer → explains the last claim. `edb4964`
20. "Is it valuable?" → pronoun resolved to "is relic valuable" (unparseable) → "is the relic valuable". `edb4964`
21. "Do you remember the lantern?" refused → topic answer. `edb4964`
22. "The sky is blue." treated as a question (no "?") → learned as statement. `b1efcab`
23. "a blue" wrong article → adjective check uses Wiktionary POS. `b1efcab`
24. Replies starting lowercase → capitalized. `b1efcab`
25. "I am tired." echoed as "the traveler is tired" → "you are tired". `af1f0b8`
26. "Can you help me?" / "Tell me something interesting" / "opposite of X" → direct replies. `b1efcab`, `eca4e06`

## Known open flaws (next round)
- "Who keeps the archive?" → answers with Mira's residence (no keeper relation).
- "Is a relic a sacred object?" → "it is well known that the relic is something sacred" (kind-of phrasing).
- "Am I tired?" → "archive holds nothing" (first person in yes/no not mapped to player).
- "Who wrote Pepys's diary?" → "diary" unknown; possessive not parsed.
- "What is a knowledge repository?" → "is important" without the chain sentence.
- Keyword fallback still produces odd facts for unparsed questions.
- Word learning: taught facts are not used by "why" chains.

## Not done in this round
- Push: the repo has no git remote configured; nothing could be pushed.
- Mayfly channel: not running; the 20-minute wait was not re-run.

## Interactive round 1 (one message per call, session_server.py)
Setup bug found first: sandbox restore dropped the libhunspell soname link, so Link Grammar was
silently unavailable and conversation 1 ran with no parser. Fixed in lg_env.sh (commit "lg_env: ..."),
then conversation 1 was replayed.
Flaws found and fixed:
- "Hello, Mira. Who are you?" → residence fact. Now self-introduction anywhere in the message.
- "manuscripts are rares" (plural applied to adjective). `_pluralize_pred` leaves adjectives alone.
- "I know little of find/what" (wh-word and verb leaking into topic). `_TOPIC_STOP` list.
- "the traveler found the key" (player not shown as "you"). Eval sentences use "you" for the player.
- "What did I find?" → "no record". "I" in questions now maps to the stored `player` concept.
- "Do you remember what I told you?" → random book fact. Now recalls the last learned statement.
Open (not fixed yet):
- Book-extraction noise: "Pepys puts on the yesterday" (temporal word as object). Needs a filter at build time.
- "Is the relic dangerous?" → "archive holds nothing" vs. "I have not heard that" — two wordings for the same state.

## Interactive round 2 (fresh session, everyday topics, 11 messages)
Fixed:
- Yes/no fallback confirmed "Is a river bigger than a stream?" with "That is so" from a related fact.
  Now a confirmation needs the stored fact to cover every content word; negated questions are not confirmed.
Open:
- Ditransitive statements ("My brother gave two apples to his friend") are not learned.
- Relative clauses in definitions are dropped ("a stream of water that flows to the sea" → "a large stream").
- Book noise in keyword fallback: "the empperor writes to the friend" (typo from Gutenberg extraction).
- "Pepys met the evening", "Pepys puts on the yesterday": temporal words as objects; filter at build time.
- Negated question "A stream is not a river, is it?" gets a positive fact back.
- Unknown plural nouns ("apples") are reported as unknown words even when the singular is near-known.

## Interactive round 3 (partial, session_server, 4 messages before a restart)
Fixed:
- "Hi. My name is Anna…" → greeting swallowed the statement. Greeting+content is answered; name remembered; "What is my name?" answered.
- "Where do I live?" → unrelated fact. "I live in Saint Petersburg" is now learned ("you live in Petersburg").
- "you lives" → "you live" (plural agreement for "you").
- "What did I find?" → "you found the silver key" (irregular past tenses now match their lemma in questions).
- Repeat question said "the dog served the traveler": first-person parse now uses "I" (the grammar cannot parse "player").
- Repeat greeting attached random book fact: removed.
- Double hedge "The records say: You told me —…, they say.": lead removed.
Open:
- Who found the silver key? → "I do not know the word 'silver'" (adjective of a stored object is not treated as known).
- Book noise still leaks ("Montaigne plays with the cat", "Pepys took the sir").
- Ditransitive "gave X to Y" not learned.

## Repo note
The sandbox restore rolled back git history: commits 6dbcb55 … eca4e06 from earlier in the session are not in the current log (HEAD chain now starts from ef75938 on this branch). Working-tree code from those commits was mostly kept; the ingest compound change was lost when ingest.py was checked out and was re-applied in 4ba1d7f.

## Interactive rounds 4–8 (session_server, one message per call, 10+ messages per conversation)
Fixed (commits c3ca755 … 2e717f7):
- "Hello. I am Dmitry." → deflection; now acknowledged. Punctuation-only remainder is not a message.
- Pronouns she/he/it/they resolve to the last topic in statements and questions ("My grandmother visited the city." then "She cooked fish."). Dropped when no antecedent.
- "X is made of Y" learned as material (Pv copula-preposition and Ou object links; relation made_of).
- "Saint Petersburg" kept whole (GN proper-name link); no article before place names.
- Mid-sentence and sentence-initial capitalized names are kept proper; imperatives ("Name a sacred object.") are not names.
- "Do you know who X is?" read as the embedded question; copula order fixed ("Who is Pepys?").
- "Hello again. What is the Veil?" and "Hello Mira. Do you know…" are no longer blocked by the greeting.
- Taught facts outrank recorded ones for where/what questions; "work_at" counts as a place; taught facts need two shared stems to answer.
- Contradicting place/job/material claims are flagged ("You said museum before, and now library. I will keep both…"); adjectives are not contradictions.
- Yes/no and wh answers about taught facts say "You told me …", never "everyone knows" or "they say".
- Player's claims are not echoed as common knowledge; no doubled "You told me —"; no stray ", .".
- Plural subjects by -s take plural verbs ("guards are loyal"); already-plural nouns are not pluralized again ("traderses").
- "a kind of doctor" → "a doctor" in yes/no replies.
- "Name a sacred object." no longer yields "I know little of sacred".
- Opinion questions ("What is your opinion of Pepys?") get an honest reply about the subject.
- "And who guards it?" is a question, not an "and the X" follow-up; "it" resolves to the topic.
- Unknown-word reply also says there is no record of the thing asked.
Open:
- "Is the relic stolen?" answers from the book and does not flag the player's conflicting "gift from the merchants".
- Multi-clause statements lose their second clause ("He works at the Admiralty" after a first clause).
- "in the market" / "from the merchants" / "loyal to Veles" prepositional objects after adjectives or transitive verbs are dropped.
- "Who found the relic?" → answers with who seeks it (no "found" relation in the records).
- "Where do I work?" after two contradicting claims returns only one of them.
- "Veil" lacks its article in some replies ("Everyone knows Veil is…").
- "Are manuscripts rare?" → "archive holds nothing" (records say "irreplaceable"; rare is not a recorded synonym).
- Echo of a taught fact can pull in a book clause ("the relic, which is a stolen artifact, made of silver").

## Interactive rounds 9–20 (session_server, one message per call, 10+ messages per conversation)
Fixed (commits 1f0d11c … 7a62109):
- Plurals: no "guardianses"; already-plural nouns unchanged; articles skipped when agreeing a plural subject (1f0d11c).
- Compound statements with two copular clauses are split and both learned (305ea8c); and before "I/he/she/they + verb" ("I am a teacher and I live in Pskov", 0c1c266 / e8067b7).
- "Where is X?" matches locative and "holds" facts (3872c5f); locative match is on whole words, so "separates" is not "at" (4d776d2). An unplaced "where" says so ("I have no record of where the Veil is.") instead of an unrelated fact.
- "Who searches X?" matches passive "X is searched by Y" facts (56e1f04).
- "Please tell me who/what X" is a question (679f499).
- Insults are not stored as facts about Mira; "are you a robot" answered honestly (798f1d8).
- Negated statements are not stored as positive facts; she says she cannot record a denial (9239690).
- Auxiliaries (did, can, will...) never take a third-person s: "Pepys did the service" (f75fe0b).
- Kinship: "my sister Olga lives in Tver" learned as Olga; "my sister" in questions resolves to her; "Who is my brother?" answers from the kin map; "Who is Pavel?" answers the player's name (5288e80, 1fd9f7a).
- Articles: the statement echo and yes/no replies keep the player's "a river" (70b52eb, 3591803) and "the Volga"; player-introduced names lose a stray "The" (0c1c266).
- "What do I do?" answers from the stated occupation; "What did I tell you about X?" answers about X (55ffe34, 0c1c266).
- Reply cleanup for all paths: "the traveler, who is X," and "guards, which are loyal," book clauses are removed; "you" takes the base verb ("you live"); plural subjects take "are" ("The Velespriests are guardians") (55ffe34, df43d12, 84ee5a7, 41ce44e).
- Prepositional objects are kept: "The guards are loyal to Veles", "The relic is a gift from the merchants", "Who are the guards loyal to?", "Who gave the relic?" (603b587, 73f3e03, b512aee, 9c411e7).
- Known adjectives parsed as nouns are adjectives: "the city is cold in winter" (41ce44e).
- "Do you remember my name?" answers the stored name (7a62109).
Open:
- "Where does Anton live?" names only one of two contradictory taught places.
- "Does my brother live in Moscow?" depends on the kin map; questions that name a person ("Where does Nadia live?") fail when Nadia was given only as the player's own name.
- "Is Vologda in Russia?" → "archive holds nothing" (no record of the Russian capital; expected).
- "Tell me something interesting." still gives book noise ("Pepys heard the conference").
- A second clause without copula ("they fight well") is not learned.
- Yes/no answers about taught objects drop the article ("Yes, you told me that the city has the river").
- The "is_" prepositional relation renders without its article ("a gift from merchants").

## Interactive rounds 21–24 (session_server, one message per call)
Fixed (commits 227b6b6 … e0ac5d4):
- No article before Velesgrad, Veles, Pepys, Mira, Petersburg in replies (227b6b6).
- Clause-initial subject keeps the player's "the" in echoes ("the farm is big") (8c07c35).
- "I have a dog named Rex" learned as "Rex is a dog"; "What is my dog called?" and "Who is Rex?" answered from the kin map (5e97cde).
- "The relic is stolen" is an adjective statement, not "a stolen" (93560b0); "stolen", "broken", "lost", "sealed" and similar are adjectives in the realizer.
- "Are you alive?" and "What is your name?" answered honestly (93560b0).
- "Please describe X" is a question about X (cbefda4).
- Kinship sentences ending in "too" are learned ("My friend Oleg lives in Tula too.") (e0ac5d4).
- Fix for a regression: "What is the Veil?" gave "The the Veil" (fixed before commit 7a62109).
Open:
- "Lev" as a name fails to parse (Link Grammar treats it as a currency or unknown word); "Oleg" works.
- "Who keeps the archive?" has no recorded answer.
- "The Veil divides the world." echoes as "divides world" (article dropped in an object).
- "What is ancient?" answers with "city is ancient" (no adjective-only answer).

## Interactive rounds 25–30 (session_server, one message per call)
Fixed (commits 084c3bc … latest):
- Object article restored after a verb in echoes ("divides the world"); reply's first letter and sentence starts capitalised.
- Filler words ("Hmm.", "Hmm, okay.") and acknowledgements ("Okay, thanks.") get short replies, not statements or fallbacks.
- "X is old and dusty", "X is a A and a B", "X has a A and a B" are two statements; possessions are not contradictions.
- "What is my job?", "What time is it?" answered honestly; "a old" → "an old".
- "Where do I live?" names every taught place ("You told me you live in Perm, and also in Ufa.").
- "I am a student." echoes "you are a student" (player's article restored).
Open:
- "I study history" echoes "you studies history" in one flow (the -ies fix in respond does not reach that reply; not diagnosed).
- "The forest is dark and quiet" learns "dark" only in the echo; "quiet" is learned but "What is the forest like?" has no answer.
- "Lev" as a name fails to parse; "I have a horse named Grom" works.
- "The merchants trade in silk and spices." → fallback: a list of prepositional objects ("in A and B") is not split.
- "Can you name a river?" → "The archive is glad to help." (a request for a name is not recognised; expected fallback is "I have no record").
- Round 36 (`c763176`): "I live in Moscow." → "You told me — you live in Moscow." fixed. But after "I am a painter and I live in Riga." then "Where do I live?" → "You told me — you live in the moscow." Riga is stored (confirmed by "Do I live in Riga?") yet is missing from the multi-place answer (all_claims). Open: the single-place answer path lowercases the stored place.
- "Tell me something interesting." → "The records hold that Thoreau lives in the angle." (book noise; open).
- "Is the forest dark?" after "The forest is quiet." → "The archive holds nothing on that claim." (correct as fallback).
- Round 37: "Good afternoon. My name is Yuri." lost the name ("name is Yuri") and "Who am I?" then failed. Fixed: a greeting sentence (ended by "." or "!") before a real sentence is dropped. Test added.
- Open: "The tower is tall and old." learns only "tall"; "What is the tower like?" has no answer.
- Open: "I am a sailor." then "What am I?" → fallback.
- Round 38 (`c78617b`): "Good afternoon. My name is Yuri." → name learned; "Who am I?" → "Your name is Yuri." (fixed). "The bridge is broken." → "Is the bridge broken?" → yes; "Who built the bridge?" → fallback (correct).
- Open: "The gate is locked at night." → "I have told you all I can." (the statement is not learned; "gate" is not in the vocabulary, so the reply is a generic fallback). "When is the gate locked?" → "I do not know the word 'gate'" (the vocabulary gap is confirmed).
- Open: "The priest is wise and kind." learns only "wise" (two adjectives with "and" are not split here, unlike the "is a A and a B" path).
- Open: "I do not like rain." → "I cannot record a denial yet" (the denial is not stored; "Do I like rain?" → fallback).
- Round 39 (`dd19e44`): "Hi Mira. My name is Lena." / "I am a doctor." / "I live in Samara." / "Do I live in Samara?" all correct. Open: "The hospital is near the river." is stored, but "Where is the hospital?" → "I have no record of where the hospital is." The "near X" locative is not answered (same for "The old bridge is near the market." → "Where is the old bridge?").
- Round 39: "Greetings, Mira. I am Denis." / "I work at the bakery." / "Where do I work?" / "Is the bakery warm?" correct. "Do you remember my name?" → "Your name is Denis." correct.
- Round 40 (`c6c4877`): "Hello Mira. I am Boris." / "I have a sister named Vera." / "Who is my sister?" correct. Open: "Where is the tower?" after "The tower is old." → "no record" (locative gap, same as round 39).
- Round 40: "I am a farmer and I live in Tver." → only "you are a farmer" is confirmed; the "I live in Tver" clause is lost in the compound (later "Where do I live?" → "Tver", so it is stored; the reply omits it). Open: "The merchants sell grain and wine." → learns only "grain" (same two-object gap).
- Open: "Do I live in Tver?" → "As far as the records say, yes. You told me — you live in Tver." (the hedge phrase is still in the yes/no path).
- Open: "Does the merchant sell wine?" → "I have not heard that, and will not assert it." (the "wine" fact was not stored, see above).
- Round 41 (`af5f66a`): "Good morning. I am Galya." / "I have a parrot named Kesha." / "Who is my parrot?" correct; "The city has a market and a temple." → "Does the city have a temple?" yes (fixed-looking). Open: "The river is cold and deep." learns only "cold"; "What is the river like?" → fallback (adjective-question gap).
- Round 41: "Oleg" name, "I am a guard.", "The gate is open." → "Is the gate open?" yes. "The relic is stolen." → "Who stole the relic?" → "an unknown thief". Open: "Who keeps the archive?" → book noise ("knowledge repository") instead of a record.
- Round 41: "I work at the library." / "Is the library dusty?" correct. Open: "The library is quiet and dusty." learns only "quiet" in the echo path; "What is the library like?" → fallback.
- Round 42 (`afd081a`): "I live in Perm." then "I live in Ufa." → both kept; "Where do I live?" → both named (correct). "The sky is clear tonight." → "Is the sky clear?" yes. "Who am I?" → name.
- Round 42: "Good evening. My name is Mila." / "I have a horse named Bulat." / "The guards are brave and loyal." → "Are the guards loyal?" yes (correct).
- Open: "I study music at the conservatory." → "you study the music" (the place "conservatory" is dropped and "the" is inserted before "music"). Same for "The conservatory is near the square." → "Where is the conservatory?" no record (near-locative gap, see round 39).
- Open: "The temple is old and silent." learns "old" and "silent" correctly in the yes/no path.
- Round 43 (`279d3b3`): "Good day, Mira. My name is Kirill." / "I am a fisherman." / "The lake is calm in the morning." → "Is the lake calm?" yes; "I have a brother named Ilya." → correct. All correct.
- Round 44: "I am a nurse and I live in Pskov." → "Do I live in Pskov?" → "As far as the records say, yes. You told me — you live in Pskov." (hedge still in yes/no path; open).
- Open: "I have a hobby. It is chess." → "What is my hobby?" → "You told me — you have the hobby." (chess is dropped; "the hobby" not "a hobby"; open).
- Open: "The bells ring at noon." → "You told me — the bells ring at the noon." (article inserted before "noon"; open).
- Open: "Tell me something interesting." → "The records hold that Pepys played the echo." (book noise; open).
- Round 45 (`cac48fa`): "Hello, I am Pyotr." / "I live in Omsk." / "Where do I live?" / "I have a goat named Masha." / "The field is green." all correct. "Good night, Mira." → farewell.
- Round 46: "My name is Edik. I am a cook." → name not confirmed in the reply (only the cook part is echoed); the name is stored ("What is my name?" → Edik). "What am I?" → "I have no record of that." (open: "What am I?" after "I am a X" fails; "Who am I?" works for the name only.)
- Open: "Do I work in a kitchen?" → "I have not heard that" (the "kitchen" fact was never claimed as work, so this fallback is expected).
- Open: "What is the kitchen like?" → "That is beyond what the records hold." (adjective-question gap, see round 41).
- Round 47 (`d3568dc`): "Good morning. I am Stepan." / "I have a son named Pasha." / "The gate is locked." / "Is the gate locked?" / "The merchants are honest." → all correct.
- Round 48: "Hi Mira. My name is Kseniya." / "I am a designer." / "I live in Yaroslavl." / "The bridge is long." → all correct. "Who am I?" → name.
- Round 49: "I study law at the academy." → "you study the law" (academy dropped, "the" inserted; same defect as round 42 with music). "The academy is old." → "Is the academy old?" yes (correct).
- Open: "Who are the Velespriests?" → "Everyone knows the Velespriests are guardians." (wording of the book path; acceptable but noisy).
- Round 50 (`ac328e6`): "Hi. I am Nadia." / "I work at the post office." / "Where do I work?" correct. Open: "The post office is busy." → "You told me — post office is busy." (article dropped in the echo for a two-word noun; the yes/no path also gives "post office is busy").
- Open: "I like tea." → "You told me — you like the tea." (an article is wrongly added before the mass noun "tea"; object-article restore after verbs over-applies).
- Round 50: "My name is Timofey. I am a mechanic." / "The engine is loud." / "Is the engine loud?" correct. Open: "What am I?" → fallback (same as round 46); "What is the engine like?" → fallback (adjective gap).
- Round 50: "I live in Kursk." / "Do I live in Kursk?" → hedge "As far as the records say, yes." (open).
- Round 51 (`10aa461`): "Hello. I am Maxim." / "I am a driver and I live in Vologda." / "Where do I live?" / "The road is long and empty." / "Is the road empty?" / "Do you remember my name?" all correct.
- Open: "I have a garden." → "You told me — you have the garden." (the article "a" after "have" is dropped; the "the" is inserted instead. Same family as "I like tea", round 50.)
- Open: "The temple is quiet." → "Where is the temple?" → "I have no record of where the temple is." (locative gap; "Where is X" is not answered when X has an adjective-only fact).
- Round 51: "Greetings. My name is Tamara." / "I have a cat named Pushok." / "The priests are wise." / "Who are the priests?" correct.
- Round 52 (`e024106`): "Hi Mira. I am Anya." / "I am a pharmacist." / "I live in Ryazan." / "Where do I live?" / "The medicine is strong." / "Is the medicine strong?" / "Who am I?" all correct.
- Round 52: "I study physics at the institute." → "you study the physics" (the place "institute" is dropped and "the" is wrongly inserted; third instance of the "study X at Y" defect after music and law). "The institute is big." → "Is the institute big?" yes.
- Round 53 (`1b1a827`): "Good afternoon. I am Nikolai." / "I have a truck named Zhora." / "Who is my truck?" / "The bridge is safe." / "Is the bridge safe?" correct.
- Open: "The guards are loyal and brave." → echo confirms only "loyal", but "Are the guards brave?" answers "Yes" (the "brave" fact from the compound is probably not stored, and the yes/no path may answer from a different fact; needs diagnosis). "The guards are brave." on its own → "Are the guards brave?" yes (correct).
- Round 54 (`2cab90b`): "Hi, my name is Svetlana." / "I am a librarian." / "The archive is dusty." / "Is the archive dusty?" correct. Open: "What am I?" → fallback (same as rounds 46 and 51).
- Open: "I live in Tomsk and I work at the mill." → only "you live in Tomsk" is confirmed; the "work at the mill" clause is lost (second clause of an "and I ..." compound is dropped). "Where do I work?" → "Tomsk" (wrong).
- Round 55 (`2bc5c0d`): "Good day. My name is Arkady." / "I am a sculptor." / "The statue is tall." / "Is the statue tall?" / "The Velespriests are old." / "Are the Velespriests old?" / "What is my name?" all correct.
- Round 56: "Hi Mira. I am Kostya." / "I have a dog named Bim." / "Who is my dog?" correct. Open: "The forest is quiet." → "What is the forest like?" → fallback (adjective-question gap).
- Open: "The merchants trade in silk." → "You told me — the merchants trade in the silk." (the article is inserted before "silk"; the "in X" object of "trade" over-applies the object-article rule, same family as "I like tea" and "study the physics").
- Round 57 (`8b88246`): "Hello, I am Lilia." / "I am a poet." / "I live in Penza." / "Do I live in Penza?" / "The river is wide and cold." / "Is the river cold?" / "Who am I?" all correct (the second adjective is stored, though the echo shows only "wide").
- Open: "I have a job at the port." → "Where is my job?" → "I have no record of where the job is." (locative with "at X" for a "have a job" fact; "at the port" is not in the reply).
- Round 57: "The port is busy." → "Is the port busy?" yes (correct). "What is the port like?" → fallback (adjective-question gap).
- Round 58 (`2fa0eca`): "Hello Mira. My name is Oksana." / "I am a painter." / "The studio is bright." / "Is the studio bright?" / "Do you remember my name?" correct.
- Open: "I am a painter." → "What do I do?" → "You told me you are a painter." (acceptable; the correct answer form).
- Round 58: "Good morning. I am Pavel." / "I have a sister named Vera." / "The kitchen is clean." / "The Velespriests are kind." / "Okay, thanks." → "You are welcome." all correct.
- Round 59 (`0f682a5`): "I live in Kaluga." / "Where do I live?" / "I am a teacher." / "What do I do?" correct. Open: "The school is near the church." → "Where is the school?" → "I have no record of where the school is." (near-locative gap, rounds 39 and 40).
- Round 59: "Good evening. My name is Grisha." / "I have a horse named Groza." / "Who is my horse?" / "The merchants are rich." / "Are the merchants rich?" correct.
- Open: "What is ancient?" → "You told me — city is ancient." (the article is dropped and the answer picks an unrelated fact; open since round 15).
- Round 60 (`2c56a0f`): "Hi Mira. I am Denis." / "I have a parrot named Kesha." / "Who is my parrot?" / "The wall is high." / "Is the wall high?" / "I am a builder." / "What do I do?" all correct.
- Round 61: "Hello. I am Ruslan." / "I live in Ulyanovsk." / "Do I live in Ulyanovsk?" → hedge "As far as the records say, yes." (open).
- Open: "The bells ring at night." → "the bells ring at the night" (article inserted before "night"; the "at X" object over-applies the same rule as "in the silk" and "at the mill").
- Open: "Who keeps the archive?" → "I have no record of that." (open since round 41).
- Round 62 (`03ce628`): "Good day. My name is Yulia." / "I am a nanny." / "The garden is lovely." / "Is the garden lovely?" correct. Open: "What am I?" → fallback (see rounds 46, 51, 54).
- Round 63: "Hi Mira, I am Vitaly." / "I live in Orel." / "Where do I live?" / "The lab is clean." / "Is the lab clean?" correct. Open: "I live in Orel and I study chemistry." → "you study the chemistry" (the "study the X" defect), and the "live in Orel" clause is confirmed only via the other statement.
- Round 64 (`8b9ccc2`): "Hello. I am Ilya." / "I have a brother named Oleg." / "Who is my brother?" / "The tower is broken." / "Is the tower broken?" correct. "Who are the guards?" → fallback (no guard facts in this session).
- Round 65: "Hi, I am Gleb." / "I am a hunter." / "What do I do?" / "Okay, thanks." → "You are welcome." correct. Open: "The forest is dark." → "Where is the forest?" → "I have no record of where the forest is." (locative gap again).
- Round 66: "Good afternoon, Mira. I am Anna." → "you are a Anna", name lost (the comma-after-greeting was not dropped). Fixed: the greeting may be followed by ", Mira" and a comma; "Good evening, Mira." alone still gets the greeting reply. 233 tests pass.
- Round 66: "I am a writer and I live in Pskov." → "Where do I live?" → Pskov; "The library is old." → "Is the library old?" yes; "What am I?" → fallback (open).
- Round 67 (uncommitted, repo HEAD e2a3106 with separate changes): "What am I?" answers the stored job. "I like tea." → "What do I like?" → "you like tea" (no "the"). "I have a garden." keeps "a garden" in later answers. "The school is near the church." → "Where is the school?" answers (the "near" relation is a place; wh-words no longer count as content words). "What is the archive like?" answers as "What is the archive?". 237 tests pass.
- Open: "Who keeps the archive?" with no taught fact → fallback (expected).
