'use client';
import { useEffect, useRef, useState } from 'react';
import type * as Leaflet from 'leaflet';
import { Crosshair, Globe2, Layers, MapPin, Minus, Plus, RefreshCw } from 'lucide-react';
import { inCoverage, type Facility, type Point } from '../lib/domain';
import { placeZoom } from '../lib/places';

type Props = { facilities: Facility[]; destination: Point; destinationName: string; destinationKind?: string; selectedId: string | null; onSelect: (id: string) => void; pinMode: boolean; onPin: (p: Point) => void; onPinMode: () => void };
export function ParkingMap(props: Props) {
  const div = useRef<HTMLDivElement>(null), map = useRef<Leaflet.Map | null>(null), L = useRef<typeof Leaflet | null>(null);
  const markers = useRef<Leaflet.LayerGroup | null>(null), base = useRef<Leaflet.LayerGroup | null>(null), tiles = useRef<Leaflet.TileLayer | null>(null);
  const current = useRef(props);
  useEffect(() => { current.current = props; }, [props]);
  const [ready, setReady] = useState(false), [street, setStreet] = useState(true), [failure, setFailure] = useState(false);
  useEffect(() => {
    let disposed = false; const controller = new AbortController(); let resize: ResizeObserver | undefined;
    import('leaflet').then(module => {
      if (disposed || !div.current) return;
      L.current = module;
      const m = module.map(div.current, { zoomControl: false, attributionControl: true, scrollWheelZoom: true, minZoom: 3, maxZoom: 19, maxBounds: [[4, 65], [40, 101]], maxBoundsViscosity: 0.8 }).setView([28.632, 77.2187], 16);
      map.current = m; m.attributionControl.setPrefix(false);
      m.attributionControl.addAttribution('© <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap contributors</a>');
      m.createPane('baseData'); m.getPane('baseData')!.style.zIndex = '190';
      base.current = module.layerGroup();
      markers.current = module.layerGroup().addTo(m);
      m.on('click', e => { if (current.current.pinMode) current.current.onPin({ lat: e.latlng.lat, lng: e.latlng.lng }); });
      resize = new ResizeObserver(() => m.invalidateSize()); resize.observe(div.current);
      setReady(true);
      void fetch('/data/connaught-place.geojson', { signal: controller.signal }).then(r => { if (!r.ok) throw new Error('map_data'); return r.json(); }).then(data => {
        if (disposed || !base.current) return;
        module.geoJSON(data as GeoJSON.GeoJsonObject, { pane: 'baseData', interactive: false, filter: f => f.geometry.type !== 'Point', style: f => {
          const p = f?.properties ?? {};
          return p.highway ? { color: '#fff', weight: p.highway === 'footway' ? 2 : 8 } : { color: '#d6d8cd', weight: 1, fillColor: p.leisure === 'park' || p.landuse === 'grass' ? '#d5dfc5' : p.amenity === 'parking' ? '#e4dfc5' : '#e2e3dc', fillOpacity: 1 };
        } }).addTo(base.current);
      }).catch(() => { /* Street tiles remain independent of the local CP data file. */ });
    }).catch(() => { if (!disposed) setFailure(true); });
    return () => { disposed = true; controller.abort(); resize?.disconnect(); map.current?.remove(); map.current = null; };
  }, []);

  useEffect(() => {
    if (!ready || !map.current || !L.current) return;
    const m = map.current;
    if (!street) { base.current?.addTo(m); return () => { base.current?.remove(); }; }
    base.current?.remove();
    const layer = L.current.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', { maxZoom: 19, keepBuffer: 1, updateWhenIdle: true });
    let failures = 0;
    layer.on('tileerror', () => { if (++failures >= 3) setFailure(true); });
    layer.addTo(m); tiles.current = layer;
    return () => { layer.off(); layer.remove(); tiles.current = null; };
  }, [ready, street]);

  useEffect(() => {
    if (!ready || !map.current || !L.current || !markers.current) return;
    const lib = L.current, group = markers.current; group.clearLayers();
    for (const [i, f] of props.facilities.entries()) {
      const selected = f.id === props.selectedId;
      lib.marker([f.point.lat, f.point.lng], { keyboard: true, title: f.name, alt: f.name, icon: lib.divIcon({ className: 'custom-marker', html: `<span class="parking-pin ${selected ? 'selected' : ''}"><b>P</b><span>${i + 1}</span></span>`, iconSize: [58, 40], iconAnchor: [29, 40] }) }).on('click', () => current.current.onSelect(f.id)).addTo(group);
    }
    lib.marker([props.destination.lat, props.destination.lng], { title: props.destinationName, icon: lib.divIcon({ className: 'custom-marker', html: '<span class="destination-pin"><span></span></span>', iconSize: [36, 36], iconAnchor: [18, 18] }) }).addTo(group);
    const selected = props.facilities.find(f => f.id === props.selectedId);
    if (selected) lib.polyline([[selected.point.lat, selected.point.lng], [props.destination.lat, props.destination.lng]], { color: '#1d4c47', weight: 2, dashArray: '4 7', interactive: false }).addTo(group);
  }, [ready, props.facilities, props.destination, props.destinationName, props.selectedId]);

  useEffect(() => {
    if (ready) map.current?.setView([props.destination.lat, props.destination.lng], placeZoom(props.destinationKind), { animate: false });
  }, [ready, props.destination.lat, props.destination.lng, props.destinationKind]);

  return <section className={`map-section ${props.pinMode ? 'pin-mode' : ''}`} aria-label="Parking and destination map">
    <div ref={div} className="parking-map" role="region" aria-label="Interactive India map. Parking locations are also available in the results list."/>
    {!ready && <div className="map-loading"><span className="spinner"/>Loading the map…</div>}
    <div className="map-top"><div className="map-location"><span className="small-dot"/><span className="map-place-name">{props.destinationName}</span></div><button className="map-button" onClick={() => { setStreet(v => !v); setFailure(false); }} disabled={!ready} aria-pressed={street}><Layers size={16}/>{street ? 'Street map on' : 'Load street map'}</button></div>
    <div className="map-controls"><button aria-label="Zoom in" onClick={() => map.current?.zoomIn()}><Plus size={18}/></button><button aria-label="Zoom out" onClick={() => map.current?.zoomOut()}><Minus size={18}/></button><button aria-label="Recenter on destination" onClick={() => map.current?.setView([props.destination.lat, props.destination.lng], placeZoom(props.destinationKind))}><Crosshair size={18}/></button><button aria-label="Show all India" title="Show all India" onClick={() => map.current?.fitBounds([[6, 68], [37.5, 97.5]], { padding: [30, 30] })}><Globe2 size={18}/></button></div>
    <button className={`map-pin-tool ${props.pinMode ? 'active' : ''}`} onClick={props.onPinMode}><MapPin size={16}/>{props.pinMode ? 'Tap the map to set destination' : 'Choose destination on map'}</button>
    <div className="map-legend"><span><i className="legend-parking">P</i> Parking</span><span><i className="legend-destination"/> Destination</span><span className="legend-line">Straight-line distance</span></div>
    {(failure || !street && !inCoverage(props.destination)) && <div className="map-notice" role="status">{failure ? 'Street tiles could not load. Your selected place and directions still work.' : 'Street map is off. Turn it on to view this area.'}<button className="text-button" onClick={() => { setFailure(false); if (!street) setStreet(true); else tiles.current?.redraw(); }}><RefreshCw size={12}/> {street ? 'Retry map' : 'Load map'}</button></div>}
  </section>;
}
