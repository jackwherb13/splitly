import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

// Artifacts land in one place at the repo root (SPEC §C37); dist/ is gitignored.
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['apple-touch-icon.png'],
      manifest: {
        name: 'Splitly',
        short_name: 'Splitly',
        description: 'Shared house ledger — who owes who.',
        start_url: '/',
        scope: '/',
        // standalone is what makes iOS treat it as an app, which §R1 requires
        // before it will deliver push at all.
        display: 'standalone',
        background_color: '#FFFCF5',
        theme_color: '#064E3B',
        icons: [
          { src: 'icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: 'icon-512.png', sizes: '512x512', type: 'image/png' },
          {
            src: 'icon-maskable-512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'maskable',
          },
        ],
      },
    }),
  ],
  build: {
    outDir: '../dist/web',
    emptyOutDir: true,
  },
})
