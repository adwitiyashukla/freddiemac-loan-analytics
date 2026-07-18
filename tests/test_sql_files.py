from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SQL_DIR = REPO_ROOT / "sql"

EXPECTED_FILES = ["01_bronze.sql", "02_silver.sql", "03_gold.sql"]

GOLD_TABLES = [
    "gold.loan_outcomes",
    "gold.portfolio_summary",
    "gold.monthly_portfolio",
    "gold.vintage_delinquency",
    "gold.transition_matrix",
    "gold.state_risk",
    "gold.segment_risk",
]


def test_sql_files_present_in_order():
    found = sorted(p.name for p in SQL_DIR.glob("*.sql"))
    assert found == EXPECTED_FILES


def test_sql_files_not_empty_and_create_schemas():
    for name, schema in zip(EXPECTED_FILES, ["bronze", "silver", "gold"], strict=True):
        sql = (SQL_DIR / name).read_text(encoding="utf-8")
        assert sql.strip(), f"{name} is empty"
        assert f"CREATE SCHEMA IF NOT EXISTS {schema}" in sql


def test_gold_sql_builds_every_documented_mart():
    sql = (SQL_DIR / "03_gold.sql").read_text(encoding="utf-8")
    for table in GOLD_TABLES:
        assert f"CREATE TABLE {table}" in sql, f"missing {table}"


def test_repo_text_files_have_no_em_or_en_dashes():
    em_dash, en_dash = chr(0x2014), chr(0x2013)
    globs = ["src/**/*.py", "tests/**/*.py", "sql/*.sql", "*.md", "*.toml", "*.txt",
             ".github/**/*.yml", "docker/*.yml"]
    offenders = []
    for pattern in globs:
        for path in REPO_ROOT.glob(pattern):
            text = path.read_text(encoding="utf-8")
            if em_dash in text or en_dash in text:
                offenders.append(path.name)
    assert not offenders, f"em or en dashes found in: {offenders}"
