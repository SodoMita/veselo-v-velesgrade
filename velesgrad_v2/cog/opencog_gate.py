"""
opencog_gate.py – OpenCog import gate.

VELESGRAD_DEV=1: force dev shim (for development/testing)
Otherwise: require real OpenCog, fail if not installed
"""

import os, sys

_USE_SHIM = os.environ.get("VELESGRAD_DEV", "0") == "1"
_REAL_OPENCOG = False

if not _USE_SHIM:
    # Try real OpenCog
    try:
        from opencog.atomspace import AtomSpace, types, tvkey, createFloatValue
        from opencog.atomspace import set_thread_atomspace, get_thread_atomspace
        try:
            from opencog.atomspace import AssociateLink
        except ImportError:
            try:
                from opencog.atomspace import AssociativeLink as AssociateLink
            except ImportError:
                AssociateLink = None
        from opencog.atomspace import (
            ConceptNode, PredicateNode, VariableNode,
            InheritanceLink, ImplicationLink, EvaluationLink,
            ListLink, SetLink, AndLink, OrLink, NotLink,
            MemberLink, FloatValue, StringValue,
        )
        _REAL_OPENCOG = True

        # TruthValue compat wrapper
        class TruthValue:
            __slots__ = ('_mean', '_conf')
            def __init__(self, mean=0.5, confidence=0.0):
                self._mean = max(0.0, min(1.0, mean))
                self._conf = max(0.0, min(1.0, confidence))
            @property
            def mean(self): return self._mean
            @property
            def confidence(self): return self._conf
            def __repr__(self): return f"TV({self._mean:.3f}, {self._conf:.3f})"

    except ImportError:
        pass

if not _REAL_OPENCOG:
    if not _USE_SHIM:
        print(
            "\nOPENCOG IS NOT INSTALLED\n"
            "Set VELESGRAD_DEV=1 for development mode, or build OpenCog from source.\n"
            "See: https://wiki.opencog.org/w/Building_OpenCog\n",
            file=sys.stderr
        )
        sys.exit(1)

    # Use dev shim
    from ._dev_shim import (
        AtomSpace, TruthValue, types,
        ConceptNode, PredicateNode, VariableNode,
        InheritanceLink, ImplicationLink, EvaluationLink,
        ListLink, SetLink, AndLink, OrLink, NotLink,
        AssociateLink, MemberLink,
        FloatValue, StringValue,
        initialize_opencog, _set_current_atomspace,
    )
    tvkey = None
    createFloatValue = None
