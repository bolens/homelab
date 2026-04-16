import type * as L from 'leaflet';

declare module 'leaflet' {
  type HeatLatLngTuple = [number, number, number?];
  function heatLayer(
    latlngs: HeatLatLngTuple[] | L.LatLngExpression[],
    options?: {
      minOpacity?: number;
      maxZoom?: number;
      max?: number;
      radius?: number;
      blur?: number;
      gradient?: Record<number, string>;
    },
  ): L.Layer;
}
