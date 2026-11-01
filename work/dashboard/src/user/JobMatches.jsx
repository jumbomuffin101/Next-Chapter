import Card from '../components/Card.jsx'
import Icon from '../components/Icon.jsx'
import { ago, isNew } from './recency.js'

// Renders the job list: {job_id, title, company, location, salary_min, salary_max, apply_url, updated_at, why_matched}.
// Every listing shows when the employer last updated it, and brand-new ones are tagged.
export default function JobMatches({ jobs = [], error = '', hasProfile, now, emptyHint }) {
  return (
    <Card title="Openings picked for you" className="jobs-card">
      {jobs.length ? (
        <div className="job-list">
          {jobs.map(job => {
            let url
            try {
              const parsed = new URL(job.apply_url)
              if (['https:', 'http:'].includes(parsed.protocol)) url = parsed.href
            } catch { /* Hide invalid application links. */ }
            return (
              <article className="job-item" key={job.job_id}>
                <div className="job-top"><span className="job-company">{job.company}</span>
                  {isNew(job.updated_at, now) && <span className="tag green">New this week</span>}</div>
                <h3>{job.title}</h3>
                <p><Icon name="pin" size={14} />{job.location || 'Location not listed'}</p>
                <p>{job.salary_min != null && job.salary_max != null ? `${job.salary_min.toLocaleString()}–${job.salary_max.toLocaleString()} (as listed)` : 'Salary not listed'}</p>
                <p className="updated"><Icon name="calendar" size={14} />Updated {ago(job.updated_at, now)}</p>
                {job.why_matched && <span className="tag">{job.why_matched}</span>}
                {url && <a className="text-button" href={url} target="_blank" rel="noopener noreferrer">Apply <Icon name="arrow" size={16} /></a>}
              </article>
            )
          })}
        </div>
      ) : (
        <div className="jobs-empty">
          <span className="icon-tile"><Icon name="briefcase" size={27} /></span>
          <h3>{hasProfile ? 'No matches right now' : 'Add experience & skills'}</h3>
          <p>{error ? `We couldn’t load your matches: ${error}` : emptyHint || (hasProfile ? 'New openings are added regularly, so check back soon.' : 'Complete these in your profile to prepare for matching.')}</p>
        </div>
      )}
    </Card>
  )
}
