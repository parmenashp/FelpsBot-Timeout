import motor
import keys
from models.db import DataBase
from pprint import pprint
import asyncio

client = motor.motor_asyncio.AsyncIOMotorClient(
    keys.mongodb["key"]
)

db = DataBase(client.felpsBot.timeout)


async def main():
    x = (await db.get_user_timeouts('felps'))[1]._to_document()["revoked_at"]
    pprint(x)
    pass


x = asyncio.get_event_loop()
x.run_until_complete(main())
