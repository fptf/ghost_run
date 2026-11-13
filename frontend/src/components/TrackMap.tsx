import "maplibre-gl/dist/maplibre-gl.css";

import type { MultiPolygon, Polygon } from "geojson";
import { Map as MapLibreMap, Marker, NavigationControl } from "maplibre-gl";

import { useEffect, useRef } from "react";

import { boundsOf, MAP_STYLE, markerEl } from "../lib/mapStyle";

type Coords = number[][];

export interface TrackMapProps {
  /** Видимая часть трека (то, что видят другие). */
  line: Coords | null | undefined;
  /** Весь трек — только автору, рисуется под видимой частью пунктиром. */
  fullLine?: Coords | null;
  /** Скрытая зона у дома — только автору. */
  zone?: { lat: number; lon: number; radius_m: number } | null;
  /** Отметки километров на видимой части. */
  kmMarks?: { km: number; lon: number; lat: number }[];
  /** Экран проверки: коридор маршрута, пробежка бегуна и место схода. */
  check?: {
    corridor: Polygon | MultiPolygon | null;
    mine: Coords | null;
    deviation: { lon: number; lat: number } | null;
  } | null;
  label: string;
}

function circle(lat: number, lon: number, radius: number, steps = 64): Coords {
  const dLat = radius / 111_320;
  const dLon = radius / (111_320 * Math.cos((lat * Math.PI) / 180));
  return Array.from({ length: steps + 1 }, (_, i) => {
    const a = (i / steps) * 2 * Math.PI;
    return [lon + dLon * Math.cos(a), lat + dLat * Math.sin(a)];
  });
}

function lineFeature(coords: Coords | null | undefined) {
  return {
    type: "FeatureCollection" as const,
    features: coords?.length
      ? [
          {
            type: "Feature" as const,
            properties: {},
            geometry: { type: "LineString" as const, coordinates: coords },
          },
        ]
      : [],
  };
}

const FIT_PADDING = { top: 32, right: 48, bottom: 64, left: 32 };

export function TrackMap({ line, fullLine, zone, kmMarks, check, label }: TrackMapProps) {
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!container.current) return;
    const zoneRing = zone ? circle(zone.lat, zone.lon, zone.radius_m) : null;
    // Рамка — по треку; зона не раздвигает карту, если дом далеко от трека.
    const box =
      boundsOf([...(fullLine ?? []), ...(line ?? []), ...(check?.mine ?? [])]) ??
      boundsOf(zoneRing ?? []);
    const el = container.current;

    // Камера сразу в рамке трека: не грузим сначала тайлы всего мира.
    const map = new MapLibreMap({
      container: el,
      style: MAP_STYLE,
      ...(box
        ? { bounds: box, fitBoundsOptions: { padding: FIT_PADDING, maxZoom: 16 } }
        : { center: [37.62, 55.75] as [number, number], zoom: 9 }),
      attributionControl: { compact: true },
      cooperativeGestures: true,
    });
    map.addControl(new NavigationControl({ showCompass: false }), "top-right");
    map.on("idle", () => (el.dataset.ready = "true"));
    map.on("error", (e) => console.error("map error:", e.error?.message ?? e));

    // Стиль встроен, style.load наступает сразу — линия видна, пока догружаются тайлы.
    map.once("style.load", () => {
      el.dataset.style = "true";
      map.addSource("zone", {
        type: "geojson",
        data: {
          type: "FeatureCollection",
          features: zoneRing
            ? [
                {
                  type: "Feature",
                  properties: {},
                  geometry: { type: "Polygon", coordinates: [zoneRing] },
                },
              ]
            : [],
        },
      });
      map.addLayer({
        id: "zone-fill",
        type: "fill",
        source: "zone",
        paint: { "fill-color": "#15171A", "fill-opacity": 0.18 },
      });
      map.addLayer({
        id: "zone-edge",
        type: "line",
        source: "zone",
        paint: { "line-color": "#15171A", "line-opacity": 0.4, "line-dasharray": [2, 2] },
      });

      if (check?.corridor) {
        map.addSource("corridor", {
          type: "geojson",
          data: { type: "Feature", properties: {}, geometry: check.corridor },
        });
        map.addLayer({
          id: "corridor",
          type: "fill",
          source: "corridor",
          paint: { "fill-color": "#C2410C", "fill-opacity": 0.14 },
        });
      }

      map.addSource("full", { type: "geojson", data: lineFeature(fullLine) });
      map.addLayer({
        id: "full",
        type: "line",
        source: "full",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": "#5B6168", "line-width": 3, "line-dasharray": [1, 1.5] },
      });

      map.addSource("track", { type: "geojson", data: lineFeature(line) });
      map.addLayer({
        id: "track-casing",
        type: "line",
        source: "track",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": "#FFFFFF", "line-width": 8 },
      });
      map.addLayer({
        id: "track",
        type: "line",
        source: "track",
        layout: { "line-cap": "round", "line-join": "round" },
        paint: { "line-color": "#C2410C", "line-width": 4.5 },
      });

      if (check?.mine?.length) {
        map.addSource("mine", { type: "geojson", data: lineFeature(check.mine) });
        map.addLayer({
          id: "mine",
          type: "line",
          source: "mine",
          layout: { "line-cap": "round", "line-join": "round" },
          paint: { "line-color": "#1D4ED8", "line-width": 3, "line-opacity": 0.9 },
        });
      }
    });

    if (check?.deviation) {
      new Marker({ element: markerEl("deviation-mark", "!", "место схода") })
        .setLngLat([check.deviation.lon, check.deviation.lat])
        .addTo(map);
    }

    for (const m of kmMarks ?? []) {
      new Marker({ element: markerEl("km-mark", String(m.km)) })
        .setLngLat([m.lon, m.lat])
        .addTo(map);
    }
    if (line?.length) {
      const first = line[0] as [number, number];
      const last = line[line.length - 1] as [number, number];
      new Marker({ element: markerEl("end-mark end-mark--start", "", "старт") })
        .setLngLat(first)
        .addTo(map);
      new Marker({ element: markerEl("end-mark end-mark--finish", "", "финиш") })
        .setLngLat(last)
        .addTo(map);
    }

    const resize = new ResizeObserver(() => map.resize());
    resize.observe(el);

    return () => {
      resize.disconnect();
      map.remove();
    };
  }, [line, fullLine, zone, kmMarks, check]);

  return <div ref={container} className="track-map" role="img" aria-label={label} />;
}
