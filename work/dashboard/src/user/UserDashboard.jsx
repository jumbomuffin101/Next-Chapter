import { useEffect, useState } from 'react'
import Card from '../components/Card.jsx'
import Icon from '../components/Icon.jsx'
import Tabs from '../components/Tabs.jsx'
import { scrollBehavior } from '../comfort.js'
import Panel from '../admin/Panel.jsx'
import CareerTimeline from './CareerTimeline.jsx'
import CheckIn from './CheckIn.jsx'
import { readCheckIn, shouldAskCheckIn } from './checkin.js'
import Events from './Events.jsx'
import Growth from './Growth.jsx'
import JobMonitor from './JobMonitor.jsx'
import LevelUp from './LevelUp.jsx'
import NewsletterPreference from './NewsletterPreference.jsx'
import People from './People.jsx'
import ProfileEditor from './ProfileEditor.jsx'
import SupportBox from './SupportBox.jsx'
import MonthlyNewsletter from './MonthlyNewsletter.jsx'
import { newsletterArea } from './newsletterNavigation.js'
import { readSavedProfile, salaryLabel } from './profile.js'
import { confirmProfile, fetchMatches, getAlumniId, refreshProfile } from '../api.js'


function ProfileDetails({ profile, salary }) {
  return <Card title="Profile details" className="details-card">
    <dl className="contact-details">
      {[['Email', profile.email], ['Phone', profile.phone], ['Location', profile.location], ['Salary', salary && salaryLabel(salary)]].map(([label, value]) => (
        <div key={label}><dt>{label}</dt><dd>{value || 'Not added'}</dd></div>
      ))}
    </dl>
    <h3>Education</h3>
    {profile.education.length ? profile.education.map((item, index) => (
      <div className="education-item" key={index}>
        <strong>{item.school}</strong>
        <p>{[item.degree, item.field_of_study].filter(Boolean).join(' · ')}</p>
        <span>{[item.start_date, item.end_date].filter(Boolean).join(' — ')}</span>
      </div>
    )) : <p className="muted">Not added</p>}
    <h3>Skills</h3>
    <div className="skill-tags">
      {profile.skills.length ? profile.skills.map(skill => <span className="tag" key={skill}>{skill}</span>) : <p className="muted">Not added</p>}
    </div>
    <h3>Certifications</h3>
    <div className="skill-tags">
      {profile.certifications.length ? profile.certifications.map(item => <span className="tag" key={item}>{item}</span>) : <p className="muted">Not added</p>}
    </div>
  </Card>
}

