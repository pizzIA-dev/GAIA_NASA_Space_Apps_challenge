// Tipos del contrato API v1 que consume la web (espejo de la respuesta del backend; sin recalcular nada).

export interface Statistics {
  status: "ok" | "exploratory" | "insufficient_evidence";
  estimator: "ols" | "theil_sen";
  estimate: number | null;
  estimate_unit: string;
  ci_lower: number | null;
  ci_upper: number | null;
  ci_method: string;
  confidence_level: number;
  p_value: number | null;
  q_value: number | null;
  test_method: string;
  n_observations: number;
  n_missing: number;
  coverage_fraction: number;
  autocorrelation_lag1: number | null;
  autocorrelation_adjustment: string;
  intercept: number | null;
  warnings: string[];
  algorithm_version: string;
}

export interface SeriesPoint { time_start_utc: string; value: number | null }

export interface SourceVersion {
  dataset_id: string; ee_collection_id: string; version: string; band: string; native_scale_m: number;
}

export interface CostEstimate {
  tier: "cached" | "light" | "heavy" | "too_large";
  source_images: number; estimated_seconds: number; reason: string; roi_area_km2: number | null;
}

export interface Run {
  run_id: string;
  status: string;
  cache_hit: boolean;
  analysis_spec_hash: string;
  statistics: Statistics;
  series: SeriesPoint[];
  source_versions: SourceVersion[];
  geography: { geo_id?: string; name?: string; area_km2?: number | null; attribution?: string; kind: string };
  cost?: CostEstimate;
}

export interface Geography {
  geo_id: string; name: string; admin_level: string; iso3: string; parent_id: string | null;
  area_km2: number | null; boundary_set_id: string; path?: string[]; ubigeo?: string;
}

export interface Variable {
  variable_id: string; dataset_id: string; band: string; physical_quantity: string;
  unit_native: string; unit_display: string; temporal_aggregations: string[]; status: string;
}

export interface Dataset {
  dataset_id: string; ee_collection_id: string; title: string; provider: string; version: string;
  nominal_resolution: string; native_scale_m: number; temporal_coverage_start: string; native_granularity: string;
  citation_url: string; license: string; notes: string[];
}

export interface FeatureCollection {
  type: "FeatureCollection";
  attribution: string;
  features: {
    type: "Feature"; id: string;
    properties: { geo_id: string; name: string; admin_level: string; area_km2: number | null; role: "self" | "child" };
    geometry: GeoJSON.Geometry;
  }[];
}

export interface Problem { status: number; title: string; detail: string; cost?: CostEstimate }
