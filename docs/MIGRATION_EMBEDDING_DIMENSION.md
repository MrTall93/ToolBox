# Embedding Dimension Migration Guide

## Overview

This guide covers the migration to fix the embedding dimension mismatch between the database schema and the application configuration.

## Problem Statement

### The Issue

The initial database migration (`001_initial_schema`) hardcoded the vector embedding dimension to **1024**, but the application configuration (`settings.EMBEDDING_DIMENSION`) defaults to **1536**. This mismatch caused runtime failures when attempting to store embeddings.

**Before the fix:**
- Database schema: `Vector(1024)` ← Hardcoded in migration
- Application model: `Vector(settings.EMBEDDING_DIMENSION)` ← Uses config (1536)
- Result: **PostgreSQL errors when inserting 1536-dim vectors into 1024-dim column**

### Root Cause

The comment in the original migration suggested it was "Updated for Nomic-embed-text-v1.5", but:
- Nomic-embed-text-v1.5 produces **768-dimensional** embeddings
- The migration used **1024** dimensions
- The config uses **1536** dimensions (OpenAI ada-002 default)

This indicates the system was likely intended to work with multiple embedding models but had inconsistent configuration.

## Solution

### Migration 002: Fix Embedding Dimension

A new migration (`002_fix_embedding_dimension`) has been created to:

1. **Drop the existing vector index** (required before altering column type)
2. **Alter the embedding column** to use the configured dimension
3. **Clear existing embeddings** (incompatible dimensions)
4. **Recreate the vector index** with correct dimension

### Updated Migration 001

The original migration has been updated to read the dimension from the `EMBEDDING_DIMENSION` environment variable, ensuring fresh deployments use the correct dimension from the start.

## Migration Instructions

### For Existing Deployments

If you have an existing database with tools already registered:

#### Step 1: Set the Embedding Dimension

Decide which embedding model you'll use and set the appropriate dimension:

```bash
# For OpenAI text-embedding-ada-002 (1536 dimensions)
export EMBEDDING_DIMENSION=1536

# For Nomic embed-text-v1.5 (768 dimensions)
export EMBEDDING_DIMENSION=768

# For text-embedding-3-small (512 dimensions)
export EMBEDDING_DIMENSION=512
```

#### Step 2: Run the Migration

```bash
# Navigate to project root
cd /path/to/ToolBox

# Run migration
alembic upgrade head
```

**Expected output:**
```
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade 001 -> 002, Fix embedding dimension mismatch
Upgrading embedding column to dimension 1536...
Clearing existing embeddings (will be regenerated)...
Creating vector index for dimension 1536...
✓ Migration complete. Embedding dimension is now 1536
  Note: Existing tools need their embeddings regenerated.
  Use the /admin/tools/{tool_id}/reindex endpoint or trigger bulk re-indexing.
INFO  [alembic.runtime.migration] Running upgrade 002 -> head
```

#### Step 3: Regenerate Embeddings

After migration, all existing embeddings are cleared (incompatible dimensions). You need to regenerate them:

**Option A: Bulk Re-indexing (Recommended)**

Create a script to regenerate all embeddings:

```python
# scripts/regenerate_embeddings.py
import asyncio
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models import Tool
from app.registry import ToolRegistry

async def regenerate_all_embeddings():
    async with AsyncSessionLocal() as session:
        registry = ToolRegistry(session=session)

        # Get all tools
        result = await session.execute(
            select(Tool).where(Tool.is_active == True)
        )
        tools = result.scalars().all()

        print(f"Regenerating embeddings for {len(tools)} tools...")

        for i, tool in enumerate(tools, 1):
            try:
                await registry.update_tool_embedding(tool.id)
                print(f"[{i}/{len(tools)}] ✓ {tool.name}")
            except Exception as e:
                print(f"[{i}/{len(tools)}] ✗ {tool.name}: {e}")

        print("✓ Embedding regeneration complete")

if __name__ == "__main__":
    asyncio.run(regenerate_all_embeddings())
```

Run it:
```bash
python scripts/regenerate_embeddings.py
```

**Option B: Individual Reindexing via API**

For each tool, call the reindex endpoint:

```bash
# Get all tool IDs
curl -X POST http://localhost:8000/mcp/list_tools \
  -H "Content-Type: application/json" \
  -d '{"active_only": true, "limit": 1000}' \
  | jq -r '.tools[].id'

# For each ID, trigger reindexing
curl -X POST http://localhost:8000/admin/tools/{tool_id}/reindex \
  -H "Authorization: Bearer YOUR_API_KEY"
```

### For Fresh Deployments

Fresh deployments will automatically use the correct dimension:

```bash
# Set your embedding dimension
export EMBEDDING_DIMENSION=1536

# Run migrations
alembic upgrade head
```

The database will be created with the correct dimension from the start.

## Configuration Reference

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `EMBEDDING_DIMENSION` | `1536` | Vector dimension for embeddings |
| `EMBEDDING_MODEL` | `text-embedding-nomic-embed-text-v1.5` | Embedding model name |
| `EMBEDDING_ENDPOINT_URL` | `http://localhost:1234/v1/embeddings` | Embedding service URL |

