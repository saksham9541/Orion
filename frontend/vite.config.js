import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  server: { port: 5173, open: true },
  build: {
    rollupOptions: {
      output: {
        // Charts are only needed on the overview, so they are split out and
        // the landing page no longer pays for them.
        manualChunks: {
          react: ['react', 'react-dom', 'react-router-dom'],
          motion: ['framer-motion'],
          charts: ['recharts'],
          three: ['three', '@react-three/fiber'],
        },
      },
    },
  },
})
