"""
dialogue/book_knowledge.py – Human-centred knowledge from public-domain books.

Pipeline (run once, output committed as data/book_facts.json):

  1. Read the Project Gutenberg texts in data/raw_external/gutenberg/,
     strip the PG header/footer license blocks.
  2. Split into sentences (5–25 words, plain ASCII letters).
  3. Grammar check: Link Grammar parse rate per book, reported honestly.
     Only grammatical sentences are used for extraction.
  4. Extraction: the existing rule-based RelEx-subset (dialogue/ingest.py)
     turns each parsed sentence into subject–relation–object triples.
  5. Cleanup and filter:
       - drop function words as subjects/objects ("which", "there", ...)
       - strip Link Grammar tags left on names ("marcus.m" → "marcus")
       - keep only triples about people, households and everyday life
         (HUMAN_TERMS). Trivia about machines or geography is not kept.
  6. Write data/book_facts.json with the source book and sentence for
     every fact, so Mira can say where she read it.

Loading into Mira (opt-in): MiraChat(knowledge="books") calls seed_books(),
which writes the facts with truth value 0.7 / 0.5: "read in a book,
attributed". That is weaker than her archive knowledge (0.85–0.95) and
stronger than facts a player told her (0.6 / 0.3).

Run:
    LD_LIBRARY_PATH=$HOME/local/lib VELESGRAD_DEV=1 \\
        python -m velesgrad_v2.dialogue.book_knowledge build
"""

import json
import os
import re
import sys
import time

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
GUT_DIR = os.path.join(DATA_DIR, "raw_external", "gutenberg")
FACTS_PATH = os.path.join(DATA_DIR, "book_facts.json")
REPORT_PATH = os.path.join(DATA_DIR, "book_facts_report.json")

BOOKS = [
    {"file": "pg2680.txt", "title": "Meditations", "author": "Marcus Aurelius", "id": 2680},
    {"file": "pg205.txt", "title": "Walden, and On The Duty Of Civil Disobedience", "author": "Henry David Thoreau", "id": 205},
    {"file": "pg3600.txt", "title": "Essays", "author": "Michel de Montaigne", "id": 3600},
    {"file": "pg4200.txt", "title": "The Diary of Samuel Pepys", "author": "Samuel Pepys", "id": 4200},
]

# Words that LG-extraction keeps as "content" but carry no meaning as a subject
# or object. Derived from the first extraction run (see build report).
STOP_TERMS = {
    "which", "who", "whom", "whose", "what", "that", "this", "these", "those",
    "there", "here", "it", "one", "ones", "all", "some", "many", "much", "such",
    "any", "each", "every", "other", "others", "same", "more", "most", "less",
    "few", "several", "both", "either", "neither", "none", "something",
    "nothing", "everything", "anything", "thing", "things", "way", "time",
    "times", "day", "days", "year", "years", "part", "parts", "kind", "sort",
    "little", "lot", "long", "good", "great", "small", "new", "old", "first",
    "last", "next", "two", "three", "four", "five", "ten", "twenty", "hundred",
    "chief", "point", "ideal", "end", "lad", "tlatur", "not", "also", "only",
    "now", "then", "still", "yet", "so", "too", "very", "just", "even",
    "and", "or", "but", "hath", "doth", "thee", "thou", "ye", "hither",
    "thither", "whither", "monthly",
}

# Human, household and everyday-life vocabulary. A fact is kept only if one of
# its terms is in this set. Plain words, lowercase, lemma-ish.
HUMAN_TERMS = {
    # people and roles
    "man", "men", "woman", "women", "person", "people", "child", "children",
    "boy", "boys", "girl", "girls", "father", "mother", "parent", "parents",
    "son", "sons", "daughter", "daughters", "brother", "brothers", "sister",
    "sisters", "wife", "husband", "friend", "friends", "neighbour", "neighbor",
    "neighbours", "servant", "servants", "master", "masters", "slave", "slaves",
    "guest", "guests", "lady", "gentleman", "family", "household", "lover",
    "wedding", "marriage", "widow", "soldier", "soldiers", "citizen", "citizens",
    "king", "emperor", "lord", "priest", "teacher", "teachers", "stranger",
    "neighbours", "author", "player", "archivist", "crowd", "company",
    # body, mind, feeling, character
    "body", "bodies", "mind", "minds", "soul", "souls", "heart", "hearts",
    "hand", "hands", "face", "eye", "eyes", "head", "mouth", "voice", "blood",
    "sleep", "dream", "dreams", "health", "sick", "illness", "pain", "joy",
    "love", "hope", "fear", "anger", "pride", "shame", "grief", "sorrow",
    "happiness", "pleasure", "vanity", "temper", "character", "nature",
    "passion", "passions", "desire", "desires", "conscience", "virtue", "vice",
    "reason", "habit", "habits", "custom", "customs", "manners", "opinion",
    "opinions", "memory", "thought", "thoughts", "life", "lives", "death",
    "age", "youth", "old age",
    # home, daily life, food, work
    "house", "home", "homes", "room", "rooms", "bed", "table", "bread", "food",
    "wine", "meal", "meals", "dinner", "supper", "breakfast", "kitchen",
    "garden", "door", "clothes", "clothing", "coat", "money", "work", "labour",
    "labor", "trade", "market", "shop", "tavern", "street", "streets", "village",
    "town", "city", "land", "farm", "field", "fields", "road", "journey",
    "walk", "fire", "water", "wood", "cottage", "hut", "dog", "horse",
    "letter", "letters", "book", "books", "music", "song",
    # social, moral, time-of-life
    "society", "community", "friendship", "kindness", "justice", "law", "laws",
    "duty", "duties", "politics", "government", "war", "peace", "marriage",
    "school", "education", "learning", "knowledge",
}

