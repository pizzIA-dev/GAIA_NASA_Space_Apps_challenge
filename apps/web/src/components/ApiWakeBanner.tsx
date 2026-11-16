"use client";
// Alojamiento gratuito: la API se duerme tras 15 min sin visitas y tarda 1–2 min en despertar. Si /health no responde
// en 4 s, se avisa con una franja; las consultas se reintentan solas (providers.tsx) y la franja desaparece al responder.
import { useEffect, useState } from "react";
import { API_URL } from "@/lib/api";
import { useT } from "@/lib/i18n";

export function ApiWakeBanner() {
  const t = useT();
  const [state, setState] = useState<"ok" | "waking" | "down">("ok");
  useEffect(() => {
    let alive = true, answered = false;
    const started = Date.now();
    // Solo se avisa si /health tarda más de 4 s; si ya respondió, el temporizador no debe mostrar nada.
    const slow = setTimeout(() => { if (alive && !answered) setState("waking"); }, 4000);
    const ping = async () => {
      while (alive) {
        try {
          const r = await fetch(`${API_URL}/health`, { cache: "no-store" });
          if (r.ok && (r.headers.get("content-type") ?? "").includes("json")) {
            answered = true;
            clearTimeout(slow);
            if (alive) setState("ok");
            return;
          }
        } catch { /* sigue despertando */ }
        if (Date.now() - started > 180_000) { if (alive) setState("down"); return; }
        await new Promise((res) => setTimeout(res, 5000));
        if (alive) setState("waking");
      }
    };
    void ping();
    return () => { alive = false; clearTimeout(slow); };
  }, []);
  if (state === "ok") return null;
  return (
    <div className="wake-banner" role="status">
      {state === "waking"
        ? t("Despertando el servidor gratuito de GaIA: la primera visita tras un rato sin uso tarda 1–2 minutos. Los datos aparecerán solos.",
          "Waking up GaIA's free server: the first visit after a while without use takes 1–2 minutes. The data will appear on their own.")
        : t("No hay conexión con el servidor de GaIA. Vuelve a intentarlo en unos minutos.",
          "There is no connection to the GaIA server. Please try again in a few minutes.")}
    </div>
  );
}
