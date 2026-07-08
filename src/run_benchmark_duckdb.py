from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path

import duckdb
import pandas as pd
import psutil
from rich.console import Console
from rich.table import Table

console = Console()


@dataclass(frozen=True)
class DatasetSource:
    name: str
    path: Path
    scan_sql: str
    size_mb: float


@dataclass(frozen=True)
class QueryScenario:
    name: str
    sql_template: str
    notes: str


def load_config() -> dict:
    return json.loads(Path("configs/benchmark_config.json").read_text(encoding="utf-8"))


def get_path_size_mb(path: Path) -> float:
    if path.is_file():
        return path.stat().st_size / (1024 * 1024)
    return sum(file.stat().st_size for file in path.rglob("*") if file.is_file()) / (1024 * 1024)


def build_sources(config: dict) -> list[DatasetSource]:
    csv_path = Path(config["raw_csv_path"])
    parquet_dir = Path(config["parquet_unpartitioned_dir"])
    partitioned_dir = Path(config["parquet_partitioned_dir"])

    sources: list[DatasetSource] = []
    if csv_path.exists():
        sources.append(
            DatasetSource(
                name="csv",
                path=csv_path,
                scan_sql=f"read_csv_auto('{csv_path.as_posix()}')",
                size_mb=get_path_size_mb(csv_path),
            )
        )

    if parquet_dir.exists():
        sources.append(
            DatasetSource(
                name="parquet_unpartitioned",
                path=parquet_dir,
                scan_sql=f"read_parquet('{parquet_dir.as_posix()}/*.parquet')",
                size_mb=get_path_size_mb(parquet_dir),
            )
        )

    if partitioned_dir.exists():
        sources.append(
            DatasetSource(
                name="parquet_partitioned_event_month",
                path=partitioned_dir,
                scan_sql=(
                    f"read_parquet('{partitioned_dir.as_posix()}/**/*.parquet', "
                    "hive_partitioning=true)"
                ),
                size_mb=get_path_size_mb(partitioned_dir),
            )
        )

    return sources


def get_queries() -> list[QueryScenario]:
    return [
        QueryScenario(
            name="q01_count_all",
            sql_template="""
                SELECT COUNT(*) AS row_count
                FROM {source}
            """,
            notes="Full scan row count sebagai baseline",
        ),
        QueryScenario(
            name="q02_filter_success_jakarta",
            sql_template="""
                SELECT COUNT(*) AS success_rows, SUM(amount) AS total_amount
                FROM {source}
                WHERE status = 'success' AND region = 'Jakarta'
            """,
            notes="Filter status dan region lalu aggregation",
        ),
        QueryScenario(
            name="q03_group_by_region_category",
            sql_template="""
                SELECT region, product_category, COUNT(*) AS trx_count, SUM(amount) AS total_amount
                FROM {source}
                WHERE status = 'success'
                GROUP BY region, product_category
                ORDER BY total_amount DESC
            """,
            notes="Aggregation berdasarkan region dan product category",
        ),
        QueryScenario(
            name="q04_monthly_aggregation",
            sql_template="""
                SELECT event_month, COUNT(*) AS trx_count, SUM(amount) AS total_amount
                FROM {source}
                WHERE event_month BETWEEN '2025-06' AND '2025-09'
                GROUP BY event_month
                ORDER BY event_month
            """,
            notes="Filter range bulan lalu aggregation",
        ),
        QueryScenario(
            name="q05_channel_mix",
            sql_template="""
                SELECT channel, status, COUNT(*) AS trx_count, AVG(amount) AS avg_amount
                FROM {source}
                GROUP BY channel, status
                ORDER BY channel, status
            """,
            notes="Grouping berdasarkan channel dan status",
        ),
    ]


def execute_query(connection: duckdb.DuckDBPyConnection, sql: str) -> tuple[float, int, float]:
    process = psutil.Process()
    mem_before = process.memory_info().rss / (1024 * 1024)
    start = time.perf_counter()
    result_df = connection.execute(sql).fetchdf()
    latency = time.perf_counter() - start
    mem_after = process.memory_info().rss / (1024 * 1024)
    memory_delta = mem_after - mem_before
    return latency, len(result_df), memory_delta


def run_benchmark(repeat: int) -> pd.DataFrame:
    config = load_config()
    sources = build_sources(config)
    queries = get_queries()

    if not sources:
        raise RuntimeError(
            "Data source belum ditemukan. Jalankan generate_dataset.py dan convert_formats.py dulu."
        )

    records: list[dict] = []
    con = duckdb.connect()

    for source in sources:
        console.print(f"Menjalankan benchmark untuk [bold]{source.name}[/bold]...")
        for query in queries:
            sql = query.sql_template.format(source=source.scan_sql)
            for run_no in range(1, repeat + 1):
                latency, row_count, memory_delta = execute_query(con, sql)
                records.append(
                    {
                        "engine": "duckdb",
                        "source_format": source.name,
                        "source_path": str(source.path),
                        "source_size_mb": round(source.size_mb, 4),
                        "query_name": query.name,
                        "repeat_no": run_no,
                        "latency_seconds": round(latency, 6),
                        "result_rows": row_count,
                        "memory_delta_mb": round(memory_delta, 4),
                        "notes": query.notes,
                    }
                )

    con.close()
    return pd.DataFrame(records)


def print_summary(df: pd.DataFrame) -> None:
    table = Table(title="Ringkasan Benchmark")
    table.add_column("Source")
    table.add_column("Query")
    table.add_column("Avg Latency (s)", justify="right")
    table.add_column("Size MB", justify="right")

    summary = (
        df.groupby(["source_format", "query_name"], as_index=False)
        .agg(
            avg_latency_seconds=("latency_seconds", "mean"),
            source_size_mb=("source_size_mb", "max"),
        )
        .sort_values(["query_name", "avg_latency_seconds"])
    )

    for _, row in summary.iterrows():
        table.add_row(
            str(row["source_format"]),
            str(row["query_name"]),
            f"{row['avg_latency_seconds']:.4f}",
            f"{row['source_size_mb']:.2f}",
        )

    console.print(table)


def main() -> None:
    parser = argparse.ArgumentParser(description="Jalankan benchmark DuckDB lokal.")
    parser.add_argument("--repeat", type=int, default=3, help="Jumlah repeat untuk tiap query.")
    args = parser.parse_args()

    results_dir = Path("results")
    results_dir.mkdir(parents=True, exist_ok=True)

    df = run_benchmark(repeat=args.repeat)
    output_path = results_dir / "benchmark_results.csv"
    df.to_csv(output_path, index=False)

    print_summary(df)
    console.print(f"Hasil benchmark disimpan ke {output_path}")


if __name__ == "__main__":
    main()
