// src/pages/NotFound.tsx
// Simple 404 page

import React from 'react';
import { Link } from 'react-router-dom';

const NotFound: React.FC = () => {
  return (
    <div className="container">
      <div className="card" style={{ textAlign: 'center' }}>
        <h1>404 - Page Not Found</h1>
        <p>The page you are looking for does not exist.</p>
        <Link to="/">
          <button className="button">Go Home</button>
        </Link>
      </div>
    </div>
  );
};

export default NotFound;