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
