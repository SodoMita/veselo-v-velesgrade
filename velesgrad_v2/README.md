# Velesgrad v2

Cognitive city-sim. 7 NPCs + player in a Slavic-fantasy city.
No LLM required. Dialogue is generated from the OpenCog AtomSpace
knowledge graph and validated by the Link Grammar parser.

## 300-turn autonomous simulation

```
Atoms: 7280 | Unique dialogue texts: 151 | Conversations: 242
Relic cycle: 48 takes, 48 returns — all 7 NPCs participate
Factions: hounds -0.80, veles +0.45, veche -0.15
Goal shifts: Hounds patrol (aggressive), Veles study (scholarly), Veche find_relic (desperate)
```

## What makes it work

### NPCs have agency
Each NPC has faction-specific goals (`find_relic`, `patrol_city`, `trade_gossip`,
`study_archive`, `protect_sanctum`...) and multi-step plans. They investigate,
move, take the relic, and return it — all without player intervention.

### Faction dispositions drive behavior
When Hounds disposition drops to -0.80, they patrol aggressively (priority 1.00).
When Veles rises to +0.45, they study the archive. When Veche goes negative,
they hunt for the relic to recover their fortunes. Every 10 turns, dispositions
reshape goal priorities.

### Dialogue from the knowledge graph
No templates. `AtomeseGenerator` selects atoms by attention (STI, weighted
sampling for diversity), converts them to English via structure-based
realization with multiple patterns per atom type, and Link Grammar validates
each candidate sentence, picking the most grammatical.

```
"The Hounds suspects the Velespriests, they say."
"velesgrad was founded by veles, they say."
"Word is the archive holds prophecy records."
"the sanctum contains the veil shrine."
"Everyone knows theft is betrayal."
"the thinning Veil? Dangerous, they say."
```

### PLN derives new knowledge
Seeded chains: `relic→stolen_artifact→valuable`, `hounds→enforcer→dangerous`,
`veil→magical_boundary→fragile`. PLN deduction produces 20+ derived facts;
implications produce "Whenever stolen artifact, hounds alert follows."

### Theory of Mind
Agents track what each other knows. No fact is repeated to the same listener.
Common ground is marked. Speech acts recognized (question/statement/command).

### ECAN attention economy
STI conserved during spread. Rent/wages balance. Hebbian learning between
co-present agents. LTI-based forgetting.



## Data-driven chat layer (NPS Chat corpus)

`dialogue/speech_acts.py` + `data/` use the **NPS Chat corpus** (10,567
hand-annotated chat utterances, vendored in `data/raw/`, provenance in
`data/NOTICE.md`) for the two things corpus data can honestly improve:

**1. Speech-act recognition** — replaced regex guessing with a naive-Bayes
classifier (pure Python, 148 KB artifact):

| | Accuracy (3 held-out session files) |
|---|---|
| Trained model | **80.5%** |
| Majority-class baseline | 66.8% |
| per-class | STATEMENT .80 · GREETING .98 · QUESTION .71 · FAREWELL .44 |

`COMMAND` is *not* learned — the corpus has no directive class; imperatives
stay a heuristic whitelist, and the code says so. Weak farewell recall is
patched with corpus-verified parting patterns ("see you", "good night",
"gotta go" — each counted in the corpus), not invented ones.

**2. Small talk** — greetings, farewells, backchannels and "I don't know"
stems are mined with frequencies (`data/chat_phrases.json`), then filtered
for register: "well"/"i see"/"not sure" appear in Mira's speech; "lmao" and
IRC usernames are rejected by the filter.

**What data does NOT do:** give Mira knowledge. Her facts still come only
from the AtomSpace (and PLN derivations over it). Chat corpora contain
small talk, not Velesgrad lore — the honest boundary.

Rebuild assets: `python -m velesgrad_v2.dialogue.build_chat_assets`


## Learning from text: NL ingestion (RelEx2Logic subset)

> **Original-tooling audit:** see `docs/ORIGINAL_VS_OURS.md` — the upstream
> chain (lg-atomese/RelEx2Logic via atomspace-storage) was attempted and
> fails reproducibly on a hard Guile dependency (exact errors recorded).
> The original parser/dictionary/corpus/AtomSpace ARE used; our subset
> covers only the gap and is regression-tested (10/10 shapes).

Mira *learns*. Statements you type are parsed by Link Grammar and the
labeled links (`Ss*` subject, `Os/Osm` object, `Paf` adjective, `Pp`/`Js`
prepositions) are converted into Atomese triples by `dialogue/ingest.py` —
a rule-based subset of OpenCog's RelEx2Logic (upstream lg-atomese needs an
AtomSpaceStorage build we don't ship; boundaries are documented in the
module docstring).

