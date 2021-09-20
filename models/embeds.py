from re import T
from dispike.helper import Embed
from typing import List, TYPE_CHECKING, Optional, Union
from discord import Colour
from datetime import datetime

from dispike.response import DiscordResponse
from utils.time import friendly_time

if TYPE_CHECKING:
    from models.timeout import Timeout

ROSELHO = 0Xff3165
GRAY = 0x747474


class LookupResponse(DiscordResponse):

    def __init__(self, username, timeouts: Optional["Timeout"] = None) -> None:
        self.timeouts = timeouts
        self.timeouts.sort(key=lambda x: x.finish_at, reverse=True)
        _embeds = []
        for to in self.timeouts:
            _user = to.username
            color = ROSELHO if to.finish_at > datetime.now() or to.revoked else GRAY
            embed = Embed(color=color)
            embed.title = f"Motivo: {to.reason}"
            embed.set_author(name=f"Mod: {to.moderator}")
            embed.description = self._description(to)
            _embeds.append(embed)

        if self.timeouts:
            if len(_embeds) > 1:
                content = f"Encontrei um total de {len(self.timeouts)} timeouts registrados para **{_user}**"
            else:
                content = f"Encontrei um total de {len(self.timeouts)} timeout registrado para **{_user}**"
            super().__init__(
                content=content,
                embeds=_embeds
            )
        else:
            super().__init__(
                content=f"Não encontrei nenhum timeout registrado para **{username}**"
            )

    def _description(self, timeout: "Timeout") -> str:
        desc = (f"Início: {friendly_time(timeout.created_at)}\n"
                f"Fim: {friendly_time(timeout.finish_at)}\n")
        if timeout.revoked:
            desc += ("❗ **Revogado** ❗\n"
                     f"Por: {timeout.revoker}\n"
                     f"Motivo: {timeout.revoke_reason}\n"
                     f"Data: {friendly_time(timeout.revoked_at)}\n")
        desc += f"[Viewer Card](https://www.twitch.tv/popout/felps/viewercard/{timeout.username})"
        return desc
