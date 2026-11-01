export const STORAGE_KEY = 'tkh-alumni-profile-v1'

export function emptyProfile() {
  return { full_name: '', email: '', phone: '', location: '', linkedin_url: '', education: [], work_experience: [], skills: [], certifications: [], warnings: [] }
}

export function normalizeProfile(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('The profile must be a JSON object.')
  const profile = emptyProfile()
  if (!Object.keys(profile).some(key => key in value)) throw new Error('No profile fields found. Import the parser output with fields such as full_name and work_experience.')
  const text = (value, field) => {
    if (value == null) return ''
    if (typeof value !== 'string') throw new Error(`${field} must be text.`)
    return value.trim()
  }
  for (const key of ['full_name', 'email', 'phone', 'location', 'linkedin_url']) profile[key] = text(value[key], key)
  for (const key of ['skills', 'certifications', 'warnings']) {
    if (value[key] == null) continue
    if (!Array.isArray(value[key])) throw new Error(`${key} must be a list.`)
    profile[key] = [...new Set(value[key].map(item => text(item, key)).filter(Boolean))]
  }
  const groups = [
    ['education', ['school', 'degree', 'field_of_study', 'start_date', 'end_date']],
    ['work_experience', ['employer', 'title', 'location', 'start_date', 'end_date', 'description']],
  ]
  for (const [key, fields] of groups) {
    if (value[key] == null) continue
    if (!Array.isArray(value[key])) throw new Error(`${key} must be a list.`)
    profile[key] = value[key].map((entry, index) => {
      if (!entry || typeof entry !== 'object' || Array.isArray(entry)) throw new Error(`${key} entry ${index + 1} must be an object.`)
      const record = Object.fromEntries(fields.map(field => [field, text(entry[field], `${key}.${field}`)]))
      if (key === 'work_experience') {
        if (entry.is_current != null && typeof entry.is_current !== 'boolean') throw new Error('is_current must be true or false.')
        record.is_current = entry.is_current ?? false
        if (record.is_current) record.end_date = ''
        // what the person earned in this role; both or neither, checked again by the server
        const pay = ['salary_min', 'salary_max'].map(field => (entry[field] == null || entry[field] === '' ? null : Number(entry[field])))
        if (pay.some(value => value !== null && (!Number.isInteger(value) || value <= 0))) throw new Error('Role salaries must be whole dollar amounts.')
        if ((pay[0] === null) !== (pay[1] === null)) throw new Error('Each role salary needs both a minimum and a maximum.')
        ;[record.salary_min, record.salary_max] = pay
      }
      return record
    })
  }
  return profile
}

// A parser result is a draft suggestion. Keep existing information visible for review.
export function mergeResumeDraft(existing, parsed) {
  const old = normalizeProfile(existing)
  const found = normalizeProfile(parsed)
  const unique = (items, key) => [...new Map(items.map(item => [key(item), item])).values()]
  const mergeRecords = (before, incoming, key) => {
    const records = new Map(before.map(item => [key(item), item]))
    for (const item of incoming) {
      const prior = records.get(key(item))
      records.set(key(item), prior ? {
        ...prior,
        ...Object.fromEntries(Object.entries(item).filter(([field, value]) => field !== 'is_current' && value)),
        ...(item.end_date ? { is_current: false } : prior.is_current ? { is_current: true } : {}),
      } : item)
    }
    return [...records.values()]
  }
  return {
    ...found,
    full_name: found.full_name || old.full_name,
    email: old.email || found.email,
    phone: found.phone || old.phone,
    location: found.location || old.location,
    linkedin_url: found.linkedin_url || old.linkedin_url,
    work_experience: mergeRecords(old.work_experience, found.work_experience,
      job => `${job.employer.trim().toLowerCase()}|${job.title.trim().toLowerCase()}|${job.start_date}`),
    education: mergeRecords(old.education, found.education,
      item => `${item.school.trim().toLowerCase()}|${item.degree.trim().toLowerCase()}|${item.end_date}`),
    skills: unique([...old.skills, ...found.skills], value => value.toLowerCase()),
    certifications: unique([...old.certifications, ...found.certifications], value => value.toLowerCase()),
  }
}

