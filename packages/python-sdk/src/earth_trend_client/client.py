"""Cliente HTTP de Earth Trend Studio. No requiere Earth Engine: el backend gestiona esa integración."""

from __future__ import annotations

import os
import time
from typing import Any

import httpx

from earth_trend_client.models import Run, Statistics

DEFAULT_TIMEOUT = 300.0  # extracciones nuevas (p. ej. MERRA-2) pueden tardar minutos


class EarthTrendAPIError(Exception):
    """Error tipado de la API (application/problem+json)."""

    def __init__(self, status: int, code: str, detail: str, payload: dict | None = None):
        super().__init__(f"[{status} {code}] {detail}")
        self.status, self.code, self.detail, self.payload = status, code, detail, payload or {}


class _Resource:
    def __init__(self, client: EarthTrendClient):
        self._c = client


class Catalog(_Resource):
    def datasets(self) -> list[dict]:
        return self._c._get("catalog/datasets")

    def variables(self, dataset_id: str | None = None) -> list[dict]:
        return self._c._get("catalog/variables", params={"dataset_id": dataset_id} if dataset_id else None)

    def capabilities(self) -> dict:
        return self._c._get("catalog/capabilities")

    def search(self, query: str) -> list[dict]:
        """Busca variables por texto en id, banda, magnitud física o título del dataset (sin distinguir mayúsculas)."""
        q = query.lower()
        titles = {d["dataset_id"]: d["title"] for d in self.datasets()}
        return [
            v for v in self.variables()
            if any(q in str(x).lower() for x in (v["variable_id"], v["band"], v["physical_quantity"],
                                                  v["dataset_id"], titles.get(v["dataset_id"], "")))
        ]


class Geographies(_Resource):
    def search(self, query: str, country: str | None = None, level: str | None = None,
               boundary_set_id: str | None = None, limit: int = 20) -> list[dict]:
        params = {"q": query, "country": country, "level": level, "boundary_set_id": boundary_set_id, "limit": limit}
        return self._c._get("geographies/search", params={k: v for k, v in params.items() if v is not None})["items"]

    def get(self, geo_id: str, geometry: bool = False) -> dict:
        return self._c._get(f"geographies/{geo_id}", params={"geometry": "simplified" if geometry else "none"})

    def countries(self) -> list[dict]:
        return self._c._get("geographies/countries")["items"]


class Analyses(_Resource):
    def submit(self, spec: dict, idempotency_key: str | None = None) -> Run:
        headers = {"Idempotency-Key": idempotency_key} if idempotency_key else None
        return Run.from_api(self._c._post("analyses", json=spec, headers=headers))

    def compare(self, specs: list[dict], multiple_testing: str = "BH_FDR", family_id: str | None = None) -> dict:
        """Familia de análisis (territorios/variables) con q-valores BH-FDR; cada ítem tiene su propio estado."""
        body = {"specs": specs, "multiple_testing": multiple_testing}
        if family_id:
            body["family_id"] = family_id
        return self._c._post("analyses/compare", json=body)

    def atlas(self, parent_geo_id: str, dataset_id: str, variable_id: str, start_year: int = 2003,
              end_year: int = 2024, method: str = "sen") -> dict:
        """Pendiente anual de todas las subunidades de un territorio (misma spec que un análisis individual),
        con q-valores BH-FDR sobre las unidades. Cada unidad tiene su propio estado."""
        return self._c._post("atlas", json={"parent_geo_id": parent_geo_id, "dataset_id": dataset_id,
                                            "variable_id": variable_id, "start_year": start_year,
                                            "end_year": end_year, "method": method})

    def estimate_cost(self, spec: dict) -> dict:
        """Complejidad estimada y si tu token/identidad puede ejecutarlo (no consume cupo ni toca Earth Engine)."""
        return self._c._post("analyses/estimate-cost", json=spec)

    def get(self, run_id: str) -> Run:
        d = self._c._get(f"analyses/{run_id}")
        return Run.from_api(d)

    def wait(self, run_id: str, poll_interval: float = 3.0, timeout: float = 1800.0) -> Run:
        deadline = time.monotonic() + timeout
        while True:
            run = self.get(run_id)
            if run.done:
                if run.status != "succeeded":
                    raise EarthTrendAPIError(500, f"run_{run.status}", f"El análisis {run_id} terminó en {run.status}",
                                             run.raw)
                return run
            if time.monotonic() > deadline:
                raise TimeoutError(f"El análisis {run_id} sigue en curso; consúltalo luego por su ID")
            time.sleep(poll_interval)

    def run(self, spec: dict, idempotency_key: str | None = None, timeout: float = 1800.0) -> Run:
        """Atajo: submit + wait."""
        run = self.submit(spec, idempotency_key=idempotency_key)
        return run if run.done and run.status == "succeeded" else self.wait(run.id, timeout=timeout)

    def statistics(self, run_id: str) -> Statistics:
        return Statistics.from_api(self._c._get(f"analyses/{run_id}/statistics"))

    def series(self, run_id: str) -> dict:
        return self._c._get(f"analyses/{run_id}/series")

    def series_dataframe(self, run_id: str):
        """Serie como pandas.DataFrame (time_start_utc, value). Los faltantes quedan como NaN, nunca 0."""
        try:
            import pandas as pd
        except ImportError as exc:  # pragma: no cover
            raise ImportError("Instala el extra: pip install 'earth-trend-client[pandas]'") from exc
        s = self.series(run_id)
        df = pd.DataFrame(s["series"])
        df["time_start_utc"] = pd.to_datetime(df["time_start_utc"])
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df.attrs.update({"run_id": run_id, "unit": s.get("unit")})
        return df

    def seasonal(self, run_id: str) -> dict:
        """Matriz año × mes, climatología mensual (media, mediana, P25–P75) y meses extremos del run."""
        return self._c._get(f"analyses/{run_id}/seasonal")

    def manifest(self, run_id: str) -> dict:
        return self._c._get(f"analyses/{run_id}/manifest")

    def plot(self, run_id: str, kind: str = "time_series", ax=None):
        """Gráfico matplotlib de la serie con la recta de tendencia del propio run (no recalcula estadística)."""
        if kind != "time_series":
            raise ValueError("Por ahora solo kind='time_series'")
        import matplotlib.pyplot as plt

        df = self.series_dataframe(run_id)
        st = self.statistics(run_id)
        ax = ax or plt.subplots(figsize=(10, 4))[1]
        ax.plot(df["time_start_utc"], df["value"], lw=1, color="#1f3b4d", label="serie")
        intercept = st.raw.get("intercept")
        if st.is_inferable and intercept is not None:
            factor = 10.0 if st.estimate_unit.endswith("/decade") else 1.0
            years = df["time_start_utc"].dt.year + (df["time_start_utc"].dt.dayofyear - 1) / 365.2425
            ax.plot(df["time_start_utc"], intercept + st.estimate / factor * years, color="#c0392b", lw=1.5,
                    label=f"{st.estimator}: {st.estimate:.3g} {st.estimate_unit}")
        ax.set_ylabel(df.attrs.get("unit") or "")
        ax.set_title(f"{run_id} · {st.confidence_interval} · {st.hypothesis_test}", fontsize=9)
        ax.legend(frameon=False, fontsize=8)
        return ax


