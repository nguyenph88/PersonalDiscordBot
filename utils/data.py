import discord
import os

from utils import permissions, default
from utils.config import Config
from discord.ext.commands import AutoShardedBot, DefaultHelpCommand


class DiscordBot(AutoShardedBot):
    def __init__(self, config: Config, prefix: list[str] = None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.prefix = prefix
        self.config = config

    async def setup_hook(self):
        for file in os.listdir("cogs"):
            if not file.endswith(".py"):
                continue  # Skip non-python files

            name = file[:-3]
            
            # Skip crypto_virtual_trader if VIRTUAL_TRADER_CHANNEL is blank
            if name == "crypto_virtual_trader":
                virtual_trader_channel = getattr(self.config, 'virtual_trader_channel', None)
                if not virtual_trader_channel or virtual_trader_channel.strip() == "":
                    print(f"--- Skipping {name} cog - VIRTUAL_TRADER_CHANNEL is blank")
                    continue
            
            # Skip crypto if all crypto trading channels are blank
            if name == "crypto":
                crypto_day_trade_channel = getattr(self.config, 'crypto_day_trade_channel', None)
                crypto_swing_trade_channel = getattr(self.config, 'crypto_swing_trade_channel', None)
                crypto_long_term_trade_channel = getattr(self.config, 'crypto_long_term_trade_channel', None)
                
                # Check if all channels are empty or blank
                all_channels_empty = (
                    not crypto_day_trade_channel or crypto_day_trade_channel.strip() == "" and
                    not crypto_swing_trade_channel or crypto_swing_trade_channel.strip() == "" and
                    not crypto_long_term_trade_channel or crypto_long_term_trade_channel.strip() == ""
                )
                
                if all_channels_empty:
                    print(f"--- Skipping {name} cog - All crypto trading channels are blank")
                    continue
            
            # Skip download if REQUEST_CHANNEL_NAME is blank
            if name == "download":
                request_channel_name = getattr(self.config, 'request_channel_name', None)
                if not request_channel_name or request_channel_name.strip() == "":
                    print(f"--- Skipping {name} cog - REQUEST_CHANNEL_NAME is blank")
                    continue
            
            await self.load_extension(f"cogs.{name}")

    async def on_message(self, msg: discord.Message):
        if not self.is_ready() or msg.author.bot or \
           not permissions.can_handle(msg, "send_messages"):
            return

        await self.process_commands(msg)

    async def process_commands(self, msg):
        ctx = await self.get_context(msg, cls=default.CustomContext)
        await self.invoke(ctx)


class HelpFormat(DefaultHelpCommand):
    def get_destination(self, no_pm: bool = False):
        if no_pm:
            return self.context.channel
        else:
            return self.context.author

    async def send_error_message(self, error: str) -> None:
        """ Sends an error message to the destination. """
        destination = self.get_destination(no_pm=True)
        await destination.send(error)

    async def send_command_help(self, command) -> None:
        """ Sends the help for a single command. """
        self.add_command_formatting(command)
        self.paginator.close_page()
        await self.send_pages(no_pm=True)

    async def send_pages(self, no_pm: bool = False) -> None:
        """ Sends the help pages to the destination. """
        try:
            if permissions.can_handle(self.context, "add_reactions"):
                await self.context.message.add_reaction(chr(0x2709))
        except discord.Forbidden:
            pass

        try:
            destination = self.get_destination(no_pm=no_pm)
            for page in self.paginator.pages:
                await destination.send(page)
        except discord.Forbidden:
            destination = self.get_destination(no_pm=True)
            await destination.send("Couldn't send help to you due to blocked DMs...")
