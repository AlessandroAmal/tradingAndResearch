import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Responsive dev server; host:true so it's reachable from a phone on the LAN.
export default defineConfig({
  plugins: [react()],
  server: { host: true, port: 5273, strictPort: true },
})
