# Velesgrad v2 – AtomSpace wrapper
# Unified API over real OpenCog AtomSpace (modern value API) or dev shim.
#
# Real OpenCog path:
#   - set_thread_atomspace(asp) before creating atoms
#   - TV: asp.set_value(atom, tvkey, FloatValue([mean, conf]))
#   - AV: same mechanism with custom keys
#
# Dev shim path: atoms carry a .tv attribute directly.

from .opencog_gate import (
    AtomSpace, types, TruthValue,
    ConceptNode, PredicateNode, VariableNode,
    InheritanceLink, ImplicationLink, EvaluationLink,
    ListLink, SetLink, AndLink, OrLink, NotLink,
    MemberLink, FloatValue, StringValue,
)
from .opencog_gate import _REAL_OPENCOG

try:
    from .opencog_gate import tvkey
except ImportError:
    tvkey = None
try:
    from .opencog_gate import createFloatValue
except ImportError:
    createFloatValue = None
try:
    from .opencog_gate import AssociateLink
except ImportError:
    AssociateLink = None

try:
    from .opencog_gate import initialize_opencog
except ImportError:
    initialize_opencog = None
try:
    from .opencog_gate import _set_current_atomspace
except ImportError:
    _set_current_atomspace = None
try:
    from .opencog_gate import set_thread_atomspace
except ImportError:
    set_thread_atomspace = None


def tv_from_count(strength, count, k=800.0):
    if count <= 0: return TruthValue(strength, 0.0)
    conf = count / (count + k)
    return TruthValue(max(0.0, min(1.0, strength)), max(0.0, min(1.0, conf)))


def tv_revise(a, b):
    K = 800.0
    ca, cb = a.confidence, b.confidence
    na = ca * K / (1.0 - ca) if ca < 1.0 else K * 1000
    nb = cb * K / (1.0 - cb) if cb < 1.0 else K * 1000
    total = na + nb
    if total == 0: return TruthValue(0.5, 0.0)
    return tv_from_count((na * a.mean + nb * b.mean) / total, total)


# ── Current atomspace (needed for value ops on real OpenCog) ────────────

_ASP = None
_STI_KEY = None
_LTI_KEY = None
_VLTI_KEY = None


def _ensure_keys(asp):
    global _STI_KEY, _LTI_KEY, _VLTI_KEY, _ASP
    # Keys are handles: they must belong to the atomspace in use.
    if asp is not _ASP or _STI_KEY is None:
        _ASP = asp
        _STI_KEY = PredicateNode("sti_key")
        _LTI_KEY = PredicateNode("lti_key")
        _VLTI_KEY = PredicateNode("vlti_key")


def init_atomspace(asp):
    """Initialize atomspace for both paths."""
    global _ASP
    _ASP = asp
    if _REAL_OPENCOG:
        if set_thread_atomspace:
            set_thread_atomspace(asp)
    else:
        if initialize_opencog:
            initialize_opencog(asp)
        if _set_current_atomspace:
            _set_current_atomspace(asp)
    _ensure_keys(asp)


# ── Truth values ────────────────────────────────────────────────────────

def get_tv(atom):
    """Read truth value from any atom (real OpenCog or shim)."""
    if _REAL_OPENCOG:
        if tvkey is None or atom is None:
            return TruthValue(0.5, 0.0)
        val = atom.get_value(tvkey)
        if val is not None:
            lst = val.to_list()
            if len(lst) >= 2:
                return TruthValue(lst[0], lst[1])
        return TruthValue(0.5, 0.0)
    return getattr(atom, 'tv', None) or TruthValue(0.5, 0.0)


def set_tv(atom, tv):
    """Write truth value to any atom."""
    if _REAL_OPENCOG:
        if _ASP is not None and tvkey is not None and createFloatValue is not None:
            _ASP.set_value(atom, tvkey, createFloatValue([tv.mean, tv.confidence]))
    else:
        atom.tv = tv


# ── Attention values ────────────────────────────────────────────────────

def _av_get(atom, key, default=0.0):
    if not key: return default
    val = atom.get_value(key)
    if val is not None:
        lst = val.to_list()
        return lst[0] if lst else default
    return default


def _av_set(atom, key, value):
    if not key or _ASP is None: return
    if _REAL_OPENCOG:
        if createFloatValue is not None:
            _ASP.set_value(atom, key, createFloatValue([value]))
    else:
        atom.set_value(key, FloatValue([value]))


def get_sti(atom): return _av_get(atom, _STI_KEY)
def set_sti(atom, v): _av_set(atom, _STI_KEY, v)
def get_lti(atom): return _av_get(atom, _LTI_KEY)
def set_lti(atom, v): _av_set(atom, _LTI_KEY, v)
def get_vlti(atom): return int(_av_get(atom, _VLTI_KEY))
def set_vlti(atom, v): _av_set(atom, _VLTI_KEY, float(v))


def add_sti(atom, delta, floor=-400.0, ceiling=400.0):
    cur = get_sti(atom)
    set_sti(atom, max(floor, min(ceiling, cur + delta)))
