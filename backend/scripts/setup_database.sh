#!/bin/bash
# Setup script for the database

# Check if PostgreSQL is installed
if ! command -v psql &> /dev/null; then
    echo "PostgreSQL is not installed. Please install PostgreSQL first."
    exit 1
fi

# Default database name
DB_NAME="budget_tracker"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    key="$1"
    case $key in
        --database)
        DB_NAME="$2"
        shift
        shift
        ;;
        --help)
        echo "Usage: $0 [--database DB_NAME]"
        echo "Sets up the database for Personal Budget Tracker"
        echo ""
        echo "Options:"
        echo "  --database DB_NAME  Specify database name (default: budget_tracker)"
        echo "  --help              Show this help message"
        exit 0
        ;;
        *)
        echo "Unknown option: $1"
        echo "Use --help for usage information"
        exit 1
        ;;
    esac
done

# Navigate to the project root
cd "$(dirname "$0")/.." || exit

# Create the database if it doesn't exist
echo "Creating database $DB_NAME..."
psql -c "SELECT 1 FROM pg_database WHERE datname = '$DB_NAME'" | grep -q 1 || psql -c "CREATE DATABASE $DB_NAME"

# Set DATABASE_URL environment variable
export DATABASE_URL="postgresql://postgres:postgres@localhost/$DB_NAME"

# Run migrations
echo "Running database migrations..."
alembic upgrade head

# Initialize sample data
echo "Initializing sample data..."
python scripts/init_sample_data.py

echo "Database setup complete!"
echo "You can now start the application with: uvicorn app.main:app --reload"