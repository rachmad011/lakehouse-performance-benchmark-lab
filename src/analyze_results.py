from __future__ import annotations

from dataclasses import dataclass
from html import escape
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from rich.console import Console

console = Console()


@dataclass(frozen=True)
class ReportConfig:
    name: str
    engine_label: str
    result_path: Path
    summary_path: Path
    report_path: Path
    dashboard_path: Path
    chart_path: Path
    chart_title: str
    missing_guidance: str


LOCAL_REPORT = ReportConfig(
    name="local",
    engine_label="DuckDB lokal",
    result_path=Path("results/benchmark_results.csv"),
    summary_path=Path("results/benchmark_summary.csv"),
    report_path=Path("docs/benchmark_report.md"),
    dashboard_path=Path("docs/benchmark_dashboard.html"),
    chart_path=Path("docs/images/latency_by_query.png"),
    chart_title="Average Query Latency DuckDB Lokal",
    missing_guidance=(
        "Jalankan `uv run python src/run_benchmark_duckdb.py --repeat 3` terlebih dahulu."
    ),
)


def percentile_95(series: pd.Series) -> float:
    return float(series.quantile(0.95))


def percentile_50(series: pd.Series) -> float:
    return float(series.quantile(0.50))


def build_latency_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Ringkas hasil benchmark mentah menjadi metrik latency per query."""
    return (
        df.groupby(["engine", "source_format", "query_name"], as_index=False)
        .agg(
            avg_latency_seconds=("latency_seconds", "mean"),
            min_latency_seconds=("latency_seconds", "min"),
            max_latency_seconds=("latency_seconds", "max"),
            p50_latency_seconds=("latency_seconds", percentile_50),
            p95_latency_seconds=("latency_seconds", percentile_95),
            source_size_mb=("source_size_mb", "max"),
        )
        .sort_values(["query_name", "avg_latency_seconds"])
    )


def build_storage_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Ringkas ukuran source data dan bandingkan dengan CSV jika tersedia."""
    storage = (
        df.groupby(["engine", "source_format"], as_index=False)
        .agg(source_size_mb=("source_size_mb", "max"))
        .sort_values(["engine", "source_size_mb"])
    )

    csv_size_by_engine = (
        storage[storage["source_format"] == "csv"].set_index("engine")["source_size_mb"].to_dict()
    )

    reductions: list[float | None] = []
    for _, row in storage.iterrows():
        csv_size = csv_size_by_engine.get(row["engine"])
        if csv_size and csv_size > 0:
            reductions.append(round((1 - float(row["source_size_mb"]) / csv_size) * 100, 2))
        else:
            reductions.append(None)

    storage["reduction_vs_csv_percent"] = reductions
    return storage


def build_query_winners(summary: pd.DataFrame) -> pd.DataFrame:
    """Ambil source dengan average latency terendah untuk tiap query."""
    winner_idx = summary.groupby("query_name")["avg_latency_seconds"].idxmin()
    return (
        summary.loc[
            winner_idx,
            [
                "query_name",
                "source_format",
                "avg_latency_seconds",
                "p50_latency_seconds",
                "p95_latency_seconds",
            ],
        ]
        .sort_values("query_name")
        .reset_index(drop=True)
    )


def create_latency_chart(summary: pd.DataFrame, config: ReportConfig) -> None:
    """Buat bar chart average query latency untuk report tertentu."""
    config.chart_path.parent.mkdir(parents=True, exist_ok=True)

    pivot = summary.pivot_table(
        index="query_name",
        columns="source_format",
        values="avg_latency_seconds",
        aggfunc="mean",
    )

    ax = pivot.plot(kind="bar", figsize=(12, 6))
    ax.set_title(config.chart_title)
    ax.set_xlabel("Query Scenario")
    ax.set_ylabel("Average Latency (detik)")
    ax.tick_params(axis="x", rotation=45)
    plt.tight_layout()
    plt.savefig(config.chart_path)
    plt.close()


