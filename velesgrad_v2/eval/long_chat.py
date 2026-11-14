"""Run a scripted long conversation with Mira and write a transcript for judging.

Usage: python -m velesgrad_v2.eval.long_chat SCRIPT.txt OUT.md
SCRIPT: one user turn per line. Blank lines and lines starting with # are skipped.
"""
import sys
from velesgrad_v2.chat import MiraChat


def main(script_path, out_path):
    turns = [l.rstrip("\n") for l in open(script_path, encoding="utf-8")
             if l.strip() and not l.lstrip().startswith("#")]
    mira = MiraChat("seed", knowledge="books")
    with open(out_path, "w", encoding="utf-8") as out:
        out.write(f"# Transcript: {script_path}\n\n")
        for i, t in enumerate(turns, 1):
            reply = mira.respond(t)
            out.write(f"**{i}. User:** {t}\n\n**Mira:** {reply}\n\n")
    print(f"{len(turns)} turns -> {out_path}")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
