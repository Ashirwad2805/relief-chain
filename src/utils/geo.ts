import type { GeoPoint } from '@/types';

export const MUMBAI_AREAS: Record<string, GeoPoint> = {
  'Andheri': { lat: 19.1197, lng: 72.8468 },
  'Sion': { lat: 19.0760, lng: 72.8530 },
  'Hindmata': { lat: 19.0730, lng: 72.8360 },
  'Milan Subway': { lat: 19.1030, lng: 72.8410 },
  'Sion Circle': { lat: 19.0758, lng: 72.8535 },
  'Bandra': { lat: 19.0690, lng: 72.8390 },
  'Dadar': { lat: 19.0850, lng: 72.8430 },
  'Kurla': { lat: 19.0720, lng: 72.8780 },
  'Juhu': { lat: 19.1070, lng: 72.8380 },
  'Worli': { lat: 19.0170, lng: 72.8230 },
  'Parel': { lat: 19.0080, lng: 72.8370 },
  'Byculla': { lat: 18.9780, lng: 72.8340 },
  'Chembur': { lat: 19.0620, lng: 72.8990 },
  'Ghatkopar': { lat: 19.0860, lng: 72.9080 },
  'Vile Parle': { lat: 19.0990, lng: 72.8440 },
  'Santacruz': { lat: 19.0840, lng: 72.8410 },
  'Mahim': { lat: 19.0350, lng: 72.8400 },
  'Colaba': { lat: 18.9067, lng: 72.8147 },
};

export function haversine(p1: GeoPoint, p2: GeoPoint): number {
  const R = 6371.0;
  const dlat = ((p2.lat - p1.lat) * Math.PI) / 180;
  const dlon = ((p2.lng - p1.lng) * Math.PI) / 180;
  const a =
    Math.sin(dlat / 2) ** 2 +
    Math.cos((p1.lat * Math.PI) / 180) *
      Math.cos((p2.lat * Math.PI) / 180) *
      Math.sin(dlon / 2) ** 2;
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return Math.round(R * c * 100) / 100;
}
