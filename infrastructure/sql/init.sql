-- Initial database schema for tool registry
-- This file is used by Docker to initialize the database

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Verify pgvector is installed
SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';

-- Create tools table (will be managed by Alembic migrations)
-- This is just for reference and initial setup

COMMENT ON EXTENSION vector IS 'Vector similarity search extension for PostgreSQL';
