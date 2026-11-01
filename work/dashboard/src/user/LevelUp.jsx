import { useEffect, useState } from 'react'
import { fetchRecommendations } from '../api.js'
import { ago } from './recency.js'
import { readSavedProfile } from './profile.js'

// Certification suggestions: certifications and skills chosen for YOUR role type and the skills on your profile.
export default function LevelUp() {
  const [data, setData] = useState(null)
  const [error, setError] = useState('')
  const [now] = useState(() => Date.now())
  const { profile, savedAt } = readSavedProfile()
  const role = profile.work_experience[0]
  useEffect(() => { fetchRecommendations().then(setData, err => setError(err.message)) }, [])

  if (error) return <p className="stage-error">We couldn’t load your recommendations: {error}</p>
  if (!data) return <p className="panel-empty">Loading your recommendations…</p>
  return <div className="certs">
    <p className="fresh-line"><span className="live-dot" aria-hidden="true" />Picked for {role ? <b>{role.title}</b> : 'your field'} ({data.family_label}), based on your profile as of <b>{savedAt ? ago(savedAt, now) : 'today'}</b>.</p>
    {data.held.length > 0 && <><h4 className="mini-title">You already have</h4>
      <div className="skill-tags">{data.held.map(name => <span className="tag" key={name}>{name}</span>)}</div></>}
    <h4 className="mini-title">Consider next</h4>
    <div className="card-grid">{data.recommended.map(cert => <article className="cert-card" key={cert.name}>
      <span className="tag">{cert.level}</span><h4>{cert.name}</h4><small>{cert.provider}</small><p>{cert.why}</p>
      <a className="text-button" href={cert.url} target="_blank" rel="noopener noreferrer">Learn more →</a>
    </article>)}</div>
    {data.skills_to_add.length > 0 && <><h4 className="mini-title">Skills worth adding</h4>
      <div className="skill-tags">{data.skills_to_add.map(skill => <span className="tag" key={skill}>{skill}</span>)}</div></>}
  </div>
}
