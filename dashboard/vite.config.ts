import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // `npm run dev` serves the dashboard on http://localhost:5173 and forwards /api to the API,
    // started from backend/ with `uv run python -m moonwalkers.api` (decision 0014).
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
})
