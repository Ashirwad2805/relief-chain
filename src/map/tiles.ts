/**
 * src/map/tiles.ts
 * ================
 * Free, key-less tile fallback chain for ReliefChain.
 *
 * Order:
 *  1. CARTO dark_matter / light_all  (free, attribution required)
 *  2. OpenStreetMap standard tiles   (free, attribution required, light use only)
 *  3. Offline vector basemap from bundled roads.geojson (full offline)
 *
 * Do NOT call Google Maps, Mapbox, or MapTiler.
 */

export interface TileLayerConfig {
  id: 'carto' | 'osm' | 'offline';
  label: string;
  darkUrl: string;
  lightUrl: string;
  attribution: string;
  maxZoom: number;
  subdomains?: string;
}

const CARTO_KEY: string = (import.meta as any).env?.VITE_CARTO_API_KEY || 'cb1_46vq_1_d5bd37b8e519de49fd185db8';
const cartoParam = CARTO_KEY ? `?key=${CARTO_KEY}` : '';

export const TILE_LAYERS: TileLayerConfig[] = [
  {
    id: 'carto',
    label: 'CARTO',
    darkUrl:  `https://{s}.basemaps.cartocdn.com/rastertiles/dark_all/{z}/{x}/{y}{r}.png${cartoParam}`,
    lightUrl: `https://{s}.basemaps.cartocdn.com/rastertiles/light_all/{z}/{x}/{y}{r}.png${cartoParam}`,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
    maxZoom: 19,
    subdomains: 'abcd',
  },
  {
    id: 'osm',
    label: 'OSM',
    darkUrl:  'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    lightUrl: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
    maxZoom: 19,
  },
  {
    id: 'offline',
    label: 'Offline vector',
    darkUrl: '',
    lightUrl: '',
    attribution: 'Road data from OSM (synthetic graph). SIMULATED DATA ONLY.',
    maxZoom: 18,
  },
];

/** Returns the CARTO URL for the current theme. */
export function getCartoUrl(dark: boolean): string {
  const style = dark ? 'dark_all' : 'light_all';
  return `https://{s}.basemaps.cartocdn.com/rastertiles/${style}/{z}/{x}/{y}{r}.png${cartoParam}`;
}

/** Mumbai center and default zoom */
export const MUMBAI_CENTER: [number, number] = [19.05, 72.87];
export const MUMBAI_ZOOM = 12;

/** Mumbai operational bounding box (Colaba → Borivali / Mulund) */
export const MUMBAI_BOUNDS: [[number, number], [number, number]] = [
  [18.88, 72.77],
  [19.26, 72.96],
];
