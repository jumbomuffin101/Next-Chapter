import { useEffect, useState } from 'react'
import Navbar from './components/Navbar.jsx'
import AdminDashboard from './admin/AdminDashboard.jsx'
import Landing from './landing/Landing.jsx'
import Onboarding from './onboarding/Onboarding.jsx'
import UserDashboard from './user/UserDashboard.jsx'
import ProfilePage from './user/ProfilePage.jsx'
import { clearSession, getSession } from './api.js'
import { isOnboarded, readSavedProfile } from './user/profile.js'

// Landing (choose role) -> admin login -> admin dashboard
//                       -> alumni sign in / create -> onboarding (until a profile exists) -> alumni dashboard
function App() {
  const [session, setSession] = useState(getSession)
  const [page, setPage] = useState('dashboard') // alumni: 'dashboard' | 'profile'

  useEffect(() => { document.title = session?.role === 'alumni' ? 'TKH next chapter' : session?.role === 'admin' ? 'TKH · Career team' : 'The Knowledge House' }, [session])

  const signOut = () => { clearSession(); setSession(null); setPage('dashboard') }
  const enter = () => { setSession(getSession()); setPage('dashboard') }

  if (!session) return <Landing onAdmin={enter} onAlumni={enter} />

  if (session.role === 'alumni' && !isOnboarded(readSavedProfile())) {
    return <Onboarding key={session.id} onDone={enter} />
  }

  return (
    <>
      <Navbar role={session.role} onHome={() => setPage('dashboard')} onProfile={() => setPage('profile')} onSignOut={signOut} />
      <main className="page">
        {session.role === 'admin' ? <AdminDashboard onExpired={signOut} />
          : page === 'profile' ? <ProfilePage key={session.id} onSignOut={signOut} />
          : <UserDashboard key={session.id} />}
      </main>
    </>
  )
}

export default App
