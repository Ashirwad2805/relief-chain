/**
 * src/components/MapView.tsx  — v4 (map-fix, route-viz, high-contrast)
 * =====================================================================
 * Fixes in this version:
 *  1. Map height fix: uses 100% height inside a properly sized container.
 *  2. Road overlay: merges backend condition state with the bundled
 *     /geo/roads.geojson geometry so roads are always visible.
 *  3. High-contrast road colors (visible on both dark and light tiles).
 *  4. Active ambulance route lines drawn from current position → incident
 *     → hospital with dashed animated stroke.
 *  5. Map legend showing all entity types and road conditions.
 *  6. Road condition tooltips always visible on hover.
 *  7. Tile fallback chain: CARTO → OSM → offline vector GeoJSON.
 */

import {
  useEffect, useRef, useState, useCallback, memo
} from 'react';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { MUMBAI_CENTER, MUMBAI_ZOOM, TILE_LAYERS, getCartoUrl } from '@/map/tiles';
import type { Incident, Ambulance, Hospital, Road, GeoPoint, AllocationDecision } from '@/types';

// ── Fix Leaflet default marker icon paths broken by bundlers ─────────────────
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl:       'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl:     'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
});

// ── Types ─────────────────────────────────────────────────────────────────────

export interface MapViewProps {
  incidents:    Incident[];
  ambulances:   Ambulance[];
  hospitals:    Hospital[];
  roads:        Road[];
  decisions?:   AllocationDecision[];
  selectedType: 'incident' | 'ambulance' | 'hospital' | null;
  selectedId:   string | null;
  onSelect:     (type: 'incident' | 'ambulance' | 'hospital', id: string) => void;
  simTime:      number;
  dark?:        boolean;
}

// ── High-contrast colour helpers ──────────────────────────────────────────────

const SEV_COLOR: Record<string, string> = {
  red:    '#ff4444',
  yellow: '#ffd700',
  green:  '#00e676',
};
const AMB_COLOR: Record<string, string> = {
  idle:           '#60a5fa',
  dispatched:     '#38bdf8',
  en_route_pickup:'#f97316',
  loading:        '#a78bfa',
  transporting:   '#fbbf24',
  returning:      '#4ade80',
  broken:         '#ef4444',
};
// High-contrast road colors — clearly visible on CARTO dark tiles
const ROAD_COLOR: Record<string, string> = {
  open:    '#4a90d9',   // bright blue — subtle but visible
  slow:    '#f5a623',   // amber
  flooded: '#00bcd4',   // cyan
  blocked: '#ff3b30',   // red
};
const ROAD_DASH: Record<string, string | undefined> = {
  open:    undefined,
  slow:    '6,3',
  flooded: '4,4',
  blocked: '8,4',
};
const ROAD_WEIGHT: Record<string, number> = {
  open:    2,
  slow:    3,
  flooded: 3.5,
  blocked: 4,
};
const ROAD_OPACITY: Record<string, number> = {
  open:    0.55,
  slow:    0.85,
  flooded: 0.9,
  blocked: 1.0,
};

// ── Div-icon factory ──────────────────────────────────────────────────────────

function makeHospitalIcon(color: string, selected: boolean, label: string, idleCount: number = 0): L.DivIcon {
  const ring = selected ? `box-shadow:0 0 0 3px ${color},0 0 12px ${color}66;` : `box-shadow:0 0 6px ${color}55;`;
  const idleBadge = idleCount > 0 ? `
    <div style="
      position:absolute;top:-8px;right:-10px;
      background:#2563eb;color:#fff;
      font-size:9px;font-weight:700;
      padding:1px 4px;border-radius:10px;
      border:1px solid #60a5fa;box-shadow:0 2px 6px rgba(0,0,0,0.5);
      white-space:nowrap;display:flex;align-items:center;gap:2px;
      z-index: 10;
    "><span>🚑</span><span>${idleCount}</span></div>
  ` : '';
  return L.divIcon({
    className: '',
    iconSize:  [32, 32],
    iconAnchor:[16, 16],
    html: `
      <div style="
        position:relative;
        width:32px;height:32px;border-radius:8px;
        background:${color}22;
        border:${selected ? '3px' : '2px'} solid ${color};
        display:flex;align-items:center;justify-content:center;
        font-weight:700;font-size:12px;color:${color};font-family:monospace;
        ${ring}
      ">
        <span title="${label}">H</span>
        ${idleBadge}
      </div>`,
  });
}

