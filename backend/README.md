# Personal Budget Tracker - Backend

A FastAPI backend that connects to Plaid API to track personal finances.

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Create a `.env` file with the following variables:
```
PLAID_CLIENT_ID=your_plaid_client_id
PLAID_SECRET=your_plaid_secret
PLAID_ENV=sandbox  # or development, production
DATABASE_URL=postgresql://username:password@hostname/database
```

3. Initialize the database:
```bash
# For local development with PostgreSQL:
createdb budget_tracker

# Run migrations
cd backend
alembic upgrade head
```

## Development

Run the development server:
```bash
uvicorn app.main:app --reload
```

The API will be available at http://localhost:8000

API documentation is available at http://localhost:8000/docs

## Database

The application uses PostgreSQL with SQLAlchemy ORM. The database schema includes:

- Users
- Plaid Items (connected bank accounts)
- Accounts
- Transactions
- Categories
- Budgets

### Migrations

Database migrations are managed with Alembic:

```bash
# Create a new migration
alembic revision --autogenerate -m "Description of changes"

# Apply migrations
alembic upgrade head

# Rollback a migration
alembic downgrade -1
```

## Plaid Integration

### Using Plaid Link

The backend provides endpoints for integrating with Plaid Link, including support for Plaid Hosted Link:

#### Regular Link
1. Create a Link Token (Legacy method):
```
POST /plaid/create_link_token/
{
  "user_id": 1,
  "client_name": "Personal Budget Tracker"
}
```
Returns a link token that can be used to initialize Plaid Link on the frontend.

#### Hosted Link (Recommended)
2. Create a Hosted Link:
```
POST /plaid/create_hosted_link/
{
  "user_id": 1,
  "redirect_uri": "https://yourapp.com/plaid/callback",
  "client_name": "Personal Budget Tracker"
}
```
Returns both a link token and a hosted_link_url. The hosted_link_url can be used to redirect users directly to Plaid's hosted Link interface without needing to implement Plaid Link in your frontend.

#### Common Endpoints
3. Exchange Public Token:
```
POST /plaid/exchange_token/
{
  "public_token": "public-token-from-plaid-link",
  "user_id": 1,
  "institution_id": "ins_123456",
  "institution_name": "Bank Name"
}
```
Exchanges the public token for an access token and stores the Plaid item in the database.

4. Sync Transactions:
```
POST /plaid/sync_transactions/
{
  "access_token": "access-token",
  "user_id": 1,
  "cursor": "optional-cursor-for-pagination"
}
```
Syncs transactions for the specified Plaid item and user.

### Sandbox Testing

For testing in the Plaid sandbox environment:

```
GET /plaid/sandbox_token/
```
Returns a sandbox public token that can be used for testing.

## Analytics

The application includes SQL-based analytics for generating reports:

- Monthly spending by category
- Income vs expenses by month
- Budget vs actual spending
- Top merchants by spending
- Spending trends over time
- Account balances
- Transaction statistics
- Recurring transactions identification
- Category breakdown by year
- Spending patterns by day of week
- Savings rate analysis

## Neon PostgreSQL Setup

To use Neon for PostgreSQL database:

1. Create a free account at [Neon](https://neon.tech/)

2. Create a new project in the Neon dashboard

3. Create a new database within your project

4. Get the connection string from the dashboard and update your `.env` file:
```
DATABASE_URL=postgresql://username:password@your-neon-endpoint.neon.tech/database
```

5. Run migrations to initialize the database:
```bash
alembic upgrade head
```

## Railway Deployment

To deploy your application using Railway:

1. Create a free account at [Railway](https://railway.app/)

2. Create a new project in Railway

3. Link your GitHub repository:
   - Go to your project settings
   - Connect your GitHub repository
   - Select the repository to deploy

4. Set up environment variables in Railway dashboard:
   - PLAID_CLIENT_ID
   - PLAID_SECRET
   - PLAID_ENV
   - DATABASE_URL (use your Neon PostgreSQL connection string)

5. Configure the build and start commands:
   - Build command: `pip install -r backend/requirements.txt`
   - Start command: `cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT`

6. Deploy your application:
   - Railway will automatically deploy your application when you push changes to your GitHub repository

## Contributing

1. Use raw SQL queries for complex analytics in the `app/analytics/sql_queries.py` file
2. Use SQLAlchemy ORM for standard CRUD operations
3. Run `alembic revision --autogenerate` after making model changes