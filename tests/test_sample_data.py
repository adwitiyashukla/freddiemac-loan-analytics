import re

from freddie_pipeline.loader import FIELD_COUNT
from freddie_pipeline.sample_data import (
    generate_loan,
    generate_sample,
    origination_line,
    performance_lines,
)

LSN_PATTERN = re.compile(r"^F22Q[1-4]\d{7}$")


def test_generation_is_deterministic():
    a = generate_loan(7, seed=42)
    b = generate_loan(7, seed=42)
    assert a == b
    assert performance_lines(a, seed=42) == performance_lines(b, seed=42)


def test_different_seed_changes_output():
    assert generate_loan(7, seed=42) != generate_loan(7, seed=43)


def test_origination_line_layout():
    for i in range(200):
        loan = generate_loan(i, seed=1)
        fields = origination_line(loan).split("|")
        assert len(fields) == FIELD_COUNT
        assert LSN_PATTERN.match(fields[19])
        credit_score = int(fields[0])
        assert credit_score == 9999 or 600 <= credit_score <= 832
        assert fields[15] == "FRM"
        assert 1 <= int(fields[11]) <= 97
        assert int(fields[8]) >= int(fields[11])
        assert fields[2] in ("Y", "N")
        assert re.match(r"^20\d{4}$", fields[1])


def test_performance_history_shape():
    loan = generate_loan(3, seed=5)
    rows = [line.split("|") for line in performance_lines(loan, seed=5)]
    assert all(len(r) == FIELD_COUNT for r in rows)
    assert rows[0][4] == "000"
    ages = [int(r[4]) for r in rows]
    assert ages == list(range(len(rows)))
    months = [r[1] for r in rows]
    assert months == sorted(months)
    for r in rows[:-1]:
        assert r[8] == ""
    for r in rows:
        assert re.match(r"^\d+$", r[3])
        assert float(r[2]) >= 0


def test_terminated_loans_end_with_zero_balance():
    terminated = 0
    for i in range(400):
        loan = generate_loan(i, seed=9)
        rows = [line.split("|") for line in performance_lines(loan, seed=9)]
        last = rows[-1]
        if last[8]:
            terminated += 1
            assert last[8] in ("01", "03", "09")
            assert last[2] == "0.00"
            assert last[9] == last[1]
            assert float(last[26]) > 0
            if last[8] in ("03", "09"):
                assert float(last[21]) >= 0
    assert terminated > 10


def test_risk_signal_low_fico_more_delinquent():
    low, low_bad, high, high_bad = 0, 0, 0, 0
    for i in range(3000):
        loan = generate_loan(i, seed=11)
        if loan.credit_score == 9999:
            continue
        ever_d90 = any(
            int(line.split("|")[3]) >= 3
            for line in performance_lines(loan, seed=11)
        )
        if loan.credit_score < 700:
            low += 1
            low_bad += ever_d90
        elif loan.credit_score >= 780:
            high += 1
            high_bad += ever_d90
    assert low > 100 and high > 100
    assert low_bad / low > 2 * (high_bad / high or 1 / high)


def test_generate_sample_files(tmp_path):
    stats = generate_sample(tmp_path, n_loans=50, seed=2)
    orig = stats["origination_file"].read_text().splitlines()
    svcg = stats["performance_file"].read_text().splitlines()
    assert len(orig) == 50
    assert stats["n_performance_rows"] == len(svcg)
    assert all(len(line.split("|")) == FIELD_COUNT for line in orig)
    assert all(len(line.split("|")) == FIELD_COUNT for line in svcg)
    lsns = {line.split("|")[19] for line in orig}
    assert len(lsns) == 50
    assert {line.split("|")[0] for line in svcg} <= lsns
