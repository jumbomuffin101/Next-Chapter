import { useEffect, useRef, useState } from 'react'
import Icon from '../components/Icon.jsx'
import {
  SALARY_RANGES,
  normalizeProfile,
  rangeContaining,
  rangeKey,
  salaryLabel,
  mergeResumeDraft,
  saveErrorMessage,
  validateProfile,
} from './profile.js'

import { fetchSalaryEstimate, parseResume } from '../api.js'
import ProfileFields from './ProfileFields.jsx'

export default function ProfileEditor({ profile, onSave, onClose }) {
  const dialogRef = useRef(null)
  const [draft, setDraft] = useState(() => structuredClone(profile))
  const [skills, setSkills] = useState(profile.skills.join(', '))
  const [certifications, setCertifications] = useState(profile.certifications.join('\n'))
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [reading, setReading] = useState(false)
  const [saving, setSaving] = useState(false)
  useEffect(() => {
    const dialog = dialogRef.current
    const previous = document.activeElement
    dialog.showModal()
    const overflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => { dialog.close(); document.body.style.overflow = overflow; previous?.focus() }
  }, [])

  async function uploadResume(event) {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return
    setError(''); setNotice('')
    if (file.type !== 'application/pdf') { setError('Please choose a PDF file.'); return }
    if (file.size > 5 * 1024 * 1024) { setError('File is too large (5 MB max).'); return }
    setReading(true)
    try {
      // the email you signed in with is your account; the resume's email must not replace it
      const parsed = mergeResumeDraft(draft, await parseResume(file))
      setDraft(parsed); setSkills(parsed.skills.join(', ')); setCertifications(parsed.certifications.join('\n'))
      setNotice('Resume read. Review your details, then save.')
    } catch (err) { setError(err.message) }
    finally { setReading(false) }
  }

  async function submit(event) {
    event.preventDefault()
    setError(''); setSaving(true)
    try { await onSave(validateProfile(draft, skills, certifications)) }
    catch (err) { setError(saveErrorMessage(err)) }
    finally { setSaving(false) }
  }

  return <dialog ref={dialogRef} className="profile-dialog" aria-labelledby="editor-title" onCancel={onClose}>
    <form onSubmit={submit} noValidate>
      <div className="editor-header"><div><h2 id="editor-title">Edit profile</h2><p>* Required</p></div><button type="button" className="icon-button" onClick={onClose} aria-label="Close profile editor"><Icon name="close" /></button></div>
      <div className="editor-body">
        <details className="import-panel" open><summary>Upload resume</summary><p>Upload your resume (PDF) and we’ll fill in your details. You can review and edit everything before saving.</p><label className="secondary-button import-button">{reading ? 'Reading your resume…' : 'Upload resume (PDF)'}<input type="file" accept="application/pdf" disabled={reading} onChange={uploadResume} /></label></details>
        {notice && <p className="form-notice" role="status">{notice}</p>}
        {draft.warnings.length > 0 && <div className="parser-warnings"><h3>Review these fields</h3><ul>{draft.warnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul></div>}
        <ProfileFields draft={draft} setDraft={setDraft} skills={skills} setSkills={setSkills} certifications={certifications} setCertifications={setCertifications} lockEmail={Boolean(profile.email)} />
      </div>
      <div className="editor-footer">{error ? <p className="form-error" role="alert">{error}</p> : <p>Saved to your TKH account.</p>}<div><button type="button" className="secondary-button" onClick={onClose}>Cancel</button><button type="submit" className="primary-button" disabled={saving || reading}>{saving ? 'Saving…' : 'Save profile'} <Icon name="check" size={17} /></button></div></div>
    </form>
  </dialog>
}
