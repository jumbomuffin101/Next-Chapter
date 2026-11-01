import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // listen on the network too, so phones on the same Wi-Fi can open the in-room sign-up QR link
  server: { host: true },
})
