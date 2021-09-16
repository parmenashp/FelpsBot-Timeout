from motor.motor_asyncio import AsyncIOMotorCollection
from datetime import datetime
from typing import List, Union, TYPE_CHECKING, Type
from models.timeout import Timeout
from pymongo.results import InsertOneResult


class DataBase():

    def __init__(self, collection: AsyncIOMotorCollection):
        self.collection = collection

    async def insert_timeout(self, timeout: Type["Timeout"]) -> Type["InsertOneResult"]:
        return await self.collection.insert_one(timeout._to_document())

    async def get_active_timeouts(self) -> Union[None, List[Timeout]]:
        """Retorna uma lista de `Timeout` com todos os timeouts ativos.
        Se não encontrar, retorna `None`"""
        query = {
            "finish_at": {"$gte": datetime.now()},
            "revoked": False
        }
        cursor = self.collection.find(query).sort({"last_timeout"})
        result = []
        for timeout in await cursor.to_list(lenght=999):
            result.append(Timeout.from_database(self, timeout))

        return result if result else None

    async def revoke_timeout(self, timeout: Type["Timeout"]):
        """Envia um revoke de `Timeout` para o banco de dados"""
        update = {
            "revoke_reason": timeout.revoke_reason,
            "revoked": timeout.revoked,
            "revoker": timeout.revoker
        }
        return await self.collection.update_one(timeout._id, update)

    async def get_user_timeouts(self, username: str, limit=None) -> Union[None, List["Timeout"]]:
        """Retorna a lista de `Timeout` com todos os timeouts recebidos por esse usuário, incluindo os ativos.
        Se não encontrar, retorna `None`"""
        query = {
            "username": username.lower()
        }
        cursor = self.collection.find(query).sort({"created_at"})
        result = []
        for timeout in await cursor.to_list(lenght=limit):
            result.append(Timeout.from_database(self, timeout))

        return result if result else None

    async def get_active_user_timeout(self, username: str) -> Union[None, "Timeout"]:
        """Retorna o `Timeout` ativo desse usuário. Se não encontrar, retorna `None`"""
        query = {
            "username": username.lower(),
            "finish_at": {"$gte": datetime.now()},
            "revoked": False
        }
        result = await self.collection.find_one(query)
        return Timeout.from_database(self, result) if result else None
