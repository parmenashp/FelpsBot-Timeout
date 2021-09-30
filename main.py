import asyncio
from datetime import timedelta
import logging

import humanize
import motor.motor_asyncio
import pymongo
import twitchio
from twitchio.ext.eventsub import models
import uvicorn
from dispike import Dispike
from dispike.models import IncomingDiscordInteraction
from dispike.response import DiscordResponse
from twitchio.ext.eventsub.server import EventSubClient

import configs
import keys
from models.commands import commands
from models.db import DataBase
from models.embeds import DiscordLogger, LookupResponse
from models.timeout import Timeout
from models.timer import TimeoutTimer
from utils.time import BadArgument, ShortTime

humanize.i18n.activate("pt_BR")

bot = Dispike(
    bot_token=keys.discord["bot_token"],
    client_public_key=keys.discord["client_public_key"],
    application_id=keys.discord["application_id"]
)

bot_client = twitchio.Client(
    token=keys.twitch["token"],
    client_secret=keys.twitch["client_secret"],
    initial_channels=["mitsuaky"]
)

api_client = twitchio.Client.from_client_credentials(
    client_id=keys.twitch["client_id"],
    client_secret=keys.twitch["client_secret"]
)

eventsub_client = EventSubClient(
    api_client,
    webhook_secret='cucucuasfdasfd55cu3',
    callback_route='https://5204-177-93-252-26.ngrok.io/callback'
)

client = motor.motor_asyncio.AsyncIOMotorClient(
    keys.mongodb["key"]
)

db = DataBase(client.felpsBot.timeout)


timeout_erros = {
    "bad_timeout_mod": "Você não pode dar Timeout em outro moderador.",
    "bad_timeout_self": "Você não pode me fazer dar Timeout em mim mesmo! Vou contar pra o Mitsuaky, tá? 😭",
    "bad_timeout_broadcaster": "Oh, @<139187739248689152>, tavam querendo te dar Timeout, vai deixar? Se fosse eu, não pagaria o salário."
}

untimeout_erros = {
    "untimeout_banned": "Esse usuário está banido permanentemente, não consigo remover o timeout"
}

to_result_msg = None
to_result_tag = None


class UntimeoutError(Exception):
    def __init__(self, msg_id, message):
        self.msg_id = msg_id
        if msg_id in untimeout_erros:
            self.message = untimeout_erros[to_result_tag]
        else:
            self.message = f"Eu tentei realizar meu trabalho mas eu recebi essa mensagem aí da twitch: {message}"
        super().__init__(self.message)


class TimeoutError(Exception):
    def __init__(self, msg_id, message):
        self.msg_id = msg_id
        self.orignal_message = message
        if msg_id in timeout_erros:
            self.message = timeout_erros[to_result_tag]
        else:
            self.message = f"Eu tentei realizar meu trabalho mas eu recebi essa mensagem aí da twitch: {message}"
        super().__init__(self.message)


async def remove_timeout(timeout: "Timeout"):
    async with event_lock:
        await bot_client.get_channel("mitsuaky").send(timeout.untimeout_command)
        await event_lock.wait()
        if to_result_tag == "untimeout_success":
            return True
        else:
            raise UntimeoutError(to_result_tag, to_result_msg)


async def give_timeout(timeout: "Timeout"):
    async with event_lock:
        await bot_client.get_channel("mitsuaky").send(timeout.timeout_command)
        await event_lock.wait()
        if to_result_tag == "timeout_success":
            return True
        else:
            raise TimeoutError(to_result_tag, to_result_msg)


async def on_timeout_timer_end(timeout: "Timeout"):  # Chamado pelo timer toda vez que chega a hora de ter um timeout.
    try:
        await give_timeout(timeout)
    except TimeoutError as e:
        text = f"Não consegui renovar o timeout do usuário {timeout.username}. Resposta da Twitch: {e.orignal_message}"
        return await dlogger.error(text)

    await timeout.update_last_timeout()
    await dlogger.renew_timeout(timeout)


@bot.interaction.on("timeout")
async def handle_timeout(ctx: IncomingDiscordInteraction, username: str, tempo: str, motivo: str) -> DiscordResponse:
    try:
        try:
            time = ShortTime(tempo)
        except BadArgument:
            return DiscordResponse(
                content=f"O tempo informado é inválido. ({tempo})",
                empherical=False
            )

        to = await db.get_active_user_timeout(username)
        if to:
            end_time = to.finish_at.strftime("%d/%m/%Y ás %H:%M:%S")
            return DiscordResponse(
                content=f"{username} já recebeu um cala boca de {to.moderator} com o motivo \"{to.reason}\" e voltará a falar dia {end_time}.\n"
                "Atualmente não fui programado para lidar com alteração de tempo de sentenças ativas.\n"
                "Caso realmente deseje alterar, peço que solicite o revoke do timeout e crie um novo.", empherical=False)

        to = Timeout(db=db, moderator=ctx.member.user.username, username=username, finish_at=time.dt, reason=motivo)

        try:
            await give_timeout(to)
        except TimeoutError as e:
            return DiscordResponse(
                content=e.message,
                empherical=False,
            )

        natural = humanize.naturaldelta(time.dt)
        end_time = to.finish_at.strftime("%d/%m/%Y ás %H:%M:%S")
        await to.insert()
        await timer.unlock_timer()
        await dlogger.timeout(to)

        return DiscordResponse(
            content=f"Prontinho! {username} agora ficará de bico calado por {natural}, ou seja, até o dia {end_time}.",
            empherical=False,
        )
    except pymongo.errors.OperationFailure as e:
        return DiscordResponse(
            content=f"Ocorreu um erro durante a execução desse comando. Código de erro: {e.code}",
            empherical=False,
        )