def markdown_bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def build_query_scenarios(raw_df: pd.DataFrame) -> str:
    note_labels = {
        "q01_count_all": "Full scan row count sebagai baseline",
        "q02_filter_success_jakarta": "Filter status dan region lalu aggregation",
        "q03_group_by_region_category": "Aggregation berdasarkan region dan product category",
        "q04_monthly_aggregation": "Filter range bulan lalu aggregation",
        "q05_channel_mix": "Grouping berdasarkan channel dan status",
    }
    query_scenario_df = raw_df[["query_name", "notes"]].drop_duplicates().sort_values("query_name")
    query_scenario_df["notes"] = query_scenario_df["query_name"].map(note_labels).fillna(
        query_scenario_df["notes"]
    )
    query_scenario_df = query_scenario_df.rename(
        columns={"query_name": "query_name", "notes": "catatan"}
    )
    return query_scenario_df.drop_duplicates().to_markdown(index=False)


def generate_findings(
    summary: pd.DataFrame,
    storage: pd.DataFrame,
    config: ReportConfig,
) -> list[str]:
    """Buat temuan benchmark untuk report tertentu."""
    findings: list[str] = []

    if not storage.empty:
        smallest = storage.sort_values("source_size_mb").iloc[0]
        findings.append(
            f"Source dengan storage footprint paling kecil adalah "
            f"`{smallest['source_format']}` dengan ukuran {smallest['source_size_mb']:.2f} MB."
        )

        csv_rows = storage[storage["source_format"] == "csv"]
        if not csv_rows.empty and smallest["source_format"] != "csv":
            csv_size = float(csv_rows.iloc[0]["source_size_mb"])
            reduction = (1 - float(smallest["source_size_mb"]) / csv_size) * 100
            findings.append(
                f"Dibandingkan CSV, `{smallest['source_format']}` mengurangi storage "
                f"footprint sekitar {reduction:.1f}% pada run ini."
            )

    if not summary.empty:
        winners = build_query_winners(summary)
        winner_counts = winners["source_format"].value_counts()
        leading_source = winner_counts.index[0]
        leading_count = int(winner_counts.iloc[0])
        findings.append(
            f"`{leading_source}` menjadi source tercepat berdasarkan average latency "
            f"pada {leading_count} dari {len(winners)} skenario query {config.engine_label}."
        )

    monthly = summary[summary["query_name"] == "q04_monthly_aggregation"]
    partitioned = monthly[monthly["source_format"] == "parquet_partitioned_event_month"]
    unpartitioned = monthly[monthly["source_format"] == "parquet_unpartitioned"]
    if not partitioned.empty and not unpartitioned.empty:
        partitioned_latency = float(partitioned.iloc[0]["avg_latency_seconds"])
        unpartitioned_latency = float(unpartitioned.iloc[0]["avg_latency_seconds"])
        if partitioned_latency < unpartitioned_latency:
            improvement = (1 - partitioned_latency / unpartitioned_latency) * 100
            findings.append(
                f"Partitioned Parquet lebih cepat {improvement:.1f}% dibanding "
                "unpartitioned Parquet untuk query month-filtered aggregation."
            )
        elif partitioned_latency > unpartitioned_latency:
            overhead = (partitioned_latency / unpartitioned_latency - 1) * 100
            findings.append(
                f"Partitioned Parquet lebih lambat {overhead:.1f}% dibanding "
                "unpartitioned Parquet untuk query month-filtered aggregation."
            )

    return findings


def build_scope_table(config: ReportConfig) -> str:
    rows = [
        ("Query engine", config.engine_label),
        ("Storage format", "CSV, Parquet"),
        ("Layout", "Single CSV, unpartitioned Parquet, partitioned Parquet"),
        ("Metrics", "Latency, p50, p95, source size, result rows, memory delta"),
    ]

    table_rows = ["| Area | Scope |", "|---|---|"]
    table_rows.extend(f"| {area} | {scope} |" for area, scope in rows)
    return "\n".join(table_rows)