### Common Embedding Models

| Model | Provider | Dimension | Notes |
|-------|----------|-----------|-------|
| `text-embedding-ada-002` | OpenAI | 1536 | Production-grade, expensive |
| `text-embedding-3-small` | OpenAI | 512 or 1536 | Configurable dimension |
| `text-embedding-3-large` | OpenAI | 256 to 3072 | Configurable dimension |
| `nomic-embed-text-v1.5` | Nomic AI | 768 | Open-source, good quality |
| `all-MiniLM-L6-v2` | Sentence Transformers | 384 | Fast, lightweight |
| `all-mpnet-base-v2` | Sentence Transformers | 768 | Better quality |

**Important:** The dimension must match your embedding model's output dimension exactly.

## Troubleshooting

### Error: "embedding dimension ... does not match declared dimension ..."

**Cause:** You're trying to insert embeddings with the wrong dimension.

**Solution:**
1. Check your `EMBEDDING_DIMENSION` setting matches your model
2. Run the migration again with the correct dimension
3. Regenerate all embeddings

### Error: "Migration 002 fails with column type error"

**Cause:** PostgreSQL can't convert existing vector data.

**Solution:**
```sql
-- Manually clear embeddings before migration
UPDATE tools SET embedding = NULL;

-- Then run migration
alembic upgrade head
```

### Performance: Bulk reindexing is slow

**Cause:** Embedding generation is I/O bound (API calls).

**Solution:** Use concurrent processing:

```python
# scripts/regenerate_embeddings_concurrent.py
import asyncio
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.models import Tool
from app.registry import ToolRegistry

async def regenerate_tool_embedding(tool_id: int, tool_name: str, session):
    try:
        registry = ToolRegistry(session=session)
        await registry.update_tool_embedding(tool_id)
        return f"✓ {tool_name}"
    except Exception as e:
        return f"✗ {tool_name}: {e}"

async def regenerate_all_embeddings_concurrent(max_concurrent=10):
    async with AsyncSessionLocal() as session:
        # Get all tools
        result = await session.execute(
            select(Tool.id, Tool.name).where(Tool.is_active == True)
        )
        tools = result.all()

        print(f"Regenerating embeddings for {len(tools)} tools (max {max_concurrent} concurrent)...")

        # Create tasks
        semaphore = asyncio.Semaphore(max_concurrent)

        async def bounded_regenerate(tool_id, tool_name):
            async with semaphore:
                async with AsyncSessionLocal() as task_session:
                    return await regenerate_tool_embedding(tool_id, tool_name, task_session)

        tasks = [bounded_regenerate(tool.id, tool.name) for tool in tools]
        results = await asyncio.gather(*tasks)

        for result in results:
            print(result)

        print("✓ Embedding regeneration complete")

if __name__ == "__main__":
    asyncio.run(regenerate_all_embeddings_concurrent(max_concurrent=10))
```

## Verification

After migration and re-indexing, verify the system is working:

### 1. Check Database Schema

```sql
-- Connect to database
psql -h localhost -U toolregistry -d toolregistry

-- Check column type
SELECT
    column_name,
    udt_name,
    character_maximum_length
FROM information_schema.columns
WHERE table_name = 'tools' AND column_name = 'embedding';

-- Should show vector type
```

### 2. Test Embedding Insertion

```python
# test_embedding_insert.py
import asyncio
from app.registry.embedding_client import get_embedding_client

async def test():
    client = get_embedding_client()
    embedding = await client.embed_text("test query")
    print(f"✓ Generated embedding with dimension: {len(embedding)}")
    assert len(embedding) == int(os.getenv("EMBEDDING_DIMENSION", "1536"))

asyncio.run(test())
```

### 3. Test Semantic Search

```bash
# Search for tools
curl -X POST http://localhost:8000/mcp/find_tool \
  -H "Content-Type: application/json" \
  -d '{
    "query": "calculate numbers",
    "limit": 5,
    "threshold": 0.7
  }'
```

Should return results with similarity scores.

## Rollback Instructions

If you need to rollback to the original schema:

```bash
# Downgrade to migration 001
alembic downgrade 001
```

**Warning:** This will:
- Revert embedding dimension to 1024
- Clear all embeddings
- Require regenerating embeddings again

## Best Practices

1. **Always set `EMBEDDING_DIMENSION` before running migrations**
2. **Use the same dimension across all environments** (dev, staging, prod)
3. **Document which embedding model you're using**
4. **Test embedding generation after migration**
5. **Monitor re-indexing progress** for large deployments
6. **Back up your database** before running migrations

## Additional Resources

- [PostgreSQL pgvector documentation](https://github.com/pgvector/pgvector)
- [Alembic migration guide](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- [OpenAI Embeddings API](https://platform.openai.com/docs/guides/embeddings)
- [Nomic Embed Text](https://huggingface.co/nomic-ai/nomic-embed-text-v1.5)

## Support

If you encounter issues:

1. Check the [Troubleshooting](#troubleshooting) section
2. Review migration logs for error details
3. Open an issue on GitHub with:
   - Migration command output
   - Database logs
   - Environment configuration
