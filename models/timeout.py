from datetime import datetime
from models.db import DataBase
from typing import Union

# seconds
MAX_TIMEOUT_TIME = 1209600


class Timeout():

    def __init__(self, db: DataBase, moderator: str, username: str, finish_at: datetime, reason: Union[str, None]):
        self._id = None
        self.db = db
        self.username = username.lower()
        self.moderator = moderator.lower()
        self.reason = reason
        self.created_at = datetime.utcnow()
        self.last_timeout = None
        self.finish_at = finish_at
        self.revoke_reason = None
        self.revoked = False
        self.revoker = None

    @classmethod
    def from_database(cls, db: DataBase, data):
        """Constrói (e retorna) uma classe com os dados 
        providos pelo banco de dados (pymongo/motor)"""
        # Cria um novo objeto sem chamar o __init__
        cls.__new__(cls)
        cls.db = db
        cls._id = data["_id"]
        cls.username = data["username"]
        cls.moderator = data["moderator"]
        cls.reason = data["reason"]
        cls.created_at = data["created_at"]
        cls.last_timeout = data["last_timeout"]
        cls.finish_at = data["finish_at"]
        cls.revoke_reason = data["revoke_reason"]
        cls.revoked = data["revoked"]
        cls.revoker = data["revoker"]
        return cls

    def _to_document(self):
        document = {
            "username": self.username,
            "moderator": self.moderator,
            "reason": self.reason,
            "created_at": self.created_at,
            "last_timeout": self.last_timeout,
            "finish_at": self.finish_at,
            "revoke_reason": self.revoke_reason,
            "revoked": self.revoked,
            "revoker": self.revoker
        }
        return document

    async def revoke(self, revoker: str, reason: str):
        """Dá revoke no timeout. Revoker sendo o moderador que realizou o feito."""
        if not self._id:
            return False
        self.revoker = revoker.lower()
        self.reason = reason
        self.revoked = datetime.now()
        await self.db.revoke_timeout(self)

    async def update_last_timeout(self):
        """Atualiza o registro do último timeout realizado para esse caso"""
        self.last_timeout = datetime.utcnow()
        if self._id:
            await self.db.update_one({'_id': self._id}, {'$set': {'last_timeout': self.last_timeout}})

    async def insert(self):
        """Enfia no banco de dados"""
        if self._id:
            return False
        result = await self.db.insert_one(self._to_document())
        self._id = result.inserted_id

    @property
    def next_timeout_time(self):
        """Retorna o total de segundos para o próximo timeout"""
        now = datetime.utcnow()
        delta = (self.finish_at - now).total_seconds()
        # Tirando precisão decimal
        delta = int(delta)

        return MAX_TIMEOUT_TIME if delta > MAX_TIMEOUT_TIME else delta

    @property
    def timeout_command(self):
        return f"/timeout {self.username} {self.next_timeout_time}s"
