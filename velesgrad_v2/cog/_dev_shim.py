"""
_dev_shim.py – Minimal OpenCog API-compatible shim FOR DEVELOPMENT ONLY.

This file is NOT used in production. It exists solely so developers can
run and test the game logic in environments where OpenCog hasn't been
compiled yet (e.g. laptops without cmake/boost/guile).

The production gate (opencog_gate.py) never imports this file.
Tests that run against the real OpenCog never import this file.

It mirrors the subset of the opencog Python API that Velesgrad uses:
  - AtomSpace, TruthValue, types
  - ConceptNode, PredicateNode, VariableNode
  - InheritanceLink, ImplicationLink, EvaluationLink, etc.
  - initialize_opencog
  - FloatValue, StringValue

It is NOT a substitute for OpenCog. It has no C++ hypergraph, no
pattern matcher, no Scheme shell, no persistence. It is a dict.
"""


class TruthValue:
    __slots__ = ('_mean', '_conf')

    def __init__(self, mean: float = 0.5, confidence: float = 0.0):
        self._mean = max(0.0, min(1.0, mean))
        self._conf = max(0.0, min(1.0, confidence))

    @property
    def mean(self):
        return self._mean

    @property
    def confidence(self):
        return self._conf

    def to_list(self):
        return [self._mean, self._conf]

    def __repr__(self):
        return f"TV({self._mean:.3f}, {self._conf:.3f})"


class FloatValue:
    __slots__ = ('_vals',)
    def __init__(self, vals):
        self._vals = list(vals)
    def to_list(self):
        return list(self._vals)


class StringValue:
    __slots__ = ('_vals',)
    def __init__(self, vals):
        self._vals = list(vals) if isinstance(vals, (list, tuple)) else [vals]
    def to_list(self):
        return list(self._vals)


class _AtomHandle:
    """Lightweight handle that mimics OpenCog's Atom."""
    _counter = 0

    def __init__(self, type_name: str, name: str, out=None):
        _AtomHandle._counter += 1
        self._uuid = _AtomHandle._counter
        self.type_name = type_name
        self.name = name
        self.out = tuple(out or [])
        self._tv = TruthValue()
        self._values: dict[int, object] = {}
        self.incoming: list = []

    def h(self):
        return self._uuid

    def handle_uuid(self):
        return self._uuid

    @property
    def tv(self):
        return self._tv

    @tv.setter
    def tv(self, value):
        self._tv = value

    def get_value(self, key):
        return self._values.get(id(key))

    def set_value(self, key, value):
        self._values[id(key)] = value

    def __repr__(self):
        if self.out:
            names = ", ".join(a.name for a in self.out)
            return f"({self.type_name} {self.name} [{names}])"
        return f'({self.type_name} "{self.name}")'

    def __eq__(self, other):
        if not isinstance(other, _AtomHandle):
            return False
        return self._uuid == other._uuid

    def __hash__(self):
        return self._uuid


class _TypeNamespace:
    """Mimics opencog.atomspace.types"""
    def __getattr__(self, name):
        return name

types = _TypeNamespace()


class AtomSpace:
    def __init__(self):
        self._atoms: list[_AtomHandle] = []
        self._by_type: dict[str, list[_AtomHandle]] = {}

    def __bool__(self):
        return True  # An AtomSpace is always "truthy" even when empty

    def add_node(self, type_name, name, tv=None):
        # check for existing
        for a in self._by_type.get(type_name, []):
            if a.name == name and not a.out:
                return a
        atom = _AtomHandle(type_name, name)
        if tv:
            atom.tv = tv
        self._atoms.append(atom)
        self._by_type.setdefault(type_name, []).append(atom)
        return atom

    def add_link(self, type_name, out, tv=None):
        # Dedupe identical links like the real AtomSpace does
        out_ids = tuple(id(c) for c in out)
        for existing in self._by_type.get(type_name, []):
            if existing.out and tuple(id(c) for c in existing.out) == out_ids:
                if tv:
                    existing.tv = tv
                return existing
        atom = _AtomHandle(type_name, "", out)
        if tv:
            atom.tv = tv
        self._atoms.append(atom)
        self._by_type.setdefault(type_name, []).append(atom)
        for child in out:
            child.incoming.append(atom)
        return atom

    def get_atoms_by_type(self, type_name):
        return list(self._by_type.get(type_name, []))

    def __iter__(self):
        return iter(self._atoms)

    def __len__(self):
        return len(self._atoms)


def initialize_opencog(atomspace):
    """No-op in the shim. Real OpenCog binds the atomspace to type constructors."""
    pass


# Type constructor functions that mimic opencog.type_constructors
def ConceptNode(name, tv=None):
    return _current_atomspace.add_node("ConceptNode", name, tv) if _current_atomspace else _AtomHandle("ConceptNode", name)

def PredicateNode(name, tv=None):
    return _current_atomspace.add_node("PredicateNode", name, tv) if _current_atomspace else _AtomHandle("PredicateNode", name)

def VariableNode(name):
    return _AtomHandle("VariableNode", name)

def InheritanceLink(a, b, tv=None):
    return _current_atomspace.add_link("InheritanceLink", [a, b], tv) if _current_atomspace else _AtomHandle("InheritanceLink", "", [a, b])

def ImplicationLink(a, b, tv=None):
    return _current_atomspace.add_link("ImplicationLink", [a, b], tv) if _current_atomspace else _AtomHandle("ImplicationLink", "", [a, b])

def EvaluationLink(pred, subj, tv=None):
    return _current_atomspace.add_link("EvaluationLink", [pred, subj], tv) if _current_atomspace else _AtomHandle("EvaluationLink", "", [pred, subj])

def AssociateLink(a, b, tv=None):
    return _current_atomspace.add_link("AssociateLink", [a, b], tv) if _current_atomspace else _AtomHandle("AssociateLink", "", [a, b])

def ListLink(*args, **kwargs):
    return _AtomHandle("ListLink", "", list(args))

def SetLink(*args, **kwargs):
    return _AtomHandle("SetLink", "", list(args))

def AndLink(a, b, tv=None):
    return _AtomHandle("AndLink", "", [a, b])

def OrLink(a, b, tv=None):
    return _AtomHandle("OrLink", "", [a, b])

def NotLink(a, tv=None):
    return _AtomHandle("NotLink", "", [a])

def MemberLink(a, b, tv=None):
    return _AtomHandle("MemberLink", "", [a, b])


_current_atomspace = None

def _set_current_atomspace(asp):
    global _current_atomspace
    _current_atomspace = asp
