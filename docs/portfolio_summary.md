# Ringkasan Portfolio: Lakehouse Performance Benchmark Lab

## Gambaran Project

Project ini menunjukkan workflow Data Engineering untuk mengevaluasi storage format,
partitioning strategy, compression, dan performa SQL query pada konteks lakehouse.
Implementasi saat ini berjalan lokal dengan DuckDB agar mudah dijalankan di laptop dan
mudah direproduksi.

Spark dan Trino diposisikan sebagai rekomendasi pengembangan lanjutan, bukan dependency
utama project.

## Masalah yang Diselesaikan

Banyak platform analytics menjadi lambat atau mahal karena data disimpan dalam format
yang kurang tepat, dipartisi tanpa bukti, atau di-tuning tanpa baseline yang jelas.
Project ini menunjukkan cara mengevaluasi trade-off tersebut sebelum memberi rekomendasi
arsitektur lakehouse.

## Isi Repository

- Synthetic transaction dataset generator.
- Konversi CSV ke Parquet dengan Snappy compression.
- Hive-style partitioned Parquet berdasarkan `event_month`.
- Konversi ORC optional jika library mendukung.
- Local DuckDB benchmark runner.
- Skenario SQL yang repeatable untuk full scan, filter, aggregation, dan month filter.
- Tabel hasil dengan average, min, max, p50, dan p95 latency.
- Markdown report dan benchmark chart.
- Rekomendasi pengembangan lanjutan ke Spark dan Trino.

## Skill yang Ditunjukkan

- Desain lakehouse benchmark.
- Analytical data modeling.
- Evaluasi Parquet dan optional ORC.
- Analisis partitioning dan file layout.
- SQL performance testing dengan DuckDB.
- Interpretasi hasil benchmark.
- Penulisan technical report untuk keputusan client.
- Local proof of concept yang bisa diperluas ke distributed system.

## Tools dan Teknologi

Stack utama:

- Python
- DuckDB
- Pandas
- PyArrow
- Matplotlib

Rekomendasi pengembangan lanjutan:

- Apache Spark / Spark SQL untuk batch processing dan distributed ETL.
- Trino untuk interactive SQL di atas object storage atau lakehouse catalog.
- MinIO atau S3-compatible object storage untuk simulasi data lake.
- Apache Iceberg atau Delta Lake untuk table format modern.

## Posisi sebagai Portfolio Freelance

Repository ini dibuat sebagai bukti kemampuan untuk project Big Data yang tidak hanya
membutuhkan pipeline, tetapi juga pengukuran dan rekomendasi teknis. Project ini
menunjukkan cara:

1. Menentukan pertanyaan benchmark.
2. Membuat atau menyiapkan controlled data.
3. Mengubah data ke format yang cocok untuk lakehouse.
4. Menjalankan SQL scenario yang bisa dibandingkan.
5. Mengukur latency dan storage footprint.
6. Menjelaskan trade-off dan limitation.
7. Memberi rekomendasi arsitektur berdasarkan evidence.

## Contoh Pitch Freelance

Saya dapat membantu merancang dan menjalankan lakehouse performance benchmark untuk
platform data Anda. Scope awal dapat dibuat lokal terlebih dahulu dengan DuckDB agar
metodologi, dataset, query, dan report jelas. Setelah baseline kuat, benchmark dapat
dikembangkan ke Spark SQL untuk batch/distributed ETL atau Trino untuk interactive
analytics di atas object storage/catalog.
