"""La misma investigación con el SDK oficial (plan §12A.4).

    pip install -e packages/python-sdk[pandas]       # desde la raíz del repo
    export EARTH_TREND_API_URL=http://localhost:8000/api/v1

No requiere Earth Engine en el cliente: el backend gestiona esa integración.
"""

from earth_trend_client import EarthTrendClient

with EarthTrendClient() as client:
    print([v["variable_id"] for v in client.catalog.search("temperatura")])

    region = client.geographies.search("trujillo", country="PER", level="ADM2")[0]
    spec = {
        "data": {"dataset_id": "nasa-gpm-imerg-monthly-v07", "variable_id": "precipitation_mm_month"},
        "geography": {"geo_ids": [region["geo_id"]]},
        "time": {"start": "2003-01-01", "end_exclusive": "2025-01-01", "granularity": "month"},
        "transforms": {"seasonality": "monthly_anomaly"},
        "statistics": {"estimator": "theil_sen", "interval_method": "moving_block_bootstrap",
                       "significance_test": "mann_kendall", "resamples": 1000, "block_length": 12, "seed": 2026},
    }
    run = client.analyses.run(spec, idempotency_key="trujillo-imerg-anomalia-2003-2024")
    stats = client.analyses.statistics(run.id)
    series = client.analyses.series_dataframe(run.id)

    print(run.id, stats.status)
    print(stats.estimate, stats.estimate_unit, stats.confidence_interval, stats.hypothesis_test, sep=" · ")
    print(series.describe())
    print(client.analyses.manifest(run.id)["source_versions"])