class Cases(_Resource):
    """Casos con capas nacionales opcionales (p. ej. «trujillo-el-nino»). Coincidencia temporal ≠ causalidad."""

    def list(self) -> list[dict]:
        return self._c._get("cases")["items"]

    def get(self, case_id: str) -> dict:
        return self._c._get(f"cases/{case_id}")

    def events(self, case_id: str, geo_id: str | None = None, year_from: int | None = None,
               year_to: int | None = None, focal: bool = True) -> list[dict]:
        params = {"geo_id": geo_id, "year_from": year_from, "year_to": year_to, "focal": str(focal).lower()}
        return self._c._get(f"cases/{case_id}/events", params={k: v for k, v in params.items() if v is not None})["items"]

    def enfen(self, case_id: str, year_from: int | None = None, year_to: int | None = None) -> dict:
        params = {"year_from": year_from, "year_to": year_to}
        return self._c._get(f"cases/{case_id}/enfen", params={k: v for k, v in params.items() if v is not None})


class EarthTrendClient:
    """Cliente de la API v1.

    >>> client = EarthTrendClient()  # usa EARTH_TREND_API_URL y EARTH_TREND_API_TOKEN
    """

    def __init__(self, base_url: str | None = None, token: str | None = None, timeout: float = DEFAULT_TIMEOUT,
                 http_client: httpx.Client | None = None, max_retries: int = 3):
        self.base_url = (base_url or os.environ.get("EARTH_TREND_API_URL") or "http://localhost:8000/api/v1").rstrip("/")
        token = token if token is not None else os.environ.get("EARTH_TREND_API_TOKEN")
        self._headers = {"Accept": "application/json", "User-Agent": "earth-trend-client/0.1.0"}
        if token:
            self._headers["Authorization"] = f"Bearer {token}"
        self._http = http_client or httpx.Client(timeout=timeout)
        self._max_retries = max_retries
        self.catalog = Catalog(self)
        self.geographies = Geographies(self)
        self.analyses = Analyses(self)
        self.cases = Cases(self)

    def health(self) -> dict:
        return self._get("health")

    def me(self) -> dict:
        """Identidad, scopes y cupos vigentes del token (o del acceso anónimo)."""
        return self._get("me")

    # ------------------------------------------------------------------ HTTP

    def _request(self, method: str, path: str, **kw) -> Any:
        headers = {**self._headers, **(kw.pop("headers", None) or {})}
        url = f"{self.base_url}/{path.lstrip('/')}"
        for attempt in range(self._max_retries + 1):
            r = self._http.request(method, url, headers=headers, **kw)
            if r.status_code in (429, 503) and attempt < self._max_retries:
                retry_after = r.headers.get("Retry-After")
                time.sleep(float(retry_after) if retry_after and retry_after.isdigit() else 2 ** attempt)
                continue
            break
        if r.status_code >= 400:
            try:
                p = r.json()
            except ValueError:
                p = {}
            raise EarthTrendAPIError(r.status_code, p.get("title") or p.get("code") or "http_error",
                                     p.get("detail") if isinstance(p.get("detail"), str) else str(p.get("detail", r.text)),
                                     p)
        return r.json()

    def _get(self, path: str, params: dict | None = None) -> Any:
        return self._request("GET", path, params=params)

    def _post(self, path: str, json: dict, headers: dict | None = None) -> Any:
        return self._request("POST", path, json=json, headers=headers)

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> EarthTrendClient:  # noqa: PYI034 — typing.Self exige 3.11; SDK soporta 3.10
        return self

    def __exit__(self, *exc) -> None:
        self.close()
