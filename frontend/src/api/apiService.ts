// src/api/apiService.ts
// This file contains functions for making API requests to the backend

import axios from 'axios';
import { API_BASE_URL, API_TIMEOUT } from './config';

// Create an axios instance with default config
const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: API_TIMEOUT,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add request interceptor to include auth token in requests
api.interceptors.request.use((config) => {
  // Get token from localStorage
  const token = localStorage.getItem('token');
  
  // If token exists, add it to the request headers
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  
  return config;
});

// Auth API endpoints

interface LoginRequest {
  email: string;
  password: string;
}

interface RegisterRequest {
  full_name: string;
  email: string;
  password: string;
}

interface LoginResponse {
  access_token: string;
  token_type: string;
}

interface UserResponse {
  id: number;
  full_name: string;
  email: string;
  is_active: boolean;
}

// Function to login a user
export const login = async (credentials: LoginRequest): Promise<LoginResponse> => {
  const response = await api.post<LoginResponse>('/auth/login', credentials);
  return response.data;
};

// Function to register a new user
export const register = async (userData: RegisterRequest): Promise<UserResponse> => {
  const response = await api.post<UserResponse>('/auth/register', userData);
  return response.data;
};

// Function to get current user's profile
export const getCurrentUser = async (): Promise<UserResponse> => {
  const response = await api.get<UserResponse>('/auth/me');
  return response.data;
};

// Plaid API endpoints

// Function to create a link token
export const createLinkToken = async (userId: number): Promise<{ link_token: string }> => {
  const response = await api.post<{ link_token: string; status: string }>(
    '/plaid/create_link_token/',
    { user_id: userId, client_name: 'Personal Budget Tracker' }
  );
  return { link_token: response.data.link_token };
};

// Function to exchange a public token for an access token
export const exchangePublicToken = async (
  publicToken: string,
  userId: number,
  institutionId?: string,
  institutionName?: string
) => {
  const response = await api.post('/plaid/exchange_token/', {
    public_token: publicToken,
    user_id: userId,
    institution_id: institutionId,
    institution_name: institutionName,
  });
  return response.data;
};

// Function to sync transactions
export const syncTransactions = async (
  accessToken: string,
  userId: number,
  cursor?: string
) => {
  const response = await api.post('/plaid/sync_transactions/', {
    access_token: accessToken,
    user_id: userId,
    cursor,
  });
  return response.data;
};

// Error handler function
export const handleApiError = (error: any): string => {
  if (error.response) {
    // The request was made and the server responded with a status code
    // that falls out of the range of 2xx
    const data = error.response.data;
    return data.detail || data.message || 'An error occurred with the API';
  } else if (error.request) {
    // The request was made but no response was received
    return 'No response from server. Please check your internet connection.';
  } else {
    // Something happened in setting up the request that triggered an Error
    return error.message || 'An unknown error occurred';
  }
};

export default api;