"""Paid calibration trials, with free retrieval of already acquired records."""

from dataclasses import asdict, dataclass
import hashlib

import numpy as np

from .budget import BudgetExceeded, credits
from .config import RECORD_TIMES, SENSOR_POSITIONS, finite_real, integer, sensor_index


@dataclass(frozen=True)
class ObservationRecord:
    record_id: str
    sensor_id: int
    position: float
    times: tuple[float, ...]
    values: tuple[float, ...]
    noise_std: float
    replicate_index: int

    def __post_init__(self):
        sensor_index(self.sensor_id)
        if not isinstance(self.record_id, str) or not self.record_id:
            raise ValueError("record_id must be a nonempty string")
        if self.position != SENSOR_POSITIONS[self.sensor_id] or tuple(self.times) != RECORD_TIMES:
            raise ValueError("record must use the declared calibration sensor and times")
        if len(self.values) != len(RECORD_TIMES):
            raise ValueError("record must contain five measurements")
        values = tuple(finite_real(v, "measurement") for v in self.values)
        noise = finite_real(self.noise_std, "noise_std")
        if noise < 0:
            raise ValueError("noise_std must be nonnegative")
        integer(self.replicate_index, "replicate_index")
        object.__setattr__(self, "values", values)
        object.__setattr__(self, "times", tuple(self.times))

    def public(self):
        return asdict(self)


class ObservationService:
    def __init__(self, oracle, ledger, *, seed=0, noise_std=0.01, record_price=2.0):
        self.ledger = ledger
        self._oracle = oracle
        self._seed = integer(seed, "seed")
        self._noise = finite_real(noise_std, "noise_std")
        if self._noise < 0:
            raise ValueError("noise_std must be nonnegative")
        self._price = credits(record_price, "record_price")
        if self._price <= 0:
            raise ValueError("record_price must be positive")
        self._counts = [0] * len(SENSOR_POSITIONS)
        self._records = {}

    def acquire(self, sensor_id, replicates=1):
        sensor_id = sensor_index(sensor_id)
        replicates = integer(replicates, "replicates", 1)
        charge = self._price * replicates
        if not self.ledger.can_charge_observation(charge):
            raise BudgetExceeded("cannot fund the requested batch of calibration trials")
        truth = self._oracle.calibration_record(sensor_id)
        records = []
        for offset in range(replicates):
            index = self._counts[sensor_id] + offset
            key = f"burgers-observation-v1/{self._seed}/{sensor_id}/{index}".encode()
            rng = np.random.default_rng(int.from_bytes(hashlib.sha256(key).digest(), "big"))
            values = truth + rng.normal(0, self._noise, len(RECORD_TIMES))
            records.append(ObservationRecord(
                f"record-{len(self._records) + offset + 1:06d}", sensor_id,
                SENSOR_POSITIONS[sensor_id], RECORD_TIMES, tuple(values), self._noise, index,
            ))
        # A rejected batch consumes neither replicate indices nor budget.
        self.ledger.charge_observation(charge)
        self._counts[sensor_id] += replicates
        for record in records:
            self._records[record.record_id] = record
        return tuple(records)

    def retrieve(self, record_id):
        if not isinstance(record_id, str) or record_id not in self._records:
            raise ValueError("unknown acquired record_id")
        return self._records[record_id]

    def resolve(self, record_ids):
        if isinstance(record_ids, (str, bytes)):
            raise ValueError("record_ids must be a nonempty sequence")
        try:
            ids = tuple(record_ids)
        except TypeError as exc:
            raise ValueError("record_ids must be a nonempty sequence") from exc
        if not ids or any(not isinstance(i, str) for i in ids) or len(set(ids)) != len(ids):
            raise ValueError("record_ids must be nonempty, unique acquired IDs")
        return tuple(self.retrieve(i) for i in ids)
