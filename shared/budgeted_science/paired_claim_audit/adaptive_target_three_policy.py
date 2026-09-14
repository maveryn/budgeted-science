"""Shared planning investigator with a structured three-claim output adapter.

No physics/evaluator imports. All predictions are fitted from available evidence.
The acquisition rule still targets parameter covariance, not verdict utility.
"""

import numpy as np

from ..resource_planning.adaptive_design import Forward, run_adaptive_design
from .target_three_policy import Tools, inferred_verdicts


class AdaptiveTools(Tools):
    """Reuse the existing public report and metered audit-tool adapter."""

    def submit(self, theta):
        evidence = self.evidence()
        model = Forward(evidence, self.public_config)
        point = (np.asarray(theta, float) - model.lower) / model.width
        mean, variance = model.predict(point, fidelity=1)
        # This is prediction by the fitted approximation, NOT a physical solve.
        with np.errstate(over="ignore", under="ignore", invalid="ignore"):
            prediction = (model.scale * np.exp(mean[0] * model.times)).reshape(-1, 2)
        verdicts, quantities = inferred_verdicts(self.public, theta, prediction)
        valid = bool(np.isfinite(prediction).all() and np.all(prediction > 0))
        self.emit("adaptive_audit_prediction", theta_hat=list(theta),
                  predicted_table=prediction.tolist() if np.isfinite(prediction).all() else None,
                  prediction_valid=valid, transformed_mean=mean[0].tolist(),
                  transformed_gp_variance=float(variance[0]),
                  estimated_quantities=quantities, verdicts=verdicts,
                  note="Fitted multifidelity prediction; plug-in verdicts, not certified confidence.")
        ids = ["report", "original"] + [s["result_id"] for s in evidence["simulations"]]
        ids += [o["record_id"] for o in evidence["observations"]]
        return self.call(
            "submit", verdicts=verdicts, evidence_ids=list(dict.fromkeys(ids)),
            explanation="Adaptive multifidelity parameter investigation using public and purchased "
            "evidence. Claim verdicts use the fitted parameter vector and fitted forward trajectory, "
            "not an unpaid physical simulation. Plug-in decisions, not confidence certification."
        )


def run_policy(call, public, emit, deadline):
    return run_adaptive_design(AdaptiveTools(call, public, emit), seed=0, log=emit, deadline=deadline)
