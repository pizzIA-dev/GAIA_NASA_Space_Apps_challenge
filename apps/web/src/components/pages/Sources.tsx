"use client";
import { simpleName } from "@/lib/variables";
// Catálogo de fuentes (plan §4.1 «Fuentes» y §5.4 SourceCard): todo viene de la API, nada escrito a mano aquí.
import { useQuery } from "@tanstack/react-query";
import { api, API_URL } from "@/lib/api";
import { apiText, useT } from "@/lib/i18n";

interface BoundarySet { boundary_set_id: string; attribution: string; levels: string[]; countries: string }

const GRANULARITY: Record<string, [string, string]> = {
  month: ["mensual", "monthly"], "3h": ["cada 3 horas", "every 3 hours"], "1h": ["horaria", "hourly"],
  "16d": ["cada 16 días", "every 16 days"], "1d": ["diaria", "daily"],
};

export function Sources() {
  const t = useT();
  const datasets = useQuery({ queryKey: ["datasets"], queryFn: api.datasets });
  const variables = useQuery({ queryKey: ["variables"], queryFn: api.variables });
  const bsets = useQuery({
    queryKey: ["boundary-sets"],
    queryFn: async () => (await fetch(`${API_URL}/geographies/boundary-sets`).then((r) => r.json())) as { items: BoundarySet[] },
  });

  return (
    <main className="page" id="contenido">
      <h1>{t("Fuentes de datos", "Data sources")}</h1>
      <p className="lead">
        {t("Cada resultado de la plataforma indica de qué producto viene, su versión, su resolución y sus límites. Los datos ambientales son productos NASA procesados en Google Earth Engine; las fronteras provienen de fuentes cartográficas documentadas. Coberturas, cuotas y tiempos de respuesta están sujetos al servicio.",
          "Every result on the platform states which product it comes from, its version, its resolution and its limitations. The environmental data are NASA products processed in Google Earth Engine; boundaries come from documented cartographic sources. Coverage, quotas and response times depend on the service.")}
      </p>

      <h2>{t("Datos NASA", "NASA data")}</h2>
      {datasets.isPending && <p className="state">{t("Cargando catálogo…", "Loading catalogue…")}</p>}
      {datasets.error && <p className="state">{t("No se pudo cargar el catálogo desde la API.", "The catalogue could not be loaded from the API.")}</p>}
      <div className="cards">
        {datasets.data?.map((d) => {
          const g = GRANULARITY[d.native_granularity];
          return (
            <article key={d.dataset_id} className="panel source">
              <h3>{apiText(d.title)}</h3>
              <p className="muted">{d.provider} · {t("versión", "version")} {d.version}</p>
              <dl>
                <div><dt>{t("Colección", "Collection")}</dt><dd><code>{d.ee_collection_id}</code></dd></div>
                <div><dt>{t("Resolución", "Resolution")}</dt><dd>{apiText(d.nominal_resolution)}</dd></div>
                <div><dt>{t("Frecuencia nativa", "Native frequency")}</dt><dd>{g ? t(g[0], g[1]) : d.native_granularity}</dd></div>
                <div><dt>{t("Disponible desde", "Available since")}</dt><dd className="num">{d.temporal_coverage_start}</dd></div>
                <div><dt>{t("Variables", "Variables")}</dt><dd>{variables.data?.filter((v) => v.dataset_id === d.dataset_id)
                  .map((v) => `${simpleName(v.dataset_id, v.variable_id, v.physical_quantity)} = ${apiText(v.physical_quantity)} (${apiText(v.unit_display)}; ${t("banda", "band")} ${v.band})`).join("; ")}</dd></div>
                <div><dt>{t("Licencia", "Licence")}</dt><dd>{apiText(d.license)}</dd></div>
              </dl>
              {d.notes.length > 0 && <ul className="warn">{d.notes.map((n) => <li key={n}>{apiText(n)}</li>)}</ul>}
              <p><a href={d.citation_url} target="_blank" rel="noopener noreferrer">{t("Ficha en el catálogo de Earth Engine", "Entry in the Earth Engine catalogue")}</a></p>
            </article>
          );
        })}
      </div>

      <h2>{t("Fronteras administrativas", "Administrative boundaries")}</h2>
      <div className="cards">
        {bsets.data?.items.map((b) => (
          <article key={b.boundary_set_id} className="panel source">
            <h3><code>{b.boundary_set_id}</code></h3>
            <dl>
              <div><dt>{t("Cobertura", "Coverage")}</dt><dd>{b.countries === "global" ? t("Mundial", "Worldwide")
                : b.countries === "PER" ? t("Perú (fuente oficial, por defecto para el país)", "Peru (official source, default for the country)") : b.countries}</dd></div>
              <div><dt>{t("Niveles", "Levels")}</dt><dd>{b.levels.join(", ")}</dd></div>
              <div><dt>{t("Atribución", "Attribution")}</dt><dd>{apiText(b.attribution)}</dd></div>
            </dl>
          </article>
        ))}
      </div>
      <p className="hint">{t("Nunca se sustituye en silencio una fuente oficial por una global: cada territorio lleva su conjunto de fronteras y versión.",
        "An official source is never silently replaced by a global one: every territory carries its boundary set and version.")}</p>
    </main>
  );
}
