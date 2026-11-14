import type { GeoJSONSource, MapLayerMouseEvent } from "maplibre-gl";
import type { TFunction } from "i18next";
import { Map as MapLibreMap, Marker, NavigationControl } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";

import { ACCENT, boundsOf, MAP_STYLE, markerEl } from "../lib/mapStyle";
import type { View } from "./params";

export interface MapLine {
  id: string;
  coordinates: number[][];
}
export interface MapCluster {
  lon: number;
  lat: number;
  count: number;
}
export interface Viewport {
  bbox: [number, number, number, number];
  zoom: number;
  center: { lat: number; lon: number };
}

export interface SearchMapProps {
  initialView: View;
  lines: MapLine[];
  clusters: MapCluster[];
  selectedId: string | null;
  /** Линия выбранного трека (если её нет среди линий, например при кластерах). */
  selectedLine: number[][] | null;
  /** Счётчик: при изменении карта подгоняется под выбранный трек. */
  fitKey: number;
  /** Панели поверх карты (телефон: фильтры, выдвижной список) — трек подгоняется в свободную часть. */
  overlays?: () => (HTMLElement | null)[];
  /** Перелёт к области (сброс, «треки рядом»); key меняется при каждом запросе. */
  flyTo: (View & { key: number }) | null;
  onViewChange: (v: Viewport) => void;
  onSelect: (id: string | null) => void;
}

const FIT_PADDING = 48;
const MIN_FREE_PX = 160;

/** Отступы для fitBounds с учётом панелей, лежащих поверх карты сверху и снизу. */
function fitPadding(map: DOMRect, overlays: (HTMLElement | null)[]) {
  let top = 0;
  let bottom = 0;
  for (const el of overlays) {
    if (!el) continue;
    const r = el.getBoundingClientRect();
    const overlapW = Math.min(r.right, map.right) - Math.max(r.left, map.left);
    const overlapH = Math.min(r.bottom, map.bottom) - Math.max(r.top, map.top);
    // боковая колонка (десктоп) карту не перекрывает — её не считаем
    if (r.height === 0 || overlapH <= 0 || overlapW < map.width / 2) continue;
    if (r.top + r.height / 2 < map.top + map.height / 2) top = Math.max(top, r.bottom - map.top);
    else bottom = Math.max(bottom, map.bottom - r.top);
  }
  // Места мало (открыт список) — важнее не прятать трек под списком, фильтры сверху не учитываем.
  if (map.height - top - bottom - 2 * FIT_PADDING < MIN_FREE_PX) top = 0;
  if (map.height - top - bottom - 2 * FIT_PADDING < MIN_FREE_PX) bottom = 0;
  return {
    top: FIT_PADDING + top,
    bottom: FIT_PADDING + bottom,
    left: FIT_PADDING,
    right: FIT_PADDING,
  };
}

interface Selection {
  lines: MapLine[];
  selectedId: string | null;
  selectedLine: number[][] | null;
  t: TFunction;
}

/** Выделяет выбранный трек и ставит маркеры старта и финиша (endMarkers меняется на месте). */
function drawSelected(map: MapLibreMap, sel: Selection, endMarkers: Marker[]) {
  const { lines, selectedId, selectedLine, t } = sel;
  const line = selectedLine ?? lines.find((l) => l.id === selectedId)?.coordinates ?? null;
  const data = selectedId && line ? [{ id: selectedId, coordinates: line }] : [];
  (map.getSource("selected") as GeoJSONSource | undefined)?.setData(collection(data));
  endMarkers.splice(0).forEach((m) => m.remove());
  if (line && line.length > 1) {
    const first = line[0] as [number, number];
    const last = line[line.length - 1] as [number, number];
    endMarkers.push(
      new Marker({ element: markerEl("end-mark end-mark--start", "", t("map.start")) })
        .setLngLat(first)
        .addTo(map),
      new Marker({ element: markerEl("end-mark end-mark--finish", "", t("map.finish")) })
        .setLngLat(last)
        .addTo(map),
    );
  }
}

function collection(lines: MapLine[]) {
  return {
    type: "FeatureCollection" as const,
    features: lines.map((l) => ({
      type: "Feature" as const,
      properties: { id: l.id },
      geometry: { type: "LineString" as const, coordinates: l.coordinates },
    })),
  };
}

