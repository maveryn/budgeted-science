"""Conservative model-usage reservations, separate from scientific credits."""

from decimal import Decimal

from budgeted_science.burgers.config import integer

MILLION = Decimal(1_000_000)
INPUT_UPPER = Decimal("5")  # Covers standard short-context cache writes.
INPUT_UNCACHED = Decimal("4")
INPUT_CACHED = Decimal("0.4")
OUTPUT = Decimal("20")  # Includes reasoning tokens, not only visible text.
MAX_INPUT_TOKENS = 256_000
PRICING = {
    "date_verified": "2026-09-10", "service_tier": "default",
    "source": "https://developers.openai.com/api/docs/models/gpt-5.6-sol",
    "input_upper_per_million_usd": str(INPUT_UPPER),
    "output_per_million_usd": str(OUTPUT), "max_input_tokens": MAX_INPUT_TOKENS,
    "note": "Conservative model-usage bound, not an invoice; no cache discounts assumed in the ceiling.",
}


class ApiLimit(RuntimeError):
    pass


class AccountingUnavailable(RuntimeError):
    pass


class ApiBudget:
    def __init__(self, ceiling="2.00"):
        self.ceiling = Decimal(ceiling)
        if not self.ceiling.is_finite() or not 0 <= self.ceiling <= 2:
            raise ValueError("invalid API ceiling")
        self.known_upper = Decimal(0)
        self.pending = {}
        self.measured = []

    def reserve(self, request_id, input_tokens, max_output_tokens):
        count = integer(input_tokens, "input_tokens")
        output = integer(max_output_tokens, "max_output_tokens", 1)
        if count > MAX_INPUT_TOKENS:
            raise ApiLimit("input_context_limit")
        if request_id in self.pending:
            raise ValueError("request already reserved")
        amount = (count * INPUT_UPPER + output * OUTPUT) / MILLION
        if self.known_upper + self.reserved + amount > self.ceiling:
            raise ApiLimit("api_ceiling")
        self.pending[request_id] = {"input_tokens": count, "max_output_tokens": output, "amount": amount}
        return amount

    @property
    def reserved(self):
        return sum((v["amount"] for v in self.pending.values()), Decimal(0))

    def settle(self, request_id, usage):
        """Missing/malformed usage retains the entire uncertain reservation."""
        reservation = self.pending[request_id]
        try:
            if not isinstance(usage, dict):
                raise ValueError("missing usage")
            inputs = integer(usage["input_tokens"], "input_tokens")
            outputs = integer(usage["output_tokens"], "output_tokens")
            cached = integer((usage.get("input_tokens_details") or {}).get("cached_tokens", 0), "cached_tokens")
            reasoning = integer((usage.get("output_tokens_details") or {}).get("reasoning_tokens", 0), "reasoning_tokens")
            if cached > inputs or reasoning > outputs:
                raise ValueError("inconsistent token usage")
        except (KeyError, ValueError, TypeError) as exc:
            raise AccountingUnavailable("missing_or_invalid_usage") from exc
        upper = (inputs * INPUT_UPPER + outputs * OUTPUT) / MILLION
        lower = ((inputs - cached) * INPUT_UNCACHED + cached * INPUT_CACHED + outputs * OUTPUT) / MILLION
        self.measured.append({"request_id": request_id, "usage": usage,
                              "standard_cost_lower_usd": str(lower), "conservative_cost_upper_usd": str(upper)})
        del self.pending[request_id]
        self.known_upper += upper
        if inputs > reservation["input_tokens"] or outputs > reservation["max_output_tokens"]:
            # Keep the provider's reported usage; never clamp away a discrepancy.
            raise AccountingUnavailable("usage_exceeded_reservation")

    def status(self):
        return {
            "ceiling_usd": str(self.ceiling), "known_cost_upper_usd": str(self.known_upper),
            "uncertain_reserved_usd": str(self.reserved),
            "committed_upper_usd": str(self.known_upper + self.reserved),
            "remaining_usd": str(max(Decimal(0), self.ceiling - self.known_upper - self.reserved)),
            "measured_responses": list(self.measured), "unsettled_requests": list(self.pending),
            "is_invoice": False,
        }
