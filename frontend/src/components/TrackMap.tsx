import "maplibre-gl/dist/maplibre-gl.css";

import { Map as MapLibreMap, NavigationControl, setWorkerUrl } from "maplibre-gl";
// Vite обрабатывает воркер как воркер (без клиента HMR) и в dev, и в сборке.
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import type { GeoJSONSource, LngLatBoundsLike } from "maplibre-gl";
import { useEffect, useRef } from "react";

/** Векторные тайлы OpenFreeMap: бесплатно, без ключа. Смена провайдера — только этот URL. */
export const MAP_STYLE = "https://tiles.openfreemap.org/styles/liberty";

setWorkerUrl(workerUrl);

type Coords = number[][];

export interface TrackMapProps {
  /** Видимая часть трека (то, что видят другие). */
  line: Coords | null | undefined;
  /** Весь трек — только автору, рисуется под видимой частью пунктиром. */
  fullLine?: Coords | null;
  /** Скрытая зона у дома — только автору. */
  zone?: { lat: number; lon: number; radius_m: number } | null;
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

function bounds(coords: Coords): LngLatBoundsLike | null {
  if (coords.length === 0) return null;
  let [minX, minY, maxX, maxY] = [Infinity, Infinity, -Infinity, -Infinity];
  for (const [x = 0, y = 0] of coords) {
    minX = Math.min(minX, x);
    minY = Math.min(minY, y);
    maxX = Math.max(maxX, x);
    maxY = Math.max(maxY, y);
  }
  return [minX, minY, maxX, maxY];
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

export function TrackMap({ line, fullLine, zone, label }: TrackMapProps) {
  const container = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!container.current) return;
    const map = new MapLibreMap({
      container: container.current,
      style: MAP_STYLE,
      attributionControl: { compact: true },
      cooperativeGestures: true,
    });
    map.addControl(new NavigationControl({ showCompass: false }), "top-right");
    const el = container.current;
    map.on("idle", () => (el.dataset.ready = "true"));
    map.on("error", (e) => console.error("map error:", e.error?.message ?? e));

    map.on("load", () => {
      const zoneRing = zone ? circle(zone.lat, zone.lon, zone.radius_m) : null;
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

      // Рамка — по треку; зона рисуется, но не раздвигает карту, если дом далеко от трека.
      const box = bounds([...(fullLine ?? []), ...(line ?? [])]) ?? bounds(zoneRing ?? []);
      if (box) {
        map.fitBounds(box, {
          padding: { top: 32, right: 48, bottom: 64, left: 32 },
          animate: false,
          maxZoom: 16,
        });
      }
      (map.getSource("track") as GeoJSONSource | undefined)?.setData(lineFeature(line));
    });

    return () => map.remove();
  }, [line, fullLine, zone]);

  return <div ref={container} className="track-map" role="img" aria-label={label} />;
}
