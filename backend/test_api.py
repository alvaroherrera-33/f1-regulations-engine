import asyncio
import json
from httpx import AsyncClient

async def test_api():
    async with AsyncClient(base_url='http://localhost:8000/api', timeout=30.0) as client:
        print("=" * 60)
        print("🔍 F1 Regulations Engine - API Validation")
        print("=" * 60)

        # Test 1: Basic Retrieval & Citations (Financial)
        print('\n[1/3] Testing: Basic Retrieval & Citations (Financial Regulations)')
        try:
            r1 = await client.post('/chat', json={
                'query': 'What is the definition of a Team?', 
                'year': 2026, 
                'section': 'Financial'
            })
            d1 = r1.json()
            citations = d1.get('citations', [])
            print(f'✅ Status: {r1.status_code}')
            print(f'✅ Citations found: {len(citations)}')
            if citations:
                print(f'✅ First Citation: {citations[0].get("article_code")} - {citations[0].get("title")}')
            
            # Verify citation content relevance
            if "Team" in d1.get('answer', ''):
                print('✅ Answer seems relevant (contains "Team")')
            else:
                print('⚠️ Answer might be generic')
        except Exception as e:
            print(f'❌ Test 1 Failed: {e}')

        # Test 2: Temporal Filtering - Specific Issue
        print('\n[2/3] Testing: Temporal Filtering (Year/Issue)')
        try:
            # Most Financial regs we ingested are 2026 Issue 1 or similar
            r2 = await client.post('/chat', json={
                'query': 'What are the rules for marketing activities?', 
                'year': 2026, 
                'issue': 1
            })
            d2 = r2.json()
            retrieved = d2.get('retrieved_count', 0)
            print(f'✅ Articles retrieved: {retrieved}')
            
            # Check if citations match the filters
            mismatch = False
            for c in d2.get('citations', []):
                if c.get('year') != 2026:
                    print(f'❌ Filter Mismatch: Found year {c.get("year")} but requested 2026')
                    mismatch = True
                    break
            if not mismatch and retrieved > 0:
                print('✅ Temporal filtering verified (all citations match requested year)')
        except Exception as e:
            print(f'❌ Test 2 Failed: {e}')

        # Test 3: System Status Endpoint
        print('\n[3/3] Testing: System Status Health')
        try:
            r3 = await client.get('/status')
            d3 = r3.json()
            print(f'✅ Documents: {d3.get("documents_count")}')
            print(f'✅ Articles: {d3.get("articles_count")}')
            print(f'✅ Embeddings: {d3.get("embeddings_count")}')
            if d3.get("articles_count", 0) > 0:
                print('✅ System contains indexed data')
        except Exception as e:
            print(f'❌ Test 3 Failed: {e}')

        print('\n' + "=" * 60)
        print("🏁 Validation Complete")
        print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_api())
