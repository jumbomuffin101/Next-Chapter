export function monthLabel(month) {
  if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(month ?? '')) return 'This month'
  return new Date(`${month}-01T12:00:00Z`).toLocaleDateString('en-US', {
    month: 'long', year: 'numeric', timeZone: 'UTC',
  })
}

export function safeOpportunityUrl(value) {
  try {
    const url = new URL(value)
    return ['https:', 'http:'].includes(url.protocol) && !url.username && !url.password ? url.href : null
  } catch { return null }
}
