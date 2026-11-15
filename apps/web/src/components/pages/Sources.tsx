"use client";
// Catálogo de fuentes (plan §4.1 «Fuentes» y §5.4 SourceCard): todo viene de la API, nada escrito a mano aquí.
import { useQuery } from "@tanstack/react-query";
import { api, API_URL } from "@/lib/api";

interface BoundarySet { boundary_set_id: string; attribution: string; levels: string[]; countries: string }

const GRANULARITY: Record<string, string> = { month: "mensual", "3h": "cada 3 horas", "1h": "horaria", "16d": "cada 16 días", "1d": "diaria" };

export function Sources() {
  const datasets = useQuery({ queryKey: ["datasets"], queryFn: api.datasets });
  const variables = useQuery({ queryKey: ["variables"], queryFn: api.variables });
  const bsets = useQuery({
    queryKey: ["boundary-sets"],
    queryFn: async () => (await fetch(`${API_URL}/geographies/boundary-sets`).then((r) => r.json())) as { items: BoundarySet[] },
  });

  return (
    <main className="page" id="contenido">
      <h1>Fuentes de datos</h1>
      <p className="lead">
        Cada resultado de la plataforma indica de qué producto viene, su versión, su resolución y sus límites. Los datos
        ambientales son productos NASA procesados en Google Earth Engine; las fronteras provienen de fuentes cartográficas
        documentadas. Coberturas, cuotas y tiempos de respuesta están sujetos al servicio.
      </p>

      <h2>Datos NASA</h2>
      {datasets.isPending && <p className="state">Cargando catálogo…</p>}
      {datasets.error && <p className="state">No se pudo cargar el catálogo desde la API.</p>}
      <div className="cards">
        {datasets.data?.map((d) => (
          <article key={d.dataset_id} className="panel source">
            <h3>{d.title}</h3>
            <p className="muted">{d.provider} · versión {d.version}</p>
            <dl>
              <div><dt>Colección</dt><dd><code>{d.ee_collection_id}</code></dd></div>
              <div><dt>Resolución</dt><dd>{d.nominal_resolution}</dd></div>
              <div><dt>Frecuencia nativa</dt><dd>{GRANULARITY[d.native_granularity] ?? d.native_granularity}</dd></div>
              <div><dt>Disponible desde</dt><dd className="num">{d.temporal_coverage_start}</dd></div>
              <div><dt>Variables</dt><dd>{variables.data?.filter((v) => v.dataset_id === d.dataset_id)
                .map((v) => `${v.physical_quantity} (${v.unit_display})`).join("; ")}</dd></div>
              <div><dt>Licencia</dt><dd>{d.license}</dd></div>
            </dl>
            {d.notes.length > 0 && <ul className="warn">{d.notes.map((n) => <li key={n}>{n}</li>)}</ul>}
            <p><a href={d.citation_url} target="_blank" rel="noopener noreferrer">Ficha en el catálogo de Earth Engine</a></p>
          </article>
        ))}
      </div>

      <h2>Fronteras administrativas</h2>
      <div className="cards">
        {bsets.data?.items.map((b) => (
          <article key={b.boundary_set_id} className="panel source">
            <h3><code>{b.boundary_set_id}</code></h3>
            <dl>
              <div><dt>Cobertura</dt><dd>{b.countries === "global" ? "Mundial" : b.countries === "PER" ? "Perú (fuente oficial, por defecto para el país)" : b.countries}</dd></div>
              <div><dt>Niveles</dt><dd>{b.levels.join(", ")}</dd></div>
              <div><dt>Atribución</dt><dd>{b.attribution}</dd></div>
            </dl>
          </article>
        ))}
      </div>
      <p className="hint">Nunca se sustituye en silencio una fuente oficial por una global: cada territorio lleva su conjunto de fronteras y versión.</p>
    </main>
  );
}
