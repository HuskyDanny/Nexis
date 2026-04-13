from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase


class MongoDB:
    def __init__(self):
        self.client: AsyncIOMotorClient | None = None
        self.db: AsyncIOMotorDatabase | None = None

    async def connect(self, url: str):
        self.client = AsyncIOMotorClient(
            url,
            maxPoolSize=20,
            minPoolSize=2,
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
            socketTimeoutMS=30000,
        )
        db_name = url.rsplit("/", 1)[-1].split("?")[0]
        self.db = self.client[db_name]
        await self.db.command("ping")

    async def close(self):
        if self.client:
            self.client.close()

    def get_collection(self, name: str):
        if self.db is None:
            raise RuntimeError("MongoDB not connected. Call connect() first.")
        return self.db[name]


mongodb = MongoDB()
