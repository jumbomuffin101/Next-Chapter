import Panel from './Panel.jsx'
import { MAP_H, MAP_W, OUTLINE_PATH, project } from './geo.js'

// Where alumni live: a bubble per city on a simple US map. Cities we have no coordinates for are listed, not guessed.
export default function MapPanel({ locations }) {
  const placed = locations.filter(place => place.lat != null)
  const unplaced = locations.filter(place => place.lat == null)
  const biggest = Math.max(...locations.map(place => place.alumni), 1)
  return <Panel collapsible title="Where alumni live" caption={locations.length ? `${locations.length} ${locations.length === 1 ? 'city' : 'cities'}` : 'No locations yet'} className="square">
    {locations.length === 0 ? <p className="panel-empty">No cities on record for this cohort yet.</p> : <>
      <svg className="map" viewBox={`0 0 ${MAP_W} ${MAP_H}`} role="img" aria-label="Map of alumni locations">
        <path d={OUTLINE_PATH} className="land" />
        {placed.map(place => { const [px, py] = project(place.lat, place.lng); const r = 7 + Math.sqrt(place.alumni / biggest) * 20
          return <g key={place.city}>
            <circle cx={px} cy={py} r={r} className="bubble"><title>{`${place.city}: ${place.alumni} alumni`}</title></circle>
            {place.alumni >= Math.max(2, biggest * 0.4) && <text x={px + r + 5} y={py + 4}>{place.city} · {place.alumni}</text>}
          </g> })}
      </svg>
      <ul className="city-list">{locations.map(place => <li key={place.city}><b>{place.city}</b> {place.alumni}</li>)}</ul>
      {unplaced.length > 0 && <p className="map-note">Not shown on the map: {unplaced.map(place => `${place.city} (${place.alumni})`).join(', ')}</p>}
    </>}
  </Panel>
}