function makeIncidentIcon(inc: Incident, selected: boolean): L.DivIcon {
  const c = SEV_COLOR[inc.severity] ?? '#999';
  const r = inc.severity === 'red' ? 22 : inc.severity === 'yellow' ? 18 : 14;
  const pulse = inc.severity === 'red'
    ? `<div style="position:absolute;inset:-4px;border-radius:50%;border:2px solid ${c};opacity:.5;animation:rc-pulse 1.8s infinite;"></div>`
    : '';
  const ring = selected ? `box-shadow:0 0 0 3px ${c},0 0 16px ${c}66;` : '';
  return L.divIcon({
    className: '',
    iconSize:  [r * 2, r * 2],
    iconAnchor:[r, r],
    html: `
      <div style="position:relative;width:${r*2}px;height:${r*2}px;">
        ${pulse}
        <div style="
          position:absolute;inset:0;border-radius:50%;
          background:${c}44;
          border:${selected ? '3px' : '2px'} solid ${c};
          display:flex;align-items:center;justify-content:center;
          font-size:10px;font-weight:800;color:#fff;font-family:monospace;
          ${ring}
        ">${inc.redPatients}</div>
      </div>`,
  });
}

// ── GeoJSON road feature cache (loaded once) ──────────────────────────────────

interface GeoRoadFeature {
  name: string;
  coords: [number, number][];  // [lat, lng] pairs
  condition: string;
  highway: string;
  flood_prone: boolean;
}

let _geoRoadCache: GeoRoadFeature[] | null = null;
let _geoRoadPromise: Promise<GeoRoadFeature[]> | null = null;

function loadGeoRoads(): Promise<GeoRoadFeature[]> {
  if (_geoRoadCache) return Promise.resolve(_geoRoadCache);
  if (_geoRoadPromise) return _geoRoadPromise;
  _geoRoadPromise = fetch('/geo/roads.geojson')
    .then(r => r.json())
    .then((gj: any) => {
      const features: GeoRoadFeature[] = (gj.features ?? []).map((f: any) => ({
        name:       f.properties?.name ?? '',
        condition:  f.properties?.condition ?? 'open',
        highway:    f.properties?.highway ?? 'secondary',
        flood_prone: f.properties?.flood_prone ?? false,
        // GeoJSON coords are [lng, lat] — convert to [lat, lng]
        coords: (f.geometry?.coordinates ?? []).map(([lng, lat]: [number, number]) => [lat, lng] as [number, number]),
      }));
      _geoRoadCache = features;
      return features;
    })
    .catch(() => { _geoRoadCache = []; return []; });
  return _geoRoadPromise;
}

// ── Ambulance canvas layer ────────────────────────────────────────────────────
// All ambulances drawn on ONE <canvas> via rAF — React never touches it.

class AmbulanceCanvasLayer extends L.Layer {
  private _canvas: HTMLCanvasElement | null = null;
  private _ctx: CanvasRenderingContext2D | null = null;
  private _raf: number = 0;
  private _ambulances: Ambulance[] = [];
  private _selectedId: string | null = null;
  private _onSelect: (id: string) => void = () => {};
  private _showIdle: boolean = true;

  initialize(options?: L.LayerOptions) { L.setOptions(this, options); }

  onAdd(map: L.Map): this {
    const canvas = document.createElement('canvas');
    canvas.style.cssText = 'position:absolute;top:0;left:0;pointer-events:all;z-index:400;';
    (map.getPanes().overlayPane!).appendChild(canvas);
    this._canvas = canvas;
    this._ctx = canvas.getContext('2d');
    this._resize();
    map.on('resize', this._resize, this);
    map.on('move',   this._draw,   this);
    map.on('zoom',   this._draw,   this);
    canvas.addEventListener('click', this._onClick.bind(this, map));
    this._scheduleFrame();
    return this;
  }

  onRemove(map: L.Map): this {
    cancelAnimationFrame(this._raf);
    map.off('resize', this._resize, this);
    map.off('move',   this._draw,   this);
    map.off('zoom',   this._draw,   this);
    this._canvas?.parentNode?.removeChild(this._canvas);
    this._canvas = null; this._ctx = null;
    return this;
  }

  setData(ambulances: Ambulance[], selectedId: string | null, onSelect: (id: string) => void, showIdle: boolean = true) {
    this._ambulances = ambulances;
    this._selectedId = selectedId;
    this._onSelect = onSelect;
    this._showIdle = showIdle;
  }

  private _resize = () => {
    const map = (this as any)._map as L.Map;
    if (!map || !this._canvas) return;
    const size = map.getSize();
    this._canvas.width  = size.x;
    this._canvas.height = size.y;
    this._draw();
  };

