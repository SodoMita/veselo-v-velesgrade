# Velesgrad v2 – ECAN (Economic Attention Allocation Network)
# Operates on the REAL OpenCog AtomSpace.
# STI/LTI stored as Values on atoms. STI is CONSERVED.

from dataclasses import dataclass
from .atomspace import (
    AtomSpace, types,
    get_sti, set_sti, get_lti, set_lti, get_vlti, set_vlti, get_tv, set_tv,
    add_sti, _ensure_keys,
)


@dataclass
class ECANConfig:
    rent_per_atom: float = 0.01
    focus_wage: float = 0.05
    sti_floor: float = -400.0
    sti_ceiling: float = 400.0
    spread_fraction: float = 0.15
    focus_capacity: int = 20
    hebb_interval: int = 3
    coactivation_threshold: float = 2.0
    forget_lti_rate: float = 0.5
    min_lti: float = -50.0


class ECAN:
    def __init__(self, atomspace: AtomSpace, cfg: ECANConfig | None = None):
        self.aspace = atomspace
        self.cfg = cfg or ECANConfig()
        self.sti_bank: float = 0.0
        self.tick_n: int = 0
        _ensure_keys(atomspace)

    def spread(self, edges: list[tuple]):
        """Diffuse STI along weighted edges. CONSERVING.
        edges: list of (source_atom, target_atom, weight)
        """
        outflows: dict[int, float] = {}
        transfers: list[tuple] = []

        for src, tgt, weight in edges:
            src_sti = get_sti(src)
            if src_sti <= 0:
                continue
            transfer = src_sti * self.cfg.spread_fraction * max(0.0, weight)
            sid = id(src)
            already = outflows.get(sid, 0.0)
            transfer = min(transfer, max(0.0, src_sti - already))
            if transfer <= 1e-6:
                continue
            outflows[sid] = already + transfer
            transfers.append((src, tgt, transfer))

        for src, tgt, amount in transfers:
            add_sti(src, -amount, self.cfg.sti_floor, self.cfg.sti_ceiling)
            add_sti(tgt, amount, self.cfg.sti_floor, self.cfg.sti_ceiling)

    def rent_collect_wages(self, focus_set: list):
        """Pay rent on all atoms, pay wages to focus atoms."""
        total_rent = 0.0
        for atom in self.aspace:
            sti = get_sti(atom)
            if sti > self.cfg.sti_floor:
                add_sti(atom, -self.cfg.rent_per_atom, self.cfg.sti_floor, self.cfg.sti_ceiling)
                total_rent += self.cfg.rent_per_atom

        total_wages = 0.0
        for atom in focus_set[:self.cfg.focus_capacity]:
            add_sti(atom, self.cfg.focus_wage, self.cfg.sti_floor, self.cfg.sti_ceiling)
            total_wages += self.cfg.focus_wage

        self.sti_bank += total_rent - total_wages

    def focus_atoms(self, k: int | None = None) -> list:
        """Top-k atoms by STI from the real AtomSpace."""
        k = k or self.cfg.focus_capacity
        atoms = list(self.aspace)
        atoms.sort(key=lambda a: get_sti(a), reverse=True)
        return atoms[:k]

    def stimulate(self, atom, amount: float):
        """Inject STI into an atom."""
        add_sti(atom, amount, self.cfg.sti_floor, self.cfg.sti_ceiling)

    def hebbian_learn(self, pairs: list[tuple]):
        """Create/strengthen AssociateLinks between co-activated atoms."""
        from .atomspace import AssociateLink
        if self.tick_n % self.cfg.hebb_interval != 0:
            return
        for a, b in pairs:
            if get_sti(a) > self.cfg.coactivation_threshold and get_sti(b) > self.cfg.coactivation_threshold:
                link = AssociateLink(a, b)
                old_tv = get_tv(link)
                new_count = (old_tv.confidence * 800 / (1 - old_tv.confidence) + 1) if old_tv.confidence < 1.0 else 1
                set_tv(link, TruthValue(min(0.95, old_tv.mean + 0.05), new_count / (new_count + 800)))

    def forget_tick(self) -> list:
        """Push LTI down, return eviction candidates."""
        candidates = []
        for atom in self.aspace:
            lti = get_lti(atom)
            new_lti = lti - self.cfg.forget_lti_rate
            set_lti(atom, new_lti)
            if new_lti <= self.cfg.min_lti and get_vlti(atom) <= 0:
                candidates.append(atom)
        return candidates

    def step(self, spread_edges=None, coactivation_pairs=None) -> list:
        """Run one ECAN cycle on the real AtomSpace."""
        self.tick_n += 1
        focus = self.focus_atoms()
        if spread_edges:
            self.spread(spread_edges)
        self.rent_collect_wages(focus)
        if coactivation_pairs:
            self.hebbian_learn(coactivation_pairs)
        return self.forget_tick()


# Need TruthValue for hebbian_learn
from .atomspace import TruthValue
