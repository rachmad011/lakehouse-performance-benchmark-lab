# Metodologi Benchmark

Dokumen ini menjelaskan cara project mengukur pengaruh storage format, layout data, dan
pola SQL query terhadap performa analytics. Scope implementasi saat ini dibatasi ke
DuckDB lokal agar mudah dijalankan di laptop dan mudah direproduksi.

Spark dan Trino tidak menjadi bagian workflow utama. Keduanya direkomendasikan sebagai
pengembangan lanjutan jika benchmark ingin dinaikkan ke distributed processing atau
interactive SQL di atas object storage/catalog.

## Pertanyaan Utama

Benchmark ini dibuat untuk menjawab pertanyaan yang biasa muncul di project lakehouse:

1. Seberapa besar penghematan storage saat CSV dikonversi ke Parquet atau ORC?
2. Query seperti apa yang paling terbantu oleh columnar format?
3. Apakah partitioning berdasarkan `event_month` mempercepat query yang memfilter bulan?
4. Kapan partitioning justru menambah overhead karena file atau metadata bertambah?
5. Metrik apa yang perlu dikumpulkan sebelum memberi rekomendasi tuning?
6. Kapan hasil DuckDB lokal perlu divalidasi lagi dengan Spark atau Trino?

## Scope Benchmark Saat Ini

Baseline lokal menggunakan:

- Synthetic transaction data dengan random seed tetap.
- CSV sebagai raw baseline.
- Parquet dengan Snappy compression sebagai columnar format utama.
- Hive-style partitioned Parquet berdasarkan `event_month`.
- Optional ORC jika library mendukung.
- DuckDB sebagai SQL engine lokal.
- Query yang diulang beberapa kali untuk mengukur latency dan ukuran source data.

Di luar scope versi ini:

- Spark SQL runtime.
- Trino runtime.
- Hadoop native setup.
- MinIO/object storage.
- Delta Lake dan Apache Iceberg.
- Cluster sizing, concurrency test, dan SLA production.

## Desain Dataset

Dataset synthetic dibuat seperti transaction fact table:

| Kolom | Penjelasan |
|---|---|
| `transaction_id` | ID unik tiap transaksi |
| `customer_id` | ID customer dengan cardinality cukup tinggi |
| `event_date` | Tanggal transaksi |
| `event_month` | Bulan transaksi, dipakai untuk partitioning dan reporting |
| `region` | Dimensi wilayah |
| `channel` | Channel transaksi |
| `product_category` | Kategori produk |
| `amount` | Nilai transaksi untuk aggregation |
| `quantity` | Jumlah item/transaksi |
| `status` | Status transaksi untuk filter |
| `amount_bucket` | Segmentasi nominal transaksi |

Jumlah row default diatur di `configs/benchmark_config.json`. Untuk uji skala lebih
besar, jumlah row bisa diatur lewat command line.

Untuk dataset sangat besar, misalnya 100 juta rows, data sebaiknya dibuat per chunk dan
ditulis langsung ke Parquet. Cara ini menghindari penggunaan memory besar karena script
tidak perlu menampung seluruh dataset sekaligus. CSV tetap bisa dipakai sebagai baseline
kecil, tetapi bukan format perantara yang ideal untuk uji lokal berskala besar.

## Variabel Eksperimen

### Variabel yang Diubah

- Storage format: CSV, Parquet, dan optional ORC.
- Compression: baseline Parquet memakai Snappy.
- Layout: unpartitioned dan partitioned berdasarkan `event_month`.
- Query pattern: full scan, selective filter, grouped aggregation, month filtering, dan
  dimensional aggregation.
- Engine: DuckDB lokal.

### Variabel yang Diukur

- Query latency dalam detik.
- Average, min, max, p50, dan p95 latency.
- Ukuran source data dalam MB.
- Jumlah result rows.
- Memory delta proses benchmark lokal.

## Alur Eksperimen

1. Buat synthetic transaction dataset.
2. Simpan dataset mentah ke CSV di `data/raw/`.
3. Konversi CSV ke unpartitioned Parquet.
4. Konversi CSV ke partitioned Parquet dengan folder Hive-style.
5. Coba konversi ORC jika environment mendukung.
6. Jalankan skenario SQL yang sama untuk setiap source dengan DuckDB.
7. Ulangi setiap query sesuai nilai `--repeat`.
8. Simpan hasil mentah ke `results/benchmark_results.csv`.
9. Buat summary average, min, max, p50, dan p95 latency di
   `results/benchmark_summary.csv`.