export function profileSections(profile) {
  return [
    { label: 'Contact details', complete: Boolean(profile.full_name && profile.email && profile.location) },
    { label: 'Work experience', complete: profile.work_experience.some(job => job.employer && job.title) },
    { label: 'Education', complete: profile.education.some(item => item.school) },
    { label: 'Skills', complete: profile.skills.length > 0 },
  ]
}

export function dateLabel(value) {
  if (!value) return 'Date not provided'
  if (/^\d{4}$/.test(value)) return value
  const date = new Date(`${value.slice(0, 7)}-01T12:00:00`)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString('en-US', { month: 'short', year: 'numeric' })
}

export function readSavedProfile() {
  try {
    const stored = sessionStorage.getItem(STORAGE_KEY)
    if (!stored) return { profile: emptyProfile(), savedAt: null }
    const parsed = JSON.parse(stored)
    return { profile: normalizeProfile(parsed.profile), savedAt: typeof parsed.savedAt === 'string' ? parsed.savedAt : null, cohort: parsed.cohort ?? null, salary: parsed.salary ?? null }
  } catch {
    return { profile: emptyProfile(), savedAt: null }
  }
}

// Shared by the profile editor dialog and the profile page
export function validateProfile(draft, skills, certifications) {
  const result = normalizeProfile({ ...draft, skills: skills.split(/[,\n]/), certifications: certifications.split('\n') })
  if (!result.full_name || !result.email) throw new Error('Add your full name and email before saving.')
  for (const job of result.work_experience) if (!job.employer || !job.title) throw new Error('Each work experience needs an employer and title. Remove any unused entries.')
  for (const entry of result.education) if (!entry.school) throw new Error('Each education entry needs a school. Remove any unused entries.')
  for (const entry of [...result.education, ...result.work_experience]) {
    for (const field of ['start_date', 'end_date']) {
      if (entry[field] && !/^\d{4}(-(0[1-9]|1[0-2])(-(0[1-9]|[12]\d|3[01]))?)?$/.test(entry[field])) throw new Error('Use YYYY, YYYY-MM, or YYYY-MM-DD for dates.')
    }
    if (entry.start_date && entry.end_date && entry.end_date < entry.start_date) throw new Error('An end date cannot come before its start date.')
  }
  return result
}

export function saveProfile(profile) {
  const next = { profile, savedAt: new Date().toISOString() }
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(next))
  return next
}

export function saveErrorMessage(err) {
  return err.name === 'QuotaExceededError' || err.name === 'SecurityError' ? 'Browser storage is unavailable. Your draft is still here; enable session storage before saving.' : err.message
}

// Onboarding ends by saving the cohort year (sign-up never sets it), so a saved cohort means it was finished.
// Not "has a role": a resume with no jobs would otherwise loop back to onboarding forever.
export const isOnboarded = saved => Boolean(saved.cohort)

// General annual salary ranges for the profile dropdown: [min, max] in whole dollars
export const SALARY_RANGES = [[25000, 40000], [40000, 60000], [60000, 80000], [80000, 100000],
  [100000, 125000], [125000, 150000], [150000, 200000], [200000, 300000]]
const dollars = value => `$${Math.round(value).toLocaleString('en-US')}`
export const salaryLabel = ({ min, max }) => (max >= 300000 && min >= 200000 ? `${dollars(min)}+` : `${dollars(min)} – ${dollars(max)}`)
export const rangeKey = salary => (salary ? `${salary.min}-${salary.max}` : '')
// The general range a dollar amount falls in (the top range catches everything above it)
export function rangeContaining(value) {
  const found = SALARY_RANGES.find(([min, max]) => value >= min && value < max) ?? (value >= 200000 ? SALARY_RANGES.at(-1) : SALARY_RANGES[0])
  return { min: found[0], max: found[1] }
}
