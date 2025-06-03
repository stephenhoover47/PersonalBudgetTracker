// src/pages/Dashboard.tsx
// Simple dashboard to show user information

import React from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const Dashboard: React.FC = () => {
  const { user } = useAuth();
  
  return (
    <div className="container">
      <div className="card">
        <h1>Dashboard</h1>
        <p>Welcome, {user?.full_name || 'User'}!</p>
        
        <div style={{ margin: '20px 0' }}>
          <Link to="/link-account">
            <button className="button">Link Bank Account</button>
          </Link>
        </div>
        
        <div className="info-card">
          <h2>User Information</h2>
          <p><strong>Full Name:</strong> {user?.full_name}</p>
          <p><strong>Email:</strong> {user?.email}</p>
          <p><strong>User ID:</strong> {user?.id}</p>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;