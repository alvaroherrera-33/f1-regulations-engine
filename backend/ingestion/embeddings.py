"""Generate embeddings using OpenRouter API."""
import httpx
from typing import List
import asyncio

from app.config import settings


class EmbeddingsGenerator:
    """Generate embeddings via OpenRouter."""
    
    def __init__(self):
        """Initialize with OpenRouter configuration."""
        self.api_key = settings.openrouter_api_key
        self.model = settings.embedding_model
        self.base_url = "https://openrouter.ai/api/v1"
        self.batch_size = 100  # Max texts per request
    
    async def generate(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for a list of texts.
        
        Args:
            texts: List of text strings to embed
            
        Returns:
            List of embedding vectors (1536 dimensions for text-embedding-3-small)
        """
        if not texts:
            return []
        
        # Process in batches
        all_embeddings = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i:i + self.batch_size]
            embeddings = await self._generate_batch(batch)
            all_embeddings.extend(embeddings)
        
        return all_embeddings
    
    async def _generate_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for a single batch."""
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/embeddings",
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model": self.model,
                        "input": texts
                    }
                )
                if response.status_code != 200:
                    print(f"❌ API Error ({response.status_code}): {response.text}")
                    response.raise_for_status()
                
                data = response.json()
                if "data" not in data:
                    print(f"❌ Unexpected response format: {data}")
                    raise KeyError("data")
                
                embeddings = [item["embedding"] for item in data["data"]]
                return embeddings
                
            except httpx.HTTPError as e:
                print(f"Error generating embeddings: {e}")
                raise
    
    async def generate_one(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        embeddings = await self.generate([text])
        return embeddings[0] if embeddings else []


async def generate_embeddings(texts: List[str]) -> List[List[float]]:
    """
    Convenience function to generate embeddings.
    
    Usage:
        embeddings = await generate_embeddings(["text 1", "text 2"])
    """
    generator = EmbeddingsGenerator()
    return await generator.generate(texts)


# For testing
if __name__ == "__main__":
    async def test():
        texts = [
            "The minimum weight shall be 798kg.",
            "DRS may be activated in designated zones."
        ]
        embeddings = await generate_embeddings(texts)
        print(f"Generated {len(embeddings)} embeddings")
        print(f"Dimension: {len(embeddings[0])}")
    
    asyncio.run(test())
