import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App';
import './homepage.css';

createRoot(document.getElementById('indisea-root')!).render(
  <StrictMode><BrowserRouter basename="/indisea"><App /></BrowserRouter></StrictMode>,
);
