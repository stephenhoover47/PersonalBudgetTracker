# Transaction Sync Guide

This guide explains how to set up and use the automated transaction syncing functionality for the Personal Budget Tracker.

## Overview

The transaction sync system automatically retrieves new transactions from linked bank accounts via Plaid API and stores them in your database. It supports:

- **Incremental syncing** using Plaid's cursor-based pagination
- **Account balance updates** 
- **Error handling and retry logic**
- **Automated nightly runs** via cron jobs
- **Sandbox testing** environment

## Quick Start (Sandbox Testing)

### 1. Test the Sync System

First, test the sync functionality in sandbox mode:

```bash
cd backend
python scripts/test_sync_sandbox.py
```

This script will:
- Create a test user
- Link a sandbox bank account (First Platypus Bank)
- Run a transaction sync
- Show you the results

### 2. Manual Sync Testing

Test the sync script manually:

```bash
# Dry run (no database changes)
python scripts/sync_transactions.py --dry-run --verbose

# Real sync for all users
python scripts/sync_transactions.py --verbose

# Sync for specific user
python scripts/sync_transactions.py --user-id 1 --verbose
```

### 3. API Endpoint Testing

Test via API endpoints:

```bash
# Dry run via API
curl -X POST "http://localhost:8000/plaid/sync_all_dry_run/"

# Real sync via API
curl -X POST "http://localhost:8000/plaid/sync_all/"
```

## Setting Up Automated Syncing

### Option 1: Cron Jobs (Recommended for Production)

Use the interactive setup script:

```bash
cd backend
chmod +x scripts/setup_cron.sh
./scripts/setup_cron.sh
```

This will give you options to:
- Add nightly sync (2 AM daily)
- Add hourly sync (for testing)
- Add custom schedule
- Remove existing jobs
- Test the sync script

### Option 2: Manual Cron Setup

Add to your crontab manually:

```bash
# Edit crontab
crontab -e

# Add this line for nightly sync at 2 AM
0 2 * * * cd /path/to/PersonalBudgetTracker/backend && python scripts/sync_transactions.py >> logs/cron_sync.log 2>&1

# Add this line for hourly sync (testing)
0 * * * * cd /path/to/PersonalBudgetTracker/backend && python scripts/sync_transactions.py --verbose >> logs/cron_sync.log 2>&1
```

### Option 3: Systemd Timer (Alternative)

Create a systemd service and timer for more robust scheduling:

```bash
# Create service file
sudo nano /etc/systemd/system/budget-sync.service

[Unit]
Description=Personal Budget Tracker Transaction Sync
After=network.target

[Service]
Type=oneshot
User=your-username
WorkingDirectory=/path/to/PersonalBudgetTracker/backend
ExecStart=/usr/bin/python3 scripts/sync_transactions.py
StandardOutput=append:/path/to/PersonalBudgetTracker/backend/logs/systemd_sync.log
StandardError=append:/path/to/PersonalBudgetTracker/backend/logs/systemd_sync.log

[Install]
WantedBy=multi-user.target
```

```bash
# Create timer file
sudo nano /etc/systemd/system/budget-sync.timer

[Unit]
Description=Run Budget Sync Daily
Requires=budget-sync.service

[Timer]
OnCalendar=*-*-* 02:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

```bash
# Enable and start
sudo systemctl enable budget-sync.timer
sudo systemctl start budget-sync.timer
```

## Configuration

### Environment Variables

Ensure these are set in your `.env` file:

```bash
# Plaid Configuration
PLAID_CLIENT_ID=your_plaid_client_id
PLAID_SECRET=your_plaid_secret
PLAID_ENV=sandbox  # or development, production

# Database Configuration
DATABASE_URL=postgresql://username:password@hostname/database

# Optional: Secret key for JWT tokens
SECRET_KEY=your-secret-key
```

### Logging

Logs are written to:
- `logs/sync_transactions.log` - Manual sync runs
- `logs/cron_sync.log` - Automated cron runs
- `logs/systemd_sync.log` - Systemd timer runs (if used)

## Monitoring and Troubleshooting

### Check Sync Status

```bash
# View recent logs
tail -f logs/sync_transactions.log

# Check cron logs
tail -f logs/cron_sync.log

# List cron jobs
crontab -l

# Check systemd timer status
sudo systemctl status budget-sync.timer
```

### Common Issues

#### 1. No Transactions Found
- **Cause**: New Plaid items may not have transactions yet
- **Solution**: Wait for new transactions or test with sandbox data

#### 2. Authentication Errors
- **Cause**: Plaid access tokens may have expired
- **Solution**: Re-link accounts through the frontend

#### 3. Database Connection Issues
- **Cause**: Database URL or credentials incorrect
- **Solution**: Check DATABASE_URL in .env file

#### 4. Permission Errors
- **Cause**: Script not executable or wrong working directory
- **Solution**: Run `chmod +x scripts/sync_transactions.py`

### Debug Mode

Enable verbose logging:

```bash
python scripts/sync_transactions.py --verbose
```

This will show:
- Detailed API calls
- Database operations
- Error stack traces

## Production Deployment

### Railway Deployment

For Railway deployment, you can use Railway's built-in cron jobs:

1. Add a new service for the sync script
2. Set the command to: `python scripts/sync_transactions.py`
3. Configure it to run on a schedule

### Docker Deployment

Add to your Dockerfile:

```dockerfile
# Install cron
RUN apt-get update && apt-get install -y cron

# Copy sync script
COPY scripts/sync_transactions.py /app/scripts/

# Add cron job
RUN echo "0 2 * * * cd /app && python scripts/sync_transactions.py >> logs/cron_sync.log 2>&1" > /etc/cron.d/budget-sync
RUN chmod 0644 /etc/cron.d/budget-sync
RUN crontab /etc/cron.d/budget-sync

# Start cron in entrypoint
CMD ["cron", "-f"]
```

## API Reference

### Manual Sync Endpoints

- `POST /plaid/sync_all/` - Sync all linked accounts
- `POST /plaid/sync_all_dry_run/` - Dry run sync (no database changes)
- `POST /plaid/sync_transactions/` - Sync specific account

### Response Format

```json
{
  "status": "success",
  "items_processed": 2,
  "items_successful": 2,
  "items_failed": 0,
  "total_transactions_added": 15,
  "total_transactions_modified": 0,
  "total_transactions_removed": 0,
  "duration_seconds": 3.45,
  "start_time": "2024-01-15T02:00:00",
  "end_time": "2024-01-15T02:00:03.45",
  "errors": []
}
```

## Security Considerations

1. **Access Tokens**: Plaid access tokens are stored encrypted in the database
2. **Logs**: Sensitive data is not logged
3. **Permissions**: Scripts run with minimal required permissions
4. **Network**: All API calls use HTTPS

## Performance

- **Incremental Sync**: Only new/modified transactions are retrieved
- **Batch Processing**: Transactions are processed in batches
- **Retry Logic**: Failed API calls are retried with exponential backoff
- **Connection Pooling**: Database connections are reused efficiently

## Support

For issues or questions:
1. Check the logs first
2. Test with sandbox environment
3. Verify environment variables
4. Check Plaid API status 