// Development entry point so alumni work can be previewed without editing App.jsx.
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import UserDashboard from './UserDashboard.jsx'
import '../index.css' // shared colors and fonts
import '../tkh.css'
import './preview.css'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <main className="alumni-preview"><UserDashboard /></main>
  </StrictMode>,
)
