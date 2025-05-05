#!/bin/bash
# Script to help with Railway deployment setup

# Check if railway CLI is installed
if ! command -v railway &> /dev/null; then
    echo "Railway CLI not found. Please install it first:"
    echo "npm i -g @railway/cli"
    exit 1
fi

echo "=== Railway Project Setup ==="
echo "This script will help you set up your project on Railway."

# Login to Railway
echo "Logging in to Railway..."
railway login

# Create a new project
echo ""
echo "Creating a new Railway project..."
railway init

# Link the project to the current directory
echo ""
echo "Linking project to this directory..."
railway link

# Set environment variables
echo ""
echo "Setting up environment variables..."
echo "You'll need to set the following variables in the Railway dashboard or via CLI:"
echo "- PLAID_CLIENT_ID"
echo "- PLAID_SECRET"
echo "- PLAID_ENV"
echo "- DATABASE_URL (from Neon PostgreSQL)"
echo ""
echo "Do you want to set these variables now? (y/n)"
read -r answer

if [[ "$answer" == "y" ]]; then
    # Prompt for environment variables
    echo "Enter PLAID_CLIENT_ID:"
    read -r plaid_client_id
    railway variables set PLAID_CLIENT_ID="$plaid_client_id"
    
    echo "Enter PLAID_SECRET:"
    read -r plaid_secret
    railway variables set PLAID_SECRET="$plaid_secret"
    
    echo "Enter PLAID_ENV (sandbox, development, production):"
    read -r plaid_env
    railway variables set PLAID_ENV="$plaid_env"
    
    echo "Enter DATABASE_URL from Neon PostgreSQL:"
    read -r database_url
    railway variables set DATABASE_URL="$database_url"
fi

echo ""
echo "=== Railway Setup Complete ==="
echo "Your project is now set up for Railway deployment."
echo ""
echo "To deploy your project, run:"
echo "railway up"
echo ""
echo "To open the Railway dashboard, run:"
echo "railway open"