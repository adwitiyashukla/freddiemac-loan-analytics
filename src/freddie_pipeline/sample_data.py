from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path

from .utils import get_logger

log = get_logger(__name__)

END_MONTH = (2025, 6)

STATE_WEIGHTS = [
    ("CA", 10), ("TX", 8), ("FL", 7), ("NY", 5), ("PA", 4), ("IL", 4),
    ("OH", 4), ("GA", 4), ("NC", 4), ("MI", 3), ("NJ", 3), ("VA", 3),
    ("WA", 3), ("AZ", 3), ("MA", 2), ("TN", 2), ("IN", 2), ("MO", 2),
    ("MD", 2), ("WI", 2), ("CO", 2), ("MN", 2), ("SC", 2), ("AL", 2),
    ("LA", 1), ("KY", 1), ("OR", 1), ("OK", 1), ("CT", 1), ("UT", 1),
    ("IA", 1), ("NV", 1), ("AR", 1), ("MS", 1), ("KS", 1), ("NM", 1),
]

MSA_CODES = [
    "12060", "14460", "16980", "19100", "19820", "26420", "31080", "33100",
    "35620", "37980", "38060", "40140", "41700", "41860", "42660", "45300",
    "47900", "12580", "17140", "28140",
]

QUARTER_BASE_RATE = {1: 3.6, 2: 4.9, 3: 5.5, 4: 6.5}
QUARTER_WEIGHTS = [(1, 40), (2, 28), (3, 20), (4, 12)]

MARKET_RATE_BY_YEAR = {2022: 5.4, 2023: 6.8, 2024: 6.9, 2025: 6.8}

SELLERS = ["Other sellers"] * 6 + ["SAMPLE LENDING CO", "EXAMPLE BANK NA"]
SERVICERS = ["Other servicers"] * 6 + ["SAMPLE SERVICING LLC", "EXAMPLE BANK NA"]


@dataclass
class Loan:
    loan_sequence_number: str
    credit_score: int
    first_payment: tuple[int, int]
    first_time_homebuyer: str
    ltv: int
    cltv: int
    dti: int
    upb: int
    rate: float
    channel: str
    state: str
    property_type: str
    postal_code: str
    msa: str
    mi_pct: str
    occupancy: str
    units: int
    purpose: str
    term: int
    borrowers: int
    seller: str
    servicer: str
    super_conforming: str


def _ym_index(ym: tuple[int, int]) -> int:
    return ym[0] * 12 + (ym[1] - 1)


def _ym_from_index(idx: int) -> tuple[int, int]:
    return idx // 12, idx % 12 + 1


def _ym_str(ym: tuple[int, int]) -> str:
    return f"{ym[0]:04d}{ym[1]:02d}"


def _fmt_rate(rate: float) -> str:
    text = f"{rate:.3f}".rstrip("0").rstrip(".")
    return text if text else "0"


def _weighted_choice(rng: random.Random, pairs) -> str:
    total = sum(w for _, w in pairs)
    pick = rng.uniform(0, total)
    acc = 0.0
    for value, weight in pairs:
        acc += weight
        if pick <= acc:
            return value
    return pairs[-1][0]