export function SearchMap({
  initialView,
  lines,
  clusters,
  selectedId,
  selectedLine,
  fitKey,
  overlays,
  flyTo,
  onViewChange,
  onSelect,
}: SearchMapProps) {
  const { t } = useTranslation();
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const ready = useRef(false);
  const fittedKey = useRef(0);
  const clusterMarkers = useRef<Marker[]>([]);
  const endMarkers = useRef<Marker[]>([]);
  const handlers = useRef({ onViewChange, onSelect, overlays });
  const latest = useRef<Selection>({ lines, selectedId, selectedLine, t });
  useEffect(() => {
    handlers.current = { onViewChange, onSelect, overlays };
    latest.current = { lines, selectedId, selectedLine, t };
  });

  // Карта создаётся один раз; дальше меняются только данные.
  useEffect(() => {
    if (!container.current) return;
    const el = container.current;
    const map = new MapLibreMap({
      container: el,
      style: MAP_STYLE,
      center: [initialView.lon, initialView.lat],
      zoom: initialView.z,
      attributionControl: { compact: true },
    });
    mapRef.current = map;
    map.addControl(new NavigationControl({ showCompass: false }), "top-right");

    const emit = () => {
      const b = map.getBounds();
      const c = map.getCenter();
      handlers.current.onViewChange({
        bbox: [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()],
        zoom: map.getZoom(),
        center: { lat: c.lat, lon: c.lng },
      });
    };

    map.once("style.load", () => {
      map.addSource("lines", { type: "geojson", data: collection(latest.current.lines) });
      map.addSource("selected", { type: "geojson", data: collection([]) });
      map.addLayer({
        id: "lines",
        type: "line",
        source: "lines",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": ACCENT, "line-width": 3, "line-opacity": 0.75 },
      });
      // Широкая невидимая линия — чтобы попадать пальцем.
      map.addLayer({
        id: "lines-hit",
        type: "line",
        source: "lines",
        paint: { "line-color": "#000", "line-width": 18, "line-opacity": 0 },
      });
      map.addLayer({
        id: "selected-casing",
        type: "line",
        source: "selected",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": "#FFFFFF", "line-width": 9 },
      });
      map.addLayer({
        id: "selected",
        type: "line",
        source: "selected",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": "#15171A", "line-width": 5 },
      });
      map.on("click", "lines-hit", (e: MapLayerMouseEvent) => {
        const id = e.features?.[0]?.properties?.id as string | undefined;
        if (id) handlers.current.onSelect(id);
      });
      // Клик в пустое место карты снимает выделение (маркеры кластеров и линии — не пустое).
      map.on("click", (e) => {
        if (e.originalEvent.target !== map.getCanvas()) return;
        if (map.queryRenderedFeatures(e.point, { layers: ["lines-hit"] }).length > 0) return;
        handlers.current.onSelect(null);
      });
      map.on("mouseenter", "lines-hit", () => (map.getCanvas().style.cursor = "pointer"));
      map.on("mouseleave", "lines-hit", () => (map.getCanvas().style.cursor = ""));
      ready.current = true;
      el.dataset.ready = "true";
      // данные трека часто приходят из кеша раньше, чем карта готова
      drawSelected(map, latest.current, endMarkers.current);
      emit();
    });
    map.on("moveend", emit);
    // Карта следит только за окном; панель рядом может скрываться — следим за контейнером.
    const resize = new ResizeObserver(() => map.resize());
    resize.observe(el);

    return () => {
      resize.disconnect();
      ready.current = false;
      map.remove();
      mapRef.current = null;
    };
    // initialView нужен только при создании карты
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Линии
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !ready.current) return;
    (map.getSource("lines") as GeoJSONSource | undefined)?.setData(collection(lines));
  }, [lines]);

  // Кластеры — HTML-маркеры с числом треков; клик приближает.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    clusterMarkers.current.forEach((m) => m.remove());
    clusterMarkers.current = clusters.map((c) => {
      const el = markerEl(
        `cluster${c.count >= 100 ? " cluster--lg" : c.count >= 10 ? " cluster--md" : ""}`,
        String(c.count),
        t("map.clusterLabel", { count: c.count }),
      );
      el.addEventListener("click", () =>
        map.easeTo({ center: [c.lon, c.lat], zoom: Math.min(map.getZoom() + 2, 14) }),
      );
      return new Marker({ element: el }).setLngLat([c.lon, c.lat]).addTo(map);
    });
  }, [clusters, t]);

  // Выбранный трек: выделение, старт и финиш (повторно рисуется и при загрузке стиля).
  useEffect(() => {
    const map = mapRef.current;
    if (map && ready.current) drawSelected(map, latest.current, endMarkers.current);
  }, [selectedId, selectedLine, lines, t]);

  // «Показать на карте»: подогнать карту под трек.
  useEffect(() => {
    const map = mapRef.current;
    // Подгоняем один раз на каждый запрос (fitKey): клик по линии на карте рамку не трогает.
    if (!map || fitKey === 0 || !selectedLine || fittedKey.current === fitKey) return;
    fittedKey.current = fitKey;
    const box = boundsOf(selectedLine);
    if (!box) return;
    const padding = fitPadding(
      map.getContainer().getBoundingClientRect(),
      handlers.current.overlays?.() ?? [],
    );
    map.fitBounds(box, { padding, maxZoom: 16, duration: 0 });
  }, [fitKey, selectedLine]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !flyTo) return;
    map.jumpTo({ center: [flyTo.lon, flyTo.lat], zoom: flyTo.z });
  }, [flyTo]);

  return <div ref={container} className="search-map" role="region" aria-label={t("map.label")} />;
}
