// src/App.tsx
// This is the main application component that sets up routes and layout

import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';

// Import components and pages
import Header from './components/layout/Header';
import Footer from './components/layout/Footer';
import Home from './pages/Home';
import Login from './pages/Login';
import Register from './pages/Register';
import Dashboard from './pages/Dashboard';
import PlaidLink from './pages/PlaidLink';
import NotFound from './pages/NotFound';

// Import Auth Provider (to be created)
import { AuthProvider, useAuth } from './context/AuthContext';

// CSS for App component
import './styles/App.css';

// ProtectedRoute component checks if user is authenticated
// If not, it redirects to the login page
const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  // Get authentication state from context
  const { isAuthenticated } = useAuth();
  
  // If not authenticated, redirect to login
  if (!isAuthenticated) {
    return <Navigate to="/login" />;
  }
  
  // If authenticated, render the children components
  return <>{children}</>;
};

// Main App component
const App: React.FC = () => {
  return (
    // Wrap the entire app with AuthProvider to provide authentication context
    <AuthProvider>
      <div className="app">
        {/* Header appears on all pages */}
        <Header />
        
        <main className="main-content">
          {/* Set up routes for different pages */}
          <Routes>
            {/* Public routes */}
            <Route path="/" element={<Home />} />
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            
            {/* Protected routes - require authentication */}
            <Route 
              path="/dashboard" 
              element={
                <ProtectedRoute>
                  <Dashboard />
                </ProtectedRoute>
              } 
            />
            <Route 
              path="/link-account" 
              element={
                <ProtectedRoute>
                  <PlaidLink />
                </ProtectedRoute>
              } 
            />
            
            {/* Catch-all route for 404 errors */}
            <Route path="*" element={<NotFound />} />
          </Routes>
        </main>
        
        {/* Footer appears on all pages */}
        <Footer />
      </div>
    </AuthProvider>
  );
};

export default App;