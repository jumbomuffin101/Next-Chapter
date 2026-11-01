import { useEffect, useState } from 'react'
import { fetchEvents } from '../api.js'

const KEY = 'tkh-events-interest'
const readInterest = () => { try { return new Set(JSON.parse(sessionStorage.getItem(KEY) ?? '[]')) } catch { return new Set() } }
const month = iso => new Date(`${iso}T12:00:00`).toLocaleDateString('en-US', { month: 'short' })
const day = iso => new Date(`${iso}T12:00:00`).getDate()
const weekday = iso => new Date(`${iso}T12:00:00`).toLocaleDateString('en-US', { weekday: 'long' })

function EventCard({ event, interested, onToggle }) {
  return <li className="event-card">
    <div className="date-block" aria-hidden="true"><b>{day(event.date)}</b><span>{month(event.date)}</span></div>
    <div className="what">
      <div className="tags"><span className="tag">{event.kind}</span>{event.for_you && <span className="tag green">For you</span>}<span className="tag sample">Sample</span></div>
      <strong>{event.title}</strong>
      <small>{weekday(event.date)} · {event.time} · {event.where}</small>
      <small>Hosted by {event.host}</small>
    </div>
    <button className={interested ? 'secondary-button' : 'primary-button'} aria-pressed={interested} onClick={() => onToggle(event.id)}>{interested ? '✓ Interested' : 'I’m interested'}</button>
  </li>
}

// Meetups and events near you. Sample data for the demo: tailored to your metro area and role type.
export default function Events() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [interest, setInterest] = useState(readInterest)
  useEffect(() => { fetchEvents().then(setData, err => setError(err.message)) }, [])
  const toggle = id => setInterest(previous => {
    const next = new Set(previous); if (next.has(id)) next.delete(id); else next.add(id)
    try { sessionStorage.setItem(KEY, JSON.stringify([...next])) } catch { /* storage unavailable: keep it in memory */ }
    return next
  })
  if (error) return <p className="stage-error">We couldn’t load events: {error}</p>
  if (!data) return <p className="panel-empty">Loading events…</p>
  return <div className="events">
    <p className="lede-note">{data.note} Events with <b>For you</b> match your role type.</p>
    <h3 className="block-title">{data.metro ? `Near you · ${data.metro}` : 'Near you'}</h3>
    {data.local.length ? <ul className="event-list">{data.local.map(e => <EventCard key={e.id} event={e} interested={interest.has(e.id)} onToggle={toggle} />)}</ul>
      : <p className="panel-empty">We don’t have local events for your city yet. Online events are below.</p>}
    <h3 className="block-title">Online</h3>
    <ul className="event-list">{data.online.map(e => <EventCard key={e.id} event={e} interested={interest.has(e.id)} onToggle={toggle} />)}</ul>
  </div>
}
