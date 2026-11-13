# Velesgrad v2 – Surface realization (queries real OpenCog AtomSpace)

from ..cog.atomspace import AtomSpace, types, get_sti

class TemplateRealizer:
    """Template-based text generation using real AtomSpace context."""
    def __init__(self, atomspace: AtomSpace | None = None):
        self.aspace = atomspace

    def salient_concepts(self, agent_name: str, limit: int = 5) -> list[str]:
        if not self.aspace:
            return []
        atoms = list(self.aspace.get_atoms_by_type(types.ConceptNode))
        atoms.sort(key=lambda a: get_sti(a), reverse=True)
        return [a.name for a in atoms[:limit]]

    def realize_say(self, speaker: str, fact: str, listener_model: dict | None = None) -> str:
        return f"{speaker}: {fact}"

    def realize_narrate(self, scene: dict) -> str:
        room = scene.get("room", "somewhere")
        period = scene.get("period", "day")
        agents = scene.get("agents", [])
        if agents:
            names = ", ".join(agents[:3])
            return f"In {room}, {names} present. It is {period}."
        return f"The {room} is quiet in the {period}."

    def realize_action(self, agent: str, action: str, target: str = "") -> str:
        if target:
            return f"{agent} {action}s {target}."
        return f"{agent} {action}s."
