# Lakehouse Performance Benchmark Lab

Project portfolio Data Engineering untuk membandingkan storage format, partitioning,
compression, dan performa SQL query secara terukur.

Scope versi ini sengaja dibatasi ke **DuckDB lokal**. Tujuannya supaya project mudah
dijalankan di laptop tanpa Spark, Hadoop, Trino, Docker, atau cluster. Spark dan Trino
tetap disebut sebagai rekomendasi pengembangan lanjutan jika nanti benchmark ingin
dibawa ke implementasi yang lebih advance.

## Masalah yang Ingin Dijawab

Dalam project lakehouse, keputusan teknis sering terlihat sederhana, tetapi dampaknya
besar:

- Data sebaiknya tetap di CSV, atau dikonversi ke Parquet/ORC?
- Apakah partitioning benar-benar membuat query lebih cepat?
- Compression mana yang cocok untuk kebutuhan storage dan query?
- Metrik apa yang perlu dikumpulkan sebelum memberi rekomendasi tuning?
- Kapan perlu naik dari benchmark lokal ke Spark atau Trino?

Repository ini menjawab pertanyaan tersebut dengan benchmark yang bisa dijalankan ulang,
bukan hanya opini.

## Apa yang Dilakukan Project Ini

- Membuat synthetic transaction dataset seperti fact table analytics.
- Menyimpan data mentah ke CSV sebagai baseline.
- Mengubah CSV ke Parquet dengan Snappy compression.
- Membuat Hive-style partitioned Parquet berdasarkan `event_month`.
- Mencoba konversi ORC jika build PyArrow di environment mendukung.
- Menjalankan SQL benchmark lokal dengan DuckDB.
- Menyimpan hasil benchmark mentah ke CSV.
- Menghitung average, min, max, p50, dan p95 latency.
- Membuat chart dan laporan Markdown.
- Memberi rekomendasi kapan Spark/Trino layak dikembangkan sebagai tahap berikutnya.

## Alur Kerja Utama

```text
Buat synthetic transaction data
        |
        v
data/raw/fact_transactions.csv
        |
        +--> data/processed/parquet_unpartitioned/
        |
        +--> data/processed/parquet_partitioned/event_month=YYYY-MM/
        |
        +--> data/processed/orc_unpartitioned/       optional
        |
        v
Benchmark DuckDB lokal
        |
        v
results/benchmark_results.csv
results/benchmark_summary.csv
docs/benchmark_report.md
docs/benchmark_dashboard.html
docs/images/latency_by_query.png
```

Sederhananya: data dibuat, dikonversi ke beberapa layout, di-query dengan skenario yang
sama, lalu hasilnya diringkas menjadi laporan.

## Struktur Project Utama

```text
.
|-- configs/
|   `-- benchmark_config.json
|-- data/
|   |-- raw/
|   `-- processed/
|-- docs/
|   |-- benchmark_report.md
|   |-- benchmark_report_template.md
|   |-- images/
|   |-- methodology.md
|   `-- portfolio_summary.md
|-- results/
|-- src/
|   |-- analyze_results.py
|   |-- convert_formats.py
|   |-- generate_dataset.py
|   `-- run_benchmark_duckdb.py
|-- pyproject.toml
`-- README.md
```

Folder `data/`, `results/`, dan `docs/images/` berisi output hasil generate/benchmark.
File output tersebut tidak perlu di-commit agar repository tetap ringan.

## Kebutuhan

Untuk menjalankan benchmark utama:

- Python 3.11+
- `uv` package manager, atau `pip`

Tidak perlu memasang Spark, Hadoop, Trino, Docker, MinIO, Delta Lake, atau Iceberg untuk
menjalankan versi DuckDB lokal.

## Cara Menjalankan dari Awal dengan uv

Install dependency:

```bash
uv sync
```

Buat dataset lokal:

```bash
uv run python src/generate_dataset.py --rows 1000000 --seed 42
```

Konversi CSV ke Parquet, partitioned Parquet, dan ORC optional:

```bash
uv run python src/convert_formats.py
```

Jalankan benchmark DuckDB:

```bash
uv run python src/run_benchmark_duckdb.py --repeat 3
```

Buat summary, chart, dan laporan:

```bash
uv run python src/analyze_results.py
```

Output utama:

```text
results/benchmark_results.csv
results/benchmark_summary.csv
docs/benchmark_report.md
docs/benchmark_dashboard.html
docs/images/latency_by_query.png
```

## Mode Dataset Besar: 100 Juta Rows

Untuk data besar, jangan membuat satu Pandas dataframe raksasa. Lebih aman generate
langsung ke Parquet per chunk:

```bash
uv run python src/generate_dataset.py --rows 100000000 --chunk-size 1000000 \
  --output-format parquet
