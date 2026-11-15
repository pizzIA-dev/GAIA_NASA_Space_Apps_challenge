import Link from "next/link";

/** Sección aún no construida: lo dice claramente y lleva a lo que sí funciona (sin maquetas falsas). */
export function Upcoming({ title, description }: { title: string; description: string }) {
  return (
    <main className="page prose" id="contenido">
      <h1>{title}</h1>
      <p className="lead">{description}</p>
      <p>Esta sección todavía no está disponible. Mientras tanto puedes investigar cualquier territorio en <Link href="/explorar">Explorar</Link>.</p>
    </main>
  );
}
