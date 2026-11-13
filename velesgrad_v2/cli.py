#!/usr/bin/env python3
"""
Velesgrad v2 – Interactive CLI
"""
import sys, os, json, readline
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from velesgrad_v2.engine import Engine
from velesgrad_v2.tools.registry import execute_tool

ROOM_DESCRIPTIONS = {
    "square": "Veles Square. Cobbles worn smooth by centuries of feet. A fountain murmurs.",
    "archive": "The Archive. Dusty shelves. Scrolls and bound volumes. Candle wax.",
    "tavern": "The Tavern. Warm light, oil lamps, bread and mead.",
    "bell_tower": "The Bell Tower. Stone steps spiral upward. The great bronze bell above.",
    "market": "The Market. Stalls and awnings. Merchants call out wares. Spices and leather.",
    "sanctum": "The Sanctum. Quiet. Sacred. Candles before ancient icons. The Veil is thin here.",
    "alley": "The Alley. Narrow, shadowed. Music from the tavern, haggling from the market.",
}

NPC_DESCRIPTIONS = {
    "Mira": "Velespriest. Sharp eyes, ink-stained fingers.",
    "Yuri": "Veche merchant. Quick smile, quicker hands.",
    "Hound": "Hound enforcer. Silent, watchful, armed.",
    "Zorya": "Senior Velespriest. Calm, ancient-seeming.",
    "Boris": "Veche trader. Loud, jovial, shrewd.",
    "Kostya": "Hound. Watches from the bell tower.",
    "Vasilisa": "Veche woman of the shadows.",
}


def show_room(engine):
    room_id = engine.world.locations.get("Player", "square")
    room = engine.world.rooms.get(room_id)
    desc = ROOM_DESCRIPTIONS.get(room_id, room.name if room else room_id)
    print(f"\n  [{room.name if room else room_id}]")
    print(f"  {desc}")
    others = [n for n, r in engine.world.locations.items() if r == room_id and n != "Player"]
    if others:
        for n in others:
            print(f"  {n} is here. {NPC_DESCRIPTIONS.get(n, '')}")
    else:
        print("  You are alone.")
    if room:
        print(f"  Exits: {', '.join(room.neighbors)}")


