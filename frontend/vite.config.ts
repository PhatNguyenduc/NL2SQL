import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 9222,
    proxy: {
      '/api': {
        target: 'http://18.138.220.47:8000',
        changeOrigin: true,
      }
    }
  },
  // Build configuration
  build: {
    outDir: 'dist',
    sourcemap: false,
    minify: 'esbuild',
  }
})

