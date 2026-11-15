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
  request: object;
  statistics: Statistics;
  series: SeriesPoint[];
  source_versions: SourceVersion[];
  geography: { geo_id?: string; name?: string; area_km2?: number | null; attribution?: string; boundary_set_id?: string; kind: string };
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

export interface CompareItem {
  index: number; geo_id: string; status: "succeeded" | "failed";
  run_id?: string; statistics?: Statistics; series?: SeriesPoint[];
  geography?: Run["geography"]; source_versions?: SourceVersion[]; cache_hit?: boolean;
  error?: { status: number; code: string; detail: string };
}

export interface CompareResult { family_id: string | null; multiple_testing: string; family_size: number; items: CompareItem[]; note: string }

export interface ClimMonth {
  month: number; label: string; n_valid: number; n_years: number;
  mean: number | null; median: number | null; p25: number | null; p75: number | null; min: number | null; max: number | null;
}

export interface Seasonal {
  run_id: string; unit: string; years: number[]; months: string[]; matrix: (number | null)[][];
  climatology: ClimMonth[]; peak_month: string | null; low_month: string | null;
  extremes: { year: number; month: number; label: string; value: number; anomaly: number }[];
  n_months: number; n_missing: number; note: string;
}

export interface CaseEvent {
  sinpad_code: string; date: string | null; date_precision: string; date_raw: string; year: number;
  hazard: "huaico" | "inundacion" | null; hazard_sinpad: string; focal: boolean; ubigeo: string; district: string;
  geo_id: string | null; damages: Record<string, number | null>;
  enfen: { context: string; episode_id: string | null; icen_month: number | null };
  causal_attribution: { status: string; evidence_url: string | null };
  display_class: "atribucion_verificada" | "coincidencia_el_nino" | "fuera_de_el_nino"; source: string;
}

export interface EnfenEpisode {
  id: string; kind: "el_nino_costero" | "la_nina_costera"; start: string; end: string; months: number;
  peak_icen: number; ongoing: boolean; derived: boolean;
}

export interface CaseEvents { case_id: string; count: number; items: CaseEvent[]; legend: Record<string, string>; note: string }
export interface CaseEnfen { source: Record<string, unknown>; rule: { status: string; note: string; warm_threshold_gt: number; min_consecutive_months: number }; episodes: EnfenEpisode[] }

export interface AssociationLag {
  lag_months: number; status: string; effect: number | null; effect_unit?: string; p_value: number | null; q_value?: number | null;
  n_event_months: number; n_control_months: number; n_independent_episodes?: number; dominant_episode?: string; dominant_episode_share?: number;
}
export interface CaseAssociationResult {
  results: AssociationLag[]; warnings: string[]; n_units: number; resamples: number; seed: number;
  events_used: number; events_excluded_no_geometry: number; interpretation: string;
}

export interface CaseSummary {
  id: string; title: string; description: string; province_geo_id: string;
  sources: { kind: string; name: string; url: string; license?: string; reference?: string }[];
  enfen_rule: { status: string; note: string };
  counts: { province_records: number; focal_records: number; focal_2017_2025: number; focal_by_display_class: Record<string, number>; focal_by_year: Record<string, number> };
  reconciliation: { reference: string; official_2017_2025: number; official_districts_2017_2025: string[]; status: string; note: string };
  limitations: string[]; ingested_at: string;
}

export interface BacktestEventDetail {
  date: string; unit: string; label: string | null; evaluable: boolean; anticipated: boolean | null;
  lead_days: number | null; signal_mm: number | null; threshold_mm: number | null;
}
export interface BacktestPeriod {
  label: string; start: string; end: string; unit_days_evaluated: number; unit_days_excluded_incomplete: number;
  contingency: { tp: number; fp: number; fn: number; tn: number }; far: number | null; far_ci95: (number | null)[];
  alert_rate: number | null; alert_unit_days_per_year: number | null; alerts_per_unit_per_year: number | null;
  events: number; events_evaluable: number; events_anticipated: number; pod: number | null; pod_ci95: (number | null)[];
  pod_random_expected: number | null; events_detail: BacktestEventDetail[];
}
export interface BacktestRule { signal: string; window_days: number; percentile: number; horizon_days: number; threshold_basis: string; min_signal_mm: number }
export interface BacktestGridRow {
  percentile: number; window_days: number; horizon_days: number;
  test: Pick<BacktestPeriod, "pod" | "pod_ci95" | "events_evaluable" | "events_anticipated" | "far" | "alerts_per_unit_per_year" | "pod_random_expected" | "contingency">;
  calibration: Pick<BacktestPeriod, "pod" | "events_evaluable" | "events_anticipated" | "far" | "alerts_per_unit_per_year">;
}
export interface CaseBacktest {
  algorithm_version: string; unit: string; periods: { calibration: [string, string]; test: [string, string] };
  primary: { rule: BacktestRule; thresholds_mm: Record<string, number | null>; calibration_in_sample: BacktestPeriod; test_out_of_sample: BacktestPeriod };
  grid: BacktestGridRow[]; warnings: string[];
  events_excluded: { date: string; district: string; ubigeo: string; hazard: string; reason: string }[];
  source: { dataset: string; provenance: string; file: string }; unit_names: Record<string, string>;
}

export interface AtlasItem {
  geo_id: string; name: string; admin_level: string; area_km2: number | null; status: "succeeded" | "failed";
  run_id?: string; statistics?: Statistics; error?: { status: number; code: string; detail: string };
}
export interface AtlasResult {
  parent: { geo_id: string; name: string; admin_level: string };
  variable: { dataset_id: string; variable_id: string; unit: string; physical_quantity: string };
  period: [number, number]; n_units: number; n_succeeded: number; new_extractions: number;
  scale: { center: number; max_abs_estimate: number | null }; pixel_km2: number;
  cost: { tier: string; estimated_seconds: number; source_images: number }; items: AtlasItem[]; note: string;
}

export interface SlopeDifference {
  a: { geo_id: string; run_id: string; estimate: number | null; ci_lower: number | null; ci_upper: number | null; estimate_unit: string };
  b: { geo_id: string; run_id: string; estimate: number | null; ci_lower: number | null; ci_upper: number | null; estimate_unit: string };
  difference: {
    status: string; estimate: number | null; ci_lower: number | null; ci_upper: number | null; p_value: number | null;
    estimate_unit: string; ci_method: string | null; test_method: string | null; n_paired_observations: number;
    residual_correlation: number | null; warnings: string[];
  };
  interpretation: string;
}