10. Buat chart di `docs/images/`, report Markdown di `docs/benchmark_report.md`, dan
    dashboard HTML di `docs/benchmark_dashboard.html`.

## Skenario Query

| Query | Pattern | Yang Diuji |
|---|---|---|
| `q01_count_all` | Full scan count | Overhead scan dasar |
| `q02_filter_success_jakarta` | Filter + aggregation | Predicate filtering dan column pruning |
| `q03_group_by_region_category` | Grouped aggregation | Performa aggregation analytics |
| `q04_monthly_aggregation` | Month range filter + aggregation | Partition pruning dan date filtering |
| `q05_channel_mix` | Multi-column grouping | Grouping pada low-cardinality columns |

## Kontrol Agar Benchmark Fair

- Jalankan semua test lokal di mesin yang sama.
- Gunakan dataset yang sama untuk setiap format.
- Gunakan SQL yang secara logika setara untuk setiap source.
- Jangan commit generated data dan generated results.
- Jalankan beberapa repeat dan bandingkan p50/p95, bukan hanya average.
- Simpan jumlah result rows untuk mendeteksi perubahan semantik query.
- Jangan overclaim hasil lokal sebagai hasil production cluster.

## Batasan yang Perlu Dipahami

- Hasil DuckDB lokal belum mencakup cluster scheduling, shuffle, network transfer, atau
  object storage overhead.
- OS file cache bisa memengaruhi hasil repeated run. Untuk benchmark production-grade,
  cold run dan warm run sebaiknya dipisahkan.
- Synthetic data berguna untuk reproduksi, tetapi data client bisa punya skew, nested
  fields, schema lebih lebar, dan cardinality berbeda.
- Partitioning berdasarkan `event_month` hanya membantu jika query memang memfilter
  kolom itu dan engine bisa melakukan partition pruning.
- Dukungan ORC bergantung pada library dan engine yang terpasang.

## Rekomendasi Pengembangan Lanjutan

Jika project ingin dinaikkan ke implementasi yang lebih advance, tool yang paling
relevan adalah Spark dan Trino.

### Spark SQL

Spark cocok dikembangkan ketika kebutuhan sudah masuk ke:

- Batch processing dengan data jauh lebih besar dari kapasitas satu mesin.
- ETL distributed.
- File compaction.
- Shuffle-heavy aggregation.
- Eksperimen partitioning dan compression pada skala cluster.

Metrik tambahan yang perlu dikumpulkan:

- Job duration dan stage duration.
- Input bytes dan input rows.
- Shuffle read dan shuffle write.
- Spill to disk dan spill to memory.
- Jumlah output files.
- Physical plan sebelum dan sesudah tuning.

### Trino

Trino cocok dikembangkan ketika kebutuhan sudah masuk ke:

- Interactive analytics di atas data lake.
- Query federation ke beberapa source.
- Object storage seperti MinIO/S3.
- Hive atau Iceberg catalog.
- Analisis query plan dengan `EXPLAIN ANALYZE`.

Metrik tambahan yang perlu dikumpulkan:

- Query wall time dan CPU time.
- Physical input bytes dan physical input rows.
- Processed input rows.
- Split count.
- Planning time, queued time, dan execution time.
- Peak memory dan spilled bytes.
- Perilaku connector/catalog saat melakukan partition pruning.

## Matrix Compression dan File Layout

Eksperimen lanjutan bisa memakai matrix berikut:

| Format | Compression | Layout | Tujuan |
|---|---|---|---|
| Parquet | Snappy | Unpartitioned | Baseline cepat dan umum |
| Parquet | Zstd | Unpartitioned | Membandingkan compression ratio |
| Parquet | Snappy | Partitioned by month | Menguji partition pruning |
| ORC | Zlib atau Snappy | Unpartitioned | Membandingkan ORC dengan Parquet |
| Iceberg | Engine default | Partition spec | Menguji metadata dan planning table format |
| Delta Lake | Engine default | Partitioned by month | Menguji transactional lakehouse table |

## Struktur Laporan

Laporan client sebaiknya berisi:

1. Executive summary.
2. Pertanyaan bisnis dan scope benchmark.
3. Architecture dan data flow.
4. Dataset dan schema.
5. Desain eksperimen dan kontrol.
6. Metrik dan cara pengukuran.
7. Hasil storage footprint.
8. Hasil latency dengan average, p50, dan p95.
9. Temuan per query.
10. Rekomendasi dan next steps.
11. Batasan dan asumsi.
12. Appendix berisi command, environment, dan query.
