import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// En dev, /api se redirige al FastAPI local (127.0.0.1:8000).
// host: true habilita tanto http://localhost:5173 (IPv6) como http://127.0.0.1:5173 (IPv4).
export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
