# Velesgrad v2 – PLN (Probabilistic Logic Networks)
# Operates on the REAL OpenCog AtomSpace.
# TV formulas are implemented in Python (they're math, not C++),
# but all atoms live in the real AtomSpace.

from .atomspace import (
    AtomSpace, TruthValue, types,
    ConceptNode, PredicateNode, VariableNode,
    InheritanceLink, ImplicationLink, EvaluationLink,
    AndLink, OrLink, NotLink,
    tv_from_count, tv_revise,
    get_sti, set_sti, get_tv, set_tv,
)

# Real OpenCog pattern matcher (C++ engine). Falls back to Python loops on the shim.
try:
    from .opencog_gate import _REAL_OPENCOG as _REAL
    from opencog.atomspace import MeetLink as _MeetLink, VariableList as _VariableList
    from opencog.atomspace import AndLink as _AndLink
    _HAVE_PATTERN_MATCHER = _REAL
except ImportError:
    _HAVE_PATTERN_MATCHER = False
    _MeetLink = _VariableList = _AndLink = None


# ── TV Formulas ──────────────────────────────────────────────────────────

def deduction_tv(s_ab: TruthValue, s_bc: TruthValue) -> TruthValue:
    """PLN Deduction: A→B, B→C ⇒ A→C
    s_AC = s_AB * s_BC  (independence assumption)
    """
    s = s_ab.mean * s_bc.mean
    return TruthValue(max(0.0, min(1.0, s)), min(s_ab.confidence, s_bc.confidence))


def modus_ponens_tv(p: TruthValue, impl: TruthValue, prior: TruthValue) -> TruthValue:
    """PLN Modus Ponens: P, P→Q ⇒ Q
    s_Q = s_P * s_(P→Q) + (1 - s_P) * s_prior
    """
    s = p.mean * impl.mean + (1.0 - p.mean) * prior.mean
    return TruthValue(max(0.0, min(1.0, s)), min(p.confidence, impl.confidence))


def and_tv(a: TruthValue, b: TruthValue) -> TruthValue:
    s = a.mean * b.mean
    return TruthValue(s, min(a.confidence, b.confidence))


def or_tv(a: TruthValue, b: TruthValue) -> TruthValue:
    s = 1.0 - (1.0 - a.mean) * (1.0 - b.mean)
    return TruthValue(s, min(a.confidence, b.confidence))


def not_tv(a: TruthValue) -> TruthValue:
    return TruthValue(1.0 - a.mean, a.confidence)


# ── Inference Result ─────────────────────────────────────────────────────


def _wrap_var(v):
    return v

def _wrap_link_bin(type_name, a, b):
    """Create a binary link of the given type between two atoms."""
    if type_name == "InheritanceLink":
        return InheritanceLink(a, b)
    raise ValueError(type_name)

class InferenceResult:
    def __init__(self, source, conclusion, tv, rule, premises):
        self.source = source
        self.conclusion = conclusion
        self.tv = tv
        self.rule = rule
        self.premises = premises


# ── Reasoner ─────────────────────────────────────────────────────────────
# Forward chainer with dependency tracking (TMS).
# All atoms are real OpenCog atoms in the real AtomSpace.

