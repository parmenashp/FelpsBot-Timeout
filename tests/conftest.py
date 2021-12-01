import pytest
import datetime
from models.db import DataBase
from models.timeout import Timeout
import motor
from bson import ObjectId


@pytest.fixture
def simple_database():
    client = motor.motor_asyncio.AsyncIOMotorClient('localhost')
    return DataBase(client.felpsBot.timeout)


@pytest.fixture
def simple_timeout_dict():
    return {'_id': ObjectId('6142c15707298dcddb68d5d0'),
            'created_at': datetime.datetime(2021, 3, 2, 1),
            'finish_at': datetime.datetime(2025, 1, 2, 3),
            'last_timeout': datetime.datetime(2021, 3, 2, 1),
            'moderator': 'mitsuaky',
            'reason': 'motivo timeout',
            'revoke_reason': None,
            'revoked': False,
            'revoked_at': None,
            'revoker': None,
            'username': 'felps'}


@pytest.fixture
def revoked_timeout_dict():
    return {'_id': ObjectId('6142c15707298dcddb68d5d0'),
            'created_at': datetime.datetime(2021, 3, 2, 1),
            'finish_at': datetime.datetime(2025, 1, 2, 3),
            'last_timeout': datetime.datetime(2021, 3, 2, 1),
            'moderator': 'mitsuaky',
            'reason': 'motivo timeout',
            'revoke_reason': 'motivo revoke',
            'revoked': True,
            'revoked_at': datetime.datetime(2021, 4, 3, 2),
            'revoker': 'dilma',
            'username': 'felps'}


@pytest.fixture
def simple_timeout(simple_database, simple_timeout_dict):
    return Timeout.from_database(simple_database, simple_timeout_dict)


@pytest.fixture
def revoked_timeout(simple_database, revoked_timeout_dict):
    return Timeout.from_database(simple_database, revoked_timeout_dict)
