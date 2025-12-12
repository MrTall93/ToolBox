#!/usr/bin/env python3
"""
Mock embedding service for testing the Tool Registry MCP Server.
"""
import asyncio
import json
import logging
from typing import Dict, Any, List
from fastapi import FastAPI
import uvicorn
import hashlib

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(title="Mock Embedding Service", version="1.0.0")

def generate_embedding(text: str, dimension: int = 1536) -> List[float]:
    """
    Generate a deterministic mock embedding based on text.

    Uses hash of text to create consistent embeddings for the same input.
    """
    # Create a hash of the text
    hash_obj = hashlib.sha256(text.encode('utf-8'))
    hash_bytes = hash_obj.digest()

    # Convert hash bytes to floating point values
    embedding = []
    for i in range(dimension):
        # Cycle through hash bytes to create consistent values
        byte_idx = i % len(hash_bytes)
        # Convert byte to float between -1 and 1
        value = (hash_bytes[byte_idx] / 127.5) - 1.0
        embedding.append(round(value, 6))

    return embedding

@app.post("/embed")
async def embed_texts(request: Dict[str, Any]) -> List[List[float]]:
    """
    Generate embeddings for one or more texts.

    Supports multiple request formats:
    - {"texts": ["text1", "text2"]}
    - {"text": "single text"}
    """
    try:
        # Extract texts from request
        if "texts" in request:
            texts = request["texts"]
            if isinstance(texts, str):
                texts = [texts]
        elif "text" in request:
            texts = [request["text"]]
        else:
            # Fallback: assume the whole request is the text
            texts = [str(request)]

        # Generate embeddings
        embeddings = []
        for text in texts:
            embedding = generate_embedding(text)
            embeddings.append(embedding)

        logger.info(f"Generated embeddings for {len(texts)} texts")

        # Return in expected format
        return {
            "embeddings": embeddings,
            "dimension": len(embeddings[0]) if embeddings else 0,
            "count": len(embeddings)
        }

    except Exception as e:
        logger.error(f"Error generating embeddings: {e}")
        return {"error": str(e)}

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "mock-embedding"}

@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "service": "Mock Embedding Service",
        "version": "1.0.0",
        "endpoints": {
            "embed": "POST /embed",
            "health": "GET /health"
        }
    }

if __name__ == "__main__":
    uvicorn.run(
        "mock_embedding_server:app",
        host="0.0.0.0",
        port=8001,
        reload=False,
        log_level="info"
    )