  private _scheduleFrame() {
    this._raf = requestAnimationFrame(() => { this._draw(); this._scheduleFrame(); });
  }

  private _draw = () => {
    const map = (this as any)._map as L.Map;
    if (!map || !this._canvas || !this._ctx) return;
    const ctx = this._ctx;
    ctx.clearRect(0, 0, this._canvas.width, this._canvas.height);

    const topLeft = map.containerPointToLayerPoint([0, 0]);
    this._canvas.style.transform = `translate(${topLeft.x}px,${topLeft.y}px)`;

    const bounds = map.getBounds().pad(0.1);
    const zoom   = map.getZoom();

    for (const amb of this._ambulances) {
      if (!amb.position?.lat) continue;
      if (!bounds.contains([amb.position.lat, amb.position.lng])) continue;

      const isIdle = amb.status === 'idle';
      if (isIdle && !this._showIdle) continue;

      const pt = map.latLngToContainerPoint([amb.position.lat, amb.position.lng]);
      const x = pt.x - topLeft.x;
      const y = pt.y - topLeft.y;
      const sel = amb.id === this._selectedId;
      const color = isIdle ? '#60a5fa' : (AMB_COLOR[amb.status] ?? '#9ca3af');
      const r = sel ? 11 : isIdle ? (zoom < 13 ? 5 : 7) : zoom < 13 ? 6 : 8;

      // Glow ring for selected
      if (sel) {
        ctx.beginPath();
        ctx.arc(x, y, r + 5, 0, Math.PI * 2);
        ctx.fillStyle = color + '44';
        ctx.fill();
      }

      // Outer ring
      ctx.beginPath();
      ctx.arc(x, y, r + (sel ? 3 : 1), 0, Math.PI * 2);
      ctx.fillStyle = color + (isIdle ? '22' : '33');
      ctx.fill();

      // Body
      ctx.beginPath();
      ctx.arc(x, y, r, 0, Math.PI * 2);
      ctx.fillStyle = isIdle ? '#1d4ed8' : (color + 'dd');
      ctx.strokeStyle = isIdle ? '#93c5fd' : '#fff';
      ctx.lineWidth = sel ? 2 : 1;
      ctx.fill();
      ctx.stroke();

      if (isIdle) {
        // Inner white standby core
        ctx.beginPath();
        ctx.arc(x, y, 2, 0, Math.PI * 2);
        ctx.fillStyle = '#ffffff';
        ctx.fill();
      }

      // ID label
      if (zoom >= 13 || sel) {
        ctx.fillStyle = '#fff';
        ctx.font = `${sel ? 'bold ' : ''}${sel ? 9 : 8}px monospace`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(amb.id.replace('AMB-', ''), x, isIdle ? y - 10 : y);
      }
    }
  };

  private _onClick = (map: L.Map, e: MouseEvent) => {
    if (!this._canvas) return;
    const rect = this._canvas.getBoundingClientRect();
    const cx = e.clientX - rect.left;
    const cy = e.clientY - rect.top;
    const topLeft = map.containerPointToLayerPoint([0, 0]);

    for (const amb of this._ambulances) {
      if (!amb.position) continue;
      const pt = map.latLngToContainerPoint([amb.position.lat, amb.position.lng]);
      if (Math.hypot(cx - (pt.x - topLeft.x), cy - (pt.y - topLeft.y)) <= 14) {
        this._onSelect(amb.id);
        break;
      }
    }
  };
}

// ── MapView component ─────────────────────────────────────────────────────────

