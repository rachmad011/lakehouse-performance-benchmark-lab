from __future__ import annotations

import json
import shutil
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.csv as pv
import pyarrow.dataset as ds
import pyarrow.parquet as pq
from rich.console import Console

console = Console()


def load_config() -> dict:
    return json.loads(Path("configs/benchmark_config.json").read_text(encoding="utf-8"))


def remove_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def get_dir_size_mb(path: Path) -> float:
    total = sum(file.stat().st_size for file in path.rglob("*") if file.is_file())
    return total / (1024 * 1024)


def convert_to_parquet(csv_path: Path, output_dir: Path) -> None:
    remove_dir(output_dir)
    table = pv.read_csv(csv_path)
    pq.write_table(table, output_dir / "fact_transactions.parquet", compression="snappy")


def convert_to_partitioned_parquet(csv_path: Path, output_dir: Path, partition_column: str) -> None:
    remove_dir(output_dir)
    table = pv.read_csv(csv_path)

    # Hive-style partitioning menyimpan nama partition di path folder,
    # misalnya event_month=2025-06/part-0.parquet. Format ini memudahkan
    # DuckDB mengenali partition column dari pola folder Hive-style.
    partition_schema = pa.schema([(partition_column, pa.string())])
    ds.write_dataset(
        table,
        base_dir=str(output_dir),
        format="parquet",
        partitioning=ds.partitioning(partition_schema, flavor="hive"),
        existing_data_behavior="overwrite_or_ignore",
        file_options=ds.ParquetFileFormat().make_write_options(compression="snappy"),
    )


def try_convert_to_orc(csv_path: Path, output_dir: Path) -> None:
    """Konversi ORC optional.

    Dukungan ORC writer di PyArrow bisa berbeda antar environment. Jika tidak tersedia,
    fungsi ini hanya menampilkan warning dan melewati output ORC.
    """
    remove_dir(output_dir)
    try:
        import pyarrow.orc as orc

        df = pd.read_csv(csv_path)
        table = pa.Table.from_pandas(df, preserve_index=False)
        with (output_dir / "fact_transactions.orc").open("wb") as file_obj:
            orc.write_table(table, file_obj)
        console.print("Konversi ORC selesai.")
    except Exception as exc:  # noqa: BLE001
        console.print(f"[yellow]Konversi ORC dilewati: {exc}[/yellow]")


def main() -> None:
    config = load_config()
    csv_path = Path(config["raw_csv_path"])
    if not csv_path.exists():
        raise FileNotFoundError(
            f"Raw CSV tidak ditemukan: {csv_path}. Jalankan generate_dataset.py dulu."
        )

    parquet_dir = Path(config["parquet_unpartitioned_dir"])
    partitioned_dir = Path(config["parquet_partitioned_dir"])
    orc_dir = Path(config["orc_dir"])

    console.print("Mengonversi CSV ke unpartitioned Parquet...")
    convert_to_parquet(csv_path, parquet_dir)
    console.print(f"Ukuran Parquet: {get_dir_size_mb(parquet_dir):,.2f} MB")

    console.print("Mengonversi CSV ke partitioned Parquet...")
    convert_to_partitioned_parquet(csv_path, partitioned_dir, config["partition_column"])
    console.print(f"Ukuran partitioned Parquet: {get_dir_size_mb(partitioned_dir):,.2f} MB")

    console.print("Mencoba konversi ORC optional...")
    try_convert_to_orc(csv_path, orc_dir)
    if any(orc_dir.rglob("*")):
        console.print(f"Ukuran ORC: {get_dir_size_mb(orc_dir):,.2f} MB")


if __name__ == "__main__":
    main()
