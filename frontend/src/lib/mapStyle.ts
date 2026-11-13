import type { StyleSpecification } from "maplibre-gl";

/**
 * Подложка карты — растровые тайлы OpenStreetMap.
 *
 * Стиль встроен в код: не нужно скачивать стиль, шрифты и спрайты, поэтому трек рисуется
 * сразу, а тайлы подгружаются под ним. Правила использования тайлов OSM:
 * https://operations.osmfoundation.org/policies/tiles/ — атрибуция обязательна, для большой
 * нагрузки нужен свой или коммерческий провайдер (меняется только этот файл).
 */
export const TILE_HOST = "https://tile.openstreetmap.org";

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
