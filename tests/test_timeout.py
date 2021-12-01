import datetime

import pytest
from bson.objectid import ObjectId
from freezegun import freeze_time
from models.db import DataBase
from models.timeout import MAX_TIMEOUT_TIME, Timeout


def test_simple_timeout_creation_from_dict(simple_timeout):
    to = simple_timeout
    assert to.created_at == datetime.datetime(2021, 3, 2, 1)
    assert to.finish_at == datetime.datetime(2025, 1, 2, 3)
    assert to.last_timeout == datetime.datetime(2021, 3, 2, 1)
    assert to.moderator == 'mitsuaky'
    assert to.reason == 'motivo timeout'
    assert to.revoke_reason == None
    assert to.revoked == False
    assert to.revoked_at == None
    assert to.revoker == None
    assert to.username == 'felps'
    assert to._id == ObjectId('6142c15707298dcddb68d5d0')
    assert isinstance(to.db, DataBase)


def test_revoked_timeout_creation_from_dict(revoked_timeout_dict, simple_database):
    to = Timeout.from_database(simple_database, revoked_timeout_dict)
    assert to.created_at == datetime.datetime(2021, 3, 2, 1)
    assert to.finish_at == datetime.datetime(2025, 1, 2, 3)
    assert to.last_timeout == datetime.datetime(2021, 3, 2, 1)
    assert to.moderator == 'mitsuaky'
    assert to.reason == 'motivo timeout'
    assert to.revoke_reason == 'motivo revoke'
    assert to.revoked == True
    assert to.revoked_at == datetime.datetime(2021, 4, 3, 2)
    assert to.revoker == 'dilma'
    assert to.username == 'felps'
    assert to._id == ObjectId('6142c15707298dcddb68d5d0')
    assert isinstance(to.db, DataBase)


@pytest.mark.asyncio
async def test_timeout_revoke(mocker, simple_timeout, simple_database):
    to = simple_timeout
    revoke_timeout = mocker.patch.object(simple_database, 'revoke_timeout', autospec=True)
    await to.revoke('revogador', 'motivo')
    # ',' to unpack tuple
    new_to, = revoke_timeout.call_args.args
    assert new_to.revoker == 'revogador'
    assert new_to.revoke_reason == 'motivo'
    assert new_to.revoked == True
    assert isinstance(to.revoked_at, datetime.datetime)


@pytest.mark.asyncio
async def test_insert_timeout(mocker, simple_timeout, simple_database):
    to = simple_timeout
    # Inserindo com _id existente
    assert await to.insert() == False
    insert_timeout = mocker.patch.object(simple_database, 'insert_timeout', autospec=True)
    to._id = None
    assert await to.insert()
    insert_timeout.assert_called_once_with(to)

MAX_TIMEOUT_TIME = 1209600


@freeze_time("2025-1-2 2:00:00", tz_offset=-3)
def test_next_timeout_seconds(simple_timeout):
    to = simple_timeout
    assert to.next_timeout_seconds == 3600


@freeze_time("2022-1-2 2:00:00", tz_offset=-3)
def test_next_timeout_seconds_max(simple_timeout):
    to = simple_timeout
    assert to.next_timeout_seconds == MAX_TIMEOUT_TIME


@freeze_time("2022-1-2 2:00:00", tz_offset=-3)
def test_next_timeout_time(simple_timeout):
    to = simple_timeout
    assert to.next_timeout_time == datetime.datetime(2021, 3, 16, 1)


@freeze_time("2022-1-2 2:00:00", tz_offset=-3)
def test_timeout_command(simple_timeout):
    to = simple_timeout
    assert to.timeout_command == '/timeout felps 1209600 motivo timeout'


def test_untimeout_command(simple_timeout):
    to = simple_timeout
    assert to.untimeout_command == '/untimeout felps'
