import { useEffect, useState } from 'react'
import { fetchCurrentNewsletter, generateDemoNewsletter, getDemoNewsletterConsent, getNewsletterToken, setDemoNewsletterConsent } from '../api.js'
import { monthLabel, safeOpportunityUrl } from './monthlyNewsletter.js'
import { demoNewsletterProfile } from './demoNewsletterProfile.js'

export default function MonthlyNewsletter({ onBack, profile, cohort }) {
  const available = Boolean(getNewsletterToken())
  const [confirmed, setConfirmed] = useState(getDemoNewsletterConsent)
  const [digest, setDigest] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!available && !confirmed) return undefined
    let active = true
    const operation = available ? fetchCurrentNewsletter() : generateDemoNewsletter(demoNewsletterProfile(profile, cohort))
    operation.then(value => { if (active) setDigest(value) },
      failure => { if (active) setError(failure.message) })
    return () => { active = false }
  }, [available, confirmed, profile, cohort])

  const content = digest?.content
  return <main className="monthly-view" aria-labelledby="monthly-title">
    <button type="button" className="secondary-button monthly-back" onClick={onBack}>← Return to dashboard</button>
    <header className="monthly-hero">
      <p className="eyebrow">THE KNOWLEDGE HOUSE · MADE FOR YOU</p>
      <h2 id="monthly-title">Next Chapter Monthly</h2>
      <p>{monthLabel(digest?.month)}</p>
    </header>
    {!available && !confirmed && <section className="card monthly-section">
      <h3>Generate a synthetic demo newsletter</h3>
      <p>Continue only if this profile is fictional. The demo uses your first name, role titles, skills, city, and cohort to find public jobs. It does not send your email, employer, salary, or profile ID. No subscription or email delivery is involved.</p>
      <button type="button" className="primary-button" onClick={() => { setDemoNewsletterConsent(); setConfirmed(true) }}>
        This profile is fictional — generate newsletter
      </button>
    </section>}
    {(available || confirmed) && !content && !error && <p role="status">Loading your monthly newsletter…</p>}
    {error && <p className="form-error" role="alert">{error}</p>}
    {content && <>
      <p className="monthly-demo">Synthetic demo content · illustrative events are not scheduled TKH events</p>
      <p className="monthly-greeting">Hi {content.first_name}, here is your career and community digest.</p>
      <section className="card monthly-section" aria-labelledby="monthly-jobs"><h3 id="monthly-jobs">Career Opportunities</h3>
        {content.jobs.length ? <ul className="monthly-list">{content.jobs.map((job, index) => {
          const url = !job.example && safeOpportunityUrl(job.apply_url)
          return <li key={`${job.title}-${index}`}><h4>{job.title}</h4><p>{job.company} · {job.location}</p>
            <p>{job.why_matched}</p>
            {url ? <a href={url} target="_blank" rel="noopener noreferrer">View original job posting ↗</a>
              : <span>Example opportunity — no live posting link</span>}
          </li>
        })}</ul> : <p>No eligible job listings are available for this profile right now.</p>}
      </section>
      <section className="card monthly-section" aria-labelledby="monthly-events"><h3 id="monthly-events">Upcoming Events</h3>
        {content.events.length ? <ul className="monthly-list">{content.events.map((event, index) =>
          <li key={`${event.title}-${index}`}><h4>{event.title}</h4><p>{event.date} · {event.location}</p>
            <p>{event.details}</p>{event.example && <span>Illustrative event — no registration page available</span>}</li>)}</ul>
          : <p>No verified upcoming events are available. Check back later for community updates.</p>}
      </section>
      <section className="card monthly-section" aria-labelledby="monthly-cohort"><h3 id="monthly-cohort">Cohort Updates</h3>
        <p>{content.cohort_message}</p></section>
    </>}
    <button type="button" className="primary-button monthly-return" onClick={onBack}>Return to dashboard</button>
  </main>
}