_NUM = re.compile(r"^[0-9ivxlc.]+$", re.I)
_TAG = re.compile(r"\.[a-z](-[a-z]+)?$")        # 'marcus.m', 'or.j-n'
_BRACK = re.compile(r"\[.*?\]")


def strip_gutenberg(raw: str) -> str:
    """Return only the book body: between the PG START and END markers."""
    start = raw.find("*** START")
    if start != -1:
        start = raw.find("\n", start) + 1
    else:
        start = 0
    end = raw.find("*** END", start)
    body = raw[start:end] if end != -1 else raw[start:]
    return body


def split_sentences(body: str) -> list[str]:
    text = _BRACK.sub(" ", body).replace("_", " ")
    # Typographic quotes/dashes → ASCII: LG warns on ’ and breaks contractions.
    for a, b in (("\u2019", "'"), ("\u2018", "'"), ("\u201c", '"'),
                 ("\u201d", '"'), ("\u2014", " - "), ("\u2013", "-")):
        text = text.replace(a, b)
    text = re.sub(r"\s+", " ", text)
    parts = re.split(r'(?<=[.!?])\s+(?=[A-Z"“])', text)
    out = []
    for p in parts:
        p = p.strip()
        words = p.split()
        if not (5 <= len(words) <= 25):
            continue
        # plain prose only: letters, spaces, common punctuation
        if not re.fullmatch(r"[A-Za-z ,;:'\"\-().!?0-9]+", p):
            continue
        out.append(p)
    return out


def clean_term(term: str) -> str | None:
    """Normalize an extracted word; None if it is not a usable concept."""
    t = _TAG.sub("", term.strip().lower())
    t = re.sub(r"[^a-z\- ]", "", t).strip()
    if len(t) < 3 or _NUM.match(t) or t in STOP_TERMS:
        return None
    return t


def is_human_fact(a: str, b: str) -> bool:
    return a in HUMAN_TERMS or b in HUMAN_TERMS


def extract_book(body: str, title: str, narrator: str, dictionary=None):
    """Run the grammar check and extraction on one book body.

    Returns (facts, stats). Each fact: {kind, a, b, rel, source, sentence}.
    """
    from .ingest import extract_triples
    from .lg_ctypes import parse_count, get_dictionary

    d = dictionary or get_dictionary()
    sents = split_sentences(body)
    stats = {"sentences": len(sents), "grammatical": 0, "triples": 0, "kept": 0}
    facts, seen = [], set()
    for s in sents:
        if parse_count(s, d) <= 0:
            continue
        stats["grammatical"] += 1
        for t in extract_triples(s, speaker="author", dictionary=d):
            stats["triples"] += 1
            a, b = clean_term(t["a"]), clean_term(t["b"])
            # first-person "I" is the book's author, by surname
            if a == "author":
                a = narrator
            if b == "author":
                b = narrator
            rel = clean_term(t["rel"].replace("_", " ")) if t["rel"] else None
            if not (a and b and rel) or a == b:
                continue
            if not (is_human_fact(a, b) or a == narrator or b == narrator):
                continue
            key = (t["kind"], a, b, rel)
            if key in seen:
                continue
            seen.add(key)
            facts.append({"kind": t["kind"], "a": a, "b": b, "rel": rel,
                          "source": title, "sentence": s})
            stats["kept"] += 1
    return facts, stats


def build(verbose: bool = True):
    from .lg_ctypes import is_available
    if not is_available():
        raise SystemExit("Link Grammar not available: source velesgrad_v2/data/lg_env.sh")
    all_facts, report = [], {"books": [], "total_facts": 0}
    for b in BOOKS:
        path = os.path.join(GUT_DIR, b["file"])
        with open(path, encoding="utf-8", errors="ignore") as f:
            body = strip_gutenberg(f.read())
        t0 = time.time()
        narrator = b["author"].split()[-1].lower()
        facts, stats = extract_book(body, b["title"], narrator)
        stats.update({"title": b["title"], "author": b["author"],
                      "gutenberg_id": b["id"],
                      "parse_rate": round(stats["grammatical"] / max(1, stats["sentences"]), 3),
                      "seconds": round(time.time() - t0, 1)})
        report["books"].append(stats)
        all_facts.extend(facts)
        if verbose:
            print(json.dumps(stats), flush=True)
    report["total_facts"] = len(all_facts)
    with open(FACTS_PATH, "w", encoding="utf-8") as f:
        json.dump(all_facts, f, ensure_ascii=False, indent=1)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    if verbose:
        print(f"facts: {len(all_facts)} -> {FACTS_PATH}")
    return all_facts


def load_facts(path: str = FACTS_PATH) -> list[dict]:
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def seed_books(aspace, facts: list[dict] | None = None) -> int:
    """Write book facts into an AtomSpace. Returns number of links written."""
    from ..cog.atomspace import (
        ConceptNode, PredicateNode, InheritanceLink, EvaluationLink,
        ListLink, TruthValue, set_tv,
    )
    facts = load_facts() if facts is None else facts
    n = 0
    for f in facts:
        if f["kind"] == "inh":
            link = InheritanceLink(ConceptNode(f["a"]), ConceptNode(f["b"]))
        else:
            link = EvaluationLink(PredicateNode(f["rel"]),
                                  ListLink(ConceptNode(f["a"]), ConceptNode(f["b"])))
        set_tv(link, TruthValue(0.7, 0.5))
        n += 1
    return n


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "build":
        build()
    else:
        print(__doc__)
