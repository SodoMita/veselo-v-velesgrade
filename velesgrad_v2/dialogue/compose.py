"""
dialogue/compose.py – Compositional response building (less templated).

Instead of picking one pre-written sentence frame per atom, these functions
*construct* sentences from the graph structure itself:

  relative_clause  eval(S,V,O) + inh(S,X)
      → "the Hounds, which are enforcers, patrol the night streets."
  reason_clause    inh(A,B) + inh(B,C)
      → "the relic is valuable, since all stolen artifacts are valuable."
  contrast_clause  eval(p,S,A) + eval(p,S,B) with A≠B
      → "the Hounds suspect the Velespriests, and the merchants, too."

Every composed candidate still goes through the Link Grammar validator
(the caller picks the most-parseable one), so composition cannot produce
ungrammatical output without our noticing.
"""

import random

from ..cog.atomspace import (
    get_tv, types,
)


def _np(atom) -> str:
    from .realizer import _np as real_np
    return real_np(getattr(atom, "name", ""))


def _subject_and_object(eval_atom):
    """Return (subject_atom, object_atom, pred_name) for an EvaluationLink."""
    out = list(getattr(eval_atom, "out", []))
    if len(out) < 2:
        return None
    pred = out[0]
    args = out[1]
    inner = list(getattr(args, "out", []) or [])
    if len(inner) < 2:
        return None
    return inner[0], inner[1], getattr(pred, "name", "")


def _inheritances_of(atom, aspace, limit=3):
    """All InheritanceLinks whose subject is `atom`."""
    found = []
    for link in aspace.get_atoms_by_type(types.InheritanceLink):
        out = list(getattr(link, "out", []))
        if len(out) == 2 and out[0] == atom:
            found.append(link)
            if len(found) >= limit:
                break
    return found


def relative_clause(eval_atom, aspace, rng: random.Random):
    """eval(S,V,O) + inh(S,X) → 'S, which are X, V O.'"""
    parsed = _subject_and_object(eval_atom)
    if not parsed:
        return None
    s, o, pred = parsed
    inher = _inheritances_of(s, aspace)
    if not inher:
        return None
    inh = inher[0]
    x = list(inh.out)[1]
    # Verb form from the realizer's vocabulary (with plural agreement logic)
    from .realizer import _VERBS, _is_plural, _agree_verb, _np as _npf, _pluralize_pred
    plural = _is_plural(getattr(s, "name", ""))
    verb = _VERBS.get(pred, (pred.replace("_", " "),))[0]
    verb = _agree_verb(verb, getattr(s, "name", ""))
    from .realizer import _PROPER as _PROPERN
    is_person = getattr(s, "name", "").lower() in _PROPERN
    if is_person:
        rel = "who are" if plural else "who is"
    else:
        rel = "which are" if plural else "which is"
    x_np = _npf(getattr(x, "name", ""))
    if plural:
        x_np = _pluralize_pred(x_np)
    elif not x_np.startswith(("the ", "a ", "an ", "some ")):
        x_np = ("an " if x_np[0:1] in "aeiou" else "a ") + x_np
    return f"{_np(s)}, {rel} {x_np}, {verb} {_np(o)}."


def reason_clause(inh_atom, aspace, rng: random.Random):
    """inh(A,B) + inh(B,C) → 'A is B, since all Bs are C.'"""
    out = list(getattr(inh_atom, "out", []))
    if len(out) != 2:
        return None
    a, b = out
    for link in aspace.get_atoms_by_type(types.InheritanceLink):
        o2 = list(getattr(link, "out", []))
        if len(o2) == 2 and o2[0] == b:
            c = o2[1]
            from .realizer import _is_plural, _np as real_np, _pluralize_pred
            bnp = real_np(getattr(b, "name", ""))
            bare = bnp
            for art in ("the ", "a ", "an ", "some "):
                if bare.startswith(art):
                    bare = bare[len(art):]
                    break
            b_plural = _pluralize_pred(bnp) if not _is_plural(getattr(b, "name", "")) else bnp
            a_plural = _is_plural(getattr(a, "name", ""))
            copula = "are" if a_plural else "is"
            if a_plural:
                bnp = _pluralize_pred(bnp)
            return (f"{_np(a)} {copula} {bnp}, since all {b_plural} "
                    f"are {real_np(getattr(c, 'name', ''))}.")
    return None


def contrast_clause(eval_atom, aspace, rng: random.Random):
    """eval(P,S,A) + eval(P,S,B) → 'S Ps A, and B, too.'"""
    parsed = _subject_and_object(eval_atom)
    if not parsed:
        return None
    s, a, pred = parsed
    for link in aspace.get_atoms_by_type(types.EvaluationLink):
        p2 = _subject_and_object(link)
        if not p2:
            continue
        s2, b2, pred2 = p2
        if pred2 == pred and s2 == s and b2 != a:
            from .realizer import _VERBS, _agree_verb, _np
            verb = _VERBS.get(pred, (pred.replace("_", " "),))[0]
            verb = _agree_verb(verb, getattr(s, "name", ""))
            return f"{_np(s)} {verb} {_np(a)}, and {_np(b2)}, too."
    return None


def compose(atom, aspace, rng: random.Random) -> list[str]:
    """All compositional candidates for an atom (may be empty)."""
    from .realizer import atom_to_text
    out = []
    type_name = getattr(atom, "type_name", "")
    if "Evaluation" in type_name:
        for fn in (relative_clause, contrast_clause):
            try:
                c = fn(atom, aspace, rng)
            except Exception:
                c = None
            if c:
                out.append(c)
    elif "Inheritance" in type_name:
        try:
            c = reason_clause(atom, aspace, rng)
        except Exception:
            c = None
        if c:
            out.append(c)
    base = atom_to_text(atom, rng)
    if base:
        out.append(base)
    return out
