// Builds the email draft that opens in the person's own mail app. Nothing is sent from our server.
// A mailto: body is plain text, so the dashboard link appears as a URL (mail apps make it clickable).
const enc = encodeURIComponent

export function buildDraft({ toName, me = {}, appUrl }) {
  const first = (toName || '').trim().split(/\s+/)[0] || 'there'
  const who = [`I'm ${me.name || 'a fellow TKH alum'}`,
    me.cohort ? ` (TKH cohort ${me.cohort})` : '',
    me.title ? `, ${me.title}${me.employer ? ` at ${me.employer}` : ''}` : ''].join('')
  const body = [`Hi ${first},`, '', `${who}. I found you on the TKH alumni network and would love to connect.`, '',
    `Stay connected through TKH: ${appUrl}`].join('\n')
  return { subject: 'Connecting through TKH', body }
}

const crlf = text => text.replace(/\r?\n/g, '\r\n') // what mail apps expect inside a mailto: body

export function mailtoLink({ to, ...rest }) {
  const { subject, body } = buildDraft(rest)
  const address = to.trim().replace(/[^A-Za-z0-9@._+-]/g, ch => enc(ch))
  return `mailto:${address}?subject=${enc(subject)}&body=${enc(crlf(body))}`
}

export function gmailLink({ to, ...rest }) {
  const { subject, body } = buildDraft(rest)
  return `https://mail.google.com/mail/?view=cm&fs=1&to=${enc(to.trim())}&su=${enc(subject)}&body=${enc(body)}`
}

// Where "Stay connected through TKH" points: set VITE_APP_URL for a deployed site, else this page's address.
export const appUrl = () => import.meta.env?.VITE_APP_URL || (typeof window !== 'undefined' ? window.location.origin : '')
