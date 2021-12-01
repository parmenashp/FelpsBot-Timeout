from io import BytesIO
import traceback
from discord import File
from discord.webhook import AsyncWebhookAdapter, Webhook
from dispike.helper import Embed
from typing import TYPE_CHECKING, Optional
from datetime import datetime
import humanize

from dispike.response import DiscordResponse
from utils.generic import to_codeblock
from utils.time import discord_time, friendly_time
from aiohttp.client import ClientSession

if TYPE_CHECKING:
    from models.timeout import Timeout

ROSELHO = 0xfe3867
TWITCH = 0x9347ff
GRAY = 0x747474
RED = 0xf00000
LIGHT_RED = 0Xef4846
CRITICAL = 0x7e0101
GREEN = 0x32dc32
YELLOW = 0x0d000
LIGHT_BLUE = 0x2ea4ff


class TimeoutsResponse(DiscordResponse):

    def __init__(self, timeouts: Optional["Timeout"] = None) -> None:
        if not timeouts:
            super().__init__(content=f"Atualmente não existe nenhum timeout ativo pelo bot.")
            return

        timeouts.sort(key=lambda x: x.created_at)
        old_size = len(timeouts)
        _big = old_size > 15
        if _big:
            timeouts = timeouts[:15]

        _ = friendly_time
        fmt = "\n".join([
            f"► {to.username} • Mod: {_(to.moderator)} • Criado: {_(to.created_at)} • Até: {_(to.finish_at)} • Último Timeout: {_(to.last_timeout)}"
            for to in timeouts
        ])
        content = f"Total de timeouts ativos: {len(timeouts)}\n{fmt}" + f"\n...e mais {old_size-15} timeouts." if _big else ""
        return super().__init__(
            content=to_codeblock(content)
        )


class LookupResponse(DiscordResponse):

    def __init__(self, username, timeouts: Optional["Timeout"] = None) -> None:
        self.timeouts = timeouts
        self.timeouts.sort(key=lambda x: x.created_at)
        _embeds = []
        for to in self.timeouts:
            _user = to.username
            color = ROSELHO if to.finish_at > datetime.utcnow() and not to.revoked else GRAY
            embed = Embed(color=color)
            embed.title = f"Motivo: {to.reason}"
            embed.set_author(name=f"Mod: {to.moderator}")
            embed.description = self._description(to)
            _embeds.append(embed)

        if self.timeouts:
            if len(_embeds) > 1:
                content = f"Encontrei um total de {len(self.timeouts)} timeouts registrados para **{_user}**"
            else:
                content = f"Encontrei um total de 1 timeout registrado para **{_user}**"
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


class DiscordLogger():

    def __init__(self, webhook_url: str) -> None:
        self.webhook_url = webhook_url

    async def setup(self):
        self.webhook = Webhook.from_url(
            self.webhook_url, adapter=AsyncWebhookAdapter(ClientSession())
        )

    @staticmethod
    def _format_title(title: str) -> str:
        return f"[{title}](https://twitch.tv/felps)"

    async def timeout(self, timeout: "Timeout"):
        embed = Embed(color=RED, title="Timeout")
        embed.add_field(name="Usuário", value=timeout.username)
        embed.add_field(name="Mod", value=timeout.moderator)
        embed.add_field(name="Motivo", value=timeout.reason, inline=False)
        embed.add_field(name="Até", value=discord_time(timeout.finish_at), inline=False)
        await self.webhook.send(embed=embed)

    async def timeout_end(self, timeout: "Timeout"):
        embed = Embed(color=GRAY, title="Fim de Timeout")
        embed.add_field(name="Usuário", value=timeout.username)
        embed.add_field(name="Mod", value=timeout.moderator)
        embed.add_field(name="Motivo", value=timeout.reason, inline=False)
        embed.add_field(name="Até", value=discord_time(timeout.finish_at), inline=False)
        await self.webhook.send(embed=embed)

    async def renew_timeout(self, timeout: "Timeout", seconds: int):
        embed = Embed(color=LIGHT_BLUE, title="Renovação de Timeout")
        embed.add_field(name="Usuário", value=timeout.username)
        embed.add_field(name="Mod", value=timeout.moderator)
        embed.add_field(name="Motivo", value=timeout.reason, inline=False)
        embed.add_field(name="De", value=discord_time(timeout.created_at), inline=False)
        embed.add_field(name="Até", value=discord_time(timeout.finish_at), inline=False)
        embed.add_field(name="Timeout dado", value=humanize.naturaldelta(seconds, when=datetime.utcnow()), inline=False)
        await self.webhook.send(embed=embed)

    async def untimeout(self, timeout: "Timeout"):
        embed = Embed(color=GREEN, title="Untimeout")
        embed.add_field(name="Usuário", value=timeout.username)
        embed.add_field(name="Mod", value=timeout.moderator)
        embed.add_field(name="Motivo", value=timeout.reason, inline=False)
        await self.webhook.send(embed=embed)

    async def revoke(self, timeout: "Timeout"):
        embed = Embed(color=GREEN, title="Revoke")
        embed.add_field(name="Usuário", value=timeout.username)
        embed.add_field(name="Mod", value=timeout.moderator)
        embed.add_field(name="Motivo", value=timeout.reason, inline=False)
        await self.webhook.send(embed=embed)

    async def ban(self, timeout: "Timeout"):
        embed = Embed(color=RED, title="Ban")
        embed.add_field(name="Usuário", value=timeout.username)
        embed.add_field(name="Mod", value=timeout.moderator)
        embed.add_field(name="Motivo", value=timeout.reason, inline=False)
        await self.webhook.send(embed=embed)

    async def unban(self, timeout: "Timeout"):
        embed = Embed(color=GREEN, title="Unban")
        embed.add_field(name="Usuário", value=timeout.username)
        embed.add_field(name="Mod", value=timeout.moderator)
        await self.webhook.send(embed=embed)

    async def critical(self, text: str, error: "Exception" = None):
        embed = Embed(color=CRITICAL, title="💥  Erro Crítico do bot")
        embed.description = text
        if error:
            tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))
            file = File(BytesIO(tb.encode('utf-8')), filename='traceback.py')
        await self.webhook.send(embed=embed, file=file if error else None)

    async def error(self, text: str, error: "Exception" = None):
        embed = Embed(color=LIGHT_RED, title="<:white_x_mark:822315889742315540>  Erro do bot")
        embed.description = text
        if error:
            tb = "".join(traceback.format_exception(type(error), error, error.__traceback__))
            file = File(BytesIO(tb.encode('utf-8')), filename='traceback.py')
        await self.webhook.send(embed=embed, file=file if error else None)

    async def warning(self, text: str):
        embed = Embed(color=YELLOW, title="⚠️  Aviso do bot")
        embed.description = text
        await self.webhook.send(embed=embed)

    async def info(self, text: str):
        embed = Embed(color=LIGHT_BLUE, title="ℹ️  Informação do bot")
        embed.description = text
        await self.webhook.send(embed=embed)

    async def stream_start(self, title: str):
        embed = Embed(color=TWITCH, title="Stream Iniciada")
        embed.add_field(name="Título", value=self._format_title(title))
        await self.webhook.send(embed=embed)

    async def stream_end(self):
        embed = Embed(color=TWITCH, title="Stream Encerrada")
        await self.webhook.send(embed=embed)