def build_recommendations(config: ReportConfig) -> list[str]:
    return [
        "Gunakan report ini sebagai baseline lokal DuckDB sebelum masuk ke engine distributed.",
        "Bandingkan p50 dan p95 latency, bukan hanya average.",
        "Validasi partitioning dengan query yang memang memakai partition column.",
        "Jangan mencampur hasil dataset berbeda dalam satu interpretasi benchmark.",
        "Untuk tahap advance, kembangkan Spark SQL untuk batch/distributed ETL dan "
        "Trino untuk interactive SQL di atas object storage atau lakehouse catalog.",
    ]


def build_report(
    raw_df: pd.DataFrame,
    summary: pd.DataFrame,
    storage: pd.DataFrame,
    winners: pd.DataFrame,
    config: ReportConfig,
) -> str:
    """Buat laporan Markdown dari hasil benchmark satu engine."""
    repeat_count = int(raw_df["repeat_no"].max()) if "repeat_no" in raw_df else 1
    source_count = raw_df["source_format"].nunique()
    query_count = raw_df["query_name"].nunique()
    findings = generate_findings(summary=summary, storage=storage, config=config)
    recommendations = build_recommendations(config)
    query_scenarios = build_query_scenarios(raw_df)

    chart_relative_path = config.chart_path.relative_to(config.report_path.parent).as_posix()

    return f"""# Laporan Benchmark {config.engine_label}

## Ringkasan Eksekutif

Laporan ini hanya membahas hasil benchmark untuk **{config.engine_label}**. Report ini
menjadi baseline lokal sebelum benchmark dikembangkan ke engine yang lebih besar.

{markdown_bullets(findings)}

## Ruang Lingkup Benchmark

{build_scope_table(config)}

## Dataset dan Eksekusi

| Item | Nilai |
|---|---|
| Engine | {config.engine_label} |
| Source format yang diukur | {source_count} |
| Skenario query yang diukur | {query_count} |
| Repeat per source/query | {repeat_count} |
| File raw result | `{config.result_path.as_posix()}` |
| File summary | `{config.summary_path.as_posix()}` |
| Dashboard HTML | `{config.dashboard_path.as_posix()}` |
| Grafik | `{config.chart_path.as_posix()}` |

## Skenario Query

{query_scenarios}

## Ukuran Data

{storage.to_markdown(index=False)}

## Ringkasan Latency

{summary.to_markdown(index=False)}

## Source Tercepat per Query Berdasarkan Average Latency

{winners.to_markdown(index=False)}

## Grafik

![Latency by Query]({chart_relative_path})

## Temuan

{markdown_bullets(findings)}

## Rekomendasi

{markdown_bullets(recommendations)}

## Batasan

- Report ini hanya membaca file `{config.result_path.as_posix()}`.
- Hasil DuckDB lokal belum mewakili cluster scheduling, network transfer, object
  storage overhead, atau concurrent users.
- Jika dikembangkan ke Spark atau Trino, tambahkan metrik engine-native seperti shuffle,
  spill, bytes scanned, split count, dan query plan.
"""


def format_decimal(value: float | int | None, digits: int = 2) -> str:
    if value is None or pd.isna(value):
        return "-"
    return f"{float(value):,.{digits}f}"


def dataframe_to_html(df: pd.DataFrame) -> str:
    display_df = df.copy()
    for column in display_df.select_dtypes(include="number").columns:
        display_df[column] = display_df[column].map(lambda value: format_decimal(value, 4))
    return display_df.to_html(
        index=False,
        escape=True,
        border=0,
        classes="data-table",
        justify="left",
        na_rep="-",
    )


def html_list(items: list[str]) -> str:
    list_items = "\n".join(f"<li>{escape(item)}</li>" for item in items)
    return f"<ul>{list_items}</ul>"