def parse_command(engine, raw):
    cmd = raw.strip().lower()
    if not cmd:
        return False
    parts = cmd.split(None, 1)
    verb = parts[0]
    arg = parts[1] if len(parts) > 1 else ""

    if verb in ("quit", "exit", "q"):
        return "quit"

    if verb in ("go", "move", "walk"):
        target = arg.lower().replace(" ", "_")
        current = engine.world.locations.get("Player", "square")
        room = engine.world.rooms.get(current)
        if not room:
            print("  You are nowhere.")
            return False
        matches = [n for n in room.neighbors if target in n.lower()]
        if not matches:
            print(f"  Can't go to '{arg}'. Exits: {', '.join(room.neighbors)}")
            return False
        res = execute_tool(engine.tool_ctx, "move", "Player", matches[0])
        if res.ok:
            engine.player.perceive({"fact": f"Player is in {matches[0]}"})
            engine.tom.learn("Player", f"Player is in {matches[0]}")
            show_room(engine)
        else:
            print(f"  {res.message}")
        return False

    if verb in ("look", "l", "where"):
        show_room(engine)
        return False

    if verb in ("talk", "speak", "chat"):
        if not arg:
            print("  Talk to whom?")
            return False
        # Use engine's proper NPC reaction system
        result = engine.player_talks_to(arg.strip())
        print(f"\n  {result}")
        return True

    if verb in ("ask",):
        if not arg or len(arg.split()) < 2:
            print("  Use: ask <npc> <topic>")
            return False
        parts2 = arg.split(None, 1)
        npc_name = parts2[0]
        topic = parts2[1]
        result = engine.player_asks_about(npc_name, topic)
        print(f"\n  {result}")
        return True

    if verb in ("take", "grab"):
        if not arg:
            print("  Take what?")
            return False
        res = execute_tool(engine.tool_ctx, "take", "Player", arg)
        print(f"  {res.message}")
        engine.tom.learn("Player", f"Player has {arg}")
        return True

    if verb in ("return", "place", "put"):
        if not arg:
            print("  Return what?")
            return False
        room = engine.world.locations.get("Player", "")
        if "relic" in arg and room == "archive":
            from velesgrad_v2.cog.atomspace import ConceptNode, tv_from_count
            ConceptNode("relic_returned_to_archive").tv = tv_from_count(1.0, 10.0)
            engine.tom.learn("Player", "relic returned to archive")
            engine.tool_ctx.chronicle.append("Player returned the relic to the archive")
            print()
            print("  You place the relic back on its pedestal in the archive.")
            print("  The ancient artifact gleams in the candlelight.")
            print("  The Veil shivers. The city breathes easier.")
            return True
        elif "relic" in arg:
            print(f"  You need to be at the archive. You are at: {room}")
            return False
        print(f"  You don't know where to return {arg}.")
        return False

    if verb in ("investigate", "examine", "search"):
        if not arg:
            print("  Investigate what?")
            return False
        res = execute_tool(engine.tool_ctx, "investigate", "Player", arg)
        print(f"  {res.message}")
        engine.tom.learn("Player", f"investigated {arg}")
        return True

    if verb in ("cast",):
        if not arg:
            print("  Cast what?")
            return False
        res = execute_tool(engine.tool_ctx, "cast", "Player", arg)
        print(f"  {res.message}")
        return True

    if verb in ("wait", "z"):
        print("  You wait.")
        return True

    if verb in ("who",):
        print("\n  Who is where:")
        by_room = {}
        for name, room in engine.world.locations.items():
            by_room.setdefault(room, []).append(name)
        for room, agents in sorted(by_room.items()):
            print(f"  {room}: {', '.join(agents)}")
        return False

    if verb in ("status", "stat"):
        room = engine.world.locations.get("Player", "?")
        print(f"\n  Player @ {room} | tick {engine.clock.tick_n} | {engine.clock.period}")
        print(f"  AtomSpace: {len(list(engine.aspace))} atoms")
        for fid, disp in engine.factions.dispositions().items():
            bar = '#' * int(abs(disp) * 20)
            print(f"  {fid}: {disp:+.2f} [{bar}]")
        for t in engine.director.threads:
            if t.active:
                print(f"  Thread: {t.id} tension={t.tension:.2f}")
        return False

    if verb in ("facts", "k"):
        print("\n  What you know:")
        for fact in sorted(engine.tom.knowledge.get("Player", set())):
            print(f"    - {fact}")
        return False

    if verb in ("goals",):
        print("\n  NPC Goals:")
        for name, cog in engine.cognition.items():
            active = [g for g in cog.goals if g.status.value == "active"]
            if active:
                top = max(active, key=lambda g: g.priority)
                print(f"  {name:10s} ({cog.faction:8s}): {top.name} ({top.reason}) p={top.priority:.2f}")
        return False

    if verb in ("history",):
        print("\n  Conversations:")
        for u in engine.dialogue.memory.history[-15:]:
            if u.speaker == "Player" or u.listener == "Player":
                print(f"  [{u.turn:3d}] {u.speaker} → {u.listener}: \"{u.text}\"")
        return False

    if verb in ("map", "m"):
        print("\n  ┌─────────────────────────────────────────┐")
        print("  │    [bell_tower]                         │")
        print("  │         |                               │")
        print("  │  [archive]--[SQUARE]--[tavern]          │")
        print("  │      |         |          |             │")
        print("  │  [sanctum]  [market]---[alley]          │")
        print("  └─────────────────────────────────────────┘")
        current = engine.world.locations.get("Player", "square")
        print(f"  You are at: {current}")
        return False

    if verb in ("help", "h", "?"):
        print(__doc__)
        print("  go <room> | look | talk <npc> | ask <npc> <topic> | take <item>")
        print("  return <item> | investigate <topic> | cast <spell> | wait")
        print("  who | status | facts | goals | history | map | save | load | quit")
        return False

    if verb.startswith("save"):
        path = arg or "save.json"
        with open(path, "w") as f:
            json.dump(engine.save_state(), f, indent=2)
        print(f"  Saved to {path}")
        return False

    if verb.startswith("load"):
        path = arg or "save.json"
        if os.path.exists(path):
            with open(path) as f:
                engine.load_state(json.load(f))
            print(f"  Loaded from {path}")
            show_room(engine)
        else:
            print(f"  Not found: {path}")
        return False

    # Unknown: try as free-text speech to nearby NPCs
    if raw.strip():
        engine.player.perceive_text(raw.strip(), "Player")
        current = engine.world.locations.get("Player", "square")
        others = [n for n, r in engine.world.locations.items() if r == current and n != "Player"]
        if others:
            import random
            responder = random.choice(others)
            result = engine.player_talks_to(responder)
            print(f"\n  {result}")
        else:
            print("  You mutter to yourself.")
        return True

    return False


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--load", type=str)
    args = ap.parse_args()

    engine = Engine(seed=args.seed)
    if args.load and os.path.exists(args.load):
        with open(args.load) as f:
            engine.load_state(json.load(f))

    print()
    print("  ╔══════════════════════════════════════════════╗")
    print("  ║            VELESGRAD v2                      ║")
    print("  ║  Return the stolen relic to the archive.     ║")
    print("  ╚══════════════════════════════════════════════╝")
    print()
    print("  Type 'help' for commands.")
    show_room(engine)

    while True:
        try:
            raw = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  Farewell.")
            break

        if not raw:
            print(engine.turn())
            engine._auto_save()
            continue

        result = parse_command(engine, raw)
        if result == "quit":
            engine._auto_save()
            print("  Farewell.")
            break
        if result == True:
            print(engine.turn())
            engine._auto_save()


if __name__ == "__main__":
    main()
