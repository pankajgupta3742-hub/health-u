import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// In development, /api requests are forwarded to the Health-U API so the browser stays on one origin.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3015,
    host: '0.0.0.0',
    allowedHosts: ['.e2b.app', 'localhost'],
    proxy: { '/api': { target: 'http://127.0.0.1:8000', changeOrigin: false } },
  },
  preview: {
    port: 4173,
    host: '0.0.0.0',
    proxy: { '/api': { target: 'http://127.0.0.1:8000', changeOrigin: false } },
  },
});