```
you:  the relic lies in the tunnel
Mira: Then this is true: You told me — the relic lies in the tunnel, they say.
      I will add it to the records.

you:  the bell signals danger
Mira: You told me — word is the bell signals the danger. I will add it to the records.
```

- 10/10 supported sentence shapes extract correctly (tested):
  copula+adjective, copula+noun, copula+prepositional, transitive,
  plural subject, pronoun subject (I→player, you→listener), verb+prep.
- Learned facts enter the AtomSpace with **TV 0.6/0.3** — "heard,
  unverified" — deliberately weaker than archive knowledge (0.85–0.95),
  and with high STI so they surface immediately. She attributes them:
  "You told me — …".
- Not covered (documented, tested as skipped): nested/relative clauses in
  input, passives, quantifiers, unresolved pronouns (he/she/it/they).

## Less templated responses: composition

`dialogue/compose.py` builds *new* sentences from graph structure instead
of picking one frame per atom:

- **relative clauses**: eval(S,V,O) + inh(S,X) →
  "the archive, which is a place of learning, holds ancient manuscripts."
- **reason clauses**: inh(A,B) + inh(B,C) →
  "the archive is a place of learning, since all places of learning are important."
  (that second clause is PLN-derived, then conjugated and LG-validated)
- **contrast clauses**: eval(P,S,A) + eval(P,S,B) → "…, and the merchants, too."

Every candidate — composed or framed — passes the Link Grammar validator;
the most grammatical variant wins. Composition cannot ship ungrammatical
output silently.


## LLM ⇄ Mira: 20-message conversation (`chat_llm.py`)

A local LLM plays the traveler; Mira answers with the full cognitive stack.
Each Mira reply is fed back into the model's context, so the model follows
up on what it hears. Transcript: `chat_transcript.md`.

```bash
# one-time: model (~660 MB) + backend
mkdir -p ~/models && cd ~/models
curl -LO https://huggingface.co/openbmb/MiniCPM5-1B-GGUF/resolve/main/MiniCPM5-1B-Q4_K_M.gguf
pip install llama-cpp-python          # compiles llama.cpp (~5 min first time)

# run
python -m velesgrad_v2.chat_llm --turns 20
python -m velesgrad_v2.chat_llm --backend scripted   # rehearsal, no model
```

Notes:
- Default model is **MiniCPM5-1B Q4_K_M** (official openbmb GGUF). Any GGUF
  works via `--model` (e.g. a Gemma GGUF, if you have the RAM).
- MiniCPM5 is a *thinking* model; the harness strips `<think>…</think>`
  blocks and keeps the spoken line (visible in `chat_llm.py`).
- Verified in the Arena sandbox: 2 GB RAM + 8 GB swap, CPU-only,
  `llama-cpp-python` built from source (`TMPDIR` on real disk — the sandbox
  `/tmp` is a 992 MB tmpfs, which silently ate RAM and broke the first build).

## Simple mode: chat with one character

`velesgrad_v2/chat.py` is the minimal build: a single CLI conversation with
Mira the archivist, on the same cognitive stack as the full game — AtomSpace
knowledge, PLN deduction, Link Grammar validation, Theory of Mind.

```bash
VELESGRAD_DEV=1 python -m velesgrad_v2.chat   # no compilation
python -m velesgrad_v2.chat                   # on real OpenCog
```

```
  you: hello
  Mira: Well met. Mira, keeper of the records. Ask, and I will answer what I can.
  you: is the relic valuable?
  Mira: That much I know. Everyone knows the relic is valuable.
  you: what is the veil?
  Mira: It is well known that the veil is a magical boundary.
```

Note the second turn: **"the relic is valuable" was never seeded** — Mira
derives it at startup via PLN deduction (relic→stolen_artifact→valuable),
then answers with it. She never repeats a fact, and every sentence is
Link-Grammar-validated. Commands: `facts` (what she has told you), `quit`.

Conversation capabilities (all measured by `chat_eval.py` — 10/10 turns):

| Input | Behavior |
|---|---|
| "where does the relic lie?" | spatial routing — prefers in/at/lie_in/kept_in relations |
| "who watches the streets?" | actor routing — prefers guard/patrol/suspect/member_of |
| "why is the thinning veil dangerous?" | reason routing — implication links first, read as "If …, then …" |
| "is the relic valuable?" | yes/no — confirms with truth-value hedging ("Yes. …" / "I doubt it.") |
| "is the tunnel safe?" | unknown claim → explicit refusal ("I have not heard that, and will not assert it.") |
| "the relic lies in the tunnel" | ingestion — LG triples → AtomSpace, acknowledged ("You told me — …") |
| "where is it?" | pronoun resolution — "it" → last discussed/learned concept |
| multi-sentence input | split, each sentence ingested |
| "tell me about the archives" | plural normalization — archives→archive |

