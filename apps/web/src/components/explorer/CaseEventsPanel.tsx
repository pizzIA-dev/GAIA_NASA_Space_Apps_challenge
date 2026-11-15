"use client";
// Tabla de eventos SINPAD del caso Trujillo (plan §8.1, §9): forma = peligro; color = contexto ENFEN; nunca causa inferida.
import Link from "next/link";
import { fmt } from "@/lib/format";
import type { CaseEnfen, CaseEvents } from "@/lib/types";

const CLASS_LABEL = {
  atribucion_verificada: "Atribución causal verificada",
  coincidencia_el_nino: "Durante El Niño Costero (coincidencia, no causa)",
  fuera_de_el_nino: "Fuera de El Niño Costero",
} as const;

export function CaseEventsPanel({ data, enfen, place }: { data: CaseEvents; enfen?: CaseEnfen; place: string }) {
  const by = (k: keyof typeof CLASS_LABEL) => data.items.filter((e) => e.display_class === k).length;
  return (
    <section className="panel case-events" aria-label="Eventos SINPAD y episodios ENFEN">
      <h2>Contexto local: emergencias registradas en {place}</h2>
      <p className="hint">
        {data.count} registros SINPAD de huaico o inundación en el periodo. {by("coincidencia_el_nino")} ocurrieron durante un
        episodio El Niño Costero, {by("fuera_de_el_nino")} fuera de él y {by("atribucion_verificada")} tienen atribución causal
        verificada. Coincidir en el tiempo no demuestra que El Niño los causara.
      </p>
      <div className="event-legend" aria-label="Leyenda de eventos">
        <span><svg width="14" height="14" aria-hidden="true"><polygon points="7,1 13,13 1,13" className="ev-coincidence" /></svg> huaico</span>
        <span><svg width="14" height="14" aria-hidden="true"><circle cx="7" cy="7" r="6" className="ev-coincidence" /></svg> inundación</span>
        <span><span className="swatch ev-coincidence" /> {CLASS_LABEL.coincidencia_el_nino}</span>
        <span><span className="swatch ev-outside" /> {CLASS_LABEL.fuera_de_el_nino}</span>
        <span><span className="swatch ev-verified" /> {CLASS_LABEL.atribucion_verificada} (0 casos)</span>
        <span><span className="swatch band-nino" /> episodio El Niño Costero</span>
        <span><span className="swatch band-nina" /> episodio La Niña Costera</span>
      </div>
      {data.count > 0 && (
        <table className="table events-table">
          <caption className="sr-only">Registros SINPAD de huaicos e inundaciones</caption>
          <thead>
            <tr><th scope="col">Fecha</th><th scope="col">Distrito</th><th scope="col">Peligro</th><th scope="col">Contexto ENFEN</th>
              <th scope="col">Afectados</th><th scope="col">Código SINPAD</th></tr>
          </thead>
          <tbody>
            {data.items.map((e) => (
              <tr key={e.sinpad_code}>
                <td className="num">{e.date}</td>
                <td>{e.district}{e.geo_id == null && <small className="muted"> · sin polígono IGN</small>}</td>
                <td>{e.hazard === "huaico" ? "Huaico" : "Inundación"}</td>
                <td><span className={`swatch ${e.display_class === "coincidencia_el_nino" ? "ev-coincidence" : e.display_class === "atribucion_verificada" ? "ev-verified" : "ev-outside"}`} />{" "}
                  {e.enfen.episode_id ?? "fuera de episodio"}{e.enfen.icen_month != null && <small className="muted"> · ICEN {fmt(e.enfen.icen_month, 2)}</small>}</td>
                <td className="num">{e.damages.afectados != null ? fmt(e.damages.afectados, 0) : "sin dato"}</td>
                <td className="num">{e.sinpad_code}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <p className="hint">
        Fuentes: INDECI/SINPAD (datos abiertos, ODC-BY) y serie oficial ICEN (IGP/ENFEN). {data.note}
        {enfen?.rule.status === "umbral_citado_pendiente_de_verificacion" &&
          ` Episodios derivados con ICEN > +${enfen.rule.warm_threshold_gt} durante ≥ ${enfen.rule.min_consecutive_months} meses; umbral pendiente de verificación directa con la Nota Técnica ENFEN 01-2024.`}
        {" "}<Link href="/metodos">Cómo leer esto</Link>.
      </p>
    </section>
  );
}
