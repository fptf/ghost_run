import { setWorkerUrl } from "maplibre-gl";
import type { LngLatBoundsLike, StyleSpecification } from "maplibre-gl";
// Vite обрабатывает воркер как воркер (без клиента HMR) и в dev, и в сборке.
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";

setWorkerUrl(workerUrl);

/**
 * Подложка карты — растровые тайлы OpenStreetMap.
 *
 * Стиль встроен в код: не нужно скачивать стиль, шрифты и спрайты, поэтому трек рисуется
 * сразу, а тайлы подгружаются под ним. Правила использования тайлов OSM:
 * https://operations.osmfoundation.org/policies/tiles/ — атрибуция обязательна, для большой
 * нагрузки нужен свой или коммерческий провайдер (меняется только этот файл).
 */
const TILE_HOST = "https://tile.openstreetmap.org";

export const MAP_STYLE: StyleSpecification = {
  version: 8,
  sources: {
    basemap: {
      type: "raster",
      tiles: [`${TILE_HOST}/{z}/{x}/{y}.png`],
      tileSize: 256,
      maxzoom: 19,
      attribution:
        '© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">участники OpenStreetMap</a>',
    },
  },
  layers: [
    { id: "background", type: "background", paint: { "background-color": "#EEF0EC" } },
    { id: "basemap", type: "raster", source: "basemap", paint: { "raster-saturation": -0.35 } },
  ],
};

export const ACCENT = "#C2410C";

export function boundsOf(coords: number[][]): LngLatBoundsLike | null {
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

/** HTML-маркер: у встроенного растрового стиля нет шрифтов для подписей на карте. */
export function markerEl(className: string, text = "", label?: string): HTMLElement {
  const el = document.createElement("div");
  el.className = className;
  el.textContent = text;
  if (label) {
    el.setAttribute("role", "img");
    el.setAttribute("aria-label", label);
  }
  return el;
}
