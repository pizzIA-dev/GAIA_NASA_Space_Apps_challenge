"use client";
// Métodos (plan §7 y Anexo B): explicación honesta de cada procedimiento. La matriz de compatibilidad viene de la API.
import { useQuery } from "@tanstack/react-query";
import { API_URL } from "@/lib/api";

interface Capabilities { estimators: Record<string, { interval_methods: string[]; significance_tests: string[] }>; confidence_levels: number[] }

const NAMES: Record<string, string> = {
  ols: "Regresión lineal (OLS)", theil_sen: "Pendiente de Theil–Sen",
  ols_classic: "IC clásico de OLS", hac_newey_west: "IC robusto HAC (Newey–West)", theil_sen_analytic: "IC analítico de Theil–Sen",
  moving_block_bootstrap: "Bootstrap por bloques móviles", ols_t: "Prueba t clásica", ols_hac_t: "Prueba t con errores HAC",
  mann_kendall: "Mann–Kendall", none: "Sin prueba",
};

const GLOSSARY: [string, string][] = [
  ["Tendencia", "Dirección y magnitud de un cambio sistemático en el tiempo durante el periodo elegido."],
  ["Anomalía", "Diferencia respecto al promedio del mismo mes en el periodo de referencia (enero con eneros, etc.)."],
  ["Pendiente de Theil–Sen", "Mediana de las pendientes entre todos los pares de años: un cambio típico, robusto a valores extremos."],
  ["OLS con HAC", "Recta de mínimos cuadrados con errores estándar que toleran dependencia entre periodos cercanos."],
  ["Mann–Kendall", "Prueba de tendencia monotónica. Sin corrección, es optimista si la serie tiene autocorrelación; la plataforma lo advierte."],
  ["Intervalo de confianza", "Rango producido por un procedimiento con cobertura nominal bajo sus supuestos. No es la probabilidad de que el valor real esté dentro."],
  ["p-valor", "Compatibilidad de los datos con «no hay tendencia» bajo el modelo. No es la probabilidad de que una hipótesis sea verdadera."],
  ["No concluyente", "Los datos no permiten distinguir el cambio de cero con ese método. No demuestra que no haya cambio."],
  ["Datos faltantes", "No hubo dato utilizable. Nunca se convierten en cero ni se interpolan en silencio."],
  ["Resolución espacial", "Tamaño de la celda del producto. Un distrito menor que una celda recibe el valor de una celda que lo excede."],
];

export function Methods() {
  const caps = useQuery({
    queryKey: ["capabilities"],
    queryFn: async () => (await fetch(`${API_URL}/catalog/capabilities`).then((r) => r.json())) as Capabilities,
  });
  return (
    <main className="page prose" id="contenido">
      <h1>Métodos</h1>
      <p className="lead">
        Todos los números de la web, la API y el SDK de Python salen del mismo motor estadístico. La interfaz no calcula nada
        por su cuenta: envía una especificación del análisis y muestra lo que el motor devuelve, con su identificador de ejecución.
      </p>

      <h2>Cómo se obtiene una tendencia</h2>
      <ol>
        <li>Earth Engine filtra el producto NASA por fechas y calidad, y promedia los píxeles del territorio ponderando por área.</li>
        <li>Se agregan los meses en años (total o media según la variable). Un año incompleto queda vacío, no se rellena.</li>
        <li>Opcionalmente se resta la climatología mensual para estudiar anomalías sin el ciclo estacional.</li>
        <li>Se estima la pendiente con el método elegido, su intervalo de confianza del mismo procedimiento y una prueba compatible.</li>
        <li>Se revisan la cobertura, la autocorrelación y el soporte espacial; cada limitación aparece como advertencia.</li>
      </ol>

      <h2>Combinaciones permitidas</h2>
      <p>No se mezclan procedimientos incompatibles (por ejemplo, la pendiente de Theil–Sen con el intervalo de OLS). La API rechaza esas combinaciones.</p>
      {caps.data && (
        <table className="table">
          <thead><tr><th scope="col">Estimador</th><th scope="col">Intervalos de confianza</th><th scope="col">Pruebas</th></tr></thead>
          <tbody>
            {Object.entries(caps.data.estimators).map(([k, v]) => (
              <tr key={k}>
                <th scope="row">{NAMES[k] ?? k}</th>
                <td>{v.interval_methods.map((m) => NAMES[m] ?? m).join(", ")}</td>
                <td>{v.significance_tests.map((m) => NAMES[m] ?? m).join(", ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <h2>Cómo leer el veredicto</h2>
      <p>
        «Evidencia de aumento» o «de disminución» exige que la prueba dé p &lt; 0,05 y que el intervalo excluya el cero. Cuando se
        comparan varios territorios o unidades a la vez (Estudio, mapa por distritos), se usa el q-valor corregido por pruebas
        múltiples (Benjamini–Hochberg) en lugar de p. En cualquier otro caso el resultado es «no concluyente». En el mapa, las unidades sin evidencia se rayan en lugar de ocultarse.
        Una tendencia describe el periodo elegido: no es un pronóstico ni una alerta.
      </p>

      <h2>Glosario</h2>
      <dl className="glossary">
        {GLOSSARY.map(([t, d]) => <div key={t}><dt>{t}</dt><dd>{d}</dd></div>)}
      </dl>
    </main>
  );
}
