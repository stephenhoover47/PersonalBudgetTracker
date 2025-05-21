// server.js
// This is an Express server that serves your React application in production.
//
// WHY IS THIS NEEDED?
// -----------------
// 1. Railway (and most hosting platforms) expect a server that listens on a port
//    React's development server does this, but your production build is just static files
//
// 2. Your React app uses client-side routing (React Router), but when deployed,
//    direct URL access to routes like /dashboard would return 404 errors
//    This server solves that by returning index.html for all routes
//
// 3. It provides a way to serve your built React app (the files in the 'dist' folder)
//    without needing to configure a separate web server like Nginx

const express = require('express');
const path = require('path');
const cors = require('cors');

// Create Express app
const app = express();
const PORT = process.env.PORT || 3000;

// Enable CORS (Cross-Origin Resource Sharing)
// This allows your frontend to make requests to different origins (important for API calls)
app.use(cors());

// Parse JSON request bodies
app.use(express.json());

// Serve static files from the 'dist' directory
// This is where webpack outputs your built React app
// Express will serve these files when requested (CSS, JS, images, etc.)
app.use(express.static(path.join(__dirname, 'dist')));

// Health check endpoint for Railway
// Railway will ping this to make sure your app is running
app.get('/health', (req, res) => {
  res.status(200).send('OK');
});

// The key part: handle all other routes by returning index.html
// This enables client-side routing with React Router
// Without this, direct access to URLs like /dashboard would return 404
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'dist', 'index.html'));
});

// Start the server and listen on the specified port
app.listen(PORT, () => {
  console.log(`Frontend server running on port ${PORT}`);
});