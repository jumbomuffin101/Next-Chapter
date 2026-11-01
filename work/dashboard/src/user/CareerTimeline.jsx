import Card from '../components/Card.jsx'
import Icon from '../components/Icon.jsx'
import { dateLabel } from './profile.js'

export default function CareerTimeline({ profile, compact = false }) {
  const jobs = [...profile.work_experience].sort((a, b) => Number(b.is_current) - Number(a.is_current) || b.start_date.localeCompare(a.start_date))
  const visibleJobs = compact ? jobs.slice(0, 3) : jobs
  return (
    <Card title="Career timeline" className="journey-card">
      {jobs.length ? (
        <>
          <ol className="career-timeline">
            {visibleJobs.map((job, index) => (
              <li key={index}>
                <span className={`timeline-node ${job.is_current ? 'current' : ''}`}><Icon name="briefcase" size={17} /></span>
                <div className="timeline-heading">
                  <span className="eyebrow">{dateLabel(job.start_date)} — {job.is_current ? 'Present' : dateLabel(job.end_date)}</span>
                  {job.is_current && <span className="tag green">Current</span>}
                </div>
                <h3>{job.title || 'Role not provided'}</h3>
                <p>{job.employer || 'Employer not provided'}{job.location && ` · ${job.location}`}</p>
                {!compact && job.description && <details className="role-details"><summary>Role details</summary><p className="timeline-description">{job.description}</p></details>}
              </li>
            ))}
          </ol>
          {compact && jobs.length > 3 && <p className="compact-note">{jobs.length - 3} earlier {jobs.length - 3 === 1 ? 'role' : 'roles'} in My profile</p>}
        </>
      ) : (
        <div className="journey-empty">
          <div className="journey-illustration" aria-hidden="true"><span /><span /><span /><Icon name="briefcase" size={26} /></div>
          <h3>No experience added</h3>
          <p>Your roles will appear here.</p>
        </div>
      )}
    </Card>
  )
}
