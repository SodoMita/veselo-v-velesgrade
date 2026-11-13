# Original OpenCog tooling vs. our components — evaluated, with receipts

Rule applied: **if the original is better, use the original.** This file
records what was attempted, what broke, what is used as-is, and what
stands as our own code with the measurements that justified keeping it.

## Attempt 1 — original text→AtomSpace pipeline (lg-atomese / RelEx2Logic)

Upstream chain needed: `cogutil → atomspace → atomspace-storage → lg-atomese`
(+ Guile for the Scheme APIs through which lg-atomese is exposed).

Result: **failed, reproducibly, at atomspace-storage.** Exact blockers
encountered in this environment:

| Target | Blocking error |
|---|---|
| `opencog/persist/csv` (csv-table) | `fatal error: opencog/guile/SchemeModule.h` — Guile-disabled AtomSpace ships no such header; target also links `smob` (Guile bridge) |
| `opencog/persist/tlb` (guile-uuid) | same `SchemeModule.h` failure |
| `opencog/persist/file` (persist-file, fast_load_scm) | links `sexcom`, `smob` — Guile-only libraries |
| `opencog/persist/api` (persist) | `/usr/bin/ld: cannot find -lsmob` |
| `opencog/CMakeLists.txt` | `WRITE_GUILE_CONFIG` fails with `list index out of range` under GUILE_FOUND=0 |

Root cause: atomspace-storage hard-depends on Guile throughout; Guile 3.0.9
itself failed to build here earlier (toolchain), so every Scheme-based
OpenCog component is unavailable. **lg-atomese and RelEx2Logic are
therefore not deployable in this environment** — verified, not assumed.
(Stripping the four Guile targets was attempted; the remaining API lib
still requires `smob` at link time. Continuing would mean fabricating
Guile stubs — exactly the decorative shim anti-pattern this project
exists to avoid.)

## What IS original and IS used

| Component | Status |
|---|---|
| `liblink-grammar.so` 5.13.0 (C/C++, upstream) | used via ctypes — every parse, every grammar validation |
| English dictionary (`4.0.dict` + `words/`, upstream) | vendored, used verbatim |
| NPS Chat corpus (upstream NLTK data) | used verbatim for the act model |
| AtomSpace C++ hypergraph + C++ pattern matcher | used when compiled (bootstrap.sh) |

Our `dialogue/ingest.py` is a ~250-line logic layer *on top of the
original parser's labeled links* (`Ss*`, `Os`, `Paf`, `Pp/Js`, `OFj/Ju`) —
not a reimplementation of parsing. Same for the realizer: it consumes
LG-validated candidates.

## Attempt 2 — original sentence splitter/tokenizer instead of ours

`nm liblink-grammar.so` exports only `sentence_split(Sentence, Parse_Options)`
(per `link-includes.h:269`) — a Sentence-object method; the public C API has
no word enumeration for a split Sentence (no `sentence_get_word` in the
header; enumerate attempts segfault). A ctypes adapter that materializes the
split is not available without SWIG bindings we couldn't rebuild (SWIG got
purged from the snapshot). Verdict: **not usable here; single-sentence
ingestion stays our contract** (documented as such).

## Measured comparison of what ships

Extraction coverage, 10-shape suite (`tests/test_ingest.py`):
ours **10/10**. The alternative baseline (no parser, punctuation/regex
heuristics) reconstructs only the `X is Y` copula shapes — the LG-based
path won on structure fidelity, so ours stays.

Speech-act classification (NPS held-out, 3 session files):
trained model **80.5%** vs majority baseline 66.8% — the corpus-trained
model stays.

## Bottom line

- Original used wherever it runs: parser, dictionary, corpus, AtomSpace,
  pattern matcher.
- Original *not* used where it cannot run here: lg-atomese, RelEx2Logic,
  Scheme APIs — with the exact build failures recorded above so this is
  falsifiable, not a slogan.
- Our code covers only the gap, stays small, and is measured against
  baselines in the test suite.

## Attempt 3 — Aigents (Java) text analysis — RUN, not just read

Aigents (Kolonin, MIT license) was evaluated as an alternative text-analysis
stack. Java 11 is present in this environment, so unlike the Guile path this
was actually executed. Reproduce: `docs/compare_aigents.sh`.

What exists in the repos (cloned: `aigents-java`, `aigents-java-nlp`):

| Piece | What it is | Runnable here? |
|---|---|---|
| `cat/StringUtil.toTokens` + `BasicTokenizer` | delimiter tokenizer + token-ID storage; the basis of their 2015 "text classification and property extraction" (token-pattern mining over web/social text) | **yes** — compiled the subset, ran it (results below) |
| `al/Parser.java` | parses the *Aigents Language* (commands: find/get/…), not natural language | n/a for NL |
| `nlp/lg/` (aigents-java-nlp) | pure-Java LG **dictionary linker** research harness (Ramesh–Kolonin segmentation papers) | compiled OK; `Loader.buildLGDict` **NPEs on the stock 4.0.dict**; Segment/Generator shells out to external processes — paper harness, not a library |
| `gram/core/` | character-level n-gram memory (grammar learning from raw text) | compiles; not sentence semantics |

Measured head-to-head, same sentences as our ingest suite:

```
Aigents StringUtil.toTokens:
  "The relic lies in the tunnel." -> [The, relic, lies, in, the, tunnel]
  "The Veil-relic was kept ..."   -> [The, Veil, relic, was, kept, ...]

Ours (LG parse + RelEx2Logic subset):
  "The relic lies in the tunnel." -> {kind: eval, a: relic, b: tunnel, rel: lie_in}
  ... 10/10 shapes -> subject/relation/object triples into the AtomSpace
```

Verdict:
- **Aigents tokenization is correct but role-free** — by design it feeds
  bag-of-token *categorization* (reputation/sentiment over social media),
  not sentence→logic conversion. It cannot produce the subject/predicate/
  object triples our ingestion needs; there is nothing to swap in.
- Their **sentence→structure line (nlp/lg) targets segmentation and
  generation research**, and does not run against the standard dictionary
  in this environment (NPE; external-process dependencies).
- Their genuine strengths — social-media connectors, character-grammar
  learning for non-English scripts, high-volume document categorization —
  are real but orthogonal to the single-character chat and city sim.
- If Velesgrad ever needs web/social text mining at scale, Aigents is the
  right dependency to add (MIT); for sentence→AtomSpace, Link Grammar +
  our subset stays the measured winner (10/10 shapes vs 0 role-producing
  alternatives).

Decision: **keep ours**; Aigents recorded as evaluated-and-orthogonal,
with a reproducible comparison script in this repo.
