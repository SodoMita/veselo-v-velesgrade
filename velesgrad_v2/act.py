#!/usr/bin/env python3
"""
act.py – Single action executor for Velesgrad v2.
Usage: VELESGRAD_DEV=1 python -m velesgrad_v2.act <command>
"""
import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

SAVE_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "velesgrad_save.json")

def load_engine():
    from velesgrad_v2.engine import Engine
    eng = Engine(seed=42)
    if os.path.exists(SAVE_PATH):
        with open(SAVE_PATH) as f:
            eng.load_state(json.load(f))
    return eng

def save_engine(eng):
    with open(SAVE_PATH, "w") as f:
        json.dump(eng.save_state(), f)

def main():
    if len(sys.argv) < 2:
        print("Usage: python -m velesgrad_v2.act <command>")
        sys.exit(1)

    cmd = " ".join(sys.argv[1:])
    eng = load_engine()
    from velesgrad_v2.cli import parse_command

    result = parse_command(eng, cmd)
    if result == "quit":
        save_engine(eng)
    elif result == True:
        output = eng.turn()
        print(output)
        save_engine(eng)
    else:
        save_engine(eng)

if __name__ == "__main__":
    main()
