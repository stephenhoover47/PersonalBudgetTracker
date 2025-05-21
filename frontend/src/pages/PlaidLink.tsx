// src/pages/PlaidLink.tsx
// Component for handling Plaid Link integration

import React, { useEffect, useState, useCallback } from 'react';
import { usePlaidLink } from 'react-plaid-link';
import { useAuth } from '../context/AuthContext';
import { createLinkToken, exchangePublicToken } from '../api/apiService';
import './PlaidLink.css';

const PlaidLink: React.FC = () => {
  // State for link token and errors
  const [linkToken, setLinkToken] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<boolean>(false);
  const [loading, setLoading] = useState<boolean>(false);
  
  // Get the current user from auth context
  const { user } = useAuth();
  
  // Function to get a link token from the backend
  const getLinkToken = useCallback(async () => {
    if (!user) return;
    
    try {
      setLoading(true);
      setError(null);
      
      // Call the API to get a link token
      const response = await createLinkToken(user.id);
      setLinkToken(response.link_token);
    } catch (err: any) {
      console.error('Error getting link token:', err);
      setError('Failed to initialize Plaid Link: ' + (err.message || 'Unknown error'));
    } finally {
      setLoading(false);
    }
  }, [user]);
  
  // Get a link token when the component mounts
  useEffect(() => {
    getLinkToken();
  }, [getLinkToken]);
  
  // Function that runs when Plaid Link successfully completes
  const onSuccess = useCallback(async (public_token: string, metadata: any) => {
    if (!user) return;
    
    try {
      setLoading(true);
      setError(null);
      
      // Exchange the public token for an access token
      await exchangePublicToken(
        public_token,
        user.id,
        metadata.institution?.institution_id,
        metadata.institution?.name
      );
      
      // Set success state
      setSuccess(true);
    } catch (err: any) {
      console.error('Error exchanging public token:', err);
      setError('Failed to link account: ' + (err.message || 'Unknown error'));
    } finally {
      setLoading(false);
    }
  }, [user]);
  
  // Config object for the Plaid Link hook
  const config = {
    token: linkToken,
    onSuccess,
    // Optional: Add Plaid Link customization options here
  };
  
  // Initialize the Plaid Link hook
  const { open, ready } = usePlaidLink(config);
  
  // Function to handle the "Link Account" button click
  const handleLinkClick = () => {
    if (ready) {
      open();
    }
  };
  
  // Reset the component state to try again
  const handleReset = () => {
    setSuccess(false);
    setError(null);
    getLinkToken();
  };
  
  // If we're still loading the link token
  if (loading && !linkToken) {
    return (
      <div className="container">
        <div className="card plaid-card">
          <h1>Link Your Bank Account</h1>
          <div className="loading">Loading Plaid Link...</div>
        </div>
      </div>
    );
  }
  
  // If we have an error
  if (error) {
    return (
      <div className="container">
        <div className="card plaid-card">
          <h1>Something Went Wrong</h1>
          <div className="error-message">{error}</div>
          <button className="button" onClick={handleReset}>
            Try Again
          </button>
        </div>
      </div>
    );
  }
  
  // If account linking was successful
  if (success) {
    return (
      <div className="container">
        <div className="card plaid-card">
          <h1>Account Linked Successfully!</h1>
          <p className="success-message">
            Your bank account has been successfully connected to Personal Budget Tracker.
          </p>
          <button className="button" onClick={handleReset}>
            Link Another Account
          </button>
        </div>
      </div>
    );
  }
  
  // Default view - show the "Link Account" button
  return (
    <div className="container">
      <div className="card plaid-card">
        <h1>Link Your Bank Account</h1>
        <p>
          Connect your bank account to Personal Budget Tracker using Plaid.
          Your credentials are securely handled by Plaid and never stored on our servers.
        </p>
        
        <button 
          className="button plaid-button"
          onClick={handleLinkClick}
          disabled={!ready || !linkToken}
        >
          Link Account
        </button>
        
        <div className="plaid-info">
          <p>
            <small>
              By clicking "Link Account", you authorize Personal Budget Tracker to access your
              financial data through Plaid's services.
            </small>
          </p>
        </div>
      </div>
    </div>
  );
};

export default PlaidLink;