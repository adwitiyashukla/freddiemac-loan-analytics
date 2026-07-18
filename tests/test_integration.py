from __future__ import annotations

import psycopg
import pytest

from freddie_pipeline.cli import main
from freddie_pipeline.db import fetch_all, fetch_one
from freddie_pipeline.loader import FIELD_COUNT, load_file

pytestmark = pytest.mark.db

N_LOANS = 400
SEED = 42


@pytest.fixture(scope="module")
def pipeline_run(request, tmp_path_factory):
    test_db_config = request.getfixturevalue("test_db_config")
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("FREDDIE_DB_HOST", test_db_config.db_host)
    monkeypatch.setenv("FREDDIE_DB_PORT", str(test_db_config.db_port))
    monkeypatch.setenv("FREDDIE_DB_USER", test_db_config.db_user)
    monkeypatch.setenv("FREDDIE_DB_PASSWORD", test_db_config.db_password)
    monkeypatch.setenv("FREDDIE_DB_NAME", test_db_config.db_name)
    monkeypatch.setenv("FREDDIE_SQL_DIR", str(test_db_config.sql_dir))

    work = tmp_path_factory.mktemp("pipeline")
    data_dir = work / "sample"
    reports_dir = work / "reports"

    assert main(["generate-sample", "--out-dir", str(data_dir),
                 "--loans", str(N_LOANS), "--seed", str(SEED)]) == 0
    assert main(["init-db"]) == 0
    assert main(["load", "--data-dir", str(data_dir)]) == 0
    assert main(["transform"]) == 0
    assert main(["report", "--out", str(reports_dir)]) == 0

    yield {"config": test_db_config, "data_dir": data_dir, "reports_dir": reports_dir}
    monkeypatch.undo()


@pytest.fixture()
def conn(pipeline_run):
    with psycopg.connect(pipeline_run["config"].conninfo()) as connection:
        yield connection


def test_bronze_counts_match_input_files(pipeline_run, conn):
    orig_lines = (pipeline_run["data_dir"] / "sample_orig_2022.txt").read_text().splitlines()
    svcg_lines = (pipeline_run["data_dir"] / "sample_svcg_2022.txt").read_text().splitlines()
    assert fetch_one(conn, "SELECT COUNT(*) FROM bronze.origination_raw")[0] == len(orig_lines)
    assert fetch_one(conn, "SELECT COUNT(*) FROM bronze.performance_raw")[0] == len(svcg_lines)
    assert fetch_one(conn, "SELECT COUNT(*) FROM bronze.load_rejects")[0] == 0
    assert fetch_one(conn, "SELECT COUNT(*) FROM bronze.load_audit")[0] == 2


def test_silver_typing_and_keys(conn):
    assert fetch_one(conn, "SELECT COUNT(*) FROM silver.origination")[0] == N_LOANS
    avg_score = fetch_one(conn, "SELECT AVG(credit_score) FROM silver.origination")[0]
    assert 700 < float(avg_score) < 790
    max_dti = fetch_one(conn, "SELECT MAX(dti) FROM silver.origination")[0]
    assert max_dti <= 50
    bad = fetch_one(
        conn,
        "SELECT COUNT(*) FROM silver.performance "
        "WHERE reporting_month IS NULL OR current_actual_upb < 0",
    )[0]
    assert bad == 0


def test_gold_marts_populated_and_sane(conn):
    for table in ("loan_outcomes", "portfolio_summary", "monthly_portfolio",
                  "vintage_delinquency", "transition_matrix", "state_risk",
                  "segment_risk"):
        assert fetch_one(conn, f"SELECT COUNT(*) FROM gold.{table}")[0] > 0

    assert fetch_one(conn, "SELECT n_loans FROM gold.portfolio_summary")[0] == N_LOANS

    bad_rates = fetch_one(
        conn,
        "SELECT COUNT(*) FROM gold.monthly_portfolio "
        "WHERE d30_plus_rate_pct NOT BETWEEN 0 AND 100 "
        "   OR d90_plus_rate_pct NOT BETWEEN 0 AND 100",
    )[0]
    assert bad_rates == 0


def test_vintage_curves_monotonic(conn):
    steps = fetch_all(
        conn,
        "SELECT vintage_quarter, cum_d90_rate_pct - LAG(cum_d90_rate_pct) OVER ("
        "  PARTITION BY vintage_quarter ORDER BY loan_age) AS step "
        "FROM gold.vintage_delinquency",
    )
    assert all(step is None or step >= 0 for _, step in steps)


def test_transition_matrix_rows_sum_to_one(conn):
    rows = fetch_all(
        conn,
        "SELECT from_state, SUM(probability_pct) FROM gold.transition_matrix "
        "GROUP BY from_state",
    )
    assert rows
    for _, total in rows:
        assert 99.5 <= float(total) <= 100.5


def test_reports_written(pipeline_run):
    reports = pipeline_run["reports_dir"]
    for name in ("portfolio_summary", "monthly_portfolio", "vintage_delinquency",
                 "transition_matrix", "state_risk", "segment_risk"):
        csv_path = reports / f"{name}.csv"
        assert csv_path.is_file()
        header = csv_path.read_text().splitlines()[0]
        assert "," in header
    summary = (reports / "summary.md").read_text()
    assert "Portfolio summary" in summary
    assert "Ever 90+ days delinquent" in summary


def test_loader_rejects_corrupt_lines_into_db(pipeline_run, tmp_path):
    good = "|".join(["x"] * FIELD_COUNT)
    corrupt_file = tmp_path / "corrupt_orig.txt"
    corrupt_file.write_text(f"{good}\nbad|line\n{good}\n")
    with psycopg.connect(pipeline_run["config"].conninfo()) as connection:
        result = load_file(connection, "origination", corrupt_file)
        assert result.rows_loaded == 2
        assert result.rows_rejected == 1
        reason, line_number = fetch_one(
            connection,
            "SELECT reason, line_number FROM bronze.load_rejects "
            "WHERE source_file = %s", (corrupt_file.name,),
        )
        assert "expected 32" in reason
        assert line_number == 2