def generate_loan(index: int, seed: int) -> Loan:
    rng = random.Random(f"orig:{seed}:{index}")

    quarter = int(_weighted_choice(rng, [(str(q), w) for q, w in QUARTER_WEIGHTS]))
    lsn = f"F22Q{quarter}{index + 1:07d}"

    credit_score = min(832, max(600, int(rng.gauss(748, 42))))
    if rng.random() < 0.003:
        credit_score = 9999

    purpose = _weighted_choice(rng, [("P", 55), ("C", 25), ("N", 20)])
    if purpose == "P":
        ltv = min(97, max(40, int(rng.gauss(83, 12))))
    else:
        ltv = min(95, max(20, int(rng.gauss(62, 15))))
    cltv = ltv if rng.random() < 0.85 else min(ltv + rng.randint(1, 15), 110)
    dti = min(50, max(8, int(rng.gauss(34, 8))))
    if rng.random() < 0.01:
        dti = 999

    upb = int(min(970_000, max(30_000, rng.lognormvariate(12.55, 0.45))))
    upb = round(upb, -3)

    fico_for_pricing = 748 if credit_score == 9999 else credit_score
    rate = (
        QUARTER_BASE_RATE[quarter]
        + (740 - fico_for_pricing) * 0.0022
        + max(0, ltv - 75) * 0.006
        + (0.25 if purpose == "C" else 0.0)
        + rng.gauss(0, 0.18)
    )
    rate = max(2.0, round(rate * 8) / 8)

    first_month = (quarter - 1) * 3 + rng.randint(1, 3)
    first_payment = (2022, first_month + 2) if first_month <= 10 else (2023, first_month - 10)

    state = _weighted_choice(rng, STATE_WEIGHTS)
    term = int(_weighted_choice(rng, [("360", 82), ("240", 6), ("180", 10), ("120", 2)]))

    return Loan(
        loan_sequence_number=lsn,
        credit_score=credit_score,
        first_payment=first_payment,
        first_time_homebuyer=(
            "Y" if purpose == "P" and rng.random() < 0.42 else "N"
        ),
        ltv=ltv,
        cltv=max(ltv, cltv),
        dti=dti,
        upb=upb,
        rate=rate,
        channel=_weighted_choice(rng, [("R", 55), ("C", 30), ("B", 15)]),
        state=state,
        property_type=_weighted_choice(
            rng, [("SF", 68), ("PU", 19), ("CO", 10), ("MH", 2), ("CP", 1)]
        ),
        postal_code=f"{rng.randint(10, 996) * 100:05d}",
        msa=rng.choice(MSA_CODES) if rng.random() < 0.72 else "",
        mi_pct=(
            f"{rng.choice([6, 12, 25, 30, 35]):03d}" if ltv > 80 else "000"
        ),
        occupancy=_weighted_choice(rng, [("P", 88), ("I", 7), ("S", 5)]),
        units=1 if rng.random() < 0.95 else rng.randint(2, 4),
        purpose=purpose,
        term=term,
        borrowers=1 if rng.random() < 0.45 else 2,
        seller=rng.choice(SELLERS),
        servicer=rng.choice(SERVICERS),
        super_conforming="Y" if upb > 647_200 else "",
    )


def origination_line(loan: Loan) -> str:
    maturity_idx = _ym_index(loan.first_payment) + loan.term - 1
    fields = [
        str(loan.credit_score),
        _ym_str(loan.first_payment),
        loan.first_time_homebuyer,
        _ym_str(_ym_from_index(maturity_idx)),
        loan.msa,
        loan.mi_pct,
        str(loan.units),
        loan.occupancy,
        str(loan.cltv),
        str(loan.dti),
        str(loan.upb),
        str(loan.ltv),
        _fmt_rate(loan.rate),
        loan.channel,
        "N",
        "FRM",
        loan.state,
        loan.property_type,
        loan.postal_code,
        loan.loan_sequence_number,
        loan.purpose,
        str(loan.term),
        f"{loan.borrowers:02d}",
        loan.seller,
        loan.servicer,
        loan.super_conforming,
        "",
        "9",
        "",
        str(random.Random(f"pvm:{loan.loan_sequence_number}").choice([2, 2, 2, 3, 9])),
        "N",
        "7",
    ]
    return "|".join(fields)


def _monthly_payment(upb: float, annual_rate: float, term: int) -> float:
    monthly_rate = annual_rate / 100 / 12
    if monthly_rate == 0:
        return upb / term
    factor = (1 + monthly_rate) ** term
    return upb * monthly_rate * factor / (factor - 1)


def _delinquency_hazard(loan: Loan) -> float:
    fico = 748 if loan.credit_score == 9999 else loan.credit_score
    dti = 34 if loan.dti == 999 else loan.dti
    hazard = 0.0011
    hazard *= 2.718 ** ((715 - fico) / 60.0)
    hazard *= 1 + max(0, loan.ltv - 70) / 55.0
    hazard *= 1 + max(0, dti - 35) / 45.0
    hazard *= 1.6 if loan.occupancy == "I" else 1.0
    return min(hazard, 0.05)


def _prepay_hazard(loan: Loan, year: int) -> float:
    market = MARKET_RATE_BY_YEAR.get(year, 6.8)
    incentive = max(0.0, loan.rate - market)
    return min(0.004 + incentive * 0.009, 0.08)


