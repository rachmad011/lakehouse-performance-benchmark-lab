from __future__ import annotations

import argparse
import json
import shutil
from collections.abc import Iterator
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds
from rich.console import Console

console = Console()


def load_config() -> dict:
    config_path = Path("configs/benchmark_config.json")
    return json.loads(config_path.read_text(encoding="utf-8"))


def generate_transactions(
    rows: int,
    seed: int,
    start_transaction_id: int = 1,
    customer_id_upper_bound: int | None = None,
) -> pd.DataFrame:
    """Buat synthetic transaction data untuk kebutuhan benchmark analytics.

    Bentuk dataset sengaja dibuat mirip fact table: transaksi, tanggal event, customer,
    region, channel, kategori produk, amount, quantity, dan status.
    """
    rng = np.random.default_rng(seed)

    start_date = np.datetime64("2025-01-01")
    days = rng.integers(0, 365, size=rows)
    event_dates = start_date + days.astype("timedelta64[D]")

    regions = np.array(["Jakarta", "Bandung", "Surabaya", "Medan", "Palembang", "Makassar"])
    channels = np.array(["branch", "mobile", "web", "partner"])
    categories = np.array(["loan", "saving", "investment", "card", "insurance"])
    statuses = np.array(["success", "pending", "failed"])

    amount = rng.gamma(shape=2.0, scale=250_000.0, size=rows).round(2)
    quantity = rng.integers(1, 5, size=rows)

    df = pd.DataFrame(
        {
            "transaction_id": np.arange(
                start_transaction_id,
                start_transaction_id + rows,
                dtype=np.int64,
            ),
            "customer_id": rng.integers(
                1,
                customer_id_upper_bound or max(2, rows // 10),
                size=rows,
                dtype=np.int64,
            ),
            "event_date": pd.to_datetime(event_dates),
            "region": rng.choice(regions, size=rows, p=[0.30, 0.15, 0.18, 0.12, 0.15, 0.10]),
            "channel": rng.choice(channels, size=rows, p=[0.25, 0.40, 0.25, 0.10]),
            "product_category": rng.choice(categories, size=rows),
            "amount": amount,
            "quantity": quantity,
            "status": rng.choice(statuses, size=rows, p=[0.86, 0.09, 0.05]),
        }
    )

    df["event_month"] = df["event_date"].dt.strftime("%Y-%m")
    df["amount_bucket"] = pd.cut(
        df["amount"],
        bins=[0, 100_000, 500_000, 1_000_000, np.inf],
        labels=["small", "medium", "large", "very_large"],
    ).astype(str)

    return df


def iter_transaction_chunks(
    rows: int,
    chunk_size: int,
    seed: int,
) -> Iterator[tuple[int, pd.DataFrame]]:
    """Buat data per chunk agar dataset besar tidak ditampung penuh di memory."""
    customer_id_upper_bound = max(2, rows // 10)
    chunk_no = 0

    for start in range(0, rows, chunk_size):
        chunk_rows = min(chunk_size, rows - start)
        chunk_no += 1
        chunk_seed = seed + chunk_no - 1
        yield chunk_no, generate_transactions(
            rows=chunk_rows,
            seed=chunk_seed,
            start_transaction_id=start + 1,
            customer_id_upper_bound=customer_id_upper_bound,
        )


def remove_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def get_path_size_mb(path: Path) -> float:
    if path.is_file():
        return path.stat().st_size / (1024 * 1024)
    return sum(file.stat().st_size for file in path.rglob("*") if file.is_file()) / (1024 * 1024)


def write_csv(rows: int, chunk_size: int, seed: int, output_path: Path) -> None:
    """Tulis CSV per chunk agar row count besar tidak membutuhkan satu dataframe besar."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists():
        output_path.unlink()

    for chunk_no, df in iter_transaction_chunks(rows=rows, chunk_size=chunk_size, seed=seed):
        df.to_csv(output_path, mode="a", header=chunk_no == 1, index=False)
        console.print(f"CSV chunk {chunk_no} selesai ditulis: {len(df):,} rows")


def write_unpartitioned_parquet(rows: int, chunk_size: int, seed: int, output_dir: Path) -> None:
    """Tulis file Parquet dengan Snappy compression per chunk."""
    remove_dir(output_dir)

    for chunk_no, df in iter_transaction_chunks(rows=rows, chunk_size=chunk_size, seed=seed):
        output_path = output_dir / f"part-{chunk_no:05d}.parquet"
        df.to_parquet(output_path, engine="pyarrow", compression="snappy", index=False)
        console.print(f"Parquet chunk {chunk_no} selesai ditulis: {output_path} ({len(df):,} rows)")


def write_partitioned_parquet(
    rows: int,
    chunk_size: int,
    seed: int,
    output_dir: Path,
    partition_column: str,
) -> None:
    """Tulis Hive-style partitioned Parquet per chunk."""
    remove_dir(output_dir)
    partition_schema = pa.schema([(partition_column, pa.string())])

    for chunk_no, df in iter_transaction_chunks(rows=rows, chunk_size=chunk_size, seed=seed):
        table = pa.Table.from_pandas(df, preserve_index=False)
        ds.write_dataset(
            table,
            base_dir=str(output_dir),
            format="parquet",
            partitioning=ds.partitioning(partition_schema, flavor="hive"),
            existing_data_behavior="overwrite_or_ignore",
            basename_template=f"part-{chunk_no:05d}-{{i}}.parquet",
            file_options=ds.ParquetFileFormat().make_write_options(compression="snappy"),
        )
        console.print(f"Partitioned Parquet chunk {chunk_no} selesai ditulis: {len(df):,} rows")


def main() -> None:
    parser = argparse.ArgumentParser(description="Membuat synthetic transaction dataset.")
    parser.add_argument("--rows", type=int, default=None, help="Jumlah rows yang dibuat.")
    parser.add_argument("--seed", type=int, default=None, help="Random seed.")
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=None,
        help="Jumlah rows per chunk. Berguna untuk dataset besar di laptop.",
    )
    parser.add_argument(
        "--output-format",
        choices=["csv", "parquet", "partitioned-parquet", "all"],
        default="csv",
        help="Format output yang dibuat. Default memakai workflow CSV.",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        default=None,
        help="Path output CSV optional untuk smoke test atau custom run.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Folder output Parquet optional untuk smoke test atau custom run.",
    )
    args = parser.parse_args()

    config = load_config()
    rows = args.rows or int(config["default_rows"])
    seed = args.seed or int(config["default_seed"])
    chunk_size = args.chunk_size or rows

    if rows <= 0:
        raise ValueError("--rows harus lebih besar dari 0.")
    if chunk_size <= 0:
        raise ValueError("--chunk-size harus lebih besar dari 0.")
    if args.output_format == "all" and args.output_dir is not None:
        raise ValueError("--output-dir hanya bisa dipakai untuk satu output format Parquet.")

    console.print(
        f"Membuat {rows:,} rows dengan seed={seed}, "
        f"chunk_size={chunk_size:,}, output_format={args.output_format}..."
    )

    if args.output_format in {"csv", "all"}:
        csv_path = args.output_path or Path(config["raw_csv_path"])
        write_csv(rows=rows, chunk_size=chunk_size, seed=seed, output_path=csv_path)
        console.print(f"CSV selesai: {csv_path} ({get_path_size_mb(csv_path):,.2f} MB)")

    if args.output_format in {"parquet", "all"}:
        parquet_dir = args.output_dir or Path(config["parquet_unpartitioned_dir"])
        write_unpartitioned_parquet(
            rows=rows,
            chunk_size=chunk_size,
            seed=seed,
            output_dir=parquet_dir,
        )
        console.print(f"Parquet selesai: {parquet_dir} ({get_path_size_mb(parquet_dir):,.2f} MB)")

    if args.output_format in {"partitioned-parquet", "all"}:
        default_partitioned_dir = Path(config["parquet_partitioned_dir"])
        partitioned_dir = args.output_dir or default_partitioned_dir
        write_partitioned_parquet(
            rows=rows,
            chunk_size=chunk_size,
            seed=seed,
            output_dir=partitioned_dir,
            partition_column=config["partition_column"],
        )
        console.print(
            f"Partitioned Parquet selesai: {partitioned_dir} "
            f"({get_path_size_mb(partitioned_dir):,.2f} MB)"
        )


if __name__ == "__main__":
    main()
