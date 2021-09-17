from dispike.register.models import DiscordCommand
from dispike.register.models.options import CommandOption, CommandTypes


command_timeout = DiscordCommand(
    name="timeout", description="Dê timeout nos foras da lei!",
    options=[
        CommandOption(
            name="username",
            description="a pessoa que vai receber o CALA BOCA PUTA",
            required=True,
            type=CommandTypes.STRING),
        CommandOption(
            name="tempo",
            description="quanto tempo vai durar?",
            required=True,
            type=CommandTypes.STRING),
        CommandOption(
            name="motivo",
            description="então me diga, qual o motivo desse timeout?",
            required=True,
            type=CommandTypes.STRING)
    ]
)

command_untimeout = DiscordCommand(
    name="untimeout", description="Tire os timeouts dos não mais foras da lei!",
    options=[
        CommandOption(
            name="username",
            description="a pessoa que vai deixar de receber o CALA BOCA PUTA",
            required=True,
            type=CommandTypes.STRING),
        CommandOption(
            name="motivo",
            description="cá entre nós, qual o motivo dessa libertação?",
            required=True,
            type=CommandTypes.STRING)
    ]
)

command_check = DiscordCommand(
    name="lookup", description="Verifique o histório de timeouts de algum usuário.!",
    options=[
        CommandOption(
            name="username",
            description="o nome da pessoa que você quer bisbilhotar",
            required=True,
            type=CommandTypes.STRING)
    ]
)

commands = [command_timeout, command_untimeout, command_check]
