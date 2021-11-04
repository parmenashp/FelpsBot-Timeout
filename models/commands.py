from dispike.register.models import DiscordCommand
from dispike.register.models.options import CommandOption, CommandTypes


command_timeout = DiscordCommand(
    name="timeout", description="Dá timeout nos foras da lei!",
    options=[
        CommandOption(
            name="username",
            description="A pessoa que vai receber o CALA BOCA PUTA",
            required=True,
            type=CommandTypes.STRING),
        CommandOption(
            name="tempo",
            description="Quanto tempo vai durar? (Exemplos: 300s, 120m, 20d, 3w, 1mo, 2y)",
            required=True,
            type=CommandTypes.STRING),
        CommandOption(
            name="motivo",
            description="Então me diga, qual o motivo desse timeout?",
            required=True,
            type=CommandTypes.STRING)
    ]
)

command_untimeout = DiscordCommand(
    name="untimeout", description="Tira os timeouts dos não mais foras da lei!",
    options=[
        CommandOption(
            name="username",
            description="A pessoa que vai deixar de receber o CALA BOCA PUTA",
            required=True,
            type=CommandTypes.STRING),
        CommandOption(
            name="motivo",
            description="Cá entre nós, qual o motivo dessa libertação?",
            required=True,
            type=CommandTypes.STRING)
    ]
)

command_check = DiscordCommand(
    name="timeouts", description="Verifica todos os timeouts ativos ou o histório de timeouts de algum usuário.",
    options=[
        CommandOption(
            name="username",
            description="O nome da pessoa que você quer bisbilhotar",
            required=False,
            type=CommandTypes.STRING)
    ]
)

commands = [command_timeout, command_untimeout, command_check]
