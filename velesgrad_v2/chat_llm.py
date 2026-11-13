#!/usr/bin/env python3
"""
chat_llm.py – 20-message conversation: a local LLM plays the traveler, Mira plays herself.

The LLM (MiniCPM5-1B by default; any GGUF via llama-cpp-python) generates
the PLAYER's lines; Mira answers from the Velesgrad chat stack (AtomSpace
knowledge, Link Grammar validation, PLN, NL ingestion). Each Mira reply is
fed back to the LLM's context, so the model can follow up on what it heard —
making it a real conversation, not 20 independent prompts.

Usage:
  # In the sandbox / any machine with llama-cpp-python + a GGUF:
  python -m velesgrad_v2.chat_llm

  # Custom model / length:
  python -m velesgrad_v2.chat_llm --model /path/to/MiniCPM5-1B-Q4_K_M.gguf --turns 20

  # Rehearsal mode without a model (clearly labelled; uses a scripted
  # player so the *harness* can be tested on machines without RAM):
  python -m velesgrad_v2.chat_llm --backend scripted

Model download (one-time, ~660 MB):
  mkdir -p ~/models && cd ~/models
  curl -LO https://huggingface.co/openbmb/MiniCPM5-1B-GGUF/resolve/main/MiniCPM5-1B-Q4_K_M.gguf

The transcript is saved to chat_transcript.md in the workspace root.
"""

import argparse
import os
import random
import sys
import time

DEFAULT_MODEL_CANDIDATES = [
    os.environ.get("VELESGRAD_LLM_MODEL", ""),
    os.path.expanduser("~/models/MiniCPM5-1B-Q4_K_M.gguf"),   # user machines
    "/opt/models/MiniCPM5-1B-Q4_K_M.gguf",                    # arena sandbox
]

SYSTEM_PROMPT = (
    "You are a traveler who has just stepped into the Archive of the city of "
    "Velesgrad. You are speaking with Mira, the archivist. Stay in character.\n"
    "Rules:\n"
    "- Speak as the traveler. One short line per turn (max 25 words).\n"
    "- Ask questions about: the relic, the Veil, the archive, the Hounds, the "
    "city, its people. Follow up on what Mira tells you.\n"
    "- If you learn something, you may repeat it back or ask about it further.\n"
    "- Do not narrate actions, do not write Mira's lines.\n"
    "Reply with the traveler's line only, no quotes, no prefix."
)

# Scripted-player plan for --backend scripted (harness rehearsal).
# Clearly labelled in the transcript: this is NOT a model.
SCRIPTED_LINES = [
    "hello, archivist",
    "what is the relic?",
    "where was the relic kept?",
    "who is searching for it?",
    "why is the thinning veil dangerous?",
    "what do you know about the hounds?",
    "tell me about the archive",
    "is the relic valuable?",
    "what happened at night?",
    "what is the veil?",
    "who guards the city?",
    "tell me about the velespriests",
    "what does the bell signal?",
    "the relic lies in the tunnel",
    "where is the relic now?",
    "is the tunnel safe?",
    "who suspects the velespriests?",
    "what can you tell me of velesgrad?",
    "what does the market sell?",
    "thank you, I will come again",
]


# ── Backends ─────────────────────────────────────────────────────────────

class LlamaCppPlayer:
    """The LLM as the traveler. Wraps llama-cpp-python."""

    label = "llama-cpp"

    def __init__(self, model_path: str, n_ctx: int = 2048, seed: int = 42):
        from llama_cpp import Llama
        self.label = f"llama-cpp ({os.path.basename(model_path)})"
        self.llm = Llama(
            model_path=model_path,
            n_ctx=n_ctx,
            n_threads=os.cpu_count() or 2,
            seed=seed,
            verbose=False,
        )
        self.history = []  # [(role, content)] after system prompt

    def line(self, mira_reply: str | None) -> str:
        if mira_reply is not None:
            self.history.append(("user", f"Mira says: {mira_reply}"))
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + self.history
        out = self.llm.create_chat_completion(
            messages=messages,
            max_tokens=640,          # thinking models need room for <think>
            temperature=0.8,
            top_p=0.9,
            stop=["\nMira:", "\nTraveler:"],
        )
        raw = (out["choices"][0]["message"]["content"] or "").strip()
        # MiniCPM5 is a thinking model: drop <think>…</think> reasoning,
        # keep the actual spoken line. Visible for transparency: if the
        # model *only* produced thinking, we flag it instead of faking.
        import re as _re
        text = _re.sub(r"(?s)<think>.*?</think>", "", raw)
        text = _re.sub(r"(?s)^.*?</think>", "", text)
        text = _re.sub(r"(?s)<think>.*$", "", text).strip()
        if not text or text == "…":
            # Thinking consumed the whole budget — nudge for the answer.
            messages2 = messages + [{"role": "user",
                "content": "(Reply now with your short spoken line only.)"}]
            out2 = self.llm.create_chat_completion(
                messages=messages2, max_tokens=192, temperature=0.7,
                stop=["\nMira:"])
            raw2 = (out2["choices"][0]["message"]["content"] or "").strip()
            text = _re.sub(r"(?s)<think>.*?</think>", "", raw2)
            text = _re.sub(r"(?s)^.*?</think>", "", text)
            text = _re.sub(r"(?s)<think>.*$", "", text).strip()
        if not text:
            text = "…"
        text = text.strip('"').split("\n")[0].strip()
        self.history.append(("assistant", text))
        # keep context bounded: system + last 12 exchanges
        if len(self.history) > 24:
            self.history = self.history[-24:]
        return text


