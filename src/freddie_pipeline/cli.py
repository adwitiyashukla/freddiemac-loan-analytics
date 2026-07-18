from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .config import Config
from .db import connect, run_sql_file
from .loader import load_file
from .quality import run_quality_checks
from .report import collect_metrics, export_gold_csv, write_summary
from .sample_data import generate_sample
from .utils import PipelineError, get_logger, setup_logging

log = get_logger(__name__)


def _find_input(data_dir: Path, pattern: str, label: str) -> Path:
    matches = sorted(data_dir.glob(pattern))
    if not matches:
        raise PipelineError(f"No {label} file matching {pattern!r} in {data_dir}")
    if len(matches) > 1:
        raise PipelineError(
            f"Multiple {label} files match {pattern!r} in {data_dir}: "
            f"{[m.name for m in matches]}. Pass the file explicitly with "
            f"--orig/--svcg."
        )
    return matches[0]


def cmd_init_db(args: argparse.Namespace, config: Config) -> None:
    with connect(config) as conn:
        run_sql_file(conn, config.sql_dir / "01_bronze.sql")
    log.info("Bronze schema ready")


def cmd_generate_sample(args: argparse.Namespace, config: Config) -> None:
    stats = generate_sample(Path(args.out_dir), n_loans=args.loans, seed=args.seed)
    log.info(
        "Sample ready: %s loans, %s performance rows",
        f"{stats['n_loans']:,}", f"{stats['n_performance_rows']:,}",
    )


def cmd_load(args: argparse.Namespace, config: Config) -> None:
    orig = Path(args.orig) if args.orig else None
    svcg = Path(args.svcg) if args.svcg else None
    if orig is None and svcg is None:
        data_dir = Path(args.data_dir)
        if not data_dir.is_dir():
            raise PipelineError(f"Data directory not found: {data_dir}")
        orig = _find_input(data_dir, "*orig*.txt", "origination")
        svcg = _find_input(data_dir, "*svcg*.txt", "performance")
    for path, label in ((orig, "origination"), (svcg, "performance")):
        if path is not None and not path.is_file():
            raise PipelineError(f"{label} file not found: {path}")
    with connect(config) as conn:
        if orig is not None:
            load_file(conn, "origination", orig, truncate=args.truncate)
        if svcg is not None:
            load_file(conn, "performance", svcg, truncate=args.truncate)


def cmd_transform(args: argparse.Namespace, config: Config) -> None:
    with connect(config) as conn:
        run_sql_file(conn, config.sql_dir / "02_silver.sql")
        run_sql_file(conn, config.sql_dir / "03_gold.sql")
        run_quality_checks(conn)
    log.info("Silver and gold layers built")


def cmd_report(args: argparse.Namespace, config: Config) -> None:
    out_dir = Path(args.out)
    with connect(config) as conn:
        written = export_gold_csv(conn, out_dir)
        metrics = collect_metrics(conn)
    summary = write_summary(metrics, out_dir)
    log.info("Report complete: %s CSV files and %s", len(written), summary.name)


def cmd_run_all(args: argparse.Namespace, config: Config) -> None:
    cmd_init_db(args, config)
    args.truncate = False
    args.orig = None
    args.svcg = None
    cmd_load(args, config)
    cmd_transform(args, config)
    cmd_report(args, config)
    log.info("Pipeline finished end to end")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="freddie-pipeline",
        description=(
            "ELT pipeline and credit risk analytics for the Freddie Mac "
            "Single-Family Loan-Level Dataset."
        ),
    )
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument(
        "--log-level", default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging verbosity (default INFO)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init-db", help="Create the bronze schema and tables")

    p = sub.add_parser("generate-sample", help="Generate synthetic sample data")
    p.add_argument("--out-dir", default="data/sample", help="Output directory")
    p.add_argument("--loans", type=int, default=1000, help="Number of loans")
    p.add_argument("--seed", type=int, default=42, help="Deterministic seed")

    p = sub.add_parser("load", help="Load raw files into bronze tables")
    p.add_argument("--data-dir", default="data/sample",
                   help="Directory holding *orig*.txt and *svcg*.txt")
    p.add_argument("--orig", help="Explicit origination file path")
    p.add_argument("--svcg", help="Explicit performance file path")
    p.add_argument("--truncate", action="store_true",
                   help="Truncate bronze tables before loading")

    sub.add_parser("transform", help="Build silver and gold layers, run quality checks")

    p = sub.add_parser("report", help="Export gold marts to CSV plus summary.md")
    p.add_argument("--out", default="reports", help="Output directory")

    p = sub.add_parser("run-all", help="init-db, load, transform, report in one go")
    p.add_argument("--data-dir", default="data/sample",
                   help="Directory holding *orig*.txt and *svcg*.txt")
    p.add_argument("--out", default="reports", help="Report output directory")

    return parser


COMMANDS = {
    "init-db": cmd_init_db,
    "generate-sample": cmd_generate_sample,
    "load": cmd_load,
    "transform": cmd_transform,
    "report": cmd_report,
    "run-all": cmd_run_all,
}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    setup_logging(args.log_level)
    config = Config.from_env()
    try:
        COMMANDS[args.command](args, config)
    except PipelineError as exc:
        log.error("%s", exc)
        return 1
    except KeyboardInterrupt:
        log.error("Interrupted")
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
