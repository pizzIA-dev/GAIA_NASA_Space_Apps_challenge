# Propuestas visuales F1 (plan §5.5)

Dos direcciones originales con **mapa, gráfico y panel estadístico reales** (NASA IMERG V07, provincia de Trujillo y
sus 11 distritos IGN, 2003–2024, calculados por el motor de la API; cada bloque trae su `run_id`).

| Archivo | Dirección |
|---|---|
| `prototypes/A_cuaderno_de_campo.html` | **A · Cuaderno de campo** — claro (gris hielo #E9EDEC, petróleo #0D4F5F, verde mineral), Source Serif 4 + Source Sans 3. Esqueleto §5.2 literal: carril izquierdo de configuración, veredicto como frase editorial en serif, serie + tendencia, mapa de pendientes, calidad y heatmap. |
| `prototypes/B_mesa_de_observacion.html` | **B · Mesa de observación** — grafito (#192024, verde azulado #5DB4A7, hielo #A9D6EA), IBM Plex Sans (+ Condensed para ejes). Mapa primero como lienzo principal; barra de contexto con controles segmentados; heatmap año×mes junto a la serie. |

Regenerar: `scripts/build_ux_prototype_data.py` (datos reales vía motor) → `scripts/build_ux_prototypes.py` (HTML
autocontenido desde `prototypes/src/`).

## Reglas comunes aplicadas (ambas)
- `TrendVerdict`: «evidencia de aumento / disminución / no concluyente»; nunca «confirmado al 95 %». Frase + hechos
  (cambio, IC, prueba, N) + nota de interpretación del IC y «no es pronóstico».
- Mapa divergente centrado en 0 (marrón seco ↔ azul verdoso húmedo); **rayado = sin evidencia** (no se borra);
  **borde discontinuo = distrito menor que un píxel IMERG** (~124 km²). En este caso real los 11 distritos están rayados
  (p entre 0,24 y 0,91) y 4 son sub-píxel; Florencia de Mora y La Esperanza comparten celda (misma pendiente).
- IC de la pendiente dibujado como **abanico de pendientes alrededor de la mediana** y rotulado «no es banda de predicción».
- Series con cortes en faltantes, sin interpolar. Lista de territorios como alternativa accesible por teclado al mapa.
- **Ámbar/goldenrod y darkorange reservados para la capa de eventos ENFEN/SINPAD (§8.1)**: no se usan en datos ni UI
  (corregido en la revisión: ambas propuestas tenían inicialmente la línea de tendencia en ámbar).

## Verificación realizada (2026-11-14)
- Sin errores de consola; 1440 px y 390 px sin scroll horizontal; interacción distrito → veredicto/serie/hechos;
  conmutador de método (OLS-HAC solo precalculado para la provincia) y de escala (anomalía mensual).
- Pendiente: 1024 y 768 px, contraste WCAG medido con herramienta, lector de pantalla.

## Criterios de elección (plan §5.5: por criterios, no «se ve bonito»)
1. Claridad del veredicto y de la incertidumbre para público general.
2. Tiempo para leer la serie y ubicar el territorio.
3. Accesibilidad (contraste, foco, alternativa al mapa).
4. Encaje con el flujo de §4.3 (arrastrar variables, comparar territorios) y con modo claro/oscuro (el producto final
   tendrá ambos; la dirección elegida define el carácter y el otro modo se deriva de sus tokens).

**Decisión (2026-11-14):** el usuario eligió **A «Cuaderno de campo»** → ADR-0006.