def performance_lines(loan: Loan, seed: int) -> list[str]:
    rng = random.Random(f"perf:{seed}:{loan.loan_sequence_number}")
    payment = _monthly_payment(loan.upb, loan.rate, loan.term)
    monthly_rate = loan.rate / 100 / 12

    start_idx = _ym_index(loan.first_payment) - 1
    end_idx = _ym_index(END_MONTH)
    upb = float(loan.upb)
    state = 0
    lines: list[str] = []

    for idx in range(start_idx, end_idx + 1):
        age = idx - start_idx
        year, _ = _ym_from_index(idx)
        ym = _ym_str(_ym_from_index(idx))
        remaining = max(loan.term - age, 0)

        terminated = None
        if age > 0:
            if state == 0:
                if rng.random() < _prepay_hazard(loan, year):
                    terminated = "01"
                elif rng.random() < _delinquency_hazard(loan):
                    state = 1
                else:
                    upb = max(upb - (payment - upb * monthly_rate), 0.0)
            else:
                roll = rng.random()
                if roll < 0.34:
                    state = 0
                elif roll < 0.74:
                    state += 1
                if state >= 6 and rng.random() < 0.28:
                    terminated = "09" if rng.random() < 0.6 else "03"

        reported_upb = max(round(upb, -3), 1000.0) if upb > 500 else round(upb, 2)
        est_ltv = ""
        if age % 3 == 0 or state > 0:
            drift = 1 - 0.004 * age
            est_ltv = str(max(1, min(998, int(loan.ltv * (upb / loan.upb) * drift))))

        base = {
            "upb": f"{reported_upb:.2f}",
            "status": str(state),
            "age": f"{age:03d}",
            "remaining": str(remaining),
            "rate": _fmt_rate(loan.rate),
        }

        if terminated == "01":
            lines.append(_perf_line(loan, ym, "0.00", str(state), base["age"],
                                    "0", base["rate"], zb_code="01", zb_ym=ym,
                                    removal_upb=f"{reported_upb:.2f}", est_ltv=""))
            break
        if terminated in ("03", "09"):
            months_late = state
            accrued = upb * monthly_rate * months_late
            proceeds = upb * rng.uniform(0.60, 0.92)
            expenses = upb * rng.uniform(0.03, 0.09)
            legal = expenses * 0.32
            maintenance = expenses * 0.28
            taxes = expenses * 0.25
            misc = expenses - legal - maintenance - taxes
            loss = upb - proceeds + expenses + accrued
            ddlpi_ym = _ym_str(_ym_from_index(idx - months_late))
            lines.append(_perf_line(
                loan, ym, "0.00", str(state), base["age"], "0", base["rate"],
                zb_code=terminated, zb_ym=ym, removal_upb=f"{reported_upb:.2f}",
                est_ltv="", ddlpi=ddlpi_ym,
                proceeds=f"{proceeds:.2f}", expenses=f"{expenses:.2f}",
                legal=f"{legal:.2f}", maintenance=f"{maintenance:.2f}",
                taxes=f"{taxes:.2f}", misc=f"{misc:.2f}", loss=f"{loss:.2f}",
                accrued=f"{accrued:.2f}",
            ))
            break

        lines.append(_perf_line(
            loan, ym, base["upb"], base["status"], base["age"],
            base["remaining"], base["rate"], est_ltv=est_ltv,
        ))
        if remaining <= 0:
            break

    return lines


def _perf_line(
    loan: Loan, ym: str, upb: str, status: str, age: str, remaining: str,
    rate: str, zb_code: str = "", zb_ym: str = "", removal_upb: str = "",
    est_ltv: str = "", ddlpi: str = "", proceeds: str = "", expenses: str = "",
    legal: str = "", maintenance: str = "", taxes: str = "", misc: str = "",
    loss: str = "", accrued: str = "",
) -> str:
    fields = [
        loan.loan_sequence_number,
        ym,
        upb,
        status,
        age,
        remaining,
        "",
        "",
        zb_code,
        zb_ym,
        rate,
        "0.00" if not zb_code else "",
        ddlpi,
        "",
        proceeds,
        "",
        expenses,
        legal,
        maintenance,
        taxes,
        misc,
        loss,
        "",
        "",
        "",
        est_ltv,
        removal_upb,
        accrued,
        "",
        "",
        "",
        upb if not zb_code else "",
    ]
    return "|".join(fields)


def generate_sample(
    out_dir: Path, n_loans: int = 1000, seed: int = 42
) -> dict[str, object]:
    if n_loans < 1:
        raise ValueError("n_loans must be at least 1")
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    orig_path = out_dir / "sample_orig_2022.txt"
    svcg_path = out_dir / "sample_svcg_2022.txt"

    loans = [generate_loan(i, seed) for i in range(n_loans)]
    with orig_path.open("w", encoding="utf-8", newline="\n") as fh:
        for loan in loans:
            fh.write(origination_line(loan) + "\n")

    n_perf = 0
    with svcg_path.open("w", encoding="utf-8", newline="\n") as fh:
        for loan in loans:
            rows = performance_lines(loan, seed)
            n_perf += len(rows)
            fh.write("\n".join(rows) + "\n")

    log.info(
        "Generated %s loans and %s performance rows into %s",
        f"{n_loans:,}", f"{n_perf:,}", out_dir,
    )
    return {
        "origination_file": orig_path,
        "performance_file": svcg_path,
        "n_loans": n_loans,
        "n_performance_rows": n_perf,
    }