```

Command ini menulis banyak file Parquet ke:

```text
data/processed/parquet_unpartitioned/
```

Memory yang dipakai mengikuti `--chunk-size`, bukan total 100 juta rows.

Untuk partitioned Parquet:

```bash
uv run python src/generate_dataset.py --rows 100000000 --chunk-size 1000000 \
  --output-format partitioned-parquet
```

CSV untuk 100 juta rows sebaiknya hanya dipakai jika memang ingin baseline raw file,
karena ukuran file dan waktu scan akan jauh lebih besar.

## Cara Menjalankan dengan pip

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e .
python src/generate_dataset.py --rows 1000000 --seed 42
python src/convert_formats.py
python src/run_benchmark_duckdb.py --repeat 3
python src/analyze_results.py
```

## Skenario Benchmark DuckDB

| Scenario | Source | Layout | Query Pattern | Tujuan |
|---|---|---|---|---|
| CSV baseline | CSV | Single raw file | Full scan, filter, aggregation | Membandingkan raw format |
| Parquet scan | Parquet | Unpartitioned file | SQL yang sama | Melihat manfaat columnar format |
| Partitioned Parquet | Parquet | Folder `event_month` | Month filter dan aggregation | Menguji partition pruning |
| Optional ORC | ORC | Unpartitioned file | SQL yang sama | Membandingkan columnar format |

## Metrik yang Dikumpulkan

Metrik lokal:

- Query latency dalam detik.
- Average, min, max, p50, dan p95 latency.
- Ukuran source data dalam MB.
- Jumlah result rows.
- Repeat number.
- Memory delta proses Python.
- Engine, source format, query name, source path, dan notes.

Metrik ini cukup untuk membaca pola awal: format mana yang lebih hemat storage, query
mana yang lebih cepat di Parquet, dan apakah partitioning membantu query yang memakai
filter bulan.

## Output Akhir

Setelah workflow selesai, file pentingnya adalah:

- `results/benchmark_results.csv` - hasil mentah semua run benchmark DuckDB.
- `results/benchmark_summary.csv` - ringkasan latency dan ukuran data.
- `docs/images/latency_by_query.png` - chart perbandingan latency.
- `docs/benchmark_report.md` - laporan benchmark lokal/DuckDB.
- `docs/benchmark_dashboard.html` - dashboard HTML statis yang bisa dibuka di browser.
- `docs/methodology.md` - penjelasan metodologi.
- `docs/portfolio_summary.md` - ringkasan portfolio.

## Catatan Interpretasi

Benchmark DuckDB lokal adalah baseline. Hasilnya berguna untuk membaca arah performa,
memvalidasi format file, dan menyusun rekomendasi awal. Namun hasil lokal belum
mewakili semua kondisi production cluster seperti distributed scheduling, network,
object storage, concurrent users, catalog overhead, dan table format metadata.

Karena itu, jangan overclaim hasil DuckDB sebagai hasil production. Gunakan hasil ini
sebagai proof of concept yang rapi sebelum naik ke environment yang lebih besar.

## Rekomendasi Pengembangan Lanjutan

Jika ingin implementasi yang lebih advance, tools yang paling relevan untuk dikembangkan
berikutnya adalah:

- **Apache Spark / Spark SQL**: cocok untuk batch processing, ETL skala besar,
  distributed aggregation, file compaction, dan eksperimen shuffle tuning.
- **Trino**: cocok untuk interactive SQL di atas data lake/object storage, query
  federation, catalog-based lakehouse, dan analisis `EXPLAIN ANALYZE`.
- **MinIO atau object storage**: dipakai untuk mensimulasikan S3-compatible storage
  sebelum pindah ke cloud.
- **Apache Iceberg atau Delta Lake**: dipakai jika ingin menguji table format modern
  dengan metadata, schema evolution, partition evolution, dan time travel.

Tahap lanjut yang masuk akal:

1. Jalankan baseline DuckDB sampai report-nya stabil.
2. Pindahkan dataset Parquet ke object storage seperti MinIO.
3. Tambahkan Spark SQL untuk workload batch/distributed.
4. Tambahkan Trino untuk workload interactive analytics.
5. Bandingkan hasil DuckDB, Spark, dan Trino dengan metrik yang sesuai untuk tiap engine.

## Nilai Portfolio

Project ini menunjukkan cara kerja Data Engineer dalam mengambil keputusan berbasis
data: menentukan pertanyaan benchmark, membuat dataset, menjalankan query yang
sebanding, mengukur hasil, menjelaskan trade-off, lalu memberi rekomendasi teknis.
