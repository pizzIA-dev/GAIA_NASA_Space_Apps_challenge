"use client";
// Métodos (plan §7 y Anexo B): explicación honesta de cada procedimiento. La matriz de compatibilidad viene de la API.
import { useQuery } from "@tanstack/react-query";
import { API_URL } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { methodName, type Capabilities } from "@/lib/methods";

const GLOSSARY: [string, string, string, string][] = [
  ["Tendencia", "Dirección y magnitud de un cambio sistemático en el tiempo durante el periodo elegido.",
    "Trend", "Direction and magnitude of a systematic change over time during the chosen period."],
  ["Anomalía", "Diferencia respecto al promedio del mismo mes en el periodo de referencia (enero con eneros, etc.).",
    "Anomaly", "Difference from the average of the same month in the reference period (January with Januaries, etc.)."],
  ["Pendiente de Theil–Sen", "Mediana de las pendientes entre todos los pares de años: un cambio típico, robusto a valores extremos.",
    "Theil–Sen slope", "Median of the slopes between all pairs of years: a typical change, robust to extreme values."],
  ["OLS con HAC", "Recta de mínimos cuadrados con errores estándar que toleran dependencia entre periodos cercanos.",
    "OLS with HAC", "Least-squares line with standard errors that tolerate dependence between nearby periods."],
  ["Mann–Kendall", "Prueba de tendencia monotónica. Sin corrección, es optimista si la serie tiene autocorrelación; la plataforma lo advierte.",
    "Mann–Kendall", "Test for a monotonic trend. Uncorrected, it is optimistic if the series is autocorrelated; the platform warns about it."],
  ["Intervalo de confianza", "Rango producido por un procedimiento con cobertura nominal bajo sus supuestos. No es la probabilidad de que el valor real esté dentro.",
    "Confidence interval", "Range produced by a procedure with nominal coverage under its assumptions. It is not the probability that the true value lies inside."],
  ["p-valor", "Compatibilidad de los datos con «no hay tendencia» bajo el modelo. No es la probabilidad de que una hipótesis sea verdadera.",
    "p-value", "Compatibility of the data with “no trend” under the model. It is not the probability that a hypothesis is true."],
  ["No concluyente", "Los datos no permiten distinguir el cambio de cero con ese método. No demuestra que no haya cambio.",
    "Inconclusive", "The data do not allow the change to be distinguished from zero with that method. It does not prove there is no change."],
  ["Datos faltantes", "No hubo dato utilizable. Nunca se convierten en cero ni se interpolan en silencio.",
    "Missing data", "There was no usable value. Missing data are never turned into zero or silently interpolated."],
  ["Resolución espacial", "Tamaño de la celda del producto. Un distrito menor que una celda recibe el valor de una celda que lo excede.",
    "Spatial resolution", "Size of the product's cell. A district smaller than a cell receives the value of a cell larger than it."],
];

export function Methods() {
  const t = useT();
  const caps = useQuery({
    queryKey: ["capabilities"],
    queryFn: async () => (await fetch(`${API_URL}/catalog/capabilities`).then((r) => r.json())) as Capabilities,
  });
  return (
    <main className="page prose" id="contenido">
      <h1>{t("Métodos", "Methods")}</h1>
      <p className="lead">
        {t("Todos los números de la web, la API y el SDK de Python salen del mismo motor estadístico. La interfaz no calcula nada por su cuenta: envía una especificación del análisis y muestra lo que el motor devuelve, con su identificador de ejecución.",
          "Every number in the website, the API and the Python SDK comes from the same statistical engine. The interface computes nothing on its own: it sends an analysis specification and shows what the engine returns, with its run identifier.")}
      </p>

      <h2>{t("Cómo se obtiene una tendencia", "How a trend is obtained")}</h2>
      <ol>
        <li>{t("Earth Engine filtra el producto NASA por fechas y calidad, y promedia los píxeles del territorio ponderando por área.",
          "Earth Engine filters the NASA product by date and quality, and averages the territory's pixels weighted by area.")}</li>
        <li>{t("Se agregan los meses en años (total o media según la variable). Un año incompleto queda vacío, no se rellena.",
          "Months are aggregated into years (total or mean depending on the variable). An incomplete year is left empty, not filled in.")}</li>
        <li>{t("Opcionalmente se resta la climatología mensual para estudiar anomalías sin el ciclo estacional.",
          "Optionally the monthly climatology is subtracted to study anomalies without the seasonal cycle.")}</li>
        <li>{t("Se estima la pendiente con el método elegido, su intervalo de confianza del mismo procedimiento y una prueba compatible.",
          "The slope is estimated with the chosen method, its confidence interval from the same procedure, and a compatible test.")}</li>
        <li>{t("Se revisan la cobertura, la autocorrelación y el soporte espacial; cada limitación aparece como advertencia.",
          "Coverage, autocorrelation and spatial support are checked; every limitation appears as a warning.")}</li>
      </ol>

      <h2>{t("Combinaciones permitidas", "Allowed combinations")}</h2>
      <p>{t("No se mezclan procedimientos incompatibles (por ejemplo, la pendiente de Theil–Sen con el intervalo de OLS). La API rechaza esas combinaciones.",
        "Incompatible procedures are never mixed (for example, the Theil–Sen slope with the OLS interval). The API rejects those combinations.")}</p>
      {caps.data && (
        <table className="table">
          <thead><tr><th scope="col">{t("Estimador", "Estimator")}</th><th scope="col">{t("Intervalos de confianza", "Confidence intervals")}</th><th scope="col">{t("Pruebas", "Tests")}</th></tr></thead>
          <tbody>
            {Object.entries(caps.data.estimators).map(([k, v]) => (
              <tr key={k}>
                <th scope="row">{methodName(k)}</th>
                <td>{v.interval_methods.map(methodName).join(", ")}</td>
                <td>{v.significance_tests.map(methodName).join(", ")}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <h2>{t("Cómo leer el veredicto", "How to read the verdict")}</h2>
      <p>
        {t("«Evidencia de aumento» o «de disminución» exige que la prueba dé p < 0,05 y que el intervalo excluya el cero. Cuando se comparan varios territorios o unidades a la vez (Estudio, mapa por distritos), se usa el q-valor corregido por pruebas múltiples (Benjamini–Hochberg) en lugar de p. En cualquier otro caso el resultado es «no concluyente». En el mapa, las unidades sin evidencia se rayan en lugar de ocultarse. Una tendencia describe el periodo elegido: no es un pronóstico ni una alerta.",
          "“Evidence of increase” or “of decrease” requires the test to give p < 0.05 and the interval to exclude zero. When several territories or units are compared at once (advanced analysis, map by subdivisions), the q-value corrected for multiple testing (Benjamini–Hochberg) is used instead of p. In every other case the result is “inconclusive”. On the map, units without evidence are hatched instead of hidden. A trend describes the chosen period: it is neither a forecast nor an alert.")}
      </p>

      <h2>{t("Glosario", "Glossary")}</h2>
      <dl className="glossary">
        {GLOSSARY.map(([es, desEs, en, desEn]) => <div key={es}><dt>{t(es, en)}</dt><dd>{t(desEs, desEn)}</dd></div>)}
      </dl>
    </main>
  );
}
