// "How recent is this?" helpers for job listings and profile data. Pure functions so they are easy to test.
const DAY = 86_400_000

export function daysSince(iso, now = Date.now()) {
  const when = Date.parse(iso)
  return Number.isNaN(when) ? null : Math.max(0, Math.floor((now - when) / DAY))
}

export function ago(iso, now = Date.now()) {
  const days = daysSince(iso, now)
  if (days === null) return 'date unknown'
  if (days === 0) return 'today'
  if (days === 1) return 'yesterday'
  if (days < 14) return `${days} days ago`
  if (days < 60) return `${Math.floor(days / 7)} weeks ago`
  if (days < 730) return `${Math.floor(days / 30)} months ago`
  return `${Math.floor(days / 365)} years ago`
}

export const isNew = (iso, now = Date.now(), days = 7) => {
  const age = daysSince(iso, now)
  return age !== null && age <= days
}
