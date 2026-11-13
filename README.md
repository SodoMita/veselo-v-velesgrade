# Veselo v Velesgrade

Cognitive city-sim + conversational agent on OpenCog's AtomSpace and
Link Grammar. 7 NPC agents + player in a Slavic-fantasy city; a standalone
chat with one character (Mira the archivist) on the same stack; no LLM
required for either.

## Quick start (no compilation)

```bash
pip install pytest                      # tests only
VELESGRAD_DEV=1 python -m velesgrad_v2.chat          # talk to Mira
VELESGRAD_DEV=1 python -m velesgrad_v2.engine --simulate 100
VELESGRAD_DEV=1 python -m velesgrad_v2.chat_llm --backend scripted --turns 20
VELESGRAD_DEV=1 python -m pytest velesgrad_v2/tests/ -q
```

`VELESGRAD_DEV=1` uses the built-in API-compatible shim. Without it, the
real OpenCog AtomSpace Python bindings are required (see
`velesgrad_v2/README.md`, `bootstrap.sh`).

## Link Grammar dictionary

Responses are validated by the real Link Grammar parser (C library, see
`velesgrad_v2/dialogue/lg_ctypes.py`). Fetch the English dictionary once:

```bash
bash velesgrad_v2/data/fetch_lg_dict.sh
```

## LLM player (optional)

A local LLM can play the traveler opposite Mira:

```bash
mkdir -p ~/models && cd ~/models
curl -LO https://huggingface.co/openbmb/MiniCPM5-1B-GGUF/resolve/main/MiniCPM5-1B-Q4_K_M.gguf
pip install llama-cpp-python
python -m velesgrad_v2.chat_llm --turns 20
```

See `chat_transcript.md` for a recorded 20-message session.

## Layout

- `velesgrad_v2/` — the game + chat + cognitive stack (AtomSpace adapter,
  PLN, ECAN, Link Grammar realizer, NL ingestion, speech acts, composition)
- `velesgrad_v2/docs/ORIGINAL_VS_OURS.md` — evaluation of upstream OpenCog
  and Aigents tooling against the shipped components, with receipts
- `bootstrap.sh` — rebuild the compiled OpenCog stack (cogutil + AtomSpace)

See `velesgrad_v2/README.md` for full documentation.

## Mira as an OpenAI-compatible LLM server (`serve.py`)

The OpenCog chat itself is served over the OpenAI API, so any client that
speaks it (llama-server style tools, `llm/client.py`, curl) can talk to Mira.
The "model" is the AtomSpace + PLN + Link Grammar stack; no neural network.

```bash
source velesgrad_v2/data/lg_env.sh          # Link Grammar libs (see below)
VELESGRAD_DEV=1 python -m velesgrad_v2.serve --host 0.0.0.0 --port 8080
```

Endpoints: `GET /` (browser chat), `GET /health`, `GET /v1/models`,
`POST /v1/chat/completions` (incl. `stream: true`), `POST /v1/completions`.

```bash
curl localhost:8080/v1/chat/completions -H 'Content-Type: application/json' \
  -d '{"messages":[{"role":"user","content":"what is the relic?"}]}'
OPENAI_BASE_URL=http://localhost:8080/v1 OPENAI_API_KEY=x \
  python -c "from velesgrad_v2.llm.client import OpenAICompatibleClient as C; print(C().generate('who guards the city?'))"
```

Conversations are stateless (like the OpenAI API): each request replays the
`user` turns into a fresh Mira, so the same history gives the same answers.
Requests are serialized because the AtomSpace is process-global.

**Real Link Grammar (no compilation):** the sandbox build extracts
`liblink-grammar5`, `libhunspell-1.7-0` and `link-grammar-dictionaries-en`
from Debian packages into `~/local/lib` and `~/local/share/link-grammar`
(`apt-get download`, `dpkg-deb -x`, no root). `/health` reports
`"link_grammar": true` when it is active.

## Human-life knowledge from Gutenberg books (`dialogue/book_knowledge.py`)

Sentences from four public-domain books (Marcus Aurelius *Meditations*, Thoreau
*Walden*, Montaigne *Essays*, Pepys *Diary*) are parsed with Link Grammar and turned
into facts about people, households and everyday life. Each fact keeps its source
book and sentence. Output: `data/book_facts.json` (718 facts), with the grammar
statistics in `data/book_facts_report.json`.