def build_bar_svg(
    rows: list[tuple[str, float]],
    title: str,
    unit: str,
    width: int = 920,
) -> str:
    if not rows:
        return "<p class=\"muted\">Belum ada data untuk divisualisasikan.</p>"

    label_width = 290
    chart_width = width - label_width - 120
    row_height = 34
    top = 54
    height = top + len(rows) * row_height + 28
    max_value = max(value for _, value in rows) or 1
    colors = ["#2563eb", "#059669", "#d97706", "#7c3aed", "#dc2626"]
    bars: list[str] = []

    for index, (label, value) in enumerate(rows):
        y = top + index * row_height
        bar_width = max(4, int((value / max_value) * chart_width))
        color = colors[index % len(colors)]
        bars.append(
            f'<text x="0" y="{y + 18}" class="svg-label">{escape(label)}</text>'
            f'<rect x="{label_width}" y="{y}" width="{bar_width}" height="20" '
            f'rx="4" fill="{color}"></rect>'
            f'<text x="{label_width + bar_width + 10}" y="{y + 15}" '
            f'class="svg-value">{format_decimal(value, 4)} {escape(unit)}</text>'
        )

    return f"""
<svg class="chart" viewBox="0 0 {width} {height}" role="img" aria-label="{escape(title)}">
  <title>{escape(title)}</title>
  <text x="0" y="24" class="svg-title">{escape(title)}</text>
  {''.join(bars)}
</svg>
"""


def build_storage_chart(storage: pd.DataFrame) -> str:
    rows = [
        (str(row["source_format"]), float(row["source_size_mb"]))
        for _, row in storage.sort_values("source_size_mb").iterrows()
    ]
    return build_bar_svg(rows=rows, title="Storage Footprint per Source", unit="MB")


def build_latency_chart_svg(summary: pd.DataFrame) -> str:
    ordered = summary.sort_values(["query_name", "avg_latency_seconds"])
    rows = [
        (f"{row['query_name']} | {row['source_format']}", float(row["avg_latency_seconds"]))
        for _, row in ordered.iterrows()
    ]
    return build_bar_svg(rows=rows, title="Average Latency per Query dan Source", unit="detik")


def get_partition_card(summary: pd.DataFrame) -> tuple[str, str]:
    monthly = summary[summary["query_name"] == "q04_monthly_aggregation"]
    partitioned = monthly[monthly["source_format"] == "parquet_partitioned_event_month"]
    unpartitioned = monthly[monthly["source_format"] == "parquet_unpartitioned"]
    if partitioned.empty or unpartitioned.empty:
        return "-", "Butuh hasil partitioned dan unpartitioned untuk membaca dampaknya."

    partitioned_latency = float(partitioned.iloc[0]["avg_latency_seconds"])
    unpartitioned_latency = float(unpartitioned.iloc[0]["avg_latency_seconds"])
    if unpartitioned_latency <= 0:
        return "-", "Latency unpartitioned tidak valid untuk dibandingkan."

    change = (1 - partitioned_latency / unpartitioned_latency) * 100
    if change >= 0:
        return f"{change:.1f}% lebih cepat", "Partitioned Parquet pada query filter bulan."
    return f"{abs(change):.1f}% lebih lambat", "Partitioned Parquet pada query filter bulan."


