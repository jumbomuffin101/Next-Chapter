import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import './tkh.css'
import './theme.css'
import App from './App.jsx'
import { applyComfort, applyTheme, followDeviceTheme, readComfort, readTheme } from './comfort.js'

// display preferences before the first paint, so there's no flash of the wrong look
applyComfort(readComfort())
applyTheme(readTheme())
followDeviceTheme()

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
