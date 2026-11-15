import type { CaseAssociationResult, CaseBacktest, CaseEnfen, CaseSummary, CaseEvents, CompareResult, Dataset, FeatureCollection, Geography, Problem, Run, Seasonal, Variable } from "./types";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1").replace(/\/$/, "");

export class ApiError extends Error {
  constructor(public problem: Problem) {
    super(problem.detail);
  }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_URL}/${path}`, {
      ...init,
      headers: { Accept: "application/json", ...(init?.body ? { "Content-Type": "application/json" } : {}), ...init?.headers },
    });
  } catch {
    throw new ApiError({ status: 0, title: "api_unreachable", detail: `No se pudo contactar la API en ${API_URL}. ¿Está levantado el backend?` });
  }
  if (!res.ok) {
    let p: Partial<Problem> = {};
    try { p = await res.json(); } catch { /* sin cuerpo */ }
    throw new ApiError({
      status: res.status, title: p.title ?? "http_error",
      detail: typeof p.detail === "string" ? p.detail : `Error ${res.status}`, cost: p.cost,
    });
  }
  return res.json() as Promise<T>;
}

export const api = {
  variables: () => call<Variable[]>("catalog/variables"),
  datasets: () => call<Dataset[]>("catalog/datasets"),
  searchGeographies: (q: string, country = "PER") =>
    call<{ items: Geography[]; boundary_set_id: string }>(`geographies/search?q=${encodeURIComponent(q)}&country=${country}&limit=12`),
  geography: (geoId: string) => call<Geography & { children: Geography[]; attribution: string }>(`geographies/${encodeURIComponent(geoId)}`),
  features: (geoId: string) => call<FeatureCollection>(`geographies/${encodeURIComponent(geoId)}/features`),
  caseEvents: (geoId: string, from: number, to: number) =>
    call<CaseEvents>(`cases/trujillo-el-nino/events?geo_id=${encodeURIComponent(geoId)}&year_from=${from}&year_to=${to}`),
  caseSummary: () => call<CaseSummary>("cases/trujillo-el-nino"),
  caseAssociation: (body: object) =>
    call<CaseAssociationResult>("cases/trujillo-el-nino/association", { method: "POST", body: JSON.stringify(body) }),
  caseBacktest: () => call<CaseBacktest>("cases/trujillo-el-nino/backtest"),
  caseEnfen: (from: number, to: number) => call<CaseEnfen>(`cases/trujillo-el-nino/enfen?year_from=${from}&year_to=${to}`),
  seasonal: (runId: string) => call<Seasonal>(`analyses/${encodeURIComponent(runId)}/seasonal`),
  analyze: (spec: object) => call<Run>("analyses", { method: "POST", body: JSON.stringify(spec) }),
  compare: (specs: object[], familyId?: string) =>
    call<CompareResult>("analyses/compare", { method: "POST", body: JSON.stringify({ specs, multiple_testing: "BH_FDR", family_id: familyId }) }),
};
