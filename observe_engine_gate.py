"""The one place OBSERVE chooses when the behavioral engine runs.

Upstream (observe-perceive) now offers two rules, named in `pediatric_cassette`:

* `widened_provisional` also runs the behavioral engine for a respiratory rate above 35 or a
  temperature above 38.5. Upstream marks that widening PROVISIONAL, pending pediatrician sign-off.
* `conservative_legacy` is the rule OBSERVE has always used: oxygen below 92, or a heart rate
  above 140 or below 90.

OBSERVE keeps the legacy rule until a pediatrician signs off the widened one. To adopt the
widened rule, flip ENGINE_GATE below to `ENGINE_GATE_WIDENED_PROVISIONAL`; nothing else changes.
A decision made under the legacy rule names its gate in the stored audit entry, so it can always
be told apart from one made under the default.

The copied upstream files (observe_consolidated, cassette, pediatric_cassette, kalman_trajectory,
governance_contracts) are byte-identical to observe-perceive and are never edited here.
"""

from observe_consolidated import ObserveClinicalEngine
from pediatric_cassette import (
    ENGINE_GATE_CONSERVATIVE_LEGACY,
    ENGINE_GATE_WIDENED_PROVISIONAL,  # noqa: F401 - named here so adopting the widened rule is one edit
    PediatricCassette,
)

# Legacy rule kept until a pediatrician signs off upstream's widened rule. Flip this one constant to adopt it.
ENGINE_GATE = ENGINE_GATE_CONSERVATIVE_LEGACY


def make_engine(**kwargs) -> ObserveClinicalEngine:
    """An ObserveClinicalEngine with OBSERVE's chosen behavioral-engine gate.

    Every other keyword goes to ObserveClinicalEngine unchanged. A caller that passes its own
    `cassette` keeps it, so a test can still build an engine with another cassette on purpose.
    """
    kwargs.setdefault("cassette", PediatricCassette(engine_gate=ENGINE_GATE))
    return ObserveClinicalEngine(**kwargs)
