import { useEffect, useState } from 'react'
import { fetchMyInvite } from '../api.js'
import { inviteLink } from '../landing/join.js'
import { appUrl } from './mailto.js'

// Your personal invite link, made automatically. Classmates who sign up through it join your cohort.
export default function InviteCard() {
  const [invite, setInvite] = useState(null)
  const [error, setError] = useState('')
  const [copyError, setCopyError] = useState('')
  const [copied, setCopied] = useState(false)
  useEffect(() => { fetchMyInvite().then(setInvite, err => setError(err.message)) }, [])

  if (error) return <p className="stage-error" role="alert">We couldn’t load your invite link: {error}</p>
  if (!invite) return <p className="panel-empty">Loading your invite link…</p>
  const link = inviteLink(appUrl(), invite.code)
  async function copy() {
    try { await navigator.clipboard.writeText(link); setCopied(true); setTimeout(() => setCopied(false), 1500) }
    catch { setCopyError('Could not copy. Select the link and copy it by hand.') }
  }
  return <section className="invite-card" aria-label="Your invite link">
    <span className="eyebrow">Your invite link</span>
    <p>Share it with TKH classmates who aren’t here yet. When they sign up through it, they join your cohort and you both show up in each other’s network.</p>
    <button type="button" className="copy" onClick={copy} title="Copy your invite link">{copied ? 'Copied!' : link}</button>
    <small>{invite.joined === 1 ? '1 person has' : `${invite.joined} people have`} joined through your link.</small>
    {copyError && <p className="stage-error" role="alert">{copyError}</p>}
  </section>
}
