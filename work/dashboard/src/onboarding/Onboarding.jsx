import { useEffect, useRef, useState } from 'react'
import logo from '../assets/tkh-logo.png'
import WaveArt from '../components/WaveArt.jsx'
import Icon from '../components/Icon.jsx'
import ProfileFields from '../user/ProfileFields.jsx'
import { mergeResumeDraft, readSavedProfile, saveErrorMessage, validateProfile } from '../user/profile.js'
import { confirmProfile, parseResume, refreshProfile, setCohort } from '../api.js'

const FIRST_YEAR = 2015 // The Knowledge House began in 2015
const MAX_BYTES = 5 * 1024 * 1024
const THIS_YEAR = new Date().getFullYear()
const YEARS = Array.from({ length: THIS_YEAR + 1 - FIRST_YEAR + 1 }, (_, i) => THIS_YEAR + 1 - i)
const READING = ['Reading your resume…', 'Finding your roles…', 'Picking out your skills…', 'Almost there…']
const STEPS = 4 // cohort, upload, review, extras (welcome and done are not counted)

// Airtable-style flow: one question per screen, big type, progress on top, Enter to continue.
export default function Onboarding({ onDone }) {
  const saved = readSavedProfile().profile
  const firstName = saved.full_name.split(' ')[0]

  const [step, setStep] = useState(0) // 0 welcome, 1 cohort, 2 upload, 3 review, 4 extras, 5 done
  const [year, setYear] = useState(() => readSavedProfile().cohort ?? '') // set already when you joined through an invite or the room QR
  const [draft, setDraft] = useState(saved)
  const [skills, setSkills] = useState('')
  const [certs, setCerts] = useState('')
  const [salary, setSalary] = useState({ min: '', max: '' })
  const [error, setError] = useState('')
  const [reading, setReading] = useState(false)
  const [readingLine, setReadingLine] = useState(0)
  const [over, setOver] = useState(false)
  const [saving, setSaving] = useState(false)
  const fileInput = useRef(null)

  useEffect(() => {
    if (!reading) return undefined
    const timer = setInterval(() => setReadingLine(line => (line + 1) % READING.length), 1200)
    return () => clearInterval(timer)
  }, [reading])

  const go = next => { setError(''); setStep(next); window.scrollTo(0, 0) }

  async function handleFile(file) {
    if (!file) return
    setError('')
    if (file.type !== 'application/pdf') return setError('Please choose a PDF file.')
    if (file.size > MAX_BYTES) return setError('That file is too large (5 MB max).')
    setReading(true); setReadingLine(0)
    try {
      // the email you signed in with is your account; the resume's email must not replace it
      const parsed = mergeResumeDraft(draft, await parseResume(file))
      setDraft(parsed); setSkills(parsed.skills.join(', ')); setCerts(parsed.certifications.join('\n'))
      setTimeout(() => { setReading(false); go(3) }, 600)
    } catch (err) { setError(err.message); setReading(false) }
  }

  function reviewNext(event) {
    event.preventDefault()
    try { validateProfile(draft, skills, certs); go(4) }
    catch (err) { setError(saveErrorMessage(err)) }
  }

  async function finish(withSalary) {
    setError('')
    let money = null
    if (withSalary) {
      const min = Number(salary.min), max = Number(salary.max)
      if (!salary.min && !salary.max) money = null
      else if (!Number.isInteger(min) || !Number.isInteger(max) || min <= 0 || max <= 0) return setError('Enter both numbers as whole dollar amounts, or skip this step.')
      else if (min > max) return setError('The minimum can’t be higher than the maximum.')
      else money = { min, max }
    }
    setSaving(true)
    try {
      await confirmProfile(validateProfile(draft, skills, certs), money)
      await setCohort(year)
      await refreshProfile()
      go(5)
    } catch (err) { setError(saveErrorMessage(err)) }
    finally { setSaving(false) }
  }

  const foundRoles = draft.work_experience.length, foundSkills = skills.split(/[,\n]/).filter(item => item.trim()).length

  return <div className="tkh-app onboard">
    <WaveArt />
    <header className="onboard-top">
      <img src={logo} alt="The Knowledge House" />
      {step > 0 && step < 5 && <>
        <div className="progress" role="progressbar" aria-valuemin={1} aria-valuemax={STEPS} aria-valuenow={step}>
          {Array.from({ length: STEPS }, (_, i) => <span key={i} className={i < step ? 'on' : ''} />)}
        </div>
        <span className="step-count">Step {step} of {STEPS}</span>
      </>}
    </header>

    <div className="onboard-body">
      {step === 0 && <section className="step" key="s0">
        <span className="num">Welcome</span>
        <h1>{firstName ? `Hi, ${firstName}.` : 'Welcome.'}<br />Let’s build your profile.</h1>
        <p className="sub">All you need to do is upload your resume. We’ll read it, you check it, and your dashboard is ready.</p>
        <ul className="checklist">
          <li><b>1</b>Choose your cohort year<i>10 sec</i></li>
          <li><b>2</b>Upload your resume<i>20 sec</i></li>
          <li><b>3</b>Check what we found<i>1 min</i></li>
          <li><b>4</b>Optional extras, like salary<i>Skip anytime</i></li>
        </ul>
        <div className="actions"><button className="primary-button" onClick={() => go(1)} autoFocus>Let’s go <Icon name="arrow" size={17} /></button></div>
      </section>}

      {step === 1 && <form className="step" key="s1" onSubmit={event => { event.preventDefault(); if (year) go(2); else setError('Choose the year you joined.') }}>
        <span className="num">01</span>
        <h1>Which year did you join TKH?</h1>
        <p className="sub">This puts you with your cohort, so the career team can see how your class is doing.</p>
        <label className="field-big"><span>Cohort year</span>
          <select value={year} onChange={event => { setYear(event.target.value); setError('') }} autoFocus>
            <option value="">Choose a year…</option>
            {YEARS.map(value => <option key={value} value={value}>{value}</option>)}
          </select></label>
        {error && <p className="stage-error" role="alert">{error}</p>}
        <div className="actions"><button className="primary-button">Continue <Icon name="arrow" size={17} /></button><span className="hint">press Enter ↵</span><button type="button" className="text-link" onClick={() => go(0)}>Back</button></div>
      </form>}

      {step === 2 && <section className="step" key="s2">
        <span className="num">02</span>
        <h1>Upload your resume</h1>
        <p className="sub">A PDF with selectable text works best. We read it for you; nothing is saved until you confirm.</p>
        {reading ? <div className="reading" role="status"><div className="scan" /><p>{READING[readingLine]}</p></div>
          : <label className={`dropzone ${over ? 'over' : ''}`} onDragOver={event => { event.preventDefault(); setOver(true) }} onDragLeave={() => setOver(false)}
              onDrop={event => { event.preventDefault(); setOver(false); handleFile(event.dataTransfer.files[0]) }}>
              <Icon name="upload" size={42} /><strong>Drop your resume here</strong><span>or click to choose a PDF · 5 MB max</span>
              <input ref={fileInput} type="file" accept="application/pdf" onChange={event => { handleFile(event.target.files[0]); event.target.value = '' }} />
            </label>}
        {error && <p className="stage-error" role="alert">{error}</p>}
        <div className="actions"><button type="button" className="text-link" disabled={reading} onClick={() => go(1)}>Back</button></div>
      </section>}

      {step === 3 && <form className="step" key="s3" onSubmit={reviewNext}>
        <span className="num">03</span>
        <h1>Here’s what we found</h1>
        <p className="sub">Check it over and fix anything that’s off. This is what your dashboard will show.</p>
        <div className="found"><span>{foundRoles} {foundRoles === 1 ? 'role' : 'roles'}</span><span>{draft.education.length} education</span><span>{foundSkills} skills</span></div>
        {draft.warnings.length > 0 && <div className="parser-warnings"><h3>Review these fields</h3><ul>{draft.warnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul></div>}
        {draft.linkedin_url && <p className="note-box" style={{ marginTop: 0, marginBottom: 14 }}>We found a LinkedIn link on your resume. It’s shown to other alumni in the network, and you never have to add one.</p>}
        <div className="review-scroll"><ProfileFields draft={draft} setDraft={setDraft} skills={skills} setSkills={setSkills} certifications={certs} setCertifications={setCerts} lockEmail /></div>
        {error && <p className="stage-error" role="alert" style={{ marginTop: 16 }}>{error}</p>}
        <div className="actions"><button className="primary-button">Looks good <Icon name="arrow" size={17} /></button><button type="button" className="text-link" onClick={() => go(2)}>Upload a different file</button></div>
      </form>}

      {step === 4 && <form className="step" key="s4" onSubmit={event => { event.preventDefault(); finish(true) }}>
        <span className="num">04 · OPTIONAL</span>
        <h1>A few optional extras</h1>
        <p className="sub">Annual salary range <span className="badge-rec">Recommended</span><br />It gives you accurate personal growth data. Add it now and we’ll track how your pay changes over time.</p>
        <div className="salary-row">
          <label className="field-big"><span>Minimum ($ / year)</span><input inputMode="numeric" placeholder="70000" value={salary.min} onChange={event => setSalary({ ...salary, min: event.target.value.replace(/[^\d]/g, '') })} autoFocus /></label>
          <label className="field-big"><span>Maximum ($ / year)</span><input inputMode="numeric" placeholder="90000" value={salary.max} onChange={event => setSalary({ ...salary, max: event.target.value.replace(/[^\d]/g, '') })} /></label>
        </div>
        <p className="note-box">Only you and the TKH career team can see this. The admin dashboard shows averages across alumni, never your individual number.</p>
        {error && <p className="stage-error" role="alert" style={{ marginTop: 16 }}>{error}</p>}
        <div className="actions">
          <button className="primary-button" disabled={saving}>{saving ? 'Saving…' : 'Finish'} <Icon name="check" size={17} /></button>
          <button type="button" className="text-link" disabled={saving} onClick={() => finish(false)}>Skip for now</button>
          <button type="button" className="text-link" disabled={saving} onClick={() => go(3)}>Back</button>
        </div>
      </form>}

      {step === 5 && <section className="step" key="s5">
        <div className="done-mark"><Icon name="check" size={52} /></div>
        <h1>You’re all set.</h1>
        <p className="sub">Your profile is saved. Your dashboard shows your career journey, your growth and jobs matched to you.</p>
        <div className="actions"><button className="primary-button" onClick={onDone} autoFocus>Open my dashboard <Icon name="arrow" size={17} /></button></div>
      </section>}
    </div>
  </div>
}
