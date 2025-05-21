// src/api/config.ts
// Configuration for API endpoints

// Base URL for API requests
// In development, this will use the proxy set up in webpack.config.js
// In production, set this to your actual backend URL
export const API_BASE_URL = process.env.NODE_ENV === 'production'
  ? 'https://your-railway-app-url.up.railway.app' // Replace with your actual Railway app URL
  : '/api';

// Timeout for API requests (in milliseconds)
export const API_TIMEOUT = 10000;