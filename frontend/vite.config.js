import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Dev proxy: `/api` -> FastAPI backend. Override with VITE_BACKEND_URL if needed.
const backend = process.env.VITE_BACKEND_URL || 'http://127.0.0.1:8000';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: backend, changeOrigin: true },
    },
  },
  preview: {
    port: 4173,
    proxy: {
      '/api': { target: backend, changeOrigin: true },
    },
  },
  build: {
    outDir: 'dist',
    chunkSizeWarningLimit: 900,
    rollupOptions: {
      output: {
        manualChunks: {
          three: ['three'],
          r3f: ['@react-three/fiber', '@react-three/drei'],
          charts: ['chart.js', 'react-chartjs-2'],
          react: ['react', 'react-dom', 'react-router-dom'],
        },
      },
    },
  },
});
