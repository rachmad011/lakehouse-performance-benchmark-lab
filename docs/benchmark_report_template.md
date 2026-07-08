# Template Laporan Lakehouse Benchmark

Gunakan template ini untuk membuat laporan benchmark setelah menjalankan workflow
DuckDB lokal.

## 1. Ringkasan Eksekutif

Ringkas tujuan benchmark, dataset yang diuji, hasil paling penting, dan rekomendasi
berikutnya. Bagian ini harus cukup singkat untuk dibaca stakeholder non-teknis.

Hal yang sebaiknya dijawab:

- Format mana yang paling hemat storage.
- Layout mana yang punya p50 dan p95 latency terbaik.
- Apakah partitioning membantu query dengan filter bulan.
- Test lanjutan apa yang dibutuhkan sebelum rekomendasi production.

## 2. Pertanyaan Bisnis dan Scope

Jelaskan keputusan teknis apa yang ingin dibantu oleh benchmark ini.

| Area | Masuk Scope | Di Luar Scope Baseline Lokal |
|---|---|---|
| Storage format | CSV, Parquet, optional ORC | Final design Delta/Iceberg production |
| Query engine | DuckDB local benchmark | Spark, Trino, cluster sizing, SLA testing |
| Layout | Unpartitioned dan month-partitioned data | Full table maintenance strategy |
| Metrics | Latency, p50, p95, source size, memory delta | Cloud cost dan concurrent users |

## 3. Arsitektur

Jelaskan data flow dan batasan engine yang dipakai.

```text
CSV raw data
   |
   +--> Parquet unpartitioned
   |
   +--> Parquet partitioned by event_month
   |
   +--> ORC optional
   |
   v
DuckDB local benchmark
   |
   v
Results, chart, markdown report, HTML dashboard
```

## 4. Dataset

| Atribut | Nilai |
|---|---|
| Jenis dataset | Synthetic transaction fact table |
| Jumlah row | Isi setelah menjalankan `src/generate_dataset.py` |
| Periode data | 2025-01 sampai 2025-12 |
| Partition column | `event_month` |
| Dimensi utama | `region`, `channel`, `product_category`, `status` |
| Measures | `amount`, `quantity` |

## 5. Desain Benchmark

| Scenario | Format | Layout | Query Pattern | Keputusan yang Diuji |
|---|---|---|---|---|
| Baseline scan | CSV | Single file | Count/filter/group | Biaya raw row-oriented storage |
| Columnar scan | Parquet | Unpartitioned | SQL yang sama | Manfaat columnar encoding/compression |
| Partitioned scan | Parquet | Folder `event_month` | Month-filtered aggregation | Manfaat partition pruning |
| Optional format | ORC | Unpartitioned/partitioned | SQL yang sama | Trade-off Parquet vs ORC |

## 6. Metrik

Metrik benchmark lokal:

- Average latency.
- Minimum dan maximum latency.
- p50 dan p95 latency.
- Source size dalam MB.
- Result row count.
- Memory delta.

## 7. Hasil

### 7.1 Storage Footprint

Masukkan ringkasan ukuran source data di sini.

| Source Format | Size MB | Reduction vs CSV |
|---|---:|---:|
| Isi | Isi | Isi |

### 7.2 Latency Summary

Masukkan tabel p50/p95 latency di sini.

| Engine | Source Format | Query | Avg Seconds | p50 Seconds | p95 Seconds |
|---|---|---|---:|---:|---:|
| DuckDB | Isi | Isi | Isi | Isi | Isi |

### 7.3 Query-Level Winners

Jelaskan source mana yang paling cepat untuk tiap query dan kenapa hasilnya masuk akal
atau justru perlu diselidiki.

## 8. Temuan

Kategori temuan yang disarankan:

- Storage footprint.
- Query latency.
- Partition pruning.
- Compression dan file layout.
- Operational trade-offs.

## 9. Rekomendasi

Tulis rekomendasi sebagai tindakan yang bisa diambil client.

Contoh:

- Gunakan Parquet atau ORC untuk analytical table, bukan raw CSV.
- Pilih partition column dari filter yang sering dipakai, bukan dari semua dimensi.
- Validasi pilihan compression dengan data dan query yang representatif.
- Tambahkan compaction jika partitioning menghasilkan terlalu banyak small files.
- Naikkan benchmark ke Spark atau Trino jika sudah perlu validasi distributed workload.

## 10. Batasan

Tuliskan asumsi dengan jelas:

- Hasil DuckDB lokal belum mewakili cluster scheduling atau object storage overhead.
- Synthetic data belum tentu mewakili skew, null distribution, nested schemas, atau pola
  user production.
- Warm-cache dan cold-cache run sebaiknya dipisahkan untuk benchmark production-grade.

## 11. Next Steps

- Tambahkan ORC read benchmark jika engine mendukung.
- Tambahkan perbandingan compression Snappy, Zstd, dan Gzip.
- Tambahkan eksperimen ukuran file dan small files.
- Kembangkan Spark SQL jika ingin menguji batch/distributed ETL.
- Kembangkan Trino jika ingin menguji interactive SQL di atas object storage/catalog.
- Buat final PDF report dengan appendix tables.

## 12. Appendix

Isi dengan:

- Command yang dipakai untuk menjalankan benchmark.
- Detail hardware dan operating system.
- Versi Python, DuckDB, dan PyArrow.
- Lokasi file raw result.
- Lokasi dashboard HTML.
- SQL query text.
