// src/components/layout/Header.tsx
// This component renders the header/navigation bar for the application

import React from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import './Header.css';

const Header: React.FC = () => {
  // Get auth context values
  const { isAuthenticated, user, logout } = useAuth();
  const navigate = useNavigate();
  
  // Handle logout
  const handleLogout = () => {
    logout();
    navigate('/login');
  };
  
  return (
    <header className="header">
      <div className="header-container">
        {/* Logo/App Name */}
        <div className="logo">
          <Link to="/">Personal Budget Tracker</Link>
        </div>
        
        {/* Navigation Links */}
        <nav className="nav">
          <ul className="nav-list">
            <li className="nav-item">
              <Link to="/" className="nav-link">Home</Link>
            </li>
            
            {/* Show these links only if user is authenticated */}
            {isAuthenticated && (
              <>
                <li className="nav-item">
                  <Link to="/dashboard" className="nav-link">Dashboard</Link>
                </li>
                <li className="nav-item">
                  <Link to="/link-account" className="nav-link">Link Account</Link>
                </li>
              </>
            )}
          </ul>
        </nav>
        
        {/* Auth Buttons */}
        <div className="auth-buttons">
          {isAuthenticated ? (
            <>
              {/* User is logged in - show user info and logout */}
              <span className="welcome-text">
                Welcome, {user?.username || 'User'}
              </span>
              <button 
                className="logout-button" 
                onClick={handleLogout}
              >
                Logout
              </button>
            </>
          ) : (
            <>
              {/* User is not logged in - show login and register */}
              <Link to="/login" className="login-button">
                Login
              </Link>
              <Link to="/register" className="register-button">
                Register
              </Link>
            </>
          )}
        </div>
      </div>
    </header>
  );
};

export default Header;