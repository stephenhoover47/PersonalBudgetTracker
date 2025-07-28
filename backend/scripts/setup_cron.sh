#!/bin/bash
# Setup script for automated transaction syncing with cron

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Automated Transaction Sync Setup ===${NC}"

# Get the project directory
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo "Project directory: $PROJECT_DIR"

# Check if we're in the right directory
if [[ ! -f "$PROJECT_DIR/app/main.py" ]]; then
    echo -e "${RED}Error: This script must be run from the backend directory${NC}"
    exit 1
fi

# Create logs directory
mkdir -p "$PROJECT_DIR/logs"
echo -e "${GREEN}✓ Created logs directory${NC}"

# Make the sync script executable
chmod +x "$PROJECT_DIR/scripts/sync_transactions.py"
echo -e "${GREEN}✓ Made sync script executable${NC}"

# Function to add cron job
add_cron_job() {
    local schedule="$1"
    local description="$2"
    local command="$3"
    
    # Check if cron job already exists
    if crontab -l 2>/dev/null | grep -q "$command"; then
        echo -e "${YELLOW}⚠ Cron job already exists for $description${NC}"
        return
    fi
    
    # Add the cron job
    (crontab -l 2>/dev/null; echo "$schedule $command") | crontab -
    echo -e "${GREEN}✓ Added cron job for $description${NC}"
}

# Function to remove cron job
remove_cron_job() {
    local description="$1"
    local command="$2"
    
    # Remove the cron job
    crontab -l 2>/dev/null | grep -v "$command" | crontab -
    echo -e "${GREEN}✓ Removed cron job for $description${NC}"
}

# Function to list current cron jobs
list_cron_jobs() {
    echo -e "${YELLOW}Current cron jobs:${NC}"
    crontab -l 2>/dev/null | grep -E "(sync_transactions|budget_tracker)" || echo "No budget tracker cron jobs found"
}

# Function to test the sync script
test_sync_script() {
    echo -e "${YELLOW}Testing sync script...${NC}"
    cd "$PROJECT_DIR"
    
    # Test with dry run
    python scripts/sync_transactions.py --dry-run --verbose
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Sync script test passed${NC}"
    else
        echo -e "${RED}✗ Sync script test failed${NC}"
        return 1
    fi
}

# Main menu
while true; do
    echo ""
    echo -e "${GREEN}Choose an option:${NC}"
    echo "1) Add nightly sync job (2 AM daily)"
    echo "2) Add hourly sync job (for testing)"
    echo "3) Add custom sync schedule"
    echo "4) Remove all sync jobs"
    echo "5) List current cron jobs"
    echo "6) Test sync script"
    echo "7) Exit"
    echo ""
    read -p "Enter your choice (1-7): " choice
    
    case $choice in
        1)
            # Nightly sync at 2 AM
            schedule="0 2 * * *"
            command="cd $PROJECT_DIR && python scripts/sync_transactions.py >> logs/cron_sync.log 2>&1"
            add_cron_job "$schedule" "nightly sync (2 AM daily)" "$command"
            ;;
        2)
            # Hourly sync for testing
            schedule="0 * * * *"
            command="cd $PROJECT_DIR && python scripts/sync_transactions.py --verbose >> logs/cron_sync.log 2>&1"
            add_cron_job "$schedule" "hourly sync (for testing)" "$command"
            ;;
        3)
            # Custom schedule
            echo "Enter cron schedule (e.g., '0 2 * * *' for daily at 2 AM):"
            read -p "Schedule: " custom_schedule
            command="cd $PROJECT_DIR && python scripts/sync_transactions.py >> logs/cron_sync.log 2>&1"
            add_cron_job "$custom_schedule" "custom sync" "$command"
            ;;
        4)
            # Remove all sync jobs
            remove_cron_job "all sync jobs" "sync_transactions"
            ;;
        5)
            # List current jobs
            list_cron_jobs
            ;;
        6)
            # Test sync script
            test_sync_script
            ;;
        7)
            echo -e "${GREEN}Setup complete!${NC}"
            exit 0
            ;;
        *)
            echo -e "${RED}Invalid choice. Please enter a number between 1-7.${NC}"
            ;;
    esac
done 