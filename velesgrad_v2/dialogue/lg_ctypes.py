"""
dialogue/lg_ctypes.py – ctypes wrapper for link-grammar C library.

Uses the already-compiled liblink-grammar.so directly via ctypes.
No SWIG needed. No Python bindings needed.
"""

import ctypes
import ctypes.util
import os

# Find the library
_LIB_PATHS = [
    "/home/user/local/lib/liblink-grammar.so",
    "/home/user/local/lib/liblink-grammar.so.5.13.0",
]

_lg = None
for p in _LIB_PATHS:
    if os.path.exists(p):
        try:
            _lg = ctypes.CDLL(p)
            break
        except OSError:
            continue

if _lg is None:
    try:
        _lg = ctypes.CDLL(ctypes.util.find_library("link-grammar"))
    except (OSError, TypeError):
        pass

_LG_AVAILABLE = _lg is not None

# ── C function signatures ───────────────────────────────────────────────

if _LG_AVAILABLE:
    # Dictionary
    _lg.dictionary_create_lang.restype = ctypes.c_void_p
    _lg.dictionary_create_lang.argtypes = [ctypes.c_char_p]

    _lg.dictionary_delete.restype = None
    _lg.dictionary_delete.argtypes = [ctypes.c_void_p]

    # Parse options
    _lg.parse_options_create.restype = ctypes.c_void_p
    _lg.parse_options_create.argtypes = []

    _lg.parse_options_delete.restype = None
    _lg.parse_options_delete.argtypes = [ctypes.c_void_p]

    _lg.parse_options_set_verbosity.restype = None
    _lg.parse_options_set_verbosity.argtypes = [ctypes.c_void_p, ctypes.c_int]

    # Sentence
    _lg.sentence_create.restype = ctypes.c_void_p
    _lg.sentence_create.argtypes = [ctypes.c_char_p, ctypes.c_void_p]

    _lg.sentence_delete.restype = None
    _lg.sentence_delete.argtypes = [ctypes.c_void_p]

    _lg.sentence_parse.restype = ctypes.c_int
    _lg.sentence_parse.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

    _lg.sentence_num_linkages_found.restype = ctypes.c_int
    _lg.sentence_num_linkages_found.argtypes = [ctypes.c_void_p]

    # Linkage
    _lg.linkage_create.restype = ctypes.c_void_p
    _lg.linkage_create.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p]

    _lg.linkage_delete.restype = None
    _lg.linkage_delete.argtypes = [ctypes.c_void_p]

    _lg.linkage_get_num_words.restype = ctypes.c_int
    _lg.linkage_get_num_words.argtypes = [ctypes.c_void_p]

    _lg.linkage_get_word.restype = ctypes.c_char_p
    _lg.linkage_get_word.argtypes = [ctypes.c_void_p, ctypes.c_int]

    _lg.linkage_get_num_links.restype = ctypes.c_int
    _lg.linkage_get_num_links.argtypes = [ctypes.c_void_p]

    _lg.linkage_get_link_lword.restype = ctypes.c_int
    _lg.linkage_get_link_lword.argtypes = [ctypes.c_void_p, ctypes.c_int]

    _lg.linkage_get_link_rword.restype = ctypes.c_int
    _lg.linkage_get_link_rword.argtypes = [ctypes.c_void_p, ctypes.c_int]

    _lg.linkage_get_link_label.restype = ctypes.c_char_p
    _lg.linkage_get_link_label.argtypes = [ctypes.c_void_p, ctypes.c_int]

    # Data-dir override: lets us point at the vendored dictionary that
    # travels with the repo when no system-wide one is installed.
    try:
        _lg.dictionary_set_data_dir.restype = ctypes.c_int
        _lg.dictionary_set_data_dir.argtypes = [ctypes.c_char_p]
        _HAVE_SET_DATA_DIR = True
    except AttributeError:
        _HAVE_SET_DATA_DIR = False


# ── Python API ──────────────────────────────────────────────────────────

class LGDictionary:
    """Link Grammar dictionary."""
    def __init__(self, lang="en"):
        if not _LG_AVAILABLE:
            raise RuntimeError("link-grammar library not found")
        self._dict = _lg.dictionary_create_lang(lang.encode())
        if not self._dict:
            raise RuntimeError(f"Failed to create dictionary for lang={lang}")
        self._opts = _lg.parse_options_create()
        _lg.parse_options_set_verbosity(self._opts, 0)

    def __del__(self):
        try:
            if getattr(self, '_dict', None):
                _lg.dictionary_delete(self._dict)
            if getattr(self, '_opts', None):
                _lg.parse_options_delete(self._opts)
        except Exception:
            pass


class LGParse:
    """Result of parsing a sentence."""
    def __init__(self, text, words, links, num_linkages):
        self.text = text
        self.words = words
        self.links = links  # list of (left_word, label, right_word)
        self.num_linkages = num_linkages


def parse_sentence(text: str, dictionary) -> LGParse | None:
    """Parse a sentence with Link Grammar. Returns LGParse or None."""
    if not _LG_AVAILABLE or not dictionary._dict:
        return None

    sent = _lg.sentence_create(text.encode(), dictionary._dict)
    if not sent:
        return None

    try:
        num = _lg.sentence_parse(sent, dictionary._opts)
        if num <= 0:
            return None

        linkage = _lg.linkage_create(0, sent, dictionary._opts)
        if not linkage:
            return None

        try:
            n_words = _lg.linkage_get_num_words(linkage)
            words = []
            for i in range(n_words):
                w = _lg.linkage_get_word(linkage, i)
                words.append(w.decode() if w else f"?{i}")

            n_links = _lg.linkage_get_num_links(linkage)
            links = []
            for i in range(n_links):
                lw = _lg.linkage_get_link_lword(linkage, i)
                rw = _lg.linkage_get_link_rword(linkage, i)
                label = _lg.linkage_get_link_label(linkage, i)
                w_left = words[lw] if lw < len(words) else f"?{lw}"
                w_right = words[rw] if rw < len(words) else f"?{rw}"
                label_str = label.decode() if label else "?"
                links.append((w_left, label_str, w_right))

            return LGParse(text, words, links, num)
        finally:
            _lg.linkage_delete(linkage)
    finally:
        _lg.sentence_delete(sent)


def parse_count(text: str, dictionary) -> int:
    """Count valid parses for a sentence."""
    if not _LG_AVAILABLE or not dictionary._dict:
        return -1
    sent = _lg.sentence_create(text.encode(), dictionary._dict)
    if not sent:
        return 0
    try:
        return _lg.sentence_parse(sent, dictionary._opts)
    finally:
        _lg.sentence_delete(sent)


# ── Singleton ───────────────────────────────────────────────────────────

_VENDORED = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                         "data", "link-grammar")
if _LG_AVAILABLE and _HAVE_SET_DATA_DIR and os.path.isfile(
        os.path.join(_VENDORED, "en", "4.0.dict")):
    _lg.dictionary_set_data_dir(_VENDORED.encode())

_DICT = None

def get_dictionary():
    global _DICT
    if _DICT is None and _LG_AVAILABLE:
        try:
            _DICT = LGDictionary("en")
        except RuntimeError:
            pass
    return _DICT


def is_available() -> bool:
    return _LG_AVAILABLE and get_dictionary() is not None
