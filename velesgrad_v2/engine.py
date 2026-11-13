# Velesgrad v2 – Main engine
# NPCs have goals, react to dialogue, and pursue agendas.
# All knowledge in OpenCog AtomSpace. Text from Link Grammar.

import random, json

from .cog.atomspace import (
    AtomSpace, TruthValue, ConceptNode, PredicateNode,
    InheritanceLink, ImplicationLink, EvaluationLink, ListLink,
    tv_from_count, get_sti, set_sti, get_tv, set_tv, types, init_atomspace,
)
from .cog.ecan import ECAN, ECANConfig
from .cog.pln import Reasoner
from .cog.psi import PsiModule
from .agents.agent import NPCAgent, PlayerAgent
from .agents.cognition import NPCCognition, GoalStatus
from .dialogue.tom import TheoryOfMind, DialogueManager
from .dialogue.realizer import AtomeseGenerator
from .world.time import Clock
from .world.model import WorldState
from .world.factions import FactionEngine, BeliefStore
from .content.city import build_world, NPC_ROSTER, SEED_FACTS
from .llm.client import get_client
from .tools.registry import ToolContext, execute_tool, REGISTRY
from .story.director import Director


# ── Knowledge acquisition ────────────────────────────────────────────────

def write_event_atoms(asp, event_type: str, agent: str, room: str,
                      target: str = None, extra: dict = None):
    """Write a world event as proper Atomese."""
    agent_concept = ConceptNode(agent)
    room_concept = ConceptNode(room)

    pred_at = PredicateNode("is_at")
    EvaluationLink(pred_at, ListLink(agent_concept, room_concept))

    if event_type == "move":
        EvaluationLink(PredicateNode("moved_to"), ListLink(agent_concept, room_concept))
        InheritanceLink(agent_concept, ConceptNode("traveler"))
    elif event_type == "observe":
        EvaluationLink(PredicateNode("observed"), ListLink(agent_concept, room_concept))
    elif event_type == "investigate" and target:
        EvaluationLink(PredicateNode("investigated"), ListLink(agent_concept, ConceptNode(target)))
        InheritanceLink(ConceptNode(target), ConceptNode("mystery"))
    elif event_type == "converse" and target:
        EvaluationLink(PredicateNode("talked_to"), ListLink(agent_concept, ConceptNode(target)))
    elif event_type == "take" and target:
        EvaluationLink(PredicateNode("possesses"), ListLink(agent_concept, ConceptNode(target)))
    elif event_type == "cast" and target:
        EvaluationLink(PredicateNode("cast_spell"), ListLink(agent_concept, ConceptNode(target)))

    if extra:
        if "faction" in extra:
            EvaluationLink(PredicateNode("member_of"), ListLink(agent_concept, ConceptNode(extra["faction"])))
        if "mood" in extra:
            EvaluationLink(PredicateNode("feels"), ListLink(agent_concept, ConceptNode(extra["mood"])))


