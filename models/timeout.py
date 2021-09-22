from datetime import datetime, timedelta
from typing import Union, TYPE_CHECKING, Type

if TYPE_CHECKING:
    from models.db import DataBase

# seconds
MAX_TIMEOUT_TIME = 1209600


class Timeout():

    def __init__(self, db: Type["DataBase"], moderator: str, username: str, finish_at: datetime, reason: Union[str, None]):
        self._id = None
        self.db = db
        self.username = username.lower()
        self.moderator = moderator.lower()
        self.reason = reason
        self.created_at = datetime.utcnow()
        self.last_timeout = None
        self.finish_at = finish_at
        self.revoker = None
        self.revoked_at = None
        self.revoke_reason = None
        self.revoked = False

    @classmethod
    def from_database(cls, db: Type["DataBase"], data):
        """Constrói (e retorna) uma classe com os dados 
        providos pelo banco de dados (pymongo/motor)"""
        # Cria um novo objeto sem chamar o __init__
        self = cls.__new__(cls)
        self.db = db
        self._id = data["_id"]
        self.username = data["username"]
        self.moderator = data["moderator"]
        self.reason = data["reason"]
        self.created_at = data["created_at"]
        self.last_timeout = data["last_timeout"]
        self.finish_at = data["finish_at"]
        self.revoked_at = data["revoked_at"]
        self.revoker = data["revoker"]
        self.revoke_reason = data["revoke_reason"]
        self.revoked = data["revoked"]
        return self

    def _to_document(self):
        document = {
            "username": self.username,
            "moderator": self.moderator,
            "reason": self.reason,
            "created_at": self.created_at,
            "last_timeout": self.last_timeout,
            "finish_at": self.finish_at,
            "revoked_at": self.revoked_at,
            "revoker": self.revoker,
            "revoke_reason": self.revoke_reason,
            "revoked": self.revoked
        }
        return document

    async def revoke(self, revoker: str, reason: str):
        """Dá revoke no timeout. Revoker sendo o moderador que realizou o feito."""
        if not self._id:
            return False
        self.revoker = revoker.lower()
        self.revoke_reason = reason
        self.revoked_at = datetime.now()
        self.revoked = True
        return await self.db.revoke_timeout(self)

    async def update_last_timeout(self):
        """Atualiza o registro do último timeout realizado para esse caso"""
        self.last_timeout = datetime.utcnow()
        if self._id:
            await self.db.update_one({'_id': self._id}, {'$set': {'last_timeout': self.last_timeout}})

    async def insert(self):
        """Enfia no banco de dados"""
        if self._id:
            return False
        result = await self.db.insert_timeout(self._to_document())
        self._id = result.inserted_id
        return result

    @property
    def next_timeout_seconds(self):
        """Retorna o total de segundos para o próximo timeout"""
        now = datetime.now()
        delta = (self.finish_at - now).total_seconds()
        # Tirando precisão decimal
        delta = int(delta)

        return MAX_TIMEOUT_TIME if delta > MAX_TIMEOUT_TIME else delta

    @property
    def next_timeout_time(self):
        """Retorna o datetime para o próximo timeout"""
        return self.last_timeout + timedelta(seconds=self.next_timeout_seconds)

    @property
    def timeout_command(self):
        return f"/timeout {self.username} {self.next_timeout_seconds} s"
