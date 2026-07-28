import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './styles/global.css'
import App from './App.tsx'

// 全局 React 错误捕获
window.addEventListener('error', (e) => {
  console.error('[GLOBAL_ERROR]', e.message, e.error?.stack);
  const el = document.getElementById('react-error-log');
  if (el) {
    el.textContent += `\n[${new Date().toLocaleTimeString()}] ${e.message}\n${e.error?.stack || ''}`;
  }
});

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)