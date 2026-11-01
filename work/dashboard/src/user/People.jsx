import { useEffect, useState } from 'react'
import Icon from '../components/Icon.jsx'
import { fetchPeers } from '../api.js'
import InviteCard from './InviteCard.jsx'
import { appUrl, gmailLink } from './mailto.js'
import { readSavedProfile } from './profile.js'

// Only ever link to linkedin.com over https (the server already checks, this is a second guard against a bad link).
const linkedinHref = person => (/^https:\/\/([a-z]{2,3}\.)?linkedin\.com\//i.test(person.linkedin_url ?? '') ? person.linkedin_url : null)

const SCOPES = [['all', 'All'], ['company', 'Same company'], ['city', 'Nearby, same field'], ['role', 'Same field']]

// Alumni in your field. Contact is by email (opens a prefilled draft in your own mail app) or LinkedIn when it was on their resume.
export default function People() {
  const [scope, setScope] = useState('all')
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const { profile, cohort } = readSavedProfile()

  useEffect(() => { fetchPeers(scope).then(setData, err => setError(err.message)) }, [scope])

  const me = { name: profile.full_name, cohort, title: data?.me?.title, employer: data?.me?.employer }
  return <div className="people">
    <header className="tab-intro">
      <p>Every TKH alum is in the network automatically. Reach out to people in your field for advice, referrals or a coffee. They can find you too.</p>
    </header>
    <InviteCard />
    {error && <p className="stage-error" role="alert">{error}</p>}
    {data && !data.has_role && <p className="panel-empty">Add your current role to see alumni in your field.</p>}
    {data && data.has_role && <>
      <div className="chips" role="group" aria-label="Filter alumni">
        {SCOPES.map(([key, label]) => <button key={key} aria-pressed={scope === key} onClick={() => setScope(key)}>{label}<b>{data.counts[key]}</b></button>)}
      </div>
      <p className="lede-note">Showing alumni in <b>{data.my_role_type}</b>{data.me.city ? <> near <b>{data.me.city}</b></> : null}. </p>
      {data.items.length === 0 && <p className="panel-empty">No one matches yet. As more alumni join the network they’ll appear here.</p>}
      <ul className="people-grid">{data.items.map(person => {
        const draft = { to: person.email, toName: person.name, me, appUrl: appUrl() }
        return <li className="person-card" key={person.id}>
          <div className="who"><strong>{person.name}{person.just_joined && <span className="tag green just-joined">Just joined</span>}</strong>
            <span>{person.title}{person.employer ? ` · ${person.employer}` : ''}</span>
            <small>{[person.city, person.cohort && `Cohort ${person.cohort}`].filter(Boolean).join(' · ')}</small></div>
          <div className="reason-chips">{person.reasons.map(reason => <span className="tag" key={reason}>{reason}</span>)}</div>
          <div className="contact">
            <a className="mini-link" href={gmailLink(draft)} target="_blank" rel="noopener noreferrer" title={`Opens a prefilled draft to ${person.name} in Gmail`}>Email in Gmail</a>
            {linkedinHref(person) && <a className="action-link linkedin" href={linkedinHref(person)} target="_blank" rel="noopener noreferrer"
              title={person.linkedin_kind === 'search' ? `Search LinkedIn for ${person.name}` : `${person.name} on LinkedIn`}
              aria-label={person.linkedin_kind === 'search' ? `Search LinkedIn for ${person.name}` : `${person.name} on LinkedIn`}>
              <Icon name="linkedin" size={15} />{person.linkedin_kind === 'search' ? 'Find on LinkedIn' : 'LinkedIn'}</a>}
          </div>
        </li>
      })}</ul>
    </>}
  </div>
}
