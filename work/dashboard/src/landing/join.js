// Sign-up links: ?invite=<code> (an alum's personal invite link) or ?cohort=<year>&src=room (the in-room QR code).
// An invite wins over a cohort; the backend checks both.
export function readJoinParams(search) {
  const params = new URLSearchParams(search)
  const invite = (params.get('invite') ?? '').trim()
  const cohort = (params.get('cohort') ?? '').trim()
  if (invite) return { invite, cohort: null }
  return { invite: null, cohort: /^\d{4}$/.test(cohort) ? cohort : null }
}

export const inviteLink = (appUrl, code) => `${appUrl}/?invite=${encodeURIComponent(code)}`
export const roomLink = (appUrl, cohort) => `${appUrl}/?cohort=${encodeURIComponent(cohort)}&src=room`
