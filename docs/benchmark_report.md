# Laporan Benchmark DuckDB lokal

## Ringkasan Eksekutif

Laporan ini hanya membahas hasil benchmark untuk **DuckDB lokal**. Report ini
menjadi baseline lokal sebelum benchmark dikembangkan ke engine yang lebih besar.

- Source dengan storage footprint paling kecil adalah `parquet_unpartitioned` dengan ukuran 15.98 MB.
- Dibandingkan CSV, `parquet_unpartitioned` mengurangi storage footprint sekitar 79.5% pada run ini.
- `parquet_unpartitioned` menjadi source tercepat berdasarkan average latency pada 5 dari 5 skenario query DuckDB lokal.
- Partitioned Parquet lebih lambat 12.3% dibanding unpartitioned Parquet untuk query month-filtered aggregation.

## Ruang Lingkup Benchmark

| Area | Scope |
|---|---|
| Query engine | DuckDB lokal |
| Storage format | CSV, Parquet |
| Layout | Single CSV, unpartitioned Parquet, partitioned Parquet |
| Metrics | Latency, p50, p95, source size, result rows, memory delta |

## Dataset dan Eksekusi

| Item | Nilai |
|---|---|
| Engine | DuckDB lokal |
| Source format yang diukur | 3 |
| Skenario query yang diukur | 5 |
| Repeat per source/query | 3 |
| File raw result | `results/benchmark_results.csv` |
| File summary | `results/benchmark_summary.csv` |
| Dashboard HTML | `docs/benchmark_dashboard.html` |
| Grafik | `docs/images/latency_by_query.png` |

## Skenario Query

| query_name                   | catatan                                             |
|:-----------------------------|:----------------------------------------------------|
| q01_count_all                | Full scan row count sebagai baseline                |
| q02_filter_success_jakarta   | Filter status dan region lalu aggregation           |
| q03_group_by_region_category | Aggregation berdasarkan region dan product category |
| q04_monthly_aggregation      | Filter range bulan lalu aggregation                 |
| q05_channel_mix              | Grouping berdasarkan channel dan status             |

## Ukuran Data

| engine   | source_format                   |   source_size_mb |   reduction_vs_csv_percent |
|:---------|:--------------------------------|-----------------:|---------------------------:|
| duckdb   | parquet_unpartitioned           |          15.9831 |                      79.55 |
| duckdb   | parquet_partitioned_event_month |          22.4751 |                      71.24 |
| duckdb   | csv                             |          78.1451 |                       0    |

## Ringkasan Latency

