import assert from 'node:assert/strict'
import test from 'node:test'
import { buildDraft, gmailLink, mailtoLink } from './mailto.js'

const me = { name: 'Rittrija Mandal', cohort: '2024', title: 'Software Engineer', employer: 'Acme Corp' }
const APP = 'https://tkh.example/app'
const parts = link => { const [head, query] = link.split('?'); const q = new URLSearchParams(query); return { head, subject: q.get('subject') ?? q.get('su'), body: q.get('body') } }

test('draft greets by first name, introduces the sender and ends with the TKH line and link', () => {
  const { subject, body } = buildDraft({ toName: 'Casey Colleague', me, appUrl: APP })
  assert.equal(subject, 'Connecting through TKH')
  assert.match(body, /^Hi Casey,/)
  assert.match(body, /I'm Rittrija Mandal \(TKH cohort 2024\), Software Engineer at Acme Corp\./)
  assert.ok(body.trimEnd().endsWith(`Stay connected through TKH: ${APP}`))
})

test('mailto link puts the recipient in the To field and round-trips the text exactly', () => {
  const link = mailtoLink({ to: 'casey.c+tkh@example.com', toName: 'Casey Colleague', me, appUrl: APP })
  const { head, subject, body } = parts(link)
  assert.equal(head, 'mailto:casey.c+tkh@example.com')   // '+' and '@' stay readable
  assert.equal(subject, 'Connecting through TKH')
  assert.ok(body.includes('\r\n'))                         // mail-app line breaks
  assert.ok(body.replace(/\r\n/g, '\n').endsWith(`Stay connected through TKH: ${APP}`))
})

test('names with apostrophes, accents and symbols survive encoding', () => {
  const link = mailtoLink({ to: 'jose@example.com', toName: "José O'Brien & Co", me: { name: "Zoë D'Souza" }, appUrl: APP })
  const { body } = parts(link)
  assert.match(body, /^Hi José,/)
  assert.match(body, /I'm Zoë D'Souza\./)
  assert.ok(!link.includes(' ') && !link.includes('&body=Hi José'))  // nothing unescaped in the URL
})

test('an address with odd characters cannot inject extra mailto fields', () => {
  const { head } = parts(mailtoLink({ to: 'a@b.com?cc=evil@x.com&bcc=x', toName: 'X', me, appUrl: APP }))
  assert.ok(!head.includes('?') && !head.includes('&'))
})

test('missing details fall back gracefully', () => {
  const { body } = buildDraft({ toName: '', me: {}, appUrl: APP })
  assert.match(body, /^Hi there,/)
  assert.match(body, /I'm a fellow TKH alum\./)
})

test('gmail link opens a compose window with the same draft', () => {
  const link = gmailLink({ to: 'casey@example.com', toName: 'Casey Colleague', me, appUrl: APP })
  assert.ok(link.startsWith('https://mail.google.com/mail/?view=cm'))
  const { subject, body } = parts(link)
  assert.equal(subject, 'Connecting through TKH')
  assert.ok(body.endsWith(`Stay connected through TKH: ${APP}`))
  assert.equal(new URL(link).searchParams.get('to'), 'casey@example.com')
})
