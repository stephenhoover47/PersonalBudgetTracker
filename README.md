# Personal Budget Tracker

A personal finance application that utilizes the Plaid API to retrieve bank transactions and provide spending analytics.

## Features

- Integration with Plaid API to securely connect to bank accounts
- Automatic transaction categorization and analysis
- Budget tracking and spending alerts
- SQL-powered analytics and reporting
- Visualization options (PowerBI or custom frontend)

## Architecture

The application consists of:

1. **Backend**: FastAPI + PostgreSQL (Deployed on Railway)
   - Plaid API integration
   - Database management
   - Analytics engine with raw SQL queries
   - RESTful API
   - Serverless deployment

2. **Database**: Neon PostgreSQL (Serverless)
   - Transaction data
   - User accounts
   - Budget settings
   - Categories
   - Secure, scalable, and cost-effective

3. **Analytics & Visualization**: 
   - Option 1: PowerBI for data visualization
   - Option 2: Custom frontend web application

## Setup

See individual README files in the backend and frontend directories for setup instructions.

### Neon PostgreSQL Setup

1. Create a free account at [Neon](https://neon.tech/)
2. Create a new project and database
3. Get your connection string from the Neon dashboard
4. Update your `.env` file with the Neon connection string:
   ```
   DATABASE_URL=postgresql://username:password@endpoint.neon.tech/database?sslmode=require
   ```
5. Run the connection test script to verify:
   ```
   cd backend
   python scripts/test_neon_connection.py
   ```

### Railway Deployment

1. Create a free account at [Railway](https://railway.app/)
2. Create a new project and link your GitHub repository
3. Set up environment variables in Railway dashboard:
   - PLAID_CLIENT_ID
   - PLAID_SECRET
   - PLAID_ENV
   - DATABASE_URL (from Neon PostgreSQL)
4. Configure build and start commands:
   - Build command: `pip install -r backend/requirements.txt`
   - Start command: `cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Deploy your application

## Development Roadmap

1. ✅ Initial Plaid API integration
2. ✅ Transaction syncing functionality
3. ✅ Neon PostgreSQL database integration
4. ✅ Railway deployment setup
5. ✅ Analytics engine with SQL queries
6. 🔄 User authentication
7. 🔄 Advanced budget features
8. ⬜ PowerBI integration
9. ⬜ Web frontend (optional)
