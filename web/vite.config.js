import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Artifacts land in one place at the repo root (SPEC §C37); dist/ is gitignored.
// vite-plugin-pwa is installed but not configured until T6 (PWA shell).
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: '../dist/web',
    emptyOutDir: true,
  },
})
