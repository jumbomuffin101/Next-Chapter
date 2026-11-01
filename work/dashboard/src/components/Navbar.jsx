import logo from '../assets/tkh-logo.png'
import Avatar from './Avatar.jsx'

// Shown once someone is signed in (the landing and onboarding screens have their own header).
// Alumni see the "TKH next chapter" brand; the career team sees the plain organisation name.
function Navbar({ role, onHome, onProfile, onSignOut }) {
  const alumni = role === 'alumni'
  return (
    <nav className={`navbar ${alumni ? 'dark' : ''}`}>
      <button type="button" className="brand" onClick={onHome}>
        {alumni ? <><span className="tkh">TKH</span> <span className="next-chapter">next chapter</span></> : <img className="brand-logo" src={logo} alt="The Knowledge House" />}
      </button>
      <div className="nav-actions">
        <span className="role-chip">{alumni ? 'Alumni' : 'Admin'}</span>
        <button type="button" className="sign-in-button" onClick={onSignOut}>Sign out</button>
        {alumni && <button type="button" className="avatar-button" onClick={onProfile} aria-label="Open profile"><Avatar /></button>}
      </div>
    </nav>
  )
}

export default Navbar
