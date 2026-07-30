import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react-swc';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    proxy: {
      '/api/v1': {
        target: 'http://localhost:9000',
        changeOrigin: true,
      },
      '/v1': {
        target: 'http://localhost:9000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/v1/, '/api/v1'),
      },
    },
    allowedHosts: ['.ngrok-free.dev'],
  },
  optimizeDeps: {
    include: ['@tiptap/react', '@tiptap/starter-kit', '@tiptap/extension-underline'],
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          'antv-g6-3d': ['@antv/g6-extension-3d'],
        },
      },
    },
  },
});