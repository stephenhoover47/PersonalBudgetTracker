// src/context/AuthContext.tsx
// This file provides authentication context to the entire application

import React, { createContext, useState, useContext, useEffect } from 'react';
import { login as apiLogin, register as apiRegister, getCurrentUser, handleApiError } from '../api/apiService';

// Define the shape of our user object
interface User {
  id: number;
  email: string;
  username: string;
}

// Define the shape of our auth context
interface AuthContextType {
  // Current user information (null if not logged in)
  user: User | null;
  // Whether the user is authenticated
  isAuthenticated: boolean;
  // Whether auth operations are loading
  loading: boolean;
  // Function to log the user in
  login: (email: string, password: string) => Promise<boolean>;
  // Function to register a new user
  register: (username: string, email: string, password: string) => Promise<boolean>;
  // Function to log the user out
  logout: () => void;
  // Any error messages from auth operations
  error: string | null;
  // Clear any error messages
  clearError: () => void;
}

// Create the context with a default value
const AuthContext = createContext<AuthContextType>({
  user: null,
  isAuthenticated: false,
  loading: false,
  login: async () => false,
  register: async () => false,
  logout: () => {},
  error: null,
  clearError: () => {},
});

// Custom hook for easy context access throughout the app
export const useAuth = () => useContext(AuthContext);

// The provider component that wraps our app and makes auth object available
export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  // State to store user information
  const [user, setUser] = useState<User | null>(null);
  // State to track authentication status
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  // State to track loading status during auth operations
  const [loading, setLoading] = useState<boolean>(false);
  // State to store error messages
  const [error, setError] = useState<string | null>(null);

  // Function to clear error messages
  const clearError = () => setError(null);

  // Check if user is already logged in (from localStorage) when the app loads
  useEffect(() => {
    const checkAuth = async () => {
      const token = localStorage.getItem('token');
      
      if (token) {
        try {
          setLoading(true);
          // Verify token by fetching current user data
          const userData = await getCurrentUser();
          setUser(userData);
          setIsAuthenticated(true);
        } catch (err) {
          // If token is invalid, clear it
          localStorage.removeItem('token');
          setError('Session expired. Please log in again.');
        } finally {
          setLoading(false);
        }
      }
    };
    
    checkAuth();
  }, []);

  // Function to log in a user
  const login = async (email: string, password: string): Promise<boolean> => {
    try {
      setLoading(true);
      setError(null);
      
      // Call the login API
      const response = await apiLogin({ email, password });
      
      // Store token in localStorage for persistence
      localStorage.setItem('token', response.token);
      
      // Update state with user data
      setUser(response.user);
      setIsAuthenticated(true);
      return true;
    } catch (err) {
      setError(handleApiError(err));
      return false;
    } finally {
      setLoading(false);
    }
  };

  // Function to register a new user
  const register = async (username: string, email: string, password: string): Promise<boolean> => {
    try {
      setLoading(true);
      setError(null);
      
      // Call the register API
      const response = await apiRegister({ username, email, password });
      
      // Store token in localStorage for persistence
      localStorage.setItem('token', response.token);
      
      // Update state with user data
      setUser(response.user);
      setIsAuthenticated(true);
      return true;
    } catch (err) {
      setError(handleApiError(err));
      return false;
    } finally {
      setLoading(false);
    }
  };

  // Function to log out the user
  const logout = () => {
    // Remove token from localStorage
    localStorage.removeItem('token');
    
    // Update state
    setUser(null);
    setIsAuthenticated(false);
  };

  // Value object that will be passed to consumers of this context
  const value = {
    user,
    isAuthenticated,
    loading,
    login,
    register,
    logout,
    error,
    clearError,
  };

  // Provide the context to child components
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export default AuthContext;