'use client';

import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react';
import { ArrowRight, ExternalLink, MapPin, Search, X } from 'lucide-react';
import { api } from '../lib/client';
import { coordinatePlace, mapsSearchUrl, normalizePlaceQuery, type Place } from '../lib/places';

export type PlaceSearchHandle = { resolve: () => Promise<Place | null> };
type Props = {
  id: string;
  label: string;
  value: string;
  selected: Place | null;
  quickPlaces: Place[];
  onChange: (value: string) => void;
  onSelect: (place: Place) => void;
  placeholder?: string;
};

/** Provider lookups happen only on Enter or a search button, never per keystroke. */
export const PlaceSearch = forwardRef<PlaceSearchHandle, Props>(function PlaceSearch(props, ref) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [remote, setRemote] = useState<{ query: string; places: Place[] } | null>(null);
  const [index, setIndex] = useState(-1);
  const input = useRef<HTMLInputElement>(null);
  const request = useRef<AbortController | null>(null);
  const generation = useRef(0);
  const latestValue = useRef(props.value);
  useEffect(() => { latestValue.current = props.value; }, [props.value]);
  useEffect(() => () => { generation.current++; request.current?.abort(); }, []);

  const query = normalizePlaceQuery(props.value);
  const fromProvider = remote?.query === query;
  const options = fromProvider ? remote.places : props.quickPlaces.filter(p => !query || `${p.name} ${p.subtitle}`.toLocaleLowerCase().includes(query.toLocaleLowerCase()));

  function change(value: string) {
    generation.current++;
    request.current?.abort();
    latestValue.current = value;
    setBusy(false); setError(''); setRemote(null); setIndex(-1); setOpen(true);
    props.onChange(value);
  }
  function pick(place: Place) {
    generation.current++; request.current?.abort();
    setBusy(false); setOpen(false); setError(''); setIndex(-1);
    props.onSelect(place);
  }
  async function resolve(): Promise<Place | null> {
    const term = normalizePlaceQuery(props.value);
    if (props.selected && term === normalizePlaceQuery(props.selected.name)) return props.selected;
    const coordinate = coordinatePlace(term);
    if (coordinate) return coordinate;
    const exact = props.quickPlaces.filter(p => normalizePlaceQuery(p.name).toLocaleLowerCase() === term.toLocaleLowerCase());
    if (exact.length === 1) return exact[0];
    setOpen(true); input.current?.focus();
    if (term.length < 2 || term.length > 160) { setError('Enter a place or address using 2–160 characters.'); return null; }
    if (remote?.query === term && remote.places.length) {
      if (remote.places.length === 1) return remote.places[0];
      setIndex(-1); return null;
    }
    const id = ++generation.current;
    request.current?.abort();
    const controller = new AbortController(); request.current = controller;
    setBusy(true); setError(''); setIndex(-1);
    try {
      const data = await api<{ places: Place[] }>('places/search', { query: term }, 'POST', controller.signal);
      if (id !== generation.current || normalizePlaceQuery(latestValue.current) !== term) return null;
      setRemote({ query: term, places: data.places });
      if (data.places.length === 1) return data.places[0];
      return null;
    } catch (e) {
      if (id === generation.current && e instanceof Error && e.name !== 'AbortError') setError(e.message);
      return null;
    } finally { if (id === generation.current) setBusy(false); }
  }
  useImperativeHandle(ref, () => ({ resolve }));
  async function search() { const result = await resolve(); if (result) pick(result); }

  return <div className="field-inner place-search" onBlur={e => { if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setOpen(false); }}>
    <label htmlFor={props.id}>{props.label}</label>
    <div className="place-input-row">
      <input ref={input} id={props.id} value={props.value} placeholder={props.placeholder ?? 'City, village, landmark or address'}
        autoComplete="off" spellCheck={false} maxLength={160} role="combobox" aria-autocomplete="list"
        aria-expanded={open} aria-controls={`${props.id}-options`} aria-describedby={`${props.id}-help`}
        aria-activedescendant={open && index >= 0 && options[index] ? `${props.id}-option-${index}` : undefined}
        onFocus={() => setOpen(true)} onChange={e => change(e.target.value)}
        onKeyDown={e => {
          if (e.nativeEvent.isComposing) return;
          if (e.key === 'ArrowDown') { e.preventDefault(); setOpen(true); setIndex(i => Math.min(i + 1, options.length - 1)); }
          if (e.key === 'ArrowUp') { e.preventDefault(); setIndex(i => Math.max(0, i - 1)); }
          if (e.key === 'Escape') { setOpen(false); setIndex(-1); }
          if (e.key === 'Enter') { e.preventDefault(); if (open && index >= 0 && options[index]) pick(options[index]); else void search(); }
        }} />
      {props.value && <button type="button" className="clear-query" aria-label={`Clear ${props.label.toLowerCase()}`} onClick={() => { change(''); input.current?.focus(); }}><X size={15}/></button>}
    </div>
    <span className="sr-only" id={`${props.id}-help`}>Type a place, then press Enter or Search India. Choose a result using the arrow keys and Enter.</span>
    {open && <div className="suggestions place-suggestions">
      <div className="place-search-heading"><span className="suggestion-caption">{fromProvider ? 'PLACES IN INDIA' : 'SEARCH ACROSS INDIA'}</span><button type="button" aria-label="Close place suggestions" className="icon-button" onClick={() => setOpen(false)}><X size={14}/></button></div>
      <button type="button" className="search-india-button" disabled={busy || query.length < 2} onClick={() => void search()}><Search size={16}/><span>{busy ? 'Searching places…' : `Search India${query ? ` for “${query}”` : ''}`}</span>{busy ? <span className="spinner"/> : <ArrowRight size={15}/>}</button>
      <div className="place-result-status" role="status" aria-live="polite">
        {error || (busy ? 'Looking up real map records…' : fromProvider ? options.length ? 'Choose the correct place and area below.' : 'No match found. Add the district or state, or choose a point on the map.' : options.length ? 'Quick picks from the parking directory' : 'Search cities, villages, localities, roads and landmarks. For small places, add the district or state.')}
      </div>
      <div id={`${props.id}-options`} role="listbox" aria-label={`${props.label} matches`} className="place-options">
        {!busy && options.map((place, i) => <button type="button" id={`${props.id}-option-${i}`} key={place.id} role="option" aria-selected={index === i} onMouseEnter={() => setIndex(i)} onClick={() => pick(place)}><MapPin size={17}/><span><b>{place.name}</b><small>{place.subtitle}</small></span><ArrowRight size={14}/></button>)}
      </div>
      {(error || fromProvider && !options.length) && query.length >= 2 && <a className="place-fallback" href={mapsSearchUrl(query)} target="_blank" rel="noreferrer">Look up this place in Google Maps <ExternalLink size={13}/></a>}
      <div className="place-attribution">Place data: <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noreferrer">OpenStreetMap</a> · Search by <a href="https://photon.komoot.io" target="_blank" rel="noreferrer">Photon</a></div>
    </div>}
  </div>;
});