| engine   | source_format                   | query_name                   |   avg_latency_seconds |   min_latency_seconds |   max_latency_seconds |   p50_latency_seconds |   p95_latency_seconds |   source_size_mb |
|:---------|:--------------------------------|:-----------------------------|----------------------:|----------------------:|----------------------:|----------------------:|----------------------:|-----------------:|
| duckdb   | parquet_unpartitioned           | q01_count_all                |             0.0119897 |              0.001763 |              0.031879 |              0.002327 |             0.0289238 |          15.9831 |
| duckdb   | parquet_partitioned_event_month | q01_count_all                |             0.0646363 |              0.04765  |              0.09234  |              0.053919 |             0.0884979 |          22.4751 |
| duckdb   | csv                             | q01_count_all                |             0.154322  |              0.132937 |              0.195808 |              0.134221 |             0.189649  |          78.1451 |
| duckdb   | parquet_unpartitioned           | q02_filter_success_jakarta   |             0.0597057 |              0.04528  |              0.068182 |              0.065655 |             0.0679293 |          15.9831 |
| duckdb   | csv                             | q02_filter_success_jakarta   |             0.142218  |              0.13605  |              0.149856 |              0.140747 |             0.148945  |          78.1451 |
| duckdb   | parquet_partitioned_event_month | q02_filter_success_jakarta   |             0.219133  |              0.217651 |              0.220841 |              0.218907 |             0.220648  |          22.4751 |
| duckdb   | parquet_unpartitioned           | q03_group_by_region_category |             0.107132  |              0.093716 |              0.126746 |              0.100934 |             0.124165  |          15.9831 |
| duckdb   | csv                             | q03_group_by_region_category |             0.159272  |              0.153027 |              0.165538 |              0.159252 |             0.164909  |          78.1451 |
| duckdb   | parquet_partitioned_event_month | q03_group_by_region_category |             0.267975  |              0.246536 |              0.308022 |              0.249366 |             0.302156  |          22.4751 |
| duckdb   | parquet_unpartitioned           | q04_monthly_aggregation      |             0.0503903 |              0.04653  |              0.056114 |              0.048527 |             0.0553553 |          15.9831 |
| duckdb   | parquet_partitioned_event_month | q04_monthly_aggregation      |             0.0566133 |              0.048524 |              0.066098 |              0.055218 |             0.06501   |          22.4751 |
| duckdb   | csv                             | q04_monthly_aggregation      |             0.1453    |              0.143808 |              0.147545 |              0.144546 |             0.147245  |          78.1451 |
| duckdb   | parquet_unpartitioned           | q05_channel_mix              |             0.0728247 |              0.072426 |              0.0734   |              0.072648 |             0.0733248 |          15.9831 |
| duckdb   | csv                             | q05_channel_mix              |             0.22328   |              0.152089 |              0.33774  |              0.180011 |             0.321967  |          78.1451 |
| duckdb   | parquet_partitioned_event_month | q05_channel_mix              |             0.287772  |              0.261636 |              0.31247  |              0.289211 |             0.310144  |          22.4751 |

## Source Tercepat per Query Berdasarkan Average Latency

| query_name                   | source_format         |   avg_latency_seconds |   p50_latency_seconds |   p95_latency_seconds |
|:-----------------------------|:----------------------|----------------------:|----------------------:|----------------------:|
| q01_count_all                | parquet_unpartitioned |             0.0119897 |              0.002327 |             0.0289238 |
| q02_filter_success_jakarta   | parquet_unpartitioned |             0.0597057 |              0.065655 |             0.0679293 |
| q03_group_by_region_category | parquet_unpartitioned |             0.107132  |              0.100934 |             0.124165  |
| q04_monthly_aggregation      | parquet_unpartitioned |             0.0503903 |              0.048527 |             0.0553553 |
| q05_channel_mix              | parquet_unpartitioned |             0.0728247 |              0.072648 |             0.0733248 |

## Grafik

![Latency by Query](images/latency_by_query.png)

## Temuan

- Source dengan storage footprint paling kecil adalah `parquet_unpartitioned` dengan ukuran 15.98 MB.
- Dibandingkan CSV, `parquet_unpartitioned` mengurangi storage footprint sekitar 79.5% pada run ini.
- `parquet_unpartitioned` menjadi source tercepat berdasarkan average latency pada 5 dari 5 skenario query DuckDB lokal.
- Partitioned Parquet lebih lambat 12.3% dibanding unpartitioned Parquet untuk query month-filtered aggregation.

## Rekomendasi

- Gunakan report ini sebagai baseline lokal DuckDB sebelum masuk ke engine distributed.
- Bandingkan p50 dan p95 latency, bukan hanya average.
- Validasi partitioning dengan query yang memang memakai partition column.
- Jangan mencampur hasil dataset berbeda dalam satu interpretasi benchmark.
- Untuk tahap advance, kembangkan Spark SQL untuk batch/distributed ETL dan Trino untuk interactive SQL di atas object storage atau lakehouse catalog.

## Batasan

- Report ini hanya membaca file `results/benchmark_results.csv`.
- Hasil DuckDB lokal belum mewakili cluster scheduling, network transfer, object
  storage overhead, atau concurrent users.
- Jika dikembangkan ke Spark atau Trino, tambahkan metrik engine-native seperti shuffle,
  spill, bytes scanned, split count, dan query plan.
