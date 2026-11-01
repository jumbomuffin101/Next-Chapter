// Talks to the TKH backend (FastAPI). Point it elsewhere with VITE_API_URL (e.g. in .env.local).
import { STORAGE_KEY } from './user/profile.js'

// Default: the backend on the same machine the page came from (port 8000), so a phone that opened the page
// from this computer's network address also reaches the API. VITE_API_URL overrides it.
const BASE = import.meta.env.VITE_API_URL || `${window.location.protocol}//${window.location.hostname}:8000`
const ID_KEY = 'tkh-alumni-id'
const ADMIN_KEY = 'tkh-admin-token'
const NEWSLETTER_KEY = 'tkh-newsletter-demo-token'
const DEMO_CONSENT_KEY = 'tkh-newsletter-synthetic-consent'

export const getAlumniId = () => sessionStorage.getItem(ID_KEY)
export const getAdminToken = () => sessionStorage.getItem(ADMIN_KEY)
export const getNewsletterToken = () => sessionStorage.getItem(NEWSLETTER_KEY)
export const getDemoNewsletterConsent = () => sessionStorage.getItem(DEMO_CONSENT_KEY) === 'yes'
export const setDemoNewsletterConsent = () => sessionStorage.setItem(DEMO_CONSENT_KEY, 'yes')

// Who is signed in on this tab: { role: 'admin' } | { role: 'alumni', id } | null
export function getSession() {
  if (getAdminToken()) return { role: 'admin' }
  if (getAlumniId()) return { role: 'alumni', id: getAlumniId() }
  return null
}

export function clearSession() {
  sessionStorage.removeItem(ID_KEY)
  sessionStorage.removeItem(ADMIN_KEY)
  sessionStorage.removeItem(NEWSLETTER_KEY)
  sessionStorage.removeItem(DEMO_CONSENT_KEY)
  sessionStorage.removeItem(STORAGE_KEY)
}

async function request(path, options = {}) {
  const token = getAdminToken()
  const headers = { ...(options.headers ?? {}), ...(token ? { Authorization: `Bearer ${token}` } : {}) }
  let response
  try { response = await fetch(BASE + path, { ...options, headers }) }
  catch { throw new Error('Cannot reach the TKH server. Check that the backend is running.') }
  if (!response.ok) {
    let detail
    try { detail = (await response.json()).detail } catch { /* not JSON */ }
    // FastAPI: domain errors are a string; field validation errors are a list of {loc, msg}
    const message = typeof detail === 'string' ? detail
      : Array.isArray(detail) && detail.length ? detail.map(item => `${(item.loc ?? []).slice(1).join(' › ') || 'Request'}: ${item.msg}`).join('; ')
      : `The server could not process this (error ${response.status}).`
    throw Object.assign(new Error(message), { status: response.status })
  }
  return response.json()
}

const json = body => ({ method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) })

// Backend profile -> the shape the profile form uses (same as the parser output)
function toFrontendProfile(p) {
  const text = value => value ?? ''
  return {
    full_name: text(p.full_name), email: text(p.email), phone: text(p.phone), location: text(p.city),
    education: p.education.map(e => ({
      school: e.school, degree: text(e.degree), field_of_study: text(e.field_of_study),
      start_date: e.start_year ? String(e.start_year) : '', end_date: e.graduation_year ? String(e.graduation_year) : '',
    })),
    work_experience: p.work_experiences.map(w => ({
      employer: w.employer, title: w.title, location: text(w.location),
      start_date: text(w.start_date), end_date: w.is_current ? '' : text(w.end_date),
      is_current: w.is_current, description: text(w.description),
      salary_min: w.salary_min ?? null, salary_max: w.salary_max ?? null,
    })),
    skills: p.skills, certifications: p.certifications, warnings: [],
  }
}

// Loads the saved profile from the server into the tab's cache (what the profile screens read)
export async function refreshProfile() {
  const saved = await request(`/profiles/${getAlumniId()}`)
  const profile = toFrontendProfile(saved)
  const hasContent = Boolean(profile.full_name || profile.work_experience.length)
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify({ profile, savedAt: hasContent ? saved.last_updated_at : null, cohort: saved.cohort ?? null,
    salary: saved.salary_min != null && saved.salary_max != null ? { min: saved.salary_min, max: saved.salary_max } : null }))
  return profile
}

// Admin demo login: the backend returns a signed token that the admin endpoints require
export async function adminLogin(email, password) {
  const { token } = await request('/auth/admin/login', json({ email, password }))
  clearSession()
  sessionStorage.setItem(ADMIN_KEY, token)
}

// Alumni sign in / create profile (email only, a stub): the backend looks the profile up or creates it.
// invite: code from an alum's invite link (joins their cohort); cohort: from the in-room QR code
export async function alumniEnter(mode, { email, fullName, invite = null, cohort = null }) {
  const user = await request(mode === 'signup' ? '/auth/alumni/signup' : '/auth/alumni/login',
    json(mode === 'signup' ? { email, full_name: fullName, ...(invite ? { invite } : {}), ...(cohort ? { cohort } : {}) } : { email }))
  clearSession()
  sessionStorage.setItem(ID_KEY, user.id)
  if (user.newsletter_token) sessionStorage.setItem(NEWSLETTER_KEY, user.newsletter_token)
  await refreshProfile()
  return user
}

export function parseResume(file) {
  const form = new FormData()
  form.append('file', file)
  return request('/resume/parse', { method: 'POST', body: form })
}

