import asyncio
from tracker.db import get_results

async def main():
    rows = await get_results('demo')
    print(rows)

asyncio.run(main())