class ScriptedPlayer:
    """Rehearsal player — NOT a model. Used to test the harness itself."""

    label = "scripted (rehearsal — not a model)"

    def __init__(self, lines=None, seed: int = 42):
        self.lines = list(lines or SCRIPTED_LINES)
        self.i = 0

    def line(self, mira_reply=None) -> str:
        if self.i < len(self.lines):
            s = self.lines[self.i]
            self.i += 1
            return s
        return "I must go now. farewell"


# ── Conversation loop ────────────────────────────────────────────────────

def run_conversation(player, turns: int = 20, transcript_path: str = "chat_transcript.md"):
    from .chat import MiraChat

    mira = MiraChat(seed=7)
    rows = []           # (turn, player_line, mira_reply)
    mira_reply = None

    t0 = time.time()
    for t in range(1, turns + 1):
        line = player.line(mira_reply)
        print(f"\n[{t:02d}] Traveler: {line}")
        mira_reply = mira.respond(line)
        print(f"[{t:02d}] Mira:     {mira_reply}")
        rows.append((t, line, mira_reply))
    elapsed = time.time() - t0

    # ── transcript ──────────────────────────────────────────────────────
    learned = len(mira.learned_atoms)
    told = sum(1 for r in rows if "told me" in r[2].lower())
    with open(transcript_path, "w") as f:
        f.write("# Velesgrad: LLM ⇄ Mira, 20-message transcript\n\n")
        f.write(f"- Player backend: **{player.label}**\n")
        f.write(f"- Mira backend: Velesgrad chat (AtomSpace + Link Grammar + PLN)\n")
        f.write(f"- Turns: {turns} · wall time: {elapsed:.1f}s\n")
        f.write(f"- Facts Mira learned from the traveler: {learned} "
                f"({told} turns with 'you told me' acknowledgments)\n\n")
        f.write("| # | Traveler | Mira |\n|---|----------|------|\n")
        for t, line, reply in rows:
            f.write(f"| {t} | {line} | {reply} |\n")
    print(f"\nTranscript saved to {transcript_path} ({elapsed:.1f}s)")
    return rows


# ── CLI ──────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="LLM player vs Mira chat")
    ap.add_argument("--model", help="path to GGUF model")
    ap.add_argument("--turns", type=int, default=20)
    ap.add_argument("--backend", choices=["llama-cpp", "scripted"], default="llama-cpp")
    ap.add_argument("--n-ctx", type=int, default=2048)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--transcript", default="chat_transcript.md")
    args = ap.parse_args()

    if args.backend == "scripted":
        player = ScriptedPlayer(seed=args.seed)
    else:
        model = args.model
        if not model:
            for cand in DEFAULT_MODEL_CANDIDATES:
                if cand and os.path.isfile(cand):
                    model = cand
                    break
        if not model or not os.path.isfile(model):
            print("No GGUF model found. One-time download (~660 MB):\n"
                  "  mkdir -p ~/models && cd ~/models\n"
                  "  curl -LO https://huggingface.co/openbmb/MiniCPM5-1B-GGUF/resolve/main/MiniCPM5-1B-Q4_K_M.gguf\n"
                  "Then re-run, or use --model <path>. "
                  "(Use --backend scripted to rehearse without a model.)")
            sys.exit(1)
        try:
            player = LlamaCppPlayer(model, n_ctx=args.n_ctx, seed=args.seed)
        except ImportError:
            print("llama-cpp-python not installed:\n"
                  "  pip install llama-cpp-python\n"
                  "(Building from source takes a few minutes the first time.)")
            sys.exit(1)

    run_conversation(player, turns=args.turns, transcript_path=args.transcript)


if __name__ == "__main__":
    main()
