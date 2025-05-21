// src/index.tsx
// This is the entry point of our React application

import React from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter } from 'react-router-dom';
import App from './App';

// Import global CSS if needed
import './styles/global.css';

// Find the root element in index.html where our app will be mounted
const rootElement = document.getElementById('root');

// Make sure the element exists before trying to render
if (!rootElement) {
  throw new Error('Failed to find the root element');
}

// Create a React root
const root = createRoot(rootElement);

// Render our App component wrapped in BrowserRouter for routing
// BrowserRouter provides routing capabilities to our application
root.render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>
);