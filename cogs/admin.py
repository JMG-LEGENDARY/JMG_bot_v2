"""Cog Admin - Commandes d'administration"""

import discord
from discord.ext import commands
from discord import app_commands


class AdminCog(commands.Cog):
    """Commandes d'administration du bot."""
    
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="say", description="Fait dire quelque chose au bot")
    @app_commands.checks.has_permissions(administrator=True)
    async def say(self, interaction: discord.Interaction, message: str):
        """Commande pour faire répéter un message (admin uniquement)."""
        await interaction.response.send_message(message)


async def setup(bot):
    """Fonction requise par discord.py pour charger le cog."""
    await bot.add_cog(AdminCog(bot))