// What this page is: your career after TKH in one place. Your journey, your growth, your job matches.
export default function UserDashboard() {
  const [{ profile, savedAt, salary, cohort }, setSaved] = useState(readSavedProfile)
  const [editing, setEditing] = useState(false)
  const [message, setMessage] = useState('')
  const [now] = useState(() => Date.now())
  const [matches, setMatches] = useState({ matches: [], refreshed_at: null, matched_on: null })
  const [jobsError, setJobsError] = useState('')
  const [salaryVersion, setSalaryVersion] = useState(0) // bumped on any salary save, so every card showing pay reloads
  const [viewingNewsletter, setViewingNewsletter] = useState(() => newsletterArea(window.location.search) === 'newsletter')
  const jobs = matches.matches
  const loadJobs = () => fetchMatches().then(setMatches).then(() => setJobsError(''), err => setJobsError(err.message))
  useEffect(() => { loadJobs() }, [])
  // Decide once on load: after a check-in answer, stay quiet until the next visit.
  const [askCheckIn] = useState(() => shouldAskCheckIn({ lastAnswer: readCheckIn(getAlumniId()), savedAt }))
  const [tab, setTab] = useState(() => (['events', 'network', 'newsletter'].includes(new URLSearchParams(window.location.search).get('section')) ? 'community' : 'career'))
  // Newsletter email links open the matching dashboard card, or the in-app digest.
  useEffect(() => {
    const section = new URLSearchParams(window.location.search).get('section')
    const card = section === 'events' ? 'events' : newsletterArea(window.location.search)
    if (section && section !== 'newsletter') document.getElementById(`card-${card}`)?.scrollIntoView({ behavior: scrollBehavior(), block: 'start' })
  }, [])

  const firstName = profile.full_name.split(' ')[0]
  const starts = profile.work_experience.map(job => job.start_date).filter(Boolean).sort()
  const years = starts.length ? Math.max(0, (now - new Date(`${starts[0].slice(0, 7)}-01T12:00:00`)) / 31557600000) : null
  const savedDate = savedAt && !Number.isNaN(Date.parse(savedAt))
    ? new Date(savedAt).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' }) : '—'
  const hasProfile = profile.work_experience.length > 0 && profile.skills.length > 0

  // "Yes, same role": re-confirm the saved profile so TKH counts it as recently updated
  async function confirmRole() {
    await confirmProfile(profile)
    await refreshProfile()
    setSaved(readSavedProfile())
  }

  // A salary saved in one card: reload the profile (Your profile, role salaries), growth, job monitor and pay-ranked matches
  async function salaryChanged() {
    try { await refreshProfile(); setSaved(readSavedProfile()) } catch { /* the salary is saved; the other cards still reload */ }
    setSalaryVersion(version => version + 1)
    loadJobs()
  }

  async function save(nextProfile) {
    await confirmProfile(nextProfile, null, { replace: true }) // role salaries travel inside the roles // the editor shows the whole profile; throws on failure
    // Saved on the server from here on, so always close; a failed reload only changes the message
    try { await refreshProfile(); setMessage('Profile saved.') }
    catch { setMessage('Profile saved. Refresh the page to see every change.') }
    setSaved(readSavedProfile())
    setEditing(false)
    setSalaryVersion(version => version + 1) // role salaries from the editor
    loadJobs()
  }

  // Two tabs so one page isn't overloaded: career (jobs, profile, certs, growth, path) and community (events, people, newsletter, help).
  return <div className="tkh-app admin alumni-home">
    <header className="alumni-heading">
      <div>
        <span className="eyebrow">The Knowledge House · made for you</span>
        <h1 className="visually-hidden">TKH Next Chapter: your dashboard</h1>{/* heading for screen readers; the logo above and navbar show the brand */}
        <p className="phone-greeting">{firstName ? `Hi, ${firstName}` : 'Welcome'} · Updated {savedDate}</p>
        <p>{firstName ? `${firstName}, everything here is personalized to your profile.` : 'Everything here is personalized to your profile.'} Openings and learning picks are built from your role, skills and city, and each one shows how recent it is.</p>
      </div>
      <button className="primary-button" onClick={() => setEditing(true)}><Icon name="upload" size={18} />Update profile or resume</button>
    </header>
    {message && <div className="save-message" role="status"><Icon name="check" size={18} />{message}
      <button className="icon-button" onClick={() => setMessage('')} aria-label="Dismiss confirmation"><Icon name="close" size={16} /></button></div>}
    <div className="kpi-row four kpi-swipe" aria-label="Your numbers">
      <div className="kpi-tile"><span className="kpi-label">Roles on record</span><strong>{profile.work_experience.length}</strong></div>
      <div className="kpi-tile"><span className="kpi-label">Years in the workforce</span><strong>{years == null ? '—' : years.toFixed(1)}</strong></div>
      <div className="kpi-tile"><span className="kpi-label">Jobs matched to you</span><strong>{jobs.length}</strong></div>
      <div className="kpi-tile"><span className="kpi-label">Profile last updated</span><strong className="kpi-date">{savedDate}</strong></div>
    </div>

    <div className="admin-bar alumni-tabbar">
      <Tabs className="view-tabs" label="Your next chapter" panelId="alumni-panel" active={tab}
        onChange={nextTab => { setTab(nextTab); setViewingNewsletter(false) }}
        tabs={[['career', 'My career'], ['community', 'Community & support']]} />
    </div>
    <div id="alumni-panel" role="tabpanel" aria-labelledby={`tab-${tab}`} className={viewingNewsletter ? '' : 'bento user-squares'}>
      {viewingNewsletter ? <MonthlyNewsletter key={savedAt} profile={profile} cohort={cohort} onBack={() => { setViewingNewsletter(false); setTab('community') }} /> : <>
      {tab === 'career' && <>
        {askCheckIn && <Panel title="Quick check-in" className="long checkin-panel">
          <CheckIn profile={profile} savedDate={savedDate} onConfirm={confirmRole} onNewRole={() => setEditing(true)}
            onLooking={() => document.getElementById('card-jobs')?.scrollIntoView({ behavior: scrollBehavior(), block: 'start' })} />
        </Panel>}
        <JobMonitor profile={profile} jobs={jobs} refreshedAt={matches.refreshed_at} matchedOn={matches.matched_on}
          error={jobsError} hasProfile={hasProfile} salaryVersion={salaryVersion} onSalarySaved={salaryChanged} />
        <Panel collapsible id="card-profile" title="Your profile" caption="What the career team sees" className="side"><ProfileDetails profile={profile} salary={salary} /></Panel>
        <Panel collapsible id="card-level" title="Suggested certifications" caption="Picked for your role and skills" className="pair"><LevelUp /></Panel>
        <Panel title="Your growth" caption="How your pay is changing" className="pair"><Growth salaryVersion={salaryVersion} onChanged={salaryChanged} /></Panel>
        <Panel collapsible title="Career path" caption="Every role since TKH, newest first" className="long"><CareerTimeline profile={profile} /></Panel>
      </>}
      {tab === 'community' && <>
        <Panel collapsible id="card-events" title="Meetings & events" caption="Sample data for the demo" className="pair"><Events /></Panel>
        <Panel collapsible id="card-network" title="People near you" caption="Alumni in your field, plus your invite link" className="pair"><People /></Panel>
        <div className="pair newsletter-slot" id="card-newsletter"><NewsletterPreference onView={() => setViewingNewsletter(true)} /></div>
        <Panel collapsible title="Need a hand?" caption="The career team is here to help" className="pair support-card"><SupportBox /></Panel>
      </>}
      </>}
    </div>
    {editing && <ProfileEditor profile={profile} onClose={() => setEditing(false)} onSave={save} />}
  </div>
}
