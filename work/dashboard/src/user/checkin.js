// Remembers each alumnus's last check-in answer in this browser, so the card doesn't ask again for a while.
export const ASK_EVERY_DAYS = 30
const key = alumniId => `tkh-checkin-${alumniId}`

export function readCheckIn(alumniId) {
  try { return JSON.parse(localStorage.getItem(key(alumniId))) } catch { return null } // { answer, at } or null
}

export function saveCheckIn(alumniId, answer, now = new Date()) {
  try { localStorage.setItem(key(alumniId), JSON.stringify({ answer, at: now.toISOString() })) } catch { /* storage blocked: it will just ask again */ }
}

// Ask unless they answered, or updated their profile, within the last ASK_EVERY_DAYS days.
export function shouldAskCheckIn({ lastAnswer, savedAt, now = Date.now(), days = ASK_EVERY_DAYS }) {
  const recent = when => Boolean(when) && !Number.isNaN(Date.parse(when)) && now - Date.parse(when) < days * 86400000
  return !recent(lastAnswer?.at) && !recent(savedAt)
}
