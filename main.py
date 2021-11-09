import argparse
import asyncio
from datetime import datetime
import logging
import sys

import humanize
import motor.motor_asyncio
import pymongo
import twitchio
import uvicorn
from dispike import Dispike, IncomingDiscordSlashInteraction, DiscordResponse
from twitchio.ext.eventsub import EventSubClient

import configs
import keys
from models.commands import commands
from models.db import DataBase
from models.embeds import DiscordLogger, LookupResponse, TimeoutsResponse
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

whisper_erros = {
    "whisper_restricted_recipient": ""
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


class WhisperError(Exception):
    def __init__(self, msg_id, message):
        self.msg_id = msg_id
        self.message = message
        super().__init__(self.message)


async def send_whisper(timeout: "Timeout"):
    async with event_lock:
        logger.debug(f"Tentando enviar whisper para o usuário {timeout.username}")
        msg = (
            f"Olá, {timeout.username}. Você quebrou as regras do chat do Felps e recebeu uma punição severa. ",
            "No lugar de um banimento, resolvemos te dar um tempo de espera (timeout) "
            f"extendido de {humanize.naturaldelta(timeout.finish_at, when=datetime.utcnow())}. ",
            "Você irá receber suspensões até que o tempo total seja atingido. ",
            "Caso acredite que seja um engano, ou deseja que um moderador faça uma revisão ",
            f"da suspensão, recorra ao seguinte formulário: {configs.LINK_FORMULARIO}"
        )
        users: list[twitchio.User] = await bot_client.fetch_users(names=[timeout.username])
        await users[0].channel.whisper({msg})

        # Caso o comando de sussuro funcione, a twitch não devolve um NOTICE, deixando a Condição do event_lock travado
        # Então esperamos 2 segundos para ver se a twitch irá devolver algum erro, caso contrário, podemos supor que funcionou.
        try:
            await asyncio.wait_for(event_lock.wait(), 2)
            logger.error(f"Erro ao enviar whisper para {timeout.username}. Tag recebida pela twitch no send_whisper: {to_result_tag}")
            raise WhisperError(to_result_tag, to_result_msg)
        except asyncio.TimeoutError:
            return True


async def remove_timeout(timeout: "Timeout"):
    async with event_lock:
        logger.debug(f"Tentando tirar timeout do usuário {timeout.username}")
        await bot_client.get_channel("mitsuaky").send(timeout.untimeout_command)
        await event_lock.wait()
        if to_result_tag == "untimeout_success":
            logger.debug(f"Timeout retirado com sucesso do usuário {timeout.username}.")
            return True
        else:
            logger.error(f"Remove timeout no usuário {timeout.username} falhou. TRT: {to_result_tag} TRM: {to_result_msg}")
            raise UntimeoutError(to_result_tag, to_result_msg)


async def give_timeout(timeout: "Timeout"):
    async with event_lock:
        logger.debug(f"Tentando dar timeout no usuário {timeout.username}")
        await bot_client.get_channel("mitsuaky").send(timeout.timeout_command)
        await event_lock.wait()
        if to_result_tag == "timeout_success":
            logger.debug(f"Timeout realizado com sucesso no usuário {timeout.username}.")
            return True
        else:
            logger.error(f"Timeout no usuário {timeout.username} falhou. TRT: {to_result_tag} TRM: {to_result_msg}")
            raise TimeoutError(to_result_tag, to_result_msg)


async def on_timeout_timer_end(timeout: "Timeout"):  # Chamado pelo timer toda vez que chega a hora de ter um timeout.
    try:
        seconds = timeout.next_timeout_seconds
        await give_timeout(timeout)
    except TimeoutError as e:
        text = f"Não consegui renovar o timeout do usuário {timeout.username}. Resposta da Twitch: {e.orignal_message}"
        return await dlogger.error(text)

    await timeout.update_last_timeout()
    logger.info(f"Timeout do usuário {timeout.username} foi renovado por mais {seconds} segundos.")
    await dlogger.renew_timeout(timeout, seconds)


async def on_timeout_end(timeout: "Timeout"):  # Chamado pelo timer toda vez que algum timeout chega ao final.
    logger.info(f"Timeout do usuário {timeout.username} acabou.")
    await dlogger.timeout_end(timeout)


@bot.on("timeout")
async def handle_timeout(ctx: IncomingDiscordSlashInteraction, username: str, tempo: str, motivo: str) -> DiscordResponse:
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

        whisper = True

        try:
            await send_whisper(to)
        except WhisperError:
            whisper = False
        except Exception as e:
            dlogger.error(f"Erro ao tentar enviar whisper para o usuário {username}", e)
            whisper = True

        natural = humanize.naturaldelta(time.dt, when=datetime.utcnow())
        end_time = to.finish_at.strftime("%d/%m/%Y ás %H:%M:%S")
        await to.insert()
        await timer.unlock_timers()
        await dlogger.timeout(to)

        content = f"Prontinho! {username} agora ficará de bico calado por {natural}, ou seja, até o dia {end_time}."
        if not whisper:
            content += "\n⚠️ Porém não consegui enviar Whisper para o usuário."

        return DiscordResponse(
            content=f"Prontinho! {username} agora ficará de bico calado por {natural}, ou seja, até o dia {end_time}.",
            empherical=False,
        )
    except pymongo.errors.OperationFailure as e:
        await dlogger.error("Erro no banco de dados.", e)
        return DiscordResponse(
            content=f"Ocorreu um erro no banco de dados durante a execução desse comando. Código de erro: {e.code}",
            empherical=False,
        )
    except Exception as e:
        await dlogger.error("Erro durante a execução do comando `timeout`.", e)


@bot.on("untimeout")
async def handle_untimeout(ctx: IncomingDiscordSlashInteraction, username: str, motivo: str) -> DiscordResponse:
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
            await timer.restart_timers()
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
        await dlogger.error("Erro no banco de dados.", e)
        return DiscordResponse(
            content=f"Ocorreu um erro no banco de dados durante a execução desse comando. Código de erro: {e.code}",
            empherical=False,
        )
    except Exception as e:
        await dlogger.error("Erro durante a execução do comando `untimeout`.", e)


@bot.on("timeouts")
async def handle_timeouts(ctx: IncomingDiscordSlashInteraction, **kwargs) -> DiscordResponse:
    try:
        username = kwargs.get('username')
        if username:
            tos = await db.get_user_timeouts(username)
            return LookupResponse(username, tos)

        else:
            tos = await db.get_active_timeouts()
            return TimeoutsResponse(tos)

    except pymongo.errors.OperationFailure as e:
        await dlogger.error("Erro no banco de dados.", e)
        return DiscordResponse(
            content=f"Ocorreu um erro no banco de dados durante a execução desse comando. Código de erro: {e.code}",
            empherical=False,
        )
    except Exception as e:
        await dlogger.error("Erro durante a execução do comando `timeouts`.", e)


@bot_client.event()
async def event_raw_data(data):  # Função chamada toda vez que algo é recebido pelo IRC da Twitch
    global to_result_tag
    global to_result_msg
    async with event_lock:
        # print(data)

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


@bot_client.event()
async def event_ready():
    logger.info("IRC conectado, iniciando timer.")
    await timer.start()


async def event_eventsub_notification_stream_start(data):  # Função chamada toda vez que abre stream
    fetched_data: list[twitchio.models.Stream] = await api_client.fetch_streams(user_ids=[configs.FELPS_TWITCH_ID])
    if fetched_data:
        await dlogger.stream_start(fetched_data[0].title)


async def event_eventsub_notification_stream_end(data):  # Função chamada toda vez que fecha stream
    await dlogger.stream_end()


async def setup():
    await dlogger.setup()
    await dlogger.info("Iniciando bot")
    bot_client.add_event(event_eventsub_notification_stream_start)
    bot_client.add_event(event_eventsub_notification_stream_end)

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

    await eventsub_client.listen(host="localhost", port=8081)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-rc", "--register_commands", action="store_true",
                        help="registra/atualiza os comandos no discord")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="aumenta a verbosidade do código (debug)")
    args = parser.parse_args()

    # if not args.verbose:  # fix debug trash from twitchio
    #     loguru.logger.remove()
    #     loguru.logger.add(sys.stderr, level="INFO")

    sh = logging.StreamHandler()
    sh.setFormatter(
        logging.Formatter(
            "[%(asctime)s] %(levelname)s | %(name)s - %(message)s"
        )
    )
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, handlers=[sh])
    logger = logging.getLogger('felpstimeout.main')

    if args.register_commands:
        try:
            for command in commands:
                bot.register(command=command, guild_only=True, guild_to_target=configs.GUILD_ID)
                logger.debug(f'Registrado o comando {command.name} para a guild {configs.GUILD_ID}')
            logger.info('Todos os comandos foram registrados com sucesso.')
        except Exception:
            logger.exception("Erro ao tentar registrar os comandos")
        sys.exit()

    logger.info("Iniciando bot.")

    event_lock = asyncio.Condition()
    server = uvicorn.Server(uvicorn.Config(bot.referenced_application, port=8080))
    dlogger = DiscordLogger(configs.WEBHOOK_URL)
    timer = TimeoutTimer(db, timeout_callback=on_timeout_timer_end, timeout_end_callback=on_timeout_end)

    async def run():
        try:
            await setup()
            await bot_client.connect()
            await server.serve()

            await dlogger.info("Bot desligado")
        except Exception as e:
            logger.exception("Erro fatal que fudeu a porra toda")
            await dlogger.critical("Ocorreu um erro que me impossibilita de continuar funcionando.", e)

    loop = asyncio.get_event_loop()
    loop.run_until_complete(run())