def seed_world_knowledge(asp):
    """Seed the AtomSpace with rich world knowledge."""
    import random
    rng = random.Random(123)

    def inh(a, b, s, c, sti=None):
        link = InheritanceLink(ConceptNode(a), ConceptNode(b))
        set_tv(link, TruthValue(s, c))
        if sti: set_sti(link, sti)

    def evl(pred, a, b, s, c, sti=None):
        link = EvaluationLink(PredicateNode(pred), ListLink(ConceptNode(a), ConceptNode(b)))
        set_tv(link, TruthValue(s, c))
        if sti: set_sti(link, sti)

    def imp(a, b, s, c, sti=None):
        link = ImplicationLink(ConceptNode(a), ConceptNode(b))
        set_tv(link, TruthValue(s, c))
        if sti: set_sti(link, sti)

    # ── The stolen relic (central mystery) ───────────────────────────────
    inh("relic", "stolen_artifact", 0.95, 0.9, 15)
    inh("relic", "sacred_object", 0.9, 0.85, 14)
    inh("relic", "veil_relic", 0.95, 0.9, 13)
    evl("was_located_in", "relic", "archive", 0.9, 0.85, 14)
    evl("stolen_by", "relic", "unknown_thief", 0.7, 0.6, 12)
    evl("searched_by", "relic", "hounds", 0.85, 0.8, 11)
    inh("veil_relic", "ancient_artifact", 0.9, 0.85, 10)
    inh("veil_relic", "source_of_power", 0.8, 0.7, 9)

    # ── The Veil ─────────────────────────────────────────────────────────
    inh("veil", "magical_boundary", 0.9, 0.85, 13)
    evl("separates", "veil", "material_world", 0.85, 0.8, 10)
    evl("separates", "veil", "spirit_world", 0.85, 0.8, 10)
    inh("thinning_veil", "dangerous", 0.8, 0.75, 9)
    evl("caused_by", "thinning_veil", "relic_theft", 0.6, 0.5, 8)
    inh("veil_magic", "ancient_power", 0.85, 0.8, 7)
    evl("practiced_by", "veil_magic", "velespriests", 0.9, 0.85, 8)

    # ── The archive ──────────────────────────────────────────────────────
    inh("archive", "knowledge_repository", 0.95, 0.9, 12)
    evl("holds", "archive", "ancient_manuscripts", 0.9, 0.85, 10)
    evl("holds", "archive", "prophecy_records", 0.7, 0.6, 8)
    evl("guarded_by", "archive", "mira", 0.9, 0.85, 9)
    inh("ancient_manuscripts", "irreplaceable", 0.85, 0.8, 6)

    # ── The Hounds ───────────────────────────────────────────────────────
    inh("hounds", "enforcer", 0.95, 0.9, 13)
    evl("patrols", "hounds", "night_streets", 0.9, 0.85, 11)
    evl("answers_to", "hounds", "commander", 0.8, 0.7, 8)
    inh("hounds", "suspicious", 0.7, 0.6, 9)
    evl("suspects", "hounds", "velespriests", 0.65, 0.55, 10)
    evl("suspects", "hounds", "merchants", 0.5, 0.4, 7)
    inh("hound_loyalty", "unwavering", 0.8, 0.7, 6)

    # ── The Velespriests ─────────────────────────────────────────────────
    inh("velespriests", "guardians", 0.9, 0.85, 12)
    inh("velespriests", "keepers_of_veil", 0.9, 0.85, 11)
    evl("reside_in", "velespriests", "sanctum", 0.9, 0.85, 9)
    inh("velespriests", "distrusted", 0.5, 0.4, 8)
    evl("practice", "velespriests", "veil_magic", 0.85, 0.8, 7)

    # ── The Veche (merchant faction) ─────────────────────────────────────
    inh("merchants", "traders", 0.9, 0.85, 11)
    evl("control", "merchants", "market_district", 0.85, 0.8, 9)
    inh("merchants", "opportunistic", 0.7, 0.6, 8)
    evl("spread", "merchants", "rumors", 0.8, 0.7, 10)
    inh("veche", "merchant_guild", 0.9, 0.85, 9)

    # ── The bell tower ───────────────────────────────────────────────────
    inh("bell", "signal", 0.9, 0.85, 11)
    evl("signals", "bell", "gathering", 0.85, 0.8, 10)
    evl("signals", "bell", "danger", 0.6, 0.5, 8)
    evl("rung_by", "bell", "watchman", 0.8, 0.7, 7)
    inh("bell_tower", "landmark", 0.9, 0.85, 8)

    # ── The market ───────────────────────────────────────────────────────
    inh("market", "trade_hub", 0.95, 0.9, 11)
    evl("known_for", "market", "spices", 0.8, 0.7, 8)
    evl("known_for", "market", "rumors", 0.85, 0.8, 10)
    evl("sells", "market", "exotic_goods", 0.7, 0.6, 7)
    inh("market", "busy_place", 0.85, 0.8, 6)

    # ── The tavern ───────────────────────────────────────────────────────
    inh("tavern", "gossip_hub", 0.9, 0.85, 10)
    evl("serves", "tavern", "mead", 0.9, 0.85, 7)
    evl("hosts", "tavern", "travelers", 0.8, 0.7, 8)
    inh("tavern", "warm_place", 0.85, 0.8, 6)
    evl("rumored_at", "tavern", "stranger_sighting", 0.5, 0.4, 9)

    # ── The sanctum ──────────────────────────────────────────────────────
    inh("sanctum", "sacred_place", 0.95, 0.9, 11)
    evl("protected_by", "sanctum", "ancient_wards", 0.85, 0.8, 8)
    inh("sanctum", "place_of_prayer", 0.9, 0.85, 7)
    evl("contains", "sanctum", "veil_shrine", 0.8, 0.7, 6)

    # ── The alley ────────────────────────────────────────────────────────
    inh("alley", "shadowed_place", 0.9, 0.85, 8)
    evl("known_for", "alley", "secrets", 0.7, 0.6, 9)
    inh("alley", "dangerous_at_night", 0.75, 0.7, 7)

    # ── History and legend ───────────────────────────────────────────────
    inh("velesgrad", "ancient_city", 0.95, 0.9, 10)
    inh("velesgrad", "city_of_veils", 0.85, 0.8, 9)
    evl("founded_by", "velesgrad", "veles", 0.7, 0.6, 8)
    inh("veles", "old_god", 0.8, 0.7, 7)
    inh("old_god", "forgotten", 0.6, 0.5, 6)
    evl("protects", "veles", "velesgrad", 0.7, 0.6, 8)
    inh("city_curse", "ancient_burden", 0.65, 0.55, 7)

    # ── The theft mystery ────────────────────────────────────────────────
    evl("happened_at", "theft", "deep_night", 0.85, 0.8, 10)
    evl("witnessed_by", "theft", "nobody", 0.8, 0.7, 9)
    inh("theft", "inside_job", 0.5, 0.4, 11)
    inh("theft", "outside_job", 0.4, 0.3, 8)
    evl("left_behind", "thief", "broken_ward", 0.6, 0.5, 9)
    inh("broken_ward", "clue", 0.7, 0.6, 8)

    # ── Hierarchy for PLN deduction chains ───────────────────────────────
    inh("stolen_artifact", "valuable", 0.9, 0.85, 8)
    inh("sacred_object", "ancient", 0.85, 0.8, 7)
    inh("enforcer", "dangerous", 0.8, 0.75, 7)
    inh("guardians", "trustworthy", 0.7, 0.65, 6)
    inh("knowledge_repository", "important", 0.85, 0.8, 7)
    inh("magical_boundary", "fragile", 0.75, 0.7, 6)
    inh("sacred_place", "well_protected", 0.8, 0.75, 6)
    inh("trade_hub", "crowded", 0.85, 0.8, 6)
    inh("signal", "urgent", 0.7, 0.65, 6)
    inh("gossip_hub", "place_of_rumors", 0.9, 0.85, 7)
    inh("mystery", "worth_investigating", 0.8, 0.75, 7)
    inh("ancient_artifact", "powerful", 0.8, 0.7, 7)
    inh("inside_job", "betrayal", 0.7, 0.6, 6)
    inh("ancient_city", "layered_history", 0.75, 0.7, 5)

    # ── Implications ─────────────────────────────────────────────────────
    imp("stolen_artifact", "hounds_alert", 0.85, 0.8, 9)
    imp("magical_boundary", "magic_stronger", 0.8, 0.7, 7)
    imp("inside_job", "hounds_suspect_velespriests", 0.6, 0.5, 8)
    imp("thinning_veil", "spirits_restless", 0.7, 0.6, 7)
    imp("relic_returned", "veil_restored", 0.8, 0.7, 8)

    # ── Agent faction memberships ────────────────────────────────────────
    for spec in NPC_ROSTER:
        memb = EvaluationLink(PredicateNode("member_of"),
                              ListLink(ConceptNode(spec["name"]), ConceptNode(spec["faction"])))
        set_tv(memb, TruthValue(0.95, 0.9))
        set_sti(ConceptNode(spec["name"]), 10.0)