def build_dashboard(
    raw_df: pd.DataFrame,
    summary: pd.DataFrame,
    storage: pd.DataFrame,
    winners: pd.DataFrame,
    config: ReportConfig,
) -> str:
    """Buat dashboard HTML statis dari hasil benchmark DuckDB lokal."""
    findings = generate_findings(summary=summary, storage=storage, config=config)
    recommendations = build_recommendations(config)
    repeat_count = int(raw_df["repeat_no"].max()) if "repeat_no" in raw_df else 1
    source_count = raw_df["source_format"].nunique()
    query_count = raw_df["query_name"].nunique()
    run_count = len(raw_df)

    smallest = storage.sort_values("source_size_mb").iloc[0]
    fastest_counts = winners["source_format"].value_counts()
    fastest_source = fastest_counts.index[0] if not fastest_counts.empty else "-"
    fastest_count = int(fastest_counts.iloc[0]) if not fastest_counts.empty else 0
    partition_value, partition_note = get_partition_card(summary)

    cards = [
        ("Benchmark runs", f"{run_count}", f"{source_count} source x {query_count} query"),
        ("Repeat per query", f"{repeat_count}", "Dipakai untuk p50 dan p95 latency"),
        (
            "Storage terkecil",
            f"{smallest['source_format']}",
            f"{format_decimal(smallest['source_size_mb'], 2)} MB",
        ),
        ("Source paling sering menang", f"{fastest_source}", f"{fastest_count} query"),
        ("Dampak partitioning", partition_value, partition_note),
    ]
    card_html = "\n".join(
        f"""
        <article class="metric-card">
          <span>{escape(label)}</span>
          <strong>{escape(value)}</strong>
          <small>{escape(note)}</small>
        </article>
        """
        for label, value, note in cards
    )

    return f"""<!doctype html>
<html lang="id">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Dashboard Benchmark DuckDB Lokal</title>
  <style>
    :root {{
      --bg: #f5f7fb;
      --panel: #ffffff;
      --text: #172033;
      --muted: #657085;
      --line: #d9e0ea;
      --blue: #2563eb;
      --green: #059669;
      --amber: #d97706;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: Arial, Helvetica, sans-serif;
      line-height: 1.5;
    }}
    header {{
      background: #172033;
      color: #ffffff;
      padding: 32px 28px;
    }}
    header h1 {{
      margin: 0 0 8px;
      font-size: 30px;
      letter-spacing: 0;
    }}
    header p {{
      max-width: 920px;
      margin: 0;
      color: #cbd5e1;
    }}
    main {{
      width: min(1180px, calc(100% - 32px));
      margin: 24px auto 48px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 12px;
    }}
    .metric-card,
    section {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04);
    }}
    .metric-card {{
      min-height: 126px;
      padding: 16px;
    }}
    .metric-card span,
    .metric-card small,
    .muted {{
      color: var(--muted);
    }}
    .metric-card span {{
      display: block;
      font-size: 13px;
      margin-bottom: 8px;
    }}
    .metric-card strong {{
      display: block;
      font-size: 22px;
      line-height: 1.2;
      overflow-wrap: anywhere;
    }}
    .metric-card small {{
      display: block;
      margin-top: 8px;
    }}
    section {{
      margin-top: 16px;
      padding: 20px;
    }}
    h2 {{
      margin: 0 0 14px;
      font-size: 19px;
      letter-spacing: 0;
    }}
    .section-note {{
      max-width: 860px;
      margin: -4px 0 16px;
      color: var(--muted);
    }}
    .chart {{
      display: block;
      width: 100%;
      height: auto;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fbfcfe;
      padding: 12px;
    }}
    .chart + .table-wrap {{
      margin-top: 16px;
    }}
    .svg-title {{
      font: 700 18px Arial, Helvetica, sans-serif;
      fill: var(--text);
    }}
    .svg-label {{
      font: 12px Arial, Helvetica, sans-serif;
      fill: var(--muted);
    }}
    .svg-value {{
      font: 12px Arial, Helvetica, sans-serif;
      fill: var(--text);
    }}
    .table-wrap {{
      width: 100%;
      overflow-x: auto;
    }}
    .data-table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }}
    .data-table th {{
      text-align: left;
      background: #eef2f7;
      color: #263248;
      font-weight: 700;
    }}
    .data-table th,
    .data-table td {{
      border-bottom: 1px solid var(--line);
      padding: 9px 10px;
      white-space: nowrap;
    }}
    ul {{
      margin: 0;
      padding-left: 20px;
    }}
    li + li {{
      margin-top: 8px;
    }}
    footer {{
      color: var(--muted);
      font-size: 12px;
      margin-top: 18px;
      text-align: center;
    }}
    @media (max-width: 980px) {{
      .grid {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <header>
    <h1>Dashboard Benchmark DuckDB Lokal</h1>
    <p>
      Ringkasan visual untuk membandingkan CSV, Parquet, dan partitioned Parquet
      berdasarkan latency, p50/p95, storage footprint, dan query-level winner.
    </p>
  </header>
  <main>
    <div class="grid">
      {card_html}
    </div>

    <section>
      <h2>Temuan Utama</h2>
      {html_list(findings)}
    </section>

    <section>
      <h2>Storage Footprint</h2>
      <p class="section-note">
        Section ini membandingkan ukuran fisik setiap source data di disk. Metrik ini
        penting untuk melihat efisiensi format dan dampak partitioning terhadap storage.
      </p>
      {build_storage_chart(storage)}
      <div class="table-wrap">{dataframe_to_html(storage)}</div>
    </section>

    <section>
      <h2>Source Tercepat per Query</h2>
      <div class="table-wrap">{dataframe_to_html(winners)}</div>
    </section>

    <section>
      <h2>Average Latency</h2>
      {build_latency_chart_svg(summary)}
    </section>

    <section>
      <h2>Ringkasan Latency</h2>
      <div class="table-wrap">{dataframe_to_html(summary)}</div>
    </section>

    <section>
      <h2>Rekomendasi</h2>
      {html_list(recommendations)}
    </section>

    <footer>
      Dibuat dari {escape(config.result_path.as_posix())}. Markdown report:
      {escape(config.report_path.as_posix())}.
    </footer>
  </main>
</body>
</html>
"""


