#!/bin/bash
# Start script for Toolbox with OpenTelemetry Collector

set -e

echo "Starting Toolbox with OpenTelemetry Collector..."
echo "Environment: ${ENVIRONMENT:-development}"
echo "OTel Enabled: ${OTEL_ENABLED:-false}"
echo "OTel Endpoint: ${OTEL_EXPORTER_OTLP_ENDPOINT:-none}"

# Start OpenTelemetry Collector in the background
if [ "${OTEL_ENABLED:-false}" = "true" ]; then
    echo "Starting OpenTelemetry Collector..."
    /opt/otelcol/otelcol --config=/etc/otelcol-contrib/otel-collector-config.yaml &
    OTEL_PID=$!
    echo "OTel Collector PID: $OTEL_PID"

    # Give the collector a moment to start
    sleep 2
else
    echo "OpenTelemetry disabled, skipping collector start"
fi

# Wait for database to be ready
echo "Waiting for database..."
while ! python3 -c "
import asyncio
import os
from sqlalchemy import text
from app.db.session import get_db

async def check_db():
    try:
        async for db in get_db():
            await db.execute(text('SELECT 1'))
            print('Database is ready')
            return True
    except Exception as e:
        print(f'Database not ready: {e}')
        return False

exit(0 if asyncio.run(check_db()) else 1)
"; do
    echo "Database unavailable, retrying in 5 seconds..."
    sleep 5
done

# Run database migrations
echo "Running database migrations..."
python3 -m alembic upgrade head

# Start the Toolbox application
echo "Starting Toolbox application..."
exec python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# Cleanup function
cleanup() {
    echo "Shutting down..."
    if [ ! -z "$OTEL_PID" ]; then
        echo "Stopping OpenTelemetry Collector (PID: $OTEL_PID)..."
        kill $OTEL_PID 2>/dev/null || true
        wait $OTEL_PID 2>/dev/null || true
    fi
    echo "Shutdown complete"
}

# Trap signals for graceful shutdown
trap cleanup SIGTERM SIGINT

# If the process exits, cleanup
wait