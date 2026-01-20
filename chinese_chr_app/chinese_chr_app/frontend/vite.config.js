import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  // Serve app from the root of the domain in production
  base: '/',
  plugins: [react()],
  server: {
    port: 3000,
    // Proxy only in development
    proxy: process.env.NODE_ENV === 'development' ? {
      '/api': {
        target: 'http://localhost:5001',
        changeOrigin: true
      }
    } : undefined
  }
})
