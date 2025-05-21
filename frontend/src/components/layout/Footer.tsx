// src/components/layout/Footer.tsx
// This component renders the footer for the application

import React from 'react';
import './Footer.css';

const Footer: React.FC = () => {
  // Get current year for copyright notice
  const currentYear = new Date().getFullYear();
  
  return (
    <footer className="footer">
      <div className="footer-container">
        <div className="footer-content">
          <div className="footer-section">
            <h4>Personal Budget Tracker</h4>
            <p>Track your finances with ease using Plaid integration.</p>
          </div>
          
          <div className="footer-section">
            <h4>Links</h4>
            <ul className="footer-links">
              <li><a href="https://plaid.com/" target="_blank" rel="noopener noreferrer">Plaid</a></li>
              <li><a href="https://www.railway.app/" target="_blank" rel="noopener noreferrer">Railway</a></li>
              <li><a href="https://github.com/" target="_blank" rel="noopener noreferrer">GitHub</a></li>
            </ul>
          </div>
        </div>
        
        <div className="footer-bottom">
          <p>&copy; {currentYear} Personal Budget Tracker. All rights reserved.</p>
        </div>
      </div>
    </footer>
  );
};

export default Footer;