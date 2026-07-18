# freddiemac-loan-analytics

[![CI](https://github.com/adwitiyashukla/freddiemac-loan-analytics/actions/workflows/ci.yml/badge.svg)](https://github.com/adwitiyashukla/freddiemac-loan-analytics/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

ELT pipeline and credit risk analytics for the Freddie Mac Single-Family Loan-Level Dataset. Raw pipe-delimited loan files are loaded into Postgres through bronze, silver and gold layers, and exported as CSV marts with a summary report.

## Architecture

```
data/raw/*.txt (real dataset)        data/sample/*.txt (generated)
        |                                    |
        +------------------+-----------------+
                           |
                   freddie-pipeline load
        streaming COPY, 32-field validation per line,
        invalid lines to bronze.load_rejects, runs to bronze.load_audit
                           |
                        BRONZE
        raw TEXT landing tables, rejects, load audit
                           |
                  02_silver.sql
                        SILVER
        typed and deduplicated, sentinels to NULL, YYYYMM to DATE,
        delinquency flags, primary keys, indexes
                           |
              03_gold.sql + quality checks
                         GOLD
        loan_outcomes, portfolio_summary, monthly_portfolio,
        vintage_delinquency, transition_matrix, state_risk, segment_risk
                           |
                  freddie-pipeline report
              reports/*.csv and reports/summary.md
```

## Commands

| Command | What it does |
| --- | --- |
| `init-db` | Creates the bronze schema, raw tables, reject and audit tables |
| `generate-sample` | Writes synthetic files in the official 32-field layout |
| `load` | Streams pipe-delimited files into bronze with COPY |
| `transform` | Builds silver and gold, runs data quality checks |
| `report` | Exports gold marts to CSV and writes summary.md |
| `run-all` | Runs the full pipeline in one command |

Every input line is validated for the exact 32-field layout before it is sent to Postgres. Lines that fail go to `bronze.load_rejects` with a line number and reason instead of aborting the load. After the transform, quality checks assert non-empty silver tables, delinquency rates within 0 to 100, monotone vintage curves and transition matrix rows summing to 100. A failed check stops the run.

The sample generator exists so the pipeline and CI can run without redistributing Freddie Mac data. Note rates follow the 2022 rate path and price in credit risk, and a per-loan monthly state machine drives delinquency, cure, prepayment and credit events, with hazards driven by credit score, LTV and DTI.

## Results

Run on the Freddie Mac 2022 sample dataset: 50,000 loans, 1,660,755 monthly performance rows, performance through June 2025.

| Metric | Value |
| --- | --- |
| Load | 1,660,755 rows in 16.2s, 0 rejects |
| Full pipeline | 49s end to end |
| Portfolio | 50,000 loans, $14.957B original UPB, 54 states |
| Averages | credit score 743.9, LTV 73.9, DTI 37.0, note rate 5.088% |
| Ever 30+ days delinquent | 11.614% |
| Ever 90+ days delinquent | 2.736% |
| Prepaid in full | 14.394% |
| June 2025 | 42,541 active loans, 2.729% D30+, 0.987% D90+ |

Roll rates from `gold.transition_matrix`: a current loan stays current next month with probability 98.92%, and a 30-day delinquent loan cures to current with probability 43.37%.

Ever 90+ delinquency by credit score and LTV band from `gold.segment_risk`:

| | LTV up to 60 | LTV 80-90 |
| --- | --- | --- |
| Credit score under 660 | 10.03% | 16.35% |
| Credit score 780 plus | 0.46% | 0.65% |

Cumulative D90 for the 2022Q2 vintage from `gold.vintage_delinquency`: 0.82% at age 12, 1.79% at age 24, 2.94% at age 36 months.

## Quickstart

Requires Python 3.10 or newer and Docker.

```bash
git clone https://github.com/adwitiyashukla/freddiemac-loan-analytics.git
cd freddiemac-loan-analytics

docker compose -f docker/docker-compose.yml up -d

python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .

freddie-pipeline generate-sample --out-dir data/sample --loans 1000
freddie-pipeline run-all --data-dir data/sample
cat reports/summary.md
```

On Windows activate with `.\.venv\Scripts\Activate.ps1`.

Database settings default to the bundled compose file and can be overridden with `FREDDIE_DB_HOST`, `FREDDIE_DB_PORT`, `FREDDIE_DB_USER`, `FREDDIE_DB_PASSWORD`, `FREDDIE_DB_NAME`.

### Real dataset

Download the Single-Family Loan-Level Dataset sample from [Freddie Mac](https://www.freddiemac.com/research/datasets/sf-loanlevel-dataset), which is free after registration and also documents the file layout. Unzip the origination and performance files into `data/raw/`, then:

```bash
freddie-pipeline run-all --data-dir data/raw
```

The dataset is not part of this repository and `data/` is gitignored.

## Development

```bash
pip install -r requirements-dev.txt
pytest
ruff check .
```

Database-backed tests skip automatically when Postgres is not reachable. CI runs ruff, the test suite against a Postgres 16 service container and an end-to-end smoke run of the pipeline on Python 3.11, 3.12 and 3.13.

## Tech stack

Python 3, psycopg 3, PostgreSQL 16, Docker Compose, pytest, ruff, GitHub Actions.

## Project structure

```
src/freddie_pipeline/
  cli.py
  config.py
  db.py
  loader.py
  quality.py
  report.py
  sample_data.py
  utils.py
sql/
  01_bronze.sql
  02_silver.sql
  03_gold.sql
tests/
docker/
.github/workflows/
```

## Sample output

`reports/summary.md` from the run above:

```
# Portfolio summary

Loans: 50,000 | Original UPB: $14.957B | States: 54

Averages: credit score 743.9, LTV 73.9, DTI 37.0, note rate 5.088%

## Lifetime outcomes

- Ever 30+ days delinquent: 11.614% of loans
- Ever 90+ days delinquent: 2.736% of loans
- Prepaid in full: 14.394%
- Terminated by credit event: 0.048%

## Latest month

As of 2025-06-01: 42,541 active loans, 2.729% 30+ delinquent,
0.987% 90+ delinquent.

A current loan stays current next month with probability 98.9232%.
```

## License

MIT, see [LICENSE](LICENSE).
