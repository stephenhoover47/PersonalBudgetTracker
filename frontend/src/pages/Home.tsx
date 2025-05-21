// src/pages/Home.tsx
// Simple home page with links to authentication and Plaid Link

import React from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const Home: React.FC = () => {
  const { isAuthenticated } = useAuth();
  
  return (
    <div className="container">
      <div className="card">
        <h1>Personal Budget Tracker API Frontend</h1>
        <p>This is a simple frontend for authenticating users and connecting bank accounts via Plaid.</p>
        
        {isAuthenticated ? (
          <div>
            <h2>You are logged in!</h2>
            <div className="button-group">
              <Link to="/link-account">
                <button className="button">Link Bank Account</button>
              </Link>
            </div>
          </div>
        ) : (
          <div>
            <h2>Please log in or register</h2>
            <div className="button-group">
              <Link to="/login">
                <button className="button">Login</button>
              </Link>
              <Link to="/register">
                <button className="button">Register</button>
              </Link>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default Home;