// salary is optional: { min, max } as whole annual dollars, or null.
// replace: true when the form showed the whole profile (editor, profile page), so removed or cleared items are removed;
// leave it off for a resume upload, which merges and keeps roles the resume leaves out.
export const confirmProfile = (profile, salary = null, { replace = false } = {}) => request(`/resume/confirm/${getAlumniId()}`,
  json({ resume: profile, ...(salary ? { salary_min: salary.min, salary_max: salary.max } : {}), ...(replace ? { replace: true } : {}) }))

// What BLS says people in the closest occupation typically earn: { matched, occupation, p25, median, p75, year, area }
export const fetchSalaryEstimate = title => request(`/salary/estimate?title=${encodeURIComponent(title)}`)

export const setCohort = year => request(`/profiles/${getAlumniId()}/cohort`, json({ cohort: String(year) }))
export const fetchGrowth = () => request(`/profiles/${getAlumniId()}/growth`)
// A salary range for a month ('YYYY-MM'), past or current; saving a month again replaces it. Both return the growth data.
export const addSalary = ({ min, max, month }) => request(`/profiles/${getAlumniId()}/salary`, json({ salary_min: min, salary_max: max, month }))
export const removeSalary = month => request(`/profiles/${getAlumniId()}/salary/${month}`, { method: 'DELETE' })
// Which job a month's salary was for (null clears it); returns the growth data
export const setSalaryJob = (month, jobId) => request(`/profiles/${getAlumniId()}/salary/${month}/job`,
  { ...json({ work_experience_id: jobId }), method: 'PUT' })

// -> { matches: [...with updated_at], refreshed_at, matched_on }
// 404 just means "no resume uploaded yet", so there is nothing to match: show the empty state, not an error
export const fetchMatches = () => request(`/users/${getAlumniId()}/job-matches?limit=20`).then(
  data => data,
  err => { if (err.status === 404) return { matches: [], refreshed_at: null, matched_on: null }; throw err },
)

// ---- Admin (all need the admin token) ----
// cohort: 'current' | 'next' | 'all' | a year like '2024'
export const fetchAdminDashboard = cohort => request(`/admin/dashboard?cohort=${encodeURIComponent(cohort)}`)
// Employment and pay by years since graduation; cohort: 'all' or a graduation year
export const fetchOutcomes = cohort => request(`/admin/outcomes?cohort=${encodeURIComponent(cohort)}`)
// shortcut: first 100 people only; page with offset if a cohort grows past that
export const fetchCohortPeople = cohort => request(`/profiles?cohort=${encodeURIComponent(cohort)}&limit=100`).then(data => data.items)

export function fetchActions({ cohort = 'all', flag = '', status = 'open', city = '', q = '' } = {}) {
  const params = new URLSearchParams({ cohort, status })
  if (flag) params.set('flag', flag)
  if (city) params.set('city', city)
  if (q.trim()) params.set('q', q.trim())
  return request(`/admin/actions?${params}`)
}

// Follow-up on an alumnus: status is 'open' | 'contacted' | 'resolved', plus an optional note
export const recordAction = (alumniId, { status, note }) => request(`/admin/actions/${alumniId}`, json({ status, note: note || null }))

// ---- Alumni asking the career team for help ----
export const requestSupport = message => request(`/profiles/${getAlumniId()}/support`, json({ message: message || null }))
export const fetchSupport = () => request(`/profiles/${getAlumniId()}/support`)

// ---- Alumni network, certifications, events ----
export const fetchPeers = (scope = 'all') => request(`/profiles/${getAlumniId()}/network/peers?scope=${scope}`)
export const fetchEvents = () => request(`/profiles/${getAlumniId()}/events`)
export const fetchRecommendations = () => request(`/profiles/${getAlumniId()}/recommendations`)

// Newsletter consent is separate from profile editing and networking.
export const fetchNewsletterPreference = () => request('/newsletter/preferences', {
  headers: { Authorization: `Bearer ${getNewsletterToken() || ''}` },
})
export const updateNewsletterPreference = subscribed => request('/newsletter/preferences', {
  ...json({ subscribed }), method: 'PUT',
  headers: { 'content-type': 'application/json', Authorization: `Bearer ${getNewsletterToken() || ''}` },
})
export const fetchCurrentNewsletter = () => request('/newsletter/current', {
  headers: { Authorization: `Bearer ${getNewsletterToken() || ''}` },
  cache: 'no-store',
})
export const generateDemoNewsletter = profile => request('/newsletter/demo', {
  ...json(profile), cache: 'no-store',
})
// ---- Invite links and the in-room QR code ----
// -> { code, joined }: your own invite code and how many people joined through it
export const fetchMyInvite = () => request(`/profiles/${getAlumniId()}/invite`)
// -> { inviter_first_name, cohort } for the sign-up page; 404 for an unknown code
export const fetchInvite = code => request(`/invites/${encodeURIComponent(code)}`)

// ---- Admin automation: peer invite emails (logged, not sent), the monthly newsletter, event QR codes ----
export const fetchAutomation = () => request('/admin/automation')
export const setAutoEmails = enabled => request('/admin/automation/emails', json({ enabled }))
export const setMonthlyNewsletter = enabled => request('/admin/automation/newsletter', json({ enabled }))
// -> { name, month, mode, status } for one alum (demo accounts who opted in)
export const sendNewsletterToOne = email => request('/admin/automation/newsletter/send', json({ email }))