class Reasoner:
    def __init__(self, atomspace: AtomSpace):
        self.aspace = atomspace
        # TMS: store atom handles (not ids) for dependency tracking
        self.depends: dict[int, list] = {}
        self.dependents: dict[int, list] = {}
        self.derived: list[InferenceResult] = []

    def record_dependency(self, consequent, premises: list):
        """Track which premises were used to derive a consequent."""
        cid = consequent.handle_uuid() if hasattr(consequent, 'handle_uuid') else id(consequent)
        self.depends[cid] = list(premises)
        for p in premises:
            pid = p.handle_uuid() if hasattr(p, 'handle_uuid') else id(p)
            self.dependents.setdefault(pid, []).append(consequent)

    def revise(self, atom, new_tv: TruthValue, premises: list | None = None):
        """Update belief and invalidate downstream."""
        set_tv(atom, new_tv)
        if premises:
            self.record_dependency(atom, premises)
        self.invalidate(atom)

    def invalidate(self, atom) -> set:
        """TMS: lower confidence on all downstream derivations."""
        invalidated = set()
        seen = set()
        pid = atom.handle_uuid() if hasattr(atom, 'handle_uuid') else id(atom)
        stack = list(self.dependents.get(pid, []))
        while stack:
            dep = stack.pop()
            did = dep.handle_uuid() if hasattr(dep, 'handle_uuid') else id(dep)
            if did in seen:
                continue
            seen.add(did)
            tv = get_tv(dep)
            if tv and tv.confidence > 0.01:
                set_tv(dep, TruthValue(tv.mean, tv.confidence * 0.5))
                invalidated.add(dep)
            stack.extend(self.dependents.get(did, []))
        return invalidated

    def step(self) -> list[InferenceResult]:
        """Run one inference step on the real AtomSpace."""
        self.derived = []
        self._run_deduction()
        self._run_modus_ponens()
        return self.derived

    def _find_deduction_chains(self):
        """Find (A→B, B→C) pairs. Uses the REAL C++ pattern matcher when
        available (MeetLink query); falls back to indexed Python iteration."""
        if _HAVE_PATTERN_MATCHER:
            try:
                A_ = _wrap_var(VariableNode("$A"))
                B_ = _wrap_var(VariableNode("$B"))
                C_ = _wrap_var(VariableNode("$C"))
                ab = _wrap_link_bin("InheritanceLink", A_, B_)
                bc = _wrap_link_bin("InheritanceLink", B_, C_)
                body = _AndLink(ab, bc)
                meet = _MeetLink(_VariableList(A_, B_, C_), body)
                res = meet.execute()
                chains = []
                if res is not None and hasattr(res, "to_list"):
                    for match in res.to_list():
                        atoms = match.to_list() if hasattr(match, "to_list") else list(match)
                        if len(atoms) == 3:
                            chains.append((atoms[0], atoms[1], atoms[2]))
                return chains
            except Exception:
                pass  # fall through to Python loop

        # Fallback: indexed iteration over InheritanceLinks
        inheritances = list(self.aspace.get_atoms_by_type(types.InheritanceLink))
        pairs = []
        for link_ab in inheritances:
            out = link_ab.out
            if len(out) != 2:
                continue
            a, b = out
            for link_bc in inheritances:
                out_bc = link_bc.out
                if len(out_bc) == 2 and out_bc[0] == b:
                    pairs.append((a, b, out_bc[1]))
            if len(pairs) > 500:  # safety cap for the O(n^2) path
                break
        return pairs

    def _run_deduction(self):
        """Derive A→C from A→B, B→C chains."""
        chains = self._find_deduction_chains()
        seen = set()
        for a, b, c in chains:
            key = (a, c)
            if key in seen:
                continue
            seen.add(key)
            # The derived link: creating it dedupes automatically on real
            # AtomSpace. If it already carries evidence, skip re-derivation.
            result = InheritanceLink(a, c)
            existing_tv = get_tv(result)
            if existing_tv.confidence > 0.4:
                continue
            # Premises: the two source links (re-fetch to record dependencies)
            link_ab = InheritanceLink(a, b)
            link_bc = InheritanceLink(b, c)
            tv_ab = get_tv(link_ab)
            tv_bc = get_tv(link_bc)
            tv_ac = deduction_tv(tv_ab, tv_bc)
            if tv_ac.mean <= 0.05:
                continue
            set_tv(result, tv_ac)
            set_sti(result, max(get_sti(a), get_sti(c)))
            self.record_dependency(result, [link_ab, link_bc])
            self.derived.append(InferenceResult(
                link_ab, result, tv_ac, "deduction", [link_ab, link_bc]
            ))

    def _run_modus_ponens(self):
        """Find P, P→Q pairs and update Q in the real AtomSpace."""
        implications = list(self.aspace.get_atoms_by_type(types.ImplicationLink))
        for impl in implications:
            out = impl.out
            if len(out) != 2:
                continue
            p_atom, q_atom = out
            impl_tv = get_tv(impl)
            p_tv = get_tv(p_atom)
            if p_tv.mean > 0.5 and p_tv.confidence > 0.01:
                q_tv = get_tv(q_atom)
                prior = q_tv if q_tv.confidence > 0.01 else TruthValue(0.5, 0.1)
                result_tv = modus_ponens_tv(p_tv, impl_tv, prior)
                if result_tv.mean > 0.05:
                    set_tv(q_atom, result_tv)
                    self.record_dependency(q_atom, [p_atom, impl])
                    self.derived.append(InferenceResult(
                        p_atom, q_atom, result_tv, "modus_ponens", [p_atom, impl]
                    ))


# ── BeliefStore ──────────────────────────────────────────────────────────
# Stores beliefs as EvaluationLinks in the real AtomSpace.

class BeliefStore:
    def __init__(self, atomspace: AtomSpace, reasoner: Reasoner):
        self.aspace = atomspace
        self.reasoner = reasoner
        self._index: dict[tuple, object] = {}

    def revise_belief(self, subject: str, predicate: str, truth_strength: float):
        key = (subject, predicate)
        subj = ConceptNode(subject)
        pred = ConceptNode(predicate)
        belief = EvaluationLink(pred, subj)
        old_tv = get_tv(belief)
        new_tv = tv_from_count(truth_strength, 10.0)
        revised = tv_revise(old_tv, new_tv) if old_tv.confidence > 0.01 else new_tv
        self.reasoner.revise(belief, revised)
        self._index[key] = belief
        return belief

    def get_belief(self, subject: str, predicate: str):
        key = (subject, predicate)
        atom = self._index.get(key)
        if atom:
            return get_tv(atom)
        return None
