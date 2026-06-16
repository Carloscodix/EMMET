"""Bursty traffic generator for EMMET v2.0 stress tests.

Generates traffic that mimics measured properties of real WAN flows:
  - Flow sizes follow a Lognormal distribution (heavy-tailed: many
    short flows, a few very long ones). Reference: Crovella &
    Bestavros 1997; Sarvotham et al. 2002.
  - Inter-burst gaps follow a Pareto distribution (alpha = 1.5),
    producing the characteristic on/off pattern of Internet traffic.

Output format is a list of (src, dst) pairs compatible with the
existing simulators, plus an optional list of "gap" steps (where
the simulator only applies edge-load decay without routing) to
realize the inter-burst silence.
"""
import random
import math

LOGNORMAL_MU = math.log(3.0)
LOGNORMAL_SIGMA = 1.0
PARETO_ALPHA = 1.5
MAX_FLOW_SIZE = 30
MAX_GAP_STEPS = 10

def sample_flow_size(rng):
    raw = rng.lognormvariate(LOGNORMAL_MU, LOGNORMAL_SIGMA)
    return max(1, min(MAX_FLOW_SIZE, int(round(raw))))

def sample_gap(rng):
    raw = rng.paretovariate(PARETO_ALPHA)
    return max(0, min(MAX_GAP_STEPS, int(round(raw - 1))))

GAP_SENTINEL = ('GAP', 'GAP')  # marker token for inter-burst silence

def gen_bursty(nodes, target_steps, seed):
    """Generate (src,dst) sequence with bursty structure.

    Returns a list of (src, dst) pairs of length ~= target_steps.
    Some positions contain GAP_SENTINEL: the simulator must skip
    routing on those steps and just apply edge-load decay, so the
    network experiences the inter-burst silence.
    """
    rng = random.Random(seed)
    out = []
    while len(out) < target_steps:
        # Start a new burst: pick random src,dst
        src = rng.choice(nodes)
        dst = rng.choice(nodes)
        n_pkts = sample_flow_size(rng)
        out.extend([(src, dst)] * n_pkts)
        # Inter-burst gap
        n_gap = sample_gap(rng)
        out.extend([GAP_SENTINEL] * n_gap)
    return out[:target_steps]

def stats(traf):
    if not traf:
        return {}
    gaps = sum(1 for x in traf if x == GAP_SENTINEL)
    pkts = len(traf) - gaps
    bursts = []
    cur_key = None
    cur_len = 0
    for x in traf:
        if x == GAP_SENTINEL:
            if cur_len > 0:
                bursts.append(cur_len); cur_len = 0; cur_key = None
        elif x == cur_key:
            cur_len += 1
        else:
            if cur_len > 0:
                bursts.append(cur_len)
            cur_key = x; cur_len = 1
    if cur_len > 0:
        bursts.append(cur_len)
    return dict(
        total_steps=len(traf),
        packets=pkts,
        gap_steps=gaps,
        num_bursts=len(bursts),
        burst_mean=(sum(bursts)/len(bursts)) if bursts else 0,
        burst_max=max(bursts) if bursts else 0,
        burst_min=min(bursts) if bursts else 0,
    )


def gen_bursty_weighted(pairs, weights, target_steps, seed):
    """Like gen_bursty, but each burst's (src,dst) is drawn PROPORTIONAL to a
    real demand weight instead of uniformly over node pairs. The ONLY thing
    that changes from gen_bursty is the spatial distribution of demand: the
    temporal burst/gap structure, flow sizes, and inter-burst silence are
    identical, so this isolates the effect of real demand vs uniform."""
    rng = random.Random(seed)
    out = []
    while len(out) < target_steps:
        src, dst = rng.choices(pairs, weights=weights, k=1)[0]
        n_pkts = sample_flow_size(rng)
        out.extend([(src, dst)] * n_pkts)
        n_gap = sample_gap(rng)
        out.extend([GAP_SENTINEL] * n_gap)
    return out[:target_steps]
