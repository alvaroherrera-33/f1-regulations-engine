import asyncio
from httpx import AsyncClient

async def test_routing():
    async with AsyncClient(base_url='http://localhost:8000/api', timeout=30.0) as client:
        print("=" * 60)
        print("🔍 Query Routing Verification")
        print("=" * 60)

        queries = [
            ("Technical", "What is the minimum weight for 2026?"),
            ("Conversational", "Hello! How are you today?"),
            ("Conversational", "Thank you for the information."),
            ("Technical", "Tell me about the fuel flow limit regulations.")
        ]

        for q_type, query in queries:
            print(f"\nTesting {q_type} query: '{query}'")
            try:
                r = await client.post('/chat', json={
                    'query': query,
                    'year': 2026,
                    'section': 'Technical'
                })
                data = r.json()
                
                print(f"✅ Status: {r.status_code}")
                print(f"✅ Citations: {len(data.get('citations', []))}")
                print(f"✅ Retrieved Count: {data.get('retrieved_count', 0)}")
                print(f"💬 Answer: {data.get('answer', '')[:100]}...")
                
                if q_type == "Conversational":
                    if data.get('retrieved_count', 0) == 0:
                        print("✨ Successfully routed to CONVERSATIONAL (no RAG used)")
                    else:
                        print("⚠️ Failed: Retrieval was used for a conversational query")
                else:
                    if data.get('retrieved_count', 0) > 0:
                        print("✨ Successfully routed to REGULATIONS (RAG used)")
                    else:
                        print("⚠️ Failed: Retrieval was skipped for a technical query")
            except Exception as e:
                print(f"❌ Error: {e}")

        print("\n" + "=" * 60)
        print("🏁 Routing Verification Complete")
        print("=" * 60)

if __name__ == "__main__":
    asyncio.run(test_routing())