function MapViewInner({
  incidents, ambulances, hospitals, roads, decisions = [],
  selectedType, selectedId, onSelect, simTime, dark = true,
}: MapViewProps) {
  const containerRef    = useRef<HTMLDivElement>(null);
  const mapRef          = useRef<L.Map | null>(null);
  const tileRef         = useRef<L.TileLayer | null>(null);
  const roadsLayerRef   = useRef<L.LayerGroup | null>(null);
  const routeLayerRef   = useRef<L.LayerGroup | null>(null);   // ambulance path lines
  const altRoutesLayerRef = useRef<L.LayerGroup | null>(null); // alternate candidate paths
  const hospsLayerRef   = useRef<L.LayerGroup | null>(null);
  const incsLayerRef    = useRef<L.LayerGroup | null>(null);
  const ambLayerRef     = useRef<AmbulanceCanvasLayer | null>(null);
  const geoRoadsRef     = useRef<GeoRoadFeature[]>([]);
  const [tileSource, setTileSource] = useState<'CARTO' | 'OSM' | 'Offline vector'>('CARTO');
  const [showLegend, setShowLegend] = useState(true);
  const [showAlternates, setShowAlternates] = useState(true);
  const [showIdleFleet, setShowIdleFleet] = useState(true);

  // ── Initialize map once ────────────────────────────────────────────────────
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = L.map(containerRef.current, {
      center: MUMBAI_CENTER,
      zoom:   MUMBAI_ZOOM,
      zoomControl: true,
      attributionControl: true,
      preferCanvas: true,
    });
    mapRef.current = map;

    // ── Tile fallback chain ────────────────────────────────────────────────
    const cartoLayer = L.tileLayer(getCartoUrl(dark), {
      attribution: TILE_LAYERS[0].attribution,
      maxZoom: 19,
      subdomains: 'abcd',
    });
    const osmLayer = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
      attribution: TILE_LAYERS[1].attribution,
      maxZoom: 19,
    });

    let failCount = 0;
    cartoLayer.on('tileerror', () => {
      failCount++;
      if (failCount > 3) {
        map.removeLayer(cartoLayer);
        osmLayer.addTo(map);
        tileRef.current = osmLayer;
        setTileSource('OSM');
      }
    });
    osmLayer.on('tileerror', () => {
      map.removeLayer(osmLayer);
      setTileSource('Offline vector');
    });

    cartoLayer.addTo(map);
    tileRef.current = cartoLayer;

    // ── Layer groups ────────────────────────────────────────────────────────
    const roadsLayer = L.layerGroup().addTo(map);
    roadsLayerRef.current = roadsLayer;

    const altRoutesLayer = L.layerGroup().addTo(map);
    altRoutesLayerRef.current = altRoutesLayer;

    const routeLayer = L.layerGroup().addTo(map);
    routeLayerRef.current = routeLayer;

    const hospsLayer = L.layerGroup().addTo(map);
    hospsLayerRef.current = hospsLayer;

    const incsLayer = L.layerGroup().addTo(map);
    incsLayerRef.current = incsLayer;

    const ambLayer = new AmbulanceCanvasLayer();
    ambLayerRef.current = ambLayer;
    ambLayer.addTo(map);

    // Inject keyframe CSS once
    if (!document.getElementById('rc-pulse-style')) {
      const s = document.createElement('style');
      s.id = 'rc-pulse-style';
      s.textContent = `
        @keyframes rc-pulse {
          0%   { transform:scale(1);   opacity:.5; }
          70%  { transform:scale(2.8); opacity:0;  }
          100% { transform:scale(1);   opacity:0;  }
        }
        @keyframes rc-dash {
          to { stroke-dashoffset: -20; }
        }
        .rc-road-tip {
          background: rgba(10,14,20,0.92) !important;
          border: 1px solid #1e2636 !important;
          color: #e4e7ec !important;
          font-size: 11px !important;
          font-family: monospace !important;
          border-radius: 4px !important;
          padding: 4px 8px !important;
        }
      `;
      document.head.appendChild(s);
    }

    // Pre-load GeoJSON roads
    loadGeoRoads().then(features => {
      geoRoadsRef.current = features;
      // Trigger road redraw now that geo data is available
      // We do this by nudging a synthetic roads update via the layer
      drawRoads(roadsLayer, roads, features);
    });

    return () => { map.remove(); mapRef.current = null; };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Sync tile theme ────────────────────────────────────────────────────────
  useEffect(() => {
    if (!mapRef.current || !tileRef.current || tileSource !== 'CARTO') return;
    tileRef.current.setUrl(getCartoUrl(dark));
  }, [dark, tileSource]);

  // ── Road overlay ───────────────────────────────────────────────────────────
  useEffect(() => {
    const layer = roadsLayerRef.current;
    if (!layer) return;
    drawRoads(layer, roads, geoRoadsRef.current);
  }, [roads]);

  // ── Route lines (ambulance paths) ─────────────────────────────────────────
  useEffect(() => {
    const layer = routeLayerRef.current;
    if (!layer) return;
    layer.clearLayers();

    for (const amb of ambulances) {
      if (!amb.position?.lat) continue;
      if (amb.status === 'idle' || amb.status === 'broken') continue;

      const start: [number, number] = [amb.position.lat, amb.position.lng];

      // Find incident position
      if (amb.assignedIncidentId) {
        const inc = incidents.find(i => i.id === amb.assignedIncidentId);
        if (inc?.position?.lat) {
          const incPos: [number, number] = [inc.position.lat, inc.position.lng];
          const ambColor = AMB_COLOR[amb.status] ?? '#38bdf8';

          // Draw ambulance → incident line (dashed animated)
          const routeLine = L.polyline([start, incPos], {
            color: ambColor,
            weight: 2.5,
            opacity: 0.8,
            dashArray: '8,6',
            className: 'rc-route-line',
          });
          routeLine.bindTooltip(
            `${amb.id} → ${inc.id} (${amb.status.replace(/_/g, ' ')})`,
            { direction: 'center', sticky: true, className: 'rc-road-tip' }
          );
          layer.addLayer(routeLine);

          // Draw incident → hospital line if assigned
          if (amb.assignedHospitalId) {
            const hosp = hospitals.find(h => h.id === amb.assignedHospitalId);
            if (hosp?.position?.lat) {
              const hospPos: [number, number] = [hosp.position.lat, hosp.position.lng];
              const hospLine = L.polyline([incPos, hospPos], {
                color: '#a78bfa',
                weight: 2,
                opacity: 0.6,
                dashArray: '4,6',
              });
              hospLine.bindTooltip(`${inc.id} → ${hosp.name}`, {
                direction: 'center', sticky: true, className: 'rc-road-tip'
              });
              layer.addLayer(hospLine);
            }
          }
        }
      } else if (amb.assignedHospitalId && amb.status === 'returning') {
        // Returning ambulance → home hospital
        const hosp = hospitals.find(h => h.id === amb.assignedHospitalId);
        if (hosp?.position?.lat) {
          const hospPos: [number, number] = [hosp.position.lat, hosp.position.lng];
          layer.addLayer(L.polyline([start, hospPos], {
            color: '#4ade80',
            weight: 2,
            opacity: 0.5,
            dashArray: '3,7',
          }));
        }
      }
    }
  }, [ambulances, incidents, hospitals]);

  // ── Alternate Routes (candidate paths evaluated by solver) ────────────────
  useEffect(() => {
    const layer = altRoutesLayerRef.current;
    if (!layer) return;
    layer.clearLayers();
    if (!showAlternates || !decisions || decisions.length === 0) return;

    // Filter relevant decisions: if an incident or ambulance is selected, show its candidate paths;
    // otherwise show all non-stale decisions' alternatives
    const relevantDecisions = decisions.filter(d => {
      if (selectedType === 'incident') return d.incidentId === selectedId;
      if (selectedType === 'ambulance') return d.ambulanceId === selectedId;
      return d.status !== 'stale';
    });

    for (const d of relevantDecisions) {
      const inc = incidents.find(i => i.id === d.incidentId);
      if (!inc?.position?.lat) continue;
      const incPos: [number, number] = [inc.position.lat, inc.position.lng];

      const alts = d.alternatives || [];
      for (let idx = 0; idx < alts.length; idx++) {
        const alt = alts[idx];
        if (alt.accepted || alt.hospitalId === d.hospitalId) continue;

        const altHosp = hospitals.find(h => h.id === alt.hospitalId);
        if (!altHosp?.position?.lat) continue;
        const altHospPos: [number, number] = [altHosp.position.lat, altHosp.position.lng];

        const isHighlight = (selectedType === 'incident' && selectedId === inc.id) ||
                            (selectedType === 'hospital' && selectedId === alt.hospitalId);

        const altLine = L.polyline([incPos, altHospPos], {
          color: isHighlight ? '#e879f9' : '#c084fc',
          weight: isHighlight ? 3 : 2,
          opacity: isHighlight ? 0.95 : 0.65,
          dashArray: '5,6',
          className: 'rc-alt-route-line',
        });

        altLine.bindTooltip(
          `<b>Alternate Choice #${idx + 1}: ${alt.hospitalName}</b><br/>` +
          `Benefit Score: <b>${alt.score}/100</b> · Transit ETA: ${alt.etaMinutes}m · Distance: ${alt.distance}km<br/>` +
          `<span style="color:#fbbf24">Solver Note: Bypassed (${alt.reasons?.[0] || 'Secondary headroom candidate'})</span>`,
          { direction: 'center', sticky: true, className: 'rc-road-tip' }
        );
        layer.addLayer(altLine);
      }
    }
  }, [decisions, incidents, hospitals, selectedType, selectedId, showAlternates]);

  // ── Hospitals ──────────────────────────────────────────────────────────────
  useEffect(() => {
    const layer = hospsLayerRef.current;
    if (!layer) return;
    layer.clearLayers();
    for (const h of hospitals) {
      if (!h.position?.lat) continue;
      const icuRatio = h.capacity.icu > 0 ? h.occupied.icu / h.capacity.icu : 0;
      const color =
        h.status === 'power_failure' ? '#f59e0b' :
        h.status === 'full' || h.status === 'overloaded' ? '#ef4444' :
        icuRatio > 0.8 ? '#fbbf24' : '#10b981';
      const sel = selectedType === 'hospital' && selectedId === h.id;

      // Count idle ambulances stationed at this hospital
      const idleCount = ambulances.filter(
        a => a.status === 'idle' && (a.homeHospital === h.id || a.assignedHospitalId === h.id)
      ).length;

      const marker = L.marker([h.position.lat, h.position.lng], {
        icon: makeHospitalIcon(color, sel, h.name, idleCount)
      });
      marker.on('click', () => onSelect('hospital', h.id));
      marker.bindTooltip(
        `<b>${h.name}</b><br>` +
        `<span style="color:#60a5fa;font-weight:700;">🚑 ${idleCount} Idle Ambulances Stationed</span><br>` +
        `ICU: ${h.occupied.icu}/${h.capacity.icu} · ER: ${h.occupied.er}/${h.capacity.er}<br>` +
        `Status: ${h.status.toUpperCase()}`,
        { direction: 'top', className: 'rc-road-tip' }
      );
      layer.addLayer(marker);
    }
  }, [hospitals, ambulances, selectedType, selectedId, onSelect]);

  // ── Incidents ──────────────────────────────────────────────────────────────
  useEffect(() => {
    const layer = incsLayerRef.current;
    if (!layer) return;
    layer.clearLayers();
    for (const inc of incidents) {
      if (!inc.position?.lat) continue;
      const sel = selectedType === 'incident' && selectedId === inc.id;
      const marker = L.marker([inc.position.lat, inc.position.lng], { icon: makeIncidentIcon(inc, sel) });
      marker.on('click', () => onSelect('incident', inc.id));
      marker.bindTooltip(
        `<b>${inc.id}</b> · ${inc.severity.toUpperCase()}<br>${inc.label}<br>${inc.patientCount} patients (${inc.redPatients}R ${inc.yellowPatients}Y ${inc.greenPatients}G)<br>Status: ${inc.status}`,
        { direction: 'top', className: 'rc-road-tip' }
      );
      layer.addLayer(marker);
    }
  }, [incidents, selectedType, selectedId, onSelect]);

  // ── Ambulances (canvas, imperative) ───────────────────────────────────────
  const handleAmbSelect = useCallback((id: string) => onSelect('ambulance', id), [onSelect]);

  useEffect(() => {
    ambLayerRef.current?.setData(
      ambulances,
      selectedType === 'ambulance' ? selectedId : null,
      handleAmbSelect,
      showIdleFleet
    );
  }, [ambulances, selectedType, selectedId, handleAmbSelect, showIdleFleet]);

  // ── Legend data ────────────────────────────────────────────────────────────
  const legend = [
    { label: 'Hospital',    color: '#10b981', shape: 'rect' },
    { label: 'Hospital (critical)', color: '#ef4444', shape: 'rect' },
    { label: 'Incident (red)',   color: '#ff4444', shape: 'circle' },
    { label: 'Incident (yellow)', color: '#ffd700', shape: 'circle' },
    { label: 'Amb — idle',       color: '#9ca3af', shape: 'dot' },
    { label: 'Amb — dispatched', color: '#38bdf8', shape: 'dot' },
    { label: 'Amb — en-route',   color: '#f97316', shape: 'dot' },
    { label: 'Amb — transporting', color: '#fbbf24', shape: 'dot' },
    { label: 'Route: amb→incident',  color: '#38bdf8', shape: 'dash' },
    { label: 'Route: incident→hosp', color: '#a78bfa', shape: 'dash' },
    { label: 'Route: alternate candidate', color: '#c084fc', shape: 'dash' },
    { label: 'Road: open',   color: ROAD_COLOR.open,    shape: 'line' },
    { label: 'Road: slow',   color: ROAD_COLOR.slow,    shape: 'line' },
    { label: 'Road: flooded', color: ROAD_COLOR.flooded, shape: 'line' },
    { label: 'Road: blocked', color: ROAD_COLOR.blocked, shape: 'line' },
  ];

  return (
    <div style={{ position: 'relative', width: '100%', height: '100%' }}>
      {/* Map container — must have explicit height */}
      <div ref={containerRef} style={{ width: '100%', height: '100%' }} />

      {/* Top Map Action Toolbar */}
      <div style={{
        position: 'absolute', top: 10, right: 10, zIndex: 1000,
        display: 'flex', alignItems: 'center', gap: 6,
      }}>
        <button
          onClick={() => setShowAlternates(v => !v)}
          style={{
            fontSize: 10, padding: '4px 10px', borderRadius: 16,
            border: `1px solid ${showAlternates ? '#c084fc' : 'var(--border)'}`,
            background: showAlternates ? 'rgba(192,132,252,0.25)' : 'rgba(10,14,20,0.85)',
            color: showAlternates ? '#f3e8ff' : '#94a3b8',
            cursor: 'pointer', fontFamily: 'monospace', fontWeight: 600,
            display: 'flex', alignItems: 'center', gap: 5, backdropFilter: 'blur(8px)',
          }}
          title="Toggle display of candidate alternate routes evaluated by the solver"
        >
          <span style={{ color: showAlternates ? '#c084fc' : '#64748b' }}>{showAlternates ? '●' : '○'}</span>
          <span>Alternate Paths</span>
        </button>

        <button
          onClick={() => setShowIdleFleet(v => !v)}
          style={{
            fontSize: 10, padding: '4px 10px', borderRadius: 16,
            border: `1px solid ${showIdleFleet ? '#60a5fa' : 'var(--border)'}`,
            background: showIdleFleet ? 'rgba(59,130,246,0.25)' : 'rgba(10,14,20,0.85)',
            color: showIdleFleet ? '#dbeafe' : '#94a3b8',
            cursor: 'pointer', fontFamily: 'monospace', fontWeight: 600,
            display: 'flex', alignItems: 'center', gap: 5, backdropFilter: 'blur(8px)',
          }}
          title="Toggle visibility of idle ambulances stationed at hospital bases"
        >
          <span style={{ color: showIdleFleet ? '#60a5fa' : '#64748b' }}>{showIdleFleet ? '●' : '○'}</span>
          <span>Idle Bases ({ambulances.filter(a => a.status === 'idle').length})</span>
        </button>
      </div>

      {/* Tile status chip */}
      <div style={{
        position: 'absolute', bottom: 8, left: 8, zIndex: 1000,
        fontSize: 9, padding: '3px 8px', borderRadius: 12,
        border: '1px solid var(--border)',
        background: 'var(--bg-secondary)', color: 'var(--text-muted)',
        fontFamily: 'monospace',
      }}>
        Tiles: {tileSource}
      </div>

      {/* Sim time */}
      <div style={{
        position: 'absolute', top: 10, left: 10, zIndex: 1000,
        fontSize: 10, padding: '3px 8px', borderRadius: 4,
        border: '1px solid var(--border)',
        background: 'rgba(10,14,20,0.85)', color: '#e4e7ec',
        fontFamily: 'monospace',
      }}>
        T+{Math.floor(simTime)}:{String(Math.floor((simTime % 1) * 60)).padStart(2, '0')}
      </div>

      {/* Simulated data notice */}
      <div style={{
        position: 'absolute', top: 10, left: '50%', transform: 'translateX(-50%)', zIndex: 1000,
        fontSize: 9, padding: '3px 8px', borderRadius: 4,
        border: '1px solid #f59e0b44',
        background: 'rgba(245,158,11,0.12)', color: '#f59e0b',
        fontFamily: 'monospace',
      }}>
        ⚠ SIMULATED DATA — DEMONSTRATION ONLY
      </div>

      {/* Legend toggle */}
      <button
        onClick={() => setShowLegend(v => !v)}
        style={{
          position: 'absolute', bottom: 32, right: 8, zIndex: 1001,
          fontSize: 10, padding: '4px 8px', borderRadius: 4,
          border: '1px solid var(--border)',
          background: 'rgba(10,14,20,0.9)', color: '#e4e7ec',
          cursor: 'pointer', fontFamily: 'monospace',
        }}
      >
        {showLegend ? '▼ Legend' : '▲ Legend'}
      </button>

      {/* Legend panel */}
      {showLegend && (
        <div style={{
          position: 'absolute', bottom: 58, right: 8, zIndex: 1001,
          background: 'rgba(10,14,20,0.93)', border: '1px solid #1e2636',
          borderRadius: 8, padding: '10px 12px', minWidth: 190,
          boxShadow: '0 4px 20px rgba(0,0,0,0.5)',
        }}>
          <div style={{ fontSize: 10, fontWeight: 700, color: '#98a2b3', marginBottom: 8, letterSpacing: 1, textTransform: 'uppercase' }}>
            Map Legend
          </div>
          {legend.map(item => (
            <div key={item.label} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 5 }}>
              <LegendSwatch color={item.color} shape={item.shape as any} />
              <span style={{ fontSize: 10, color: '#e4e7ec' }}>{item.label}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Road drawing helper (shared between init and updates) ──────────────────────

function drawRoads(layer: L.LayerGroup, roads: Road[], geoRoads: GeoRoadFeature[]) {
  layer.clearLayers();

  // Build a condition map from backend roads: name → condition
  const condMap = new Map<string, string>();
  for (const r of roads) {
    const name = r.from && r.to ? `${r.from}-${r.to}` : '';
    if (name) condMap.set(name, r.condition ?? 'open');
    // also try from_area/to_area
    if (r.from_area && r.to_area) condMap.set(`${r.from_area}-${r.to_area}`, r.condition ?? 'open');
  }

  // Draw GeoJSON roads with backend conditions
  for (const feature of geoRoads) {
    if (feature.coords.length < 2) continue;

    // Lookup condition from backend state (fallback to GeoJSON's own condition)
    const cond = condMap.get(feature.name) ?? feature.condition ?? 'open';
    const color   = ROAD_COLOR[cond] ?? ROAD_COLOR.open;
    const weight  = ROAD_WEIGHT[cond] ?? 2;
    const opacity = ROAD_OPACITY[cond] ?? 0.55;
    const dash    = ROAD_DASH[cond];

    const isPrimary = feature.highway === 'primary';
    const line = L.polyline(feature.coords, {
      color,
      weight:  isPrimary ? weight + 0.5 : weight,
      opacity,
      dashArray: dash,
    });

    if (cond !== 'open') {
      line.bindTooltip(
        `<b>${feature.name}</b><br>⚠ ${cond.toUpperCase()}${feature.flood_prone ? ' · flood-prone' : ''}`,
        { permanent: false, direction: 'center', sticky: true, className: 'rc-road-tip' }
      );
    } else {
      line.bindTooltip(
        `${feature.name}`,
        { permanent: false, direction: 'center', sticky: true, className: 'rc-road-tip' }
      );
    }
    layer.addLayer(line);
  }

  // Also render any backend roads that have real fromPos/toPos coords
  // (these may not be in the GeoJSON — e.g. dynamically spawned roads)
  for (const r of roads) {
    const p1 = r.fromPos ?? (r as any).from_pos;
    const p2 = r.toPos   ?? (r as any).to_pos;
    if (!p1?.lat || !p2?.lat) continue;

    const cond = r.condition ?? 'open';
    const color   = ROAD_COLOR[cond] ?? ROAD_COLOR.open;
    const weight  = ROAD_WEIGHT[cond] ?? 2;
    const opacity = ROAD_OPACITY[cond] ?? 0.55;
    const dash    = ROAD_DASH[cond];

    let latlngs: [number, number][];
    if (r.geometry && r.geometry.length >= 2) {
      latlngs = r.geometry.map((pt: any) =>
        Array.isArray(pt) ? pt as [number, number] : [pt.lat, pt.lng] as [number, number]
      );
    } else {
      latlngs = [[p1.lat, p1.lng], [p2.lat, p2.lng]];
    }

    const line = L.polyline(latlngs, { color, weight, opacity, dashArray: dash });
    if (cond !== 'open') {
      line.bindTooltip(
        `<b>${r.from ?? r.from_area} → ${r.to ?? r.to_area}</b><br>⚠ ${cond.toUpperCase()}`,
        { direction: 'center', sticky: true, className: 'rc-road-tip' }
      );
    }
    layer.addLayer(line);
  }
}

// ── Legend swatch ──────────────────────────────────────────────────────────────

function LegendSwatch({ color, shape }: { color: string; shape: 'rect' | 'circle' | 'dot' | 'line' | 'dash' }) {
  if (shape === 'rect') {
    return (
      <div style={{
        width: 14, height: 14, borderRadius: 3,
        background: color + '33', border: `2px solid ${color}`,
        flexShrink: 0,
      }} />
    );
  }
  if (shape === 'circle') {
    return (
      <div style={{
        width: 14, height: 14, borderRadius: '50%',
        background: color + '44', border: `2px solid ${color}`,
        flexShrink: 0,
      }} />
    );
  }
  if (shape === 'dot') {
    return (
      <div style={{
        width: 10, height: 10, borderRadius: '50%',
        background: color + 'dd', border: '1px solid #fff',
        margin: '0 2px', flexShrink: 0,
      }} />
    );
  }
  // line / dash
  return (
    <svg width={20} height={10} style={{ flexShrink: 0 }}>
      <line
        x1={0} y1={5} x2={20} y2={5}
        stroke={color}
        strokeWidth={shape === 'dash' ? 1.5 : 2}
        strokeDasharray={shape === 'dash' ? '4,3' : undefined}
      />
    </svg>
  );
}

export const MapView = memo(MapViewInner);
