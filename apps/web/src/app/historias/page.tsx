import type { Metadata } from "next";
import Link from "next/link";
import story from "@/stories/trujillo-el-nino.json";

export const metadata: Metadata = { title: "Casos de estudio · GaIA" };

export default function HistoriasPage() {
  return (
    <main className="page prose" id="contenido">
      <h1>Casos de estudio</h1>
      <p className="lead">
        Investigaciones guiadas y reproducibles construidas con la misma herramienta que Explorar. Son ejemplos de método, no el
        límite de lo que se puede estudiar.
      </p>
      <article className="panel story-card">
        <h2><Link href={`/historias/${story.slug}`}>{story.title}</Link></h2>
        <p>{story.subtitle}</p>
        <p className="small muted">Seis escenas · datos NASA, registros oficiales SINPAD e índice ICEN · {story.period.start}–{story.period.end}</p>
      </article>
    </main>
  );
}
