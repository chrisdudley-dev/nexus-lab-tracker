import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Override when needed:
//   VITE_API_TARGET=http://127.0.0.1:8788 npm run dev -- --host 0.0.0.0 --port 5173
const API_TARGET = process.env.VITE_API_TARGET || 'http://127.0.0.1:8787'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: API_TARGET,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
