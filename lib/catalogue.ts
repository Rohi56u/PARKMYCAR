import catalogue from '../data/source-catalog.json' with { type: 'json' };
import places from '../data/source-destinations.json' with { type: 'json' };
import type { Facility } from './domain.ts';
import type { Place } from './places.ts';
export const CATALOGUE_VERSION = 'cp-2026-10-17-v1';
export const initialFacilities: Facility[] = catalogue.facilities.map(f => ({
  id:f.id,name:f.name,area:'Connaught Place, New Delhi',nameKind:f.nameKind as Facility['nameKind'],
  point:{lat:f.coordinates.lat,lng:f.coordinates.lon},type:f.type as Facility['type'],
  access:f.access === 'yes' ? 'PUBLIC' : 'UNKNOWN', locationKind:'area_centroid', vehicles:[],features:[],hours:null,rate:null,
  entryNotes:'Follow the parking signs and access instructions at the site.',active:true,verification:'MAPPED',version:1,operatorId:null,
  sources:f.sources.map(s=>({name:s.label,url:s.url,fields:s.supports,checkedAt:s.retrievedAt,license:s.license})),
}));
export type Destination = Place;
export const destinations: Destination[] = places.map(p=>({ id:p.id,name:p.name.replace(' · ',' — '),subtitle:'Connaught Place, New Delhi',point:{lat:p.coordinates.lat,lng:p.coordinates.lon},sourceUrl:p.sourceUrl }));
