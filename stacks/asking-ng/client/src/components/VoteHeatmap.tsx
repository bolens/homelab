import L from 'leaflet';
import 'leaflet.heat';
import { useEffect, useRef, useState } from 'react';

import { COLOR_THEME_EVENT } from '../theme/colorTheme';
import { readHeatGradientFromDocumentTheme } from '../theme/heatGradient';

type HeatPoint = {
  latitude: number;
  longitude: number;
  intensity: number;
};

type VoteHeatmapProps = {
  points: HeatPoint[];
  ariaLabel: string;
};

export default function VoteHeatmap({ points, ariaLabel }: VoteHeatmapProps) {
  const mapElRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<L.Map | null>(null);
  const heatLayerRef = useRef<L.Layer | null>(null);
  const [heatThemeEpoch, setHeatThemeEpoch] = useState(0);

  useEffect(() => {
    const onTheme = () => setHeatThemeEpoch((n) => n + 1);
    window.addEventListener(COLOR_THEME_EVENT, onTheme);
    return () => window.removeEventListener(COLOR_THEME_EVENT, onTheme);
  }, []);

  useEffect(() => {
    if (!mapElRef.current || mapRef.current) return;
    const map = L.map(mapElRef.current, {
      center: [20, 0],
      zoom: 1,
      minZoom: 1,
      maxZoom: 6,
      worldCopyJump: true,
      zoomControl: true,
      attributionControl: true,
    });
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      attribution: '&copy; OpenStreetMap contributors',
    }).addTo(map);
    mapRef.current = map;
    return () => {
      map.remove();
      mapRef.current = null;
      heatLayerRef.current = null;
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    if (heatLayerRef.current) {
      map.removeLayer(heatLayerRef.current);
      heatLayerRef.current = null;
    }
    if (!points.length) return;
    const weighted = points.map(
      (point) => [point.latitude, point.longitude, point.intensity] as const,
    );
    const gradient = readHeatGradientFromDocumentTheme();
    const layer = L.heatLayer(weighted as unknown as L.HeatLatLngTuple[], {
      radius: 38,
      blur: 30,
      maxZoom: 6,
      minOpacity: 0.35,
      ...(gradient ? { gradient } : {}),
    });
    layer.addTo(map);
    heatLayerRef.current = layer;
  }, [points, heatThemeEpoch]);

  return <div className='asking-poll-page__heatmap' ref={mapElRef} role='img' aria-label={ariaLabel} />;
}
