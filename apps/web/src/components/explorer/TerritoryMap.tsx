"use client";
// Mapa de pendientes por unidad (plan §8): MapLibre con estilo vacío (sin teselas externas) + fronteras de la API.
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef } from "react";
import { cssVar, divergent } from "@/lib/colors";
import type { FeatureCollection, Statistics } from "@/lib/types";
import { verdictOf } from "@/lib/format";
import { apiText, useLang, useT } from "@/lib/i18n";

export interface UnitResult { geoId: string; st?: Statistics; error?: string }

interface Props {
  fc: FeatureCollection;
  results: Record<string, UnitResult>;
  selected: string;
  pixelKm2: number;
  onSelect: (geoId: string) => void;
}

function hatchImage(color: string): ImageData {
  const c = document.createElement("canvas");
  c.width = c.height = 8;
  const g = c.getContext("2d")!;
  g.strokeStyle = color; g.lineWidth = 1.4;
  g.beginPath(); g.moveTo(0, 8); g.lineTo(8, 0); g.moveTo(-2, 2); g.lineTo(2, -2); g.moveTo(6, 10); g.lineTo(10, 6); g.stroke();
  return g.getImageData(0, 0, 8, 8);
}

export function TerritoryMap({ fc, results, selected, pixelKm2, onSelect }: Props) {
  const t = useT();
  const lang = useLang(); // la atribución del mapa se redibuja al cambiar de idioma
  const ref = useRef<HTMLDivElement>(null);
  const mapRef = useRef<import("maplibre-gl").Map | null>(null);
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;

  const children = fc.features.filter((f) => f.properties.role === "child");
  const drawn = children.length ? children : fc.features;
  const maxAbs = Math.max(1e-9, ...drawn.map((f) => Math.abs(results[f.id]?.st?.estimate ?? 0)));

  const data = {
    type: "FeatureCollection" as const,
    features: drawn.map((f) => {
      const st = results[f.id]?.st;
      const v = st ? verdictOf(st) : null;
      return {
        ...f,
        properties: {
          ...f.properties,
          color: st?.estimate != null ? divergent(st.estimate / maxAbs) : cssVar("--nodata"),
          nonsig: v ? v.kind === "nc" || v.kind === "none" : false,
          subpixel: (f.properties.area_km2 ?? Infinity) < pixelKm2,
          selected: f.id === selected,
        },
      };
    }),
  };

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const maplibre = await import("maplibre-gl");
      maplibre.setWorkerUrl("/maplibre/maplibre-gl-worker.mjs");
      if (cancelled || !ref.current || mapRef.current) return;
      const map = new maplibre.Map({
        container: ref.current,
        style: { version: 8, sources: {}, layers: [{ id: "bg", type: "background", paint: { "background-color": cssVar("--paper") } }] },
        attributionControl: { compact: true, customAttribution: apiText(fc.attribution) },
        dragRotate: false, pitchWithRotate: false,
      });
      map.touchZoomRotate.disableRotation();
      map.addControl(new maplibre.NavigationControl({ showCompass: false }), "top-right");
      mapRef.current = map;
      map.on("load", () => {
        map.addImage("hatch", hatchImage(cssVar("--hatch")));
        map.addSource("units", { type: "geojson", data });
        map.addLayer({ id: "fill", type: "fill", source: "units", paint: { "fill-color": ["get", "color"] } });
        map.addLayer({ id: "hatch", type: "fill", source: "units", filter: ["==", ["get", "nonsig"], true],
                       paint: { "fill-pattern": "hatch", "fill-opacity": 0.75 } });
        map.addLayer({ id: "edge", type: "line", source: "units", paint: { "line-color": cssVar("--paper"), "line-width": 1.2 } });
        map.addLayer({ id: "subpixel", type: "line", source: "units", filter: ["==", ["get", "subpixel"], true],
                       paint: { "line-color": cssVar("--ink"), "line-width": 1, "line-dasharray": [2, 1.5] } });
        map.addLayer({ id: "selected", type: "line", source: "units", filter: ["==", ["get", "selected"], true],
                       paint: { "line-color": cssVar("--ink"), "line-width": 2.8 } });
        const b = new maplibre.LngLatBounds();
        fc.features.forEach((f) => {
          const walk = (c: unknown): void => { if (Array.isArray(c) && typeof c[0] === "number") b.extend(c as [number, number]); else if (Array.isArray(c)) c.forEach(walk); };
          walk((f.geometry as { coordinates: unknown }).coordinates);
        });
        map.fitBounds(b, { padding: 20, animate: false });
        map.on("click", "fill", (e: import("maplibre-gl").MapLayerMouseEvent) => { const id = e.features?.[0]?.properties?.geo_id; if (id) onSelectRef.current(String(id)); });
        map.on("mouseenter", "fill", () => { map.getCanvas().style.cursor = "pointer"; });
        map.on("mouseleave", "fill", () => { map.getCanvas().style.cursor = ""; });
      });
    })();
    return () => { cancelled = true; mapRef.current?.remove(); mapRef.current = null; };
    // El mapa se crea una vez por colección de fronteras; los datos se actualizan en el efecto siguiente.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fc, lang]);

  useEffect(() => {
    const map = mapRef.current;
    const src = map?.getSource("units") as import("maplibre-gl").GeoJSONSource | undefined;
    src?.setData(data);
  });

  return (
    <div
      ref={ref}
      className="map"
      role="group"
      aria-label={t("Mapa de unidades coloreadas por pendiente; usa la lista de territorios para elegir con teclado",
        "Map of units coloured by slope; use the territory list to choose with the keyboard")}
    />
  );
}