# ── Engine ───────────────────────────────────────────────────────────────

class Engine:
    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self.seed = seed
        self.clock = Clock()
        self.aspace = AtomSpace()
        init_atomspace(self.aspace)
        self.ecan = ECAN(self.aspace, ECANConfig())
        self.reasoner = Reasoner(self.aspace)
        self.world = build_world()
        self.tom = TheoryOfMind()
        self.generator = AtomeseGenerator(self.aspace)
        self.dialogue = DialogueManager(self.tom, self.generator)
        self.llm = get_client("template")
        self.factions = FactionEngine()
        self.beliefs = BeliefStore(self.aspace, self.reasoner)
        self.director = Director(rng=random.Random(seed))
        self.director.establish_beginning()
        self.tool_ctx = ToolContext(self.world, self.aspace, self.dialogue, self.factions, self.clock)

        seed_world_knowledge(self.aspace)

        # Create NPCs with cognition
        self.npcs: list[NPCAgent] = []
        self.cognition: dict[str, NPCCognition] = {}

        for spec in NPC_ROSTER:
            psi = PsiModule(rng=random.Random(self.rng.randint(0, 99999)))
            agent = NPCAgent(
                spec["name"], spec["faction"], spec["home"],
                atomspace=self.aspace, ecan=self.ecan,
                reasoner=self.reasoner, psi=psi, llm=self.llm,
            )
            self.npcs.append(agent)
            self.world.locations[agent.name] = spec["home"]
            self.tom.learn(agent.name, "relic is a stolen_artifact")
            self.tom.learn(agent.name, "hounds are enforcers")
            self.tom.learn(agent.name, "veil is a magical_boundary")

            # Goal-driven cognition
            cog = NPCCognition(agent.name, spec["faction"], random.Random(self.rng.randint(0, 99999)))
            self.cognition[agent.name] = cog

        self.player = PlayerAgent(
            "Player", atomspace=self.aspace, ecan=self.ecan,
            reasoner=self.reasoner, psi=PsiModule(rng=self.rng), llm=self.llm,
        )
        self.world.locations["Player"] = "square"
        self.tom.learn("Player", "relic is a stolen_artifact")
        self.tom.learn("Player", "hounds are enforcers")

    def _get_co_present(self, agent_name: str) -> list[str]:
        room = self.world.locations.get(agent_name, "")
        return [n for n, r in self.world.locations.items() if r == room and n != agent_name]

    def _build_edges(self) -> list[tuple]:
        edges = []
        loc_agents: dict[str, list[str]] = {}
        for agent, room in self.world.locations.items():
            loc_agents.setdefault(room, []).append(agent)
        for room, agents in loc_agents.items():
            for i, a1 in enumerate(agents):
                for a2 in agents[i + 1:]:
                    n1 = ConceptNode(a1)
                    n2 = ConceptNode(a2)
                    edges.append((n1, n2, 0.3))
                    edges.append((n2, n1, 0.3))
        return edges

    def _build_pairs(self) -> list[tuple]:
        pairs = []
        loc_agents: dict[str, list[str]] = {}
        for agent, room in self.world.locations.items():
            loc_agents.setdefault(room, []).append(agent)
        for room, agents in loc_agents.items():
            for i, a1 in enumerate(agents):
                for a2 in agents[i + 1:]:
                    pairs.append((ConceptNode(a1), ConceptNode(a2)))
        return pairs

    def _npc_speak_to(self, npc: NPCAgent, listener: str, room: str) -> str | None:
        """Generate speech from NPC to listener. Returns text or None."""
        others = self._get_co_present(npc.name)
        utt = self.dialogue.generate_utterance(
            npc.name, listener, self.clock.tick_n,
            room=room, agents_present=others, hour=self.clock.hour
        )
        if utt:
            return utt.text
        return None

    def _player_react_to_speech(self, speaker: str, text: str):
        """Record that player heard something. Updates ToM."""
        self.tom.learn("Player", text)
        self.player.perceive_text(text, speaker)

    def turn_npc(self, npc: NPCAgent) -> str:
        """Run one NPC's cognitive cycle with goal-driven behavior."""
        cog = self.cognition.get(npc.name)
        room = self.world.locations.get(npc.name, npc.home_room)
        others = self._get_co_present(npc.name)

        # Perceive: write co-presence
        for other in others:
            write_event_atoms(self.aspace, "observe", npc.name, room)

        # Check if NPC has the relic and should return it
        if cog and cog.has_item("relic"):
            if room == "archive":
                action = ("return", "relic")
            else:
                action = ("move", "archive")
        elif cog:
            action = cog.get_next_action(
                self.world.locations, self.world.rooms,
                npcs_present=[o for o in others if o != "Player"]
            )
            if action is None:
                action = ("observe", None)
        else:
            action = ("observe", None)

        verb, target = action
        result_text = ""

        # Handle "react_to" — NPC was talked to, respond
        if verb == "react_to":
            speaker = target or "someone"
            response = self._npc_speak_to(npc, speaker, room)
            if response:
                result_text = f"{npc.name} responds: \"{response}\""
                if speaker == "Player":
                    self._player_react_to_speech(npc.name, response)
            else:
                result_text = f"{npc.name} nods silently."
            write_event_atoms(self.aspace, "converse", npc.name, room, speaker)
            return result_text

        # Execute action
        if verb in REGISTRY:
            res = execute_tool(self.tool_ctx, verb, npc.name, target)
            result_text = res.message
            if cog:
                cog.on_action_result(verb, res.ok)
            # If NPC took the relic, record it in cognition
            if verb == "take" and target and "relic" in target.lower() and res.ok:
                if cog:
                    cog.memory.append(f"took {target}")
        elif verb == "return" and target and "relic" in str(target).lower():
            npc_room = self.world.locations.get(npc.name, "")
            if npc_room == "archive" and cog and cog.has_item("relic"):
                n = ConceptNode("relic_returned_to_archive")
                set_tv(n, tv_from_count(1.0, 10.0))
                result_text = f"{npc.name} returns the relic to the archive!"
                self.tom.learn(npc.name, "relic returned to archive")
                self.tool_ctx.chronicle.append(f"{npc.name} returned relic to archive")
                # Clear the "took" marker so they don't loop
                cog.memory = [m for m in cog.memory if not m.startswith("took relic")]
                cog.memory.append("returned relic to archive")
                # Mark the goal as done
                if cog.current_goal and cog.current_goal.name == "find_relic":
                    cog.current_goal.status = GoalStatus.COMPLETED
                write_event_atoms(self.aspace, "return", npc.name, "archive", "relic")
            elif cog and cog.has_item("relic"):
                self.world.move(npc.name, "archive")
                result_text = f"{npc.name} heads to the archive with the relic."
                cog.memory.append("moving to archive with relic")
            else:
                result_text = f"{npc.name} examines the empty relic pedestal."
        else:
            result_text = f"{npc.name} {verb}s" + (f" {target}" if target else "")

        # Write event knowledge
        write_event_atoms(self.aspace, verb, npc.name, room, target,
                          extra={"faction": npc.faction})

        # If conversing, generate speech from knowledge graph
        if verb == "converse" and target:
            speech = self._npc_speak_to(npc, target, room)
            if speech:
                result_text = f"{npc.name} → {target}: \"{speech}\""
                # If target is player, update player knowledge
                if target == "Player":
                    self._player_react_to_speech(npc.name, speech)
                # If target is another NPC, they react
                elif target in self.cognition:
                    self.cognition[target].on_dialogue_received(npc.name, speech)
            else:
                result_text = f"{npc.name} has nothing new to say to {target}."

        # Faction reactions to events
        if verb == "take" and target and "relic" in str(target).lower():
            self.factions.handle("theft", npc.name)
        elif verb == "cast":
            self.factions.handle("cast", npc.name)

        npc.act(action, self.world)
        return result_text

    def player_talks_to(self, npc_name: str) -> str:
        """Player initiates conversation with an NPC.

        The NPC reacts: stops their current action, generates a response
        from the knowledge graph.
        """
        npc = None
        for n in self.npcs:
            if n.name.lower() == npc_name.lower():
                npc = n
                break
        if not npc:
            return f"There is no one called '{npc_name}'."

        room = self.world.locations.get("Player", "square")
        npc_room = self.world.locations.get(npc.name, "")
        if room != npc_room:
            return f"{npc.name} is not here. They are at {npc_room}."

        # NPC reacts to being talked to
        cog = self.cognition.get(npc.name)
        if cog:
            cog.on_dialogue_received("Player", "")

        # Generate response from knowledge graph
        speech = self._npc_speak_to(npc, "Player", room)
        if speech:
            self._player_react_to_speech(npc.name, speech)
            return f'{npc.name}: "{speech}"'

        return f"{npc.name} has nothing to say."

    def player_asks_about(self, npc_name: str, topic: str) -> str:
        """Player asks an NPC about a topic. NPC searches their knowledge."""
        npc = None
        for n in self.npcs:
            if n.name.lower() == npc_name.lower():
                npc = n
                break
        if not npc:
            return f"There is no one called '{npc_name}'."

        room = self.world.locations.get("Player", "square")
        npc_room = self.world.locations.get(npc.name, "")
        if room != npc_room:
            return f"{npc.name} is not here. They are at {npc_room}."

        # NPC reacts
        cog = self.cognition.get(npc.name)
        if cog:
            cog.on_dialogue_received("Player", topic)

        # Search knowledge graph for topic-related LINKS (relations, not bare nodes)
        from .dialogue.realizer import atom_to_text
        topic_low = topic.lower()
        relevant = []
        for atom in self.aspace:
            type_name = getattr(atom, 'type_name', '')
            # Prefer links — they carry actual knowledge
            if not any(t in type_name for t in ['Inheritance', 'Evaluation', 'Implication']):
                continue
            out = getattr(atom, 'out', [])
            # Does the topic appear anywhere in this link?
            mentions = False
            for o in out:
                o_name = getattr(o, 'name', '').lower()
                if topic_low in o_name:
                    mentions = True
                    break
                # Check nested ListLink args
                o_out = getattr(o, 'out', None)
                if o_out:
                    for oo in o_out:
                        if topic_low in getattr(oo, 'name', '').lower():
                            mentions = True
                            break
                if mentions:
                    break
            if not mentions:
                continue
            text = atom_to_text(atom)
            if text:
                relevant.append((get_sti(atom), text))

        if relevant:
            relevant.sort(key=lambda x: x[0], reverse=True)
            # Pick randomly among top-3 for variety
            import random
            top = relevant[:3]
            text = random.choice(top)[1]
            self._player_react_to_speech(npc.name, text)
            return f'{npc.name}: "{text}"'

        # Fallback: NPC generates any speech
        speech = self._npc_speak_to(npc, "Player", room)
        if speech:
            self._player_react_to_speech(npc.name, speech)
            return f'{npc.name}: "{speech}"'

        return f'{npc.name} shrugs. "I don\'t know much about {topic}."'

    def turn(self) -> str:
        """Run one full game turn."""
        self.clock.tick()
        self.director.tick()
        self.tool_ctx.clock = self.clock

        log = [f"--- tick {self.clock.tick_n} | hour {self.clock.hour:02d}:00 ({self.clock.period}) ---"]

        # NPC turns (goal-driven)
        for npc in self.npcs:
            if self.rng.random() < 0.5:
                res = self.turn_npc(npc)
                if res:
                    log.append(f"  {res}")

        # PLN inference
        inferences = self.reasoner.step()
        if inferences:
            for ir in inferences[:2]:
                log.append(f"  [reason] {ir.rule}: derived (s={ir.tv.mean:.2f})")

        # ECAN
        if self.clock.tick_n % 5 == 0:
            self.ecan.step(self._build_edges(), self._build_pairs())

        # Faction dispositions drive NPC goal priorities
        if self.clock.tick_n % 10 == 0:
            disps = self.factions.dispositions()
            for cog in self.cognition.values():
                cog.apply_faction_disposition(disps)

        # Dialogue decay
        if self.clock.tick_n % 20 == 0:
            self.dialogue.decay_recent()

        # Director
        if self.clock.tick_n % 20 == 0 and len(self.director.threads) < 5:
            t = self.director.spawn_thread()
            log.append(f"  [story] new thread: {t.id} (tension {t.tension:.2f})")

        # Time events
        if self.clock.hour == 6 and self.clock.tick_n > 1:
            log.append("  [world] Dawn breaks.")
        elif self.clock.hour == 21 and self.clock.tick_n > 1:
            log.append("  [world] Night falls.")
        elif self.clock.hour == 12 and self.rng.random() < 0.3:
            log.append("  [world] The bell tower chimes noon.")

        return "\n".join(log)

    def save_state(self) -> dict:
        return {
            "version": 2, "seed": self.seed,
            "clock": self.clock.to_dict(),
            "locations": dict(self.world.locations),
            "plans": {a.name: {"plan": a.plan, "cursor": a.plan_cursor} for a in self.npcs + [self.player]},
            "tom": self.tom.to_dict(),
            "conversation": [
                {"speaker": u.speaker, "listener": u.listener, "text": u.text,
                 "act": u.act.value, "facts": u.facts_conveyed, "turn": u.turn}
                for u in self.dialogue.memory.history
            ],
            "factions": self.factions.dispositions(),
            "director": [
                {"id": t.id, "tension": t.tension, "active": t.active, "age": t.age}
                for t in self.director.threads
            ],
            "ecan": {"sti_bank": self.ecan.sti_bank, "tick_n": self.ecan.tick_n},
            "chronicle": self.tool_ctx.chronicle[-100:],
            "cognition": {
                name: {
                    "goals": [
                        {"name": g.name, "priority": g.priority, "status": g.status.value,
                         "steps_taken": g.steps_taken, "target": g.target, "reason": g.reason}
                        for g in cog.goals
                    ],
                    "memory": cog.memory[-20:],
                    "current_goal": cog.current_goal.name if cog.current_goal else None,
                }
                for name, cog in self.cognition.items()
            },
        }

    def load_state(self, d: dict):
        from .dialogue.tom import Utterance, SpeechAct
        from .story.director import StoryThread
        from .agents.cognition import NPCGoal, GoalStatus

        self.clock.from_dict(d["clock"])
        self.world.locations.update(d.get("locations", {}))
        for a in self.npcs + [self.player]:
            if a.name in d.get("plans", {}):
                pd = d["plans"][a.name]
                a.plan = [tuple(s) for s in pd.get("plan", [])]
                a.plan_cursor = pd.get("cursor", 0)
        if "tom" in d:
            self.tom = TheoryOfMind()
            self.tom.from_dict(d["tom"])
            self.dialogue.tom = self.tom
        self.dialogue.memory.history.clear()
        for u in d.get("conversation", []):
            act = SpeechAct(u.get("act", "statement"))
            self.dialogue.memory.history.append(
                Utterance(u["speaker"], u["listener"], u["text"], act, u.get("facts", []), u["turn"])
            )
        for fid, disp in d.get("factions", {}).items():
            if fid in self.factions.factions:
                self.factions.factions[fid].disposition = disp
        if "director" in d:
            self.director.threads = [StoryThread(**t) for t in d["director"]]
        if "ecan" in d:
            self.ecan.sti_bank = d["ecan"].get("sti_bank", 0.0)
            self.ecan.tick_n = d["ecan"].get("tick_n", 0)
        self.tool_ctx.chronicle = d.get("chronicle", [])
        # Restore cognition
        if "cognition" in d:
            for name, cog_data in d["cognition"].items():
                if name in self.cognition:
                    cog = self.cognition[name]
                    cog.memory = cog_data.get("memory", [])
                    for gd in cog_data.get("goals", []):
                        for g in cog.goals:
                            if g.name == gd["name"]:
                                g.priority = gd["priority"]
                                g.status = GoalStatus(gd["status"])
                                g.steps_taken = gd["steps_taken"]
                                break

    def _auto_save(self):
        import os
        save_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "velesgrad_save.json")
        try:
            with open(save_path, "w") as f:
                json.dump(self.save_state(), f)
        except Exception:
            pass


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Velesgrad v2")
    ap.add_argument("--simulate", type=int, default=0)
    ap.add_argument("--interactive", action="store_true")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--save", type=str)
    ap.add_argument("--load", type=str)
    args = ap.parse_args()
    eng = Engine(seed=args.seed)
    if args.load:
        with open(args.load) as f:
            eng.load_state(json.load(f))
    if args.simulate:
        for _ in range(args.simulate):
            print(eng.turn())
        if args.save:
            with open(args.save, "w") as f:
                json.dump(eng.save_state(), f, indent=2)
    elif args.interactive:
        print("Velesgrad v2 – type 'quit'")
        while True:
            print(eng.turn())
            cmd = input("> ").strip()
            if cmd in ("quit", "exit"):
                break
            if cmd.startswith("save "):
                with open(cmd[5:].strip(), "w") as f:
                    json.dump(eng.save_state(), f, indent=2)
                continue
            eng.player.perceive_text(cmd, "Player")
    else:
        print(eng.turn())


if __name__ == "__main__":
    main()
