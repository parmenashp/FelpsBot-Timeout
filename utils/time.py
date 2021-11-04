import datetime
from dateutil.relativedelta import relativedelta
import re


def friendly_time(datetime: datetime.datetime) -> str:
    """Retorna o tempo no formato \"dd/mm/yyyy ás hh/mm/ss\""""
    return datetime.strftime("%d/%m/%Y às %H:%M:%S")


def discord_time(datetime: datetime.datetime, styles: str = None) -> str:
    """Retorna o tempo no formato renderizado para o discord"""
    return f"<t:{int(datetime.timestamp())}{f':{styles}' if styles else ''}>"


class BadArgument(Exception):
    pass


# Partially from github.com/Rapptz/RoboDanny over MPL-2.0 License.
class ShortTime:
    compiled = re.compile("""(?:(?P<years>[0-9])(?:years?|y))?             # e.g. 2y
                             (?:(?P<months>[0-9]{1,2})(?:months?|mo))?     # e.g. 2months
                             (?:(?P<weeks>[0-9]{1,4})(?:weeks?|w))?        # e.g. 10w
                             (?:(?P<days>[0-9]{1,5})(?:days?|d))?          # e.g. 14d
                             (?:(?P<hours>[0-9]{1,5})(?:hours?|h))?        # e.g. 12h
                             (?:(?P<minutes>[0-9]{1,5})(?:minutes?|m))?    # e.g. 10m
                             (?:(?P<seconds>[0-9]{1,5})(?:seconds?|s))?    # e.g. 15s
                          """, re.VERBOSE)

    def __init__(self, argument: str, *, now=None):
        match = self.compiled.fullmatch(argument)
        if match is None or not match.group(0):
            raise BadArgument("a data fornecida é inválida")

        data = {k: int(v) for k, v in match.groupdict(default=0).items()}
        now = now or datetime.datetime.now()
        self.td = relativedelta(**data)
        self.dt: datetime.datetime = now + self.td
