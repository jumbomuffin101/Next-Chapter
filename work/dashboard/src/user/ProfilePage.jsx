import { useEffect, useRef, useState } from 'react'
import Icon from '../components/Icon.jsx'
import { readComfort, readTheme, saveComfort, saveTheme } from '../comfort.js'
import ProfileFields from './ProfileFields.jsx'
import NewsletterPreference from './NewsletterPreference.jsx'
import { mergeResumeDraft, readSavedProfile, saveErrorMessage, validateProfile } from './profile.js'
import { confirmProfile, parseResume, refreshProfile } from '../api.js'

const MAX_RESUME_BYTES = 5 * 1024 * 1024

export default function ProfilePage({ onSignOut }) {
  const [{ profile }] = useState(readSavedProfile)
  const [draft, setDraft] = useState(() => structuredClone(profile))
  const [skills, setSkills] = useState(profile.skills.join(', '))
  const [certifications, setCertifications] = useState(profile.certifications.join('\n'))
  const [resume, setResume] = useState(null)
  const [resumeError, setResumeError] = useState('')
  const [reading, setReading] = useState(false)
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const fileInput = useRef(null)
  useEffect(() => () => { if (resume?.url) URL.revokeObjectURL(resume.url) }, [resume])
  const [comfort, setComfort] = useState(readComfort)
  const [theme, setTheme] = useState(readTheme)
  const initials = draft.full_name.split(/\s+/).filter(Boolean).slice(0, 2).map(part => part[0]).join('').toUpperCase()

  async function handleResume(event) {
    const file = event.target.files[0]
    event.target.value = '' // lets the same file be picked again
    if (!file) return
    if (file.type !== 'application/pdf') return setResumeError('Please choose a PDF file.')
    if (file.size > MAX_RESUME_BYTES) return setResumeError('File is too large (5 MB max).')
    setResumeError(''); setMessage('')
    setReading(true)
    try {
      // the PDF is parsed on the server; nothing is saved until the user confirms the form below
      // the email you signed in with is your account; the resume's email must not replace it
      const parsed = mergeResumeDraft(draft, await parseResume(file))
      setDraft(parsed); setSkills(parsed.skills.join(', ')); setCertifications(parsed.certifications.join('\n'))
      setResume({ name: file.name, url: URL.createObjectURL(file), file })
    } catch (err) { setResumeError(err.message) }
    finally { setReading(false) }
  }

  async function submit(event) {
    event.preventDefault()
    setError(''); setMessage('')
    try {
      const valid = validateProfile(draft, skills, certifications)
      await confirmProfile(valid, null, { replace: true })
      const saved = await refreshProfile() // show what the server actually stored
      setDraft(structuredClone(saved)); setSkills(saved.skills.join(', ')); setCertifications(saved.certifications.join('\n'))
      setMessage('Profile saved. Your career journey is up to date.')
    } catch (err) { setError(saveErrorMessage(err)) }
  }

  return <div className="tkh-app profile-page">
    <header className="profile-header">
      <h1>{draft.full_name || 'Your Name'}</h1>
      <span className="avatar profile-photo">{initials || <Icon name="person" size={44} />}</span>
      <button type="button" className="primary-button" disabled={reading} onClick={() => fileInput.current.click()}>
        <Icon name="upload" size={18} />{reading ? 'Reading your resume…' : 'Resubmit Resume'}
      </button>
      <input ref={fileInput} type="file" accept="application/pdf" hidden onChange={handleResume} />
      {resume && <p className="form-notice" role="status"><Icon name="file" size={16} /> Read <a href={resume.url} target="_blank" rel="noreferrer">{resume.name}</a>. Review the details below, then confirm.</p>}
      {resumeError && <p className="form-error" role="alert">{resumeError}</p>}
    </header>

    <form className="card profile-form" onSubmit={submit}>
      {draft.warnings.length > 0 && <div className="parser-warnings"><h3>A few things to review</h3><ul>{draft.warnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul></div>}
      <ProfileFields draft={draft} setDraft={setDraft} skills={skills} setSkills={setSkills} certifications={certifications} setCertifications={setCertifications} lockEmail={Boolean(profile.email)} />
      {error && <p className="form-error" role="alert">{error}</p>}
      {message && <div className="save-message" role="status"><Icon name="check" size={18} />{message}</div>}
      <div className="profile-actions"><button type="submit" className="primary-button">Confirm & save <Icon name="check" size={17} /></button></div>
    </form>

    <section className="card comfort-card" aria-labelledby="comfort-heading">
      <h2 id="comfort-heading">Display</h2>
      <h3 className="pref-label" id="theme-label">Appearance</h3>
      <div className="chips" role="group" aria-labelledby="theme-label">
        {[['light', 'Light'], ['dark', 'Dark'], ['system', 'Match my device']].map(([value, label]) =>
          <button key={value} type="button" aria-pressed={theme === value} onClick={() => { setTheme(value); saveTheme(value) }}>{label}</button>)}
      </div>
      <h3 className="pref-label">Comfort mode</h3>
      <label className="auto-switch">
        <input type="checkbox" role="switch" checked={comfort} onChange={event => { setComfort(event.target.checked); saveComfort(event.target.checked) }} />
        <span><b>{comfort ? 'On' : 'Off'}</b> · Calmer, easier reading: no animations, no ALL-CAPS text, and a plainer font with more spacing. Saved on this device.</span>
      </label>
    </section>

    <NewsletterPreference />
    <button type="button" className="sign-out-button" onClick={onSignOut}>Sign out</button>
  </div>
}
