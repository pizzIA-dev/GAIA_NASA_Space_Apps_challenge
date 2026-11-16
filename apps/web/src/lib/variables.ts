// Nombres sencillos para la interfaz (plan: lectura rápida). Los nombres técnicos, productos y versiones se muestran en
// Fuentes; la API y el SDK siguen usando los identificadores técnicos.
import { apiText, tr } from "./i18n";

const SIMPLE: Record<string, [string, string]> = {
  "nasa-gpm-imerg-monthly-v07/precipitation_mm_month": ["Lluvia", "Rainfall"],
  "nasa-merra2-slv/air_temperature_2m_c": ["Temperatura del aire", "Air temperature"],
  "nasa-merra2-slv/total_precipitable_water_kgm2": ["Vapor de agua en el aire", "Water vapour in the air"],
  "nasa-merra2-slv/wind_u_10m_ms": ["Viento (este–oeste)", "Wind (east–west)"],
  "nasa-merra2-slv/wind_v_10m_ms": ["Viento (norte–sur)", "Wind (north–south)"],
  "nasa-gldas-noah-v21-3h/soil_moisture_0_10cm_kgm2": ["Humedad del suelo", "Soil moisture"],
  "nasa-gldas-noah-v21-3h/air_temperature_c": ["Temperatura cerca del suelo", "Near-surface temperature"],
  "nasa-modis-mod13q1-061/ndvi": ["Vegetación (verdor)", "Vegetation (greenness)"],
  "nasa-modis-aqua-sst-l3smi/sst_c": ["Temperatura del mar", "Sea temperature"],
};

/** Nombre sencillo de una variable; si no está en el mapa, su magnitud física sin paréntesis. */
export function simpleName(datasetId: string, variableId: string, fallback = ""): string {
  const s = SIMPLE[`${datasetId}/${variableId}`];
  if (s) return tr(s[0], s[1]);
  const t = apiText(fallback).replace(/\s*\(.*?\)\s*/g, " ").trim();
  return t.charAt(0).toUpperCase() + t.slice(1);
}

/** Igual, en minúscula para usarlo dentro de una frase («la lluvia en …»). */
export const simpleNameLower = (datasetId: string, variableId: string, fallback = "") => {
  const s = simpleName(datasetId, variableId, fallback);
  return s.charAt(0).toLowerCase() + s.slice(1);
};

/** Unidad legible: el NDVI no tiene unidades físicas. */
export const simpleUnit = (u: string) => u.replace(/^adimensional/, tr("índice", "index"));