def build_missing_report(config: ReportConfig) -> str:
    return f"""# Laporan Benchmark {config.engine_label}

## Status

Belum ada file hasil benchmark untuk **{config.engine_label}**.

File yang dicari:

```text
{config.result_path.as_posix()}
```

## Cara Menghasilkan Report Ini

{config.missing_guidance}

Setelah file hasil tersedia, jalankan:

```bash
uv run python src/analyze_results.py
```

## Catatan

Report ini dibuat dari hasil benchmark DuckDB lokal. Jika ingin membandingkan engine
lain, buat report terpisah agar overhead dan metrik tiap engine tidak tercampur.
"""


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def process_report(config: ReportConfig, required: bool = False) -> None:
    if not config.result_path.exists():
        if required:
            raise FileNotFoundError(
                f"File benchmark result belum ditemukan: {config.result_path}. "
                f"{config.missing_guidance}"
            )
        write_text(config.report_path, build_missing_report(config))
        console.print(f"Report placeholder dibuat: {config.report_path}")
        return

    raw_df = pd.read_csv(config.result_path)
    summary = build_latency_summary(raw_df)
    storage = build_storage_summary(raw_df)
    winners = build_query_winners(summary)

    config.summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary.to_csv(config.summary_path, index=False)
    console.print(f"Summary disimpan ke {config.summary_path}")

    create_latency_chart(summary, config)
    console.print(f"Chart disimpan ke {config.chart_path}")

    report = build_report(
        raw_df=raw_df,
        summary=summary,
        storage=storage,
        winners=winners,
        config=config,
    )
    write_text(config.report_path, report)
    console.print(f"Laporan disimpan ke {config.report_path}")

    dashboard = build_dashboard(
        raw_df=raw_df,
        summary=summary,
        storage=storage,
        winners=winners,
        config=config,
    )
    write_text(config.dashboard_path, dashboard)
    console.print(f"Dashboard HTML disimpan ke {config.dashboard_path}")


def main() -> None:
    process_report(LOCAL_REPORT, required=True)


if __name__ == "__main__":
    main()
