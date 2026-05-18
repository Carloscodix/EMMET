"""Compatibility shim. The module was renamed to emmet_newt and its
functions changed name accordingly:

  carlos_bonus            -> pressure_bonus
  edge_potential_carlos   -> edge_potential_pressure
  emmet_carlos_route      -> emmet_pressure_route
  simulate_carlos         -> simulate_pressure

This shim keeps historical scripts under experiments/blood_session/
working. New code should import from emmet_newt directly.
"""
from emmet_newt import (
    overpressure,
    pressure_bonus as carlos_bonus,
    bleeding,
    blood_penalty,
    edge_potential_pressure as edge_potential_carlos,
    emmet_pressure_route as emmet_carlos_route,
    simulate_pressure as simulate_carlos,
    simulate_momentum_live,
    DECAY,
)
