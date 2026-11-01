import { useEffect, useState } from 'react'
import { fetchSalaryEstimate } from '../api.js'
import { SALARY_RANGES, rangeContaining, rangeKey, salaryLabel } from './profile.js'

const money = value => `$${Math.round(value).toLocaleString('en-US')}`

// Profile form sections (01-04), shared by ProfileEditor, ProfilePage and onboarding
function Field({ label, value, onChange, ...props }) {
  return <label className="form-field"><span>{label}</span><input value={value} onChange={event => onChange(event.target.value)} {...props} /></label>
}

// What the person earned in one role: a general range they pick, with the BLS estimate for the role title as a guide.
// Saved with the profile as a salary entry at the role's start month, so it shows on the growth chart.
function RoleSalary({ job, onChange }) {
  const [estimate, setEstimate] = useState(null)
  const title = job.title.trim()
  useEffect(() => {
    if (!title) return
    let alive = true
    const timer = setTimeout(() => fetchSalaryEstimate(title).then(result => { if (alive) setEstimate(result) }, () => { if (alive) setEstimate(null) }), 400)
    return () => { alive = false; clearTimeout(timer) }
  }, [title])
  const current = job.salary_min != null ? { min: job.salary_min, max: job.salary_max } : null
  const options = [...SALARY_RANGES.map(([min, max]) => ({ min, max })),
    ...(current && !SALARY_RANGES.some(([min, max]) => min === current.min && max === current.max) ? [current] : [])]
  const suggested = estimate?.matched ? rangeContaining(estimate.median) : null
  return <div className="form-field wide role-salary">
    <label><span>Salary in this role (per year)</span>
      <select value={rangeKey(current)} onChange={event => onChange(options.find(option => rangeKey(option) === event.target.value) ?? null)}>
        <option value="">Not set</option>
        {options.map(option => <option key={rangeKey(option)} value={rangeKey(option)}>{salaryLabel(option)}</option>)}
      </select></label>
    {estimate?.matched && title && <p className="salary-hint">
      BLS estimate: <b>{estimate.occupation}</b> typically earn {money(estimate.p25)} – {money(estimate.p75)} (median {money(estimate.median)}, {estimate.area}, {estimate.year}).
      {rangeKey(suggested) !== rangeKey(current) && <button type="button" className="text-button" onClick={() => onChange(suggested)}>Use {salaryLabel(suggested)}</button>}
    </p>}
    {title && estimate && !estimate.matched && <p className="salary-hint">We don’t have BLS pay data for “{title}” yet. Pick the range closest to your pay.</p>}
  </div>
}

export default function ProfileFields({ draft, setDraft, skills, setSkills, certifications, setCertifications, lockEmail = false }) {
  const update = (key, value) => setDraft(previous => ({ ...previous, [key]: value }))
  const updateRecord = (key, index, field, value) => setDraft(previous => ({
    ...previous, [key]: previous[key].map((record, i) => i === index ? { ...record, [field]: value, ...(field === 'is_current' && value ? { end_date: '' } : {}) } : record),
  }))
  const remove = (key, index) => update(key, draft[key].filter((_, i) => i !== index))
  const setRoleSalary = (index, salary) => setDraft(previous => ({ ...previous,
    work_experience: previous.work_experience.map((job, i) => (i === index ? { ...job, salary_min: salary?.min ?? null, salary_max: salary?.max ?? null } : job)) }))

  return <>
        <section className="form-section"><h3>01 <span>Contact</span></h3><div className="form-grid">
          <Field label="Full name *" value={draft.full_name} onChange={value => update('full_name', value)} required autoComplete="name" />
          <Field label="Email *" value={draft.email} onChange={value => update('email', value)} required type="email" autoComplete="email" readOnly={lockEmail} title={lockEmail ? 'This is the email you signed in with' : undefined} />
          <Field label="Phone" value={draft.phone} onChange={value => update('phone', value)} type="tel" autoComplete="tel" />
          <Field label="Location" value={draft.location} onChange={value => update('location', value)} placeholder="e.g. Hoboken, NJ" autoComplete="address-level2" />
        </div></section>
        <section className="form-section"><div className="section-heading"><h3>02 <span>Work experience</span></h3><button type="button" className="text-button" onClick={() => update('work_experience', [...draft.work_experience, { employer: '', title: '', location: '', start_date: '', end_date: '', is_current: false, description: '', salary_min: null, salary_max: null }])}>+ Add role</button></div>
          {draft.work_experience.map((job, index) => <fieldset className="record-fields" key={index}><legend>Role {index + 1}</legend><div className="form-grid">
            {[['employer', 'Employer *'], ['title', 'Job title *'], ['location', 'Location'], ['start_date', 'Start date'], ['end_date', 'End date']].map(([key, label]) => <Field key={key} label={label} value={job[key]} onChange={value => updateRecord('work_experience', index, key, value)} required={key === 'employer' || key === 'title'} disabled={key === 'end_date' && job.is_current} placeholder={key.includes('date') ? 'YYYY-MM' : undefined} />)}
            <label className="checkbox-field"><input type="checkbox" checked={job.is_current} onChange={event => updateRecord('work_experience', index, 'is_current', event.target.checked)} />I currently work here</label>
            <label className="form-field wide"><span>Description</span><textarea rows="3" value={job.description} onChange={event => updateRecord('work_experience', index, 'description', event.target.value)} /></label>
            <RoleSalary job={job} onChange={salary => setRoleSalary(index, salary)} />
          </div><button type="button" className="remove-button" onClick={() => remove('work_experience', index)}>Remove role {index + 1}</button></fieldset>)}
        </section>
        <section className="form-section"><div className="section-heading"><h3>03 <span>Education</span></h3><button type="button" className="text-button" onClick={() => update('education', [...draft.education, { school: '', degree: '', field_of_study: '', start_date: '', end_date: '' }])}>+ Add education</button></div>
          {draft.education.map((entry, index) => <fieldset className="record-fields" key={index}><legend>Education {index + 1}</legend><div className="form-grid">{[['school', 'School or program *'], ['degree', 'Degree'], ['field_of_study', 'Field of study'], ['start_date', 'Start date'], ['end_date', 'End date']].map(([key, label]) => <Field key={key} label={label} value={entry[key]} onChange={value => updateRecord('education', index, key, value)} required={key === 'school'} placeholder={key.includes('date') ? 'YYYY-MM' : undefined} />)}</div><button type="button" className="remove-button" onClick={() => remove('education', index)}>Remove education {index + 1}</button></fieldset>)}
        </section>
        <section className="form-section"><h3>04 <span>Skills & certifications</span></h3><label className="form-field"><span>Skills · separate with commas</span><textarea rows="2" value={skills} onChange={event => setSkills(event.target.value)} placeholder="e.g. Python, project management, SQL" /></label><label className="form-field"><span>Certifications · one per line</span><textarea rows="3" value={certifications} onChange={event => setCertifications(event.target.value)} /></label></section>
  </>
}