Run the report yourself: `python -m velesgrad_v2.chat_eval`

## Run

```bash
# On the REAL OpenCog AtomSpace:
export LD_LIBRARY_PATH=/home/user/local/lib:/home/user/local/lib/opencog:$LD_LIBRARY_PATH
python -m velesgrad_v2.engine --simulate 300
# → 300 turns: 1044 atoms in the real C++ hypergraph,
#   238 conversations, 170 unique LG-validated texts,
#   49 relic takes / 47 returns by all 7 NPCs,
#   TVs persisted in the real AtomSpace (relic→stolen_artifact = TV(0.95, 0.90))

# Development mode (built-in shim, no compilation):
VELESGRAD_DEV=1 python -m velesgrad_v2.engine --simulate 100

# CLI:
VELESGRAD_DEV=1 python -m velesgrad_v2.cli

# Single action (auto-saves state):
VELESGRAD_DEV=1 python -m velesgrad_v2.act "go tavern"
VELESGRAD_DEV=1 python -m velesgrad_v2.act "talk Yuri"
VELESGRAD_DEV=1 python -m velesgrad_v2.act "ask Yuri relic"
```

CLI commands:
```
go <room>     | look        | talk <npc>
ask <npc> <t> | take <item> | return <item>
investigate   | cast <spell> | wait
who           | status      | facts
goals         | history     | map
save/load     | quit
```

## With real OpenCog

```bash
export LD_LIBRARY_PATH=$HOME/local/lib:$LD_LIBRARY_PATH
export PYTHONPATH=$HOME/local/lib/python3.13/site-packages:$PYTHONPATH
python -m velesgrad_v2.engine --simulate 100
```

If OpenCog is not installed, the system exits with build instructions
(unless `VELESGRAD_DEV=1`).

## Real OpenCog integration (working)

The game now runs on the **real OpenCog C++ AtomSpace** with the modern
value API:

- `set_thread_atomspace(asp)` binds type constructors to our atomspace
- Truth values are real `FloatValue`s under `tvkey` in the hypergraph
- STI/LTI are FloatValues under custom keys
- Atom equality/dedup is the real C++ handle equality (1044 unique atoms
  vs 4948 shallow copies in the dev shim — the hypergraph dedupes)

The adapter (`cog/atomspace.py`) exposes `get_tv(atom)/set_tv(atom, tv)` +
`get_sti/set_sti` which work identically on both paths. All 43 tests pass
on **both** the real OpenCog and the dev shim.

## Compiled from source (rebuild with ./bootstrap.sh)

| Component | Status |
|-----------|--------|
| Link Grammar 5.13.0 | Built (C lib + ctypes wrapper + dictionary) |
| cogutil 2.2.1 | Built |
| AtomSpace | Built (Python bindings) |
| SWIG 4.2.1 | Built |
| flex 2.6.4 | Built |
| libgc 8.2.8 | Built |
| libunistring 1.2 | Built |

The Link Grammar path is fully working: the ctypes wrapper (`dialogue/lg_ctypes.py`)
loads `liblink-grammar.so` and validates every dialogue sentence against the
real English grammar dictionary. Non-grammatical candidates are rejected.

## Architecture

```
velesgrad_v2/
  cog/
    opencog_gate.py   # Real OpenCog or dev shim
    atomspace.py      # AtomSpace, TV, AV, attention
    pln.py            # Deduction, MP, TMS
    ecan.py           # Conserving STI economy
    psi.py            # Demands, goal selection
    planner.py        # Multi-step plans
  agents/
    agent.py          # Unified agent loop
    cognition.py      # Goal-driven behavior + faction dispositions
  dialogue/
    tom.py            # Theory of Mind, conversation memory
    realizer.py       # Atomese → English (multiple patterns, LG-validated)
    lg_ctypes.py      # Link Grammar ctypes wrapper
  world/              # time, model, factions, magic
  story/director.py   # Thread tension
  content/city.py     # World map + roster
  tools/registry.py   # 6 action tools
  engine.py           # Main loop, save/load
  cli.py              # Interactive CLI
  act.py              # Single-action executor (auto save/load)
  tests/              # 43 tests, all passing
```

## Known limitations

- NPC dialogue is knowledge-graph driven but the knowledge base is finite;
  after ~300 turns themes repeat (decay helps)
- Story threads evolve tension but don't yet force plot events
- The real OpenCog Python path needs a `.tv` adapter (dev shim handles
  values natively; real AtomSpace value-set API differs)
- Guile/Scheme bindings not built (AtomSpace built without them)