@bot.interaction.on("untimeout")
async def handle_untimeout(ctx: IncomingDiscordInteraction, username: str, motivo: str) -> DiscordResponse:
    try:
        to = await db.get_active_user_timeout(username)
        if not to:
            return DiscordResponse(
                content=f"O usuário {username} não tem nenhum timeout ativo.",
                empherical=False,
            )
        try:
            # Possível bug: O timeout ser removido mas ocorrer um erro quando for mudar no banco de dados.
            await remove_timeout(to)
            await to.revoke(revoker=ctx.member.user.username, reason=motivo)
            await timer.restart_timer()
            await dlogger.revoke(to)
        except UntimeoutError as e:
            return DiscordResponse(
                content=e.message,
                empherical=False,
            )
        return DiscordResponse(
            content=f"O timeout do usuário {username} foi removido com sucesso!",
            empherical=False,
        )
    except pymongo.errors.OperationFailure as e:
        return DiscordResponse(
            content=f"Ocorreu um erro durante a execução desse comando. Código de erro: {e.code}",
            empherical=False,
        )


@bot.interaction.on("lookup")
async def handle_lookup(ctx: IncomingDiscordInteraction, username: str) -> DiscordResponse:
    try:
        tos = await db.get_user_timeouts(username)
        return LookupResponse(username, tos)

    except pymongo.errors.OperationFailure as e:
        return DiscordResponse(
            content=f"Ocorreu um erro durante a execução desse comando. Código de erro: {e.code}",
            empherical=False,
        )


@bot_client.event()
async def event_raw_data(data):
    global to_result_tag
    global to_result_msg
    async with event_lock:
        print(data)

        groups = data.split()
        try:
            if groups[2] != "NOTICE":
                return
        except IndexError:
            return

        prebadge = groups[0].split(";")
        badges = {}

        for badge in prebadge:
            badge = badge.split("=")

            try:
                badges[badge[0]] = badge[1]
            except IndexError:
                pass
            to_result_tag = badges['@msg-id']
            to_result_msg = " ".join(groups[4:]).lstrip(":")
            # libera a condição no give_timeout() ou remove_timeout()
            event_lock.notify()


async def event_eventsub_notification_stream_start(data):
    fetched_data: list[twitchio.models.Stream] = await api_client.fetch_streams(user_ids=[configs.FELPS_TWITCH_ID])
    if fetched_data:
        await dlogger.stream_start(fetched_data[0].title)


async def event_eventsub_notification_stream_end(data):
    await dlogger.stream_end()


async def setup():
    bot_client.add_event(event_eventsub_notification_stream_start)
    bot_client.add_event(event_eventsub_notification_stream_end)
    await dlogger.setup()
    await dlogger.info("Iniciando bot")

    subscriptions = await eventsub_client.get_subscriptions()
    sub_stream_online = False
    sub_stream_offline = False

    for subscription in subscriptions:
        if (subscription.status != "enabled") or (subscription.transport.callback != eventsub_client.route) \
                or (subscription.condition != {'broadcaster_user_id': configs.FELPS_TWITCH_ID}):
            continue
            # await eventsub_client._http.delete_subscription(subscription)
        if subscription.type == "stream.online":
            sub_stream_online = True
        if subscription.type == "stream.offline":
            sub_stream_offline = True

    if not sub_stream_online:
        await eventsub_client.subscribe_channel_stream_start(configs.FELPS_TWITCH_ID)
        sub_stream_online = True
    if not sub_stream_offline:
        await eventsub_client.subscribe_channel_stream_end(configs.FELPS_TWITCH_ID)
        sub_stream_offline = True

    # await eventsub_client.listen(host="localhost", port=8081)

if __name__ == "__main__":
    sh = logging.StreamHandler()
    sh.setLevel(logging.DEBUG)
    sh.setFormatter(
        logging.Formatter(
            "[%(asctime)s] %(name)s | %(filename)s - %(levelname)s - %(message)s"
        )
    )
    logging.basicConfig(level=logging.DEBUG, handlers=[sh])
    logger = logging.getLogger('felpstimeout.main')

    logger.info("Iniciando bot.")

    event_lock = asyncio.Condition()
    server = uvicorn.Server(uvicorn.Config(bot.referenced_application, port=8080))
    dlogger = DiscordLogger(configs.WEBHOOK_URL)
    timer = TimeoutTimer(db, timeout_callback=on_timeout_timer_end)
    # for command in commands:
    #     bot.register(command=command, guild_only=True, guild_to_target=296214474791190529)

    async def run():
        try:
            await setup()
            await bot_client.connect()
            await timer.start()
            await server.serve()

            await dlogger.info("Bot desligado")
        except Exception as e:
            await dlogger.critical("Ocorreu um erro que me impossibilita de continuar funcionando.", e)

    loop = asyncio.get_event_loop()
    loop.run_until_complete(run())
