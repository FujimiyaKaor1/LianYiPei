import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import { AuthProvider } from '@/src/context/AuthContext';
import '../index.css';
import './homepage.css';

createRoot(document.getElementById('indisea-root')!).render(
  <StrictMode><BrowserRouter><AuthProvider><App /></AuthProvider></BrowserRouter></StrictMode>,
);
