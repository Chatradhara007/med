import React from 'react';
import ReactDOM from 'react-dom/client';
import { AppProvider } from './app/providers';
import { AppRouter } from './app/routes';
import { ConfigRequired } from './app/ConfigRequired';
import { isConfigured } from './config';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    {isConfigured ? (
      <AppProvider>
        <AppRouter />
      </AppProvider>
    ) : (
      <ConfigRequired />
    )}
  </React.StrictMode>
);