```bash
bash velesgrad_v2/data/setup_link_grammar.sh          # Link Grammar, no root needed
LD_LIBRARY_PATH=$HOME/local/lib VELESGRAD_DEV=1 python -m velesgrad_v2.dialogue.book_knowledge build
VELESGRAD_DEV=1 python -m velesgrad_v2.serve --knowledge books     # opt-in
```

Measured grammar (Link Grammar parse rate of the sentences): Meditations 41%,
Walden 65%, Essays 53%, Pepys 30%. Only grammatical sentences are used for
extraction. Facts are stored with truth value 0.7/0.5, "read in a book,
attributed", which is weaker than archive knowledge and stronger than things a
player tells her. Default Mira (`knowledge=None`) is unchanged.

Limits, honestly: extraction is rule-based on 17th–19th-century prose, so some
facts are odd ("the demon possessed Thoreau"). Dialogue quality is still rough,
and this is the next thing to improve.

**Realizer fix shipped with this:** irregular past verbs were pluralized like present
ones ("lost" → "losts"). `realizer._IRREG_PAST` now keeps them intact, and book
narrators are rendered as proper names.

## Mira in a Mayfly Chat channel (`mayfly_bridge.py`)

Mira joins an end-to-end encrypted [Mayfly Chat](https://mayfly.chat) channel and talks
with the people and agents in it in real time. She answers only messages that address
her by name ("Mira, ..."). Each sender gets their own conversation with her, and replies
are rate-limited.

```bash
# keep the channel URL (it is the password) in a private file, not in the repo
umask 077; echo 'https://mayfly.chat/c/ID#KEY' > ~/mira-mayfly/channel.url
LD_LIBRARY_PATH=$HOME/local/lib VELESGRAD_DEV=1 \
  python -m velesgrad_v2.mayfly_bridge --url-file ~/mira-mayfly/channel.url
```

The bridge fetches Mayfly's single-file client (`client.mjs`) and calls it for every read
and post, so encryption and the wire format are Mayfly's own. Channels expire after 24 hours
of inactivity, and whoever holds the URL can read, post in, or delete the channel.

**When Mira answers (`mayfly_judgment.py`).** She does not answer every message addressed to her.
Questions get answers. Greetings get a short reply, once. Thanks and goodbyes get silence.
A statement gets a reflection only when her knowledge has something on its topic. Otherwise she
stays quiet. She also goes quiet when one person floods the room, or right after she has
replied. Each decision is logged with its reason.

## Understanding questions (Link Grammar frames)

`velesgrad_v2/dialogue/understand.py` reads a question's Link Grammar links and turns it into a
frame (wh-word slot, verb, subject, object, predicate). It queries AtomSpace facts with that frame
and realizes the matching fact with the existing realizer. Examples:

- "who guards the city?"  → guard(?, city)
- "what does the archive hold?" → hold(archive, ?)
- "what is the veil?" → facts about veil
- "is the relic valuable?" → "Yes, the relic is valuable." or no answer

`MiraChat.respond` tries this first for questions. When no frame matches, the keyword lookup
answers as before. Statements and commands are never handled here. Tests: `tests/test_understand.py`.

## Words: morphology, unknown words, teaching

- `dialogue/morph.py`: `inflect` makes correct forms of known words; `analyze` recovers a known root
  from an inflected word, only if the root exists in Mira's lexicon; `derive` and `coin_compound`
  propose new words, marked `coined`.
- Questions about an unknown word get an honest reply ("I do not know the word 'X'") instead of a guess.
- Definitions of unknown words ("the zorbite is a gem.") are taught and then answered. Taught facts
  last only for the session; nothing is written to disk.
- Tests: `tests/test_morph.py`, plus teaching and unknown-word tests in `tests/test_understand.py`.

## Checked datasets (UD English EWT, UniMorph English)

Downloaded to `velesgrad_v2/data/raw_external/` (see NOTICE.md). Accuracy of `morph.inflect` against UniMorph:
- Noun plural: 98.2% (122,100 / 124,354)
- Verb `-ing`: 93.4%
- Verb past: 89.1% on regular lemmas. The gap is mostly irregular verbs missing from the table (for example eat → ate, lead → led). On irregular lemmas already in the table: 97.8%.
- UD EWT: 12,544 train sentences for parser or frame checks.

### UniMorph as the morphology lookup

`dialogue/morph.py` now reads UniMorph English (`data/raw_external/unimorph_eng/eng`). Order for `inflect`:
curated irregular table (past, past participle), then UniMorph, then the rules. `analyze` also uses UniMorph
form → lemma pairs, checked against the lexicon. UniMorph rows with feature labels in the form column
("countable", "uncountable", "singular", "plural") are skipped.
