#!/bin/bash
set -e

echo "Running database migrations..."

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL to be ready..."
python3 << 'EOF'
import time
import sys
from sqlalchemy import create_engine, text
from app.config import settings

max_retries = 30
retry_interval = 2

for i in range(max_retries):
    try:
        # Convert async URL to sync URL for this check
        sync_url = settings.DATABASE_URL.replace('+asyncpg', '')
        engine = create_engine(sync_url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print(f"PostgreSQL is ready!")
        sys.exit(0)
    except Exception as e:
        if i < max_retries - 1:
            print(f"PostgreSQL not ready yet (attempt {i+1}/{max_retries}), waiting {retry_interval}s...")
            time.sleep(retry_interval)
        else:
            print(f"PostgreSQL failed to become ready after {max_retries} attempts")
            sys.exit(1)
EOF

echo "Applying Alembic migrations..."
alembic upgrade head

echo "Database migrations completed successfully!"
