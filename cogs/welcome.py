"""Cog Welcome - Messages de bienvenue et événements de joueurs"""

import discord
from discord.ext import commands
import random
import logging
from datetime import datetime

from db import db, get_or_create_user, GameSession, User
from utils import get_logger
from config import config

logger = get_logger(__name__)

# Messages de bienvenue (en français)
WELCOME_MESSAGES = [
    "Bienvenue, {player}! Prépare-toi pour une aventure épique!",
    "Salut {player}! Le serveur t'attendait pour commencer la fête!",
    "Attention tout le monde! {player} vient de se connecter!",
    "Hey {player}! C'est parti pour une nouvelle aventure!",
    "{player} a rejoint le serveur! Que la quête commence!",
    "Un nouvel aventurier, {player}, est parmi nous! Préparez-vous!",
    "Bienvenue sur le serveur, {player}! Ton aventure commence maintenant.",
    "Tout le monde, dites bonjour à {player}!",
    "{player} vient de débarquer! Le serveur est prêt pour toi!",
    "Un grand salut à {player} qui vient de nous rejoindre!",
    "Le héros de la légende, {player}, est enfin arrivé!",
    "Attention! {player} vient de pop comme un creeper derrière toi!",
    "Qui a laissé la porte ouverte? Ah non, c'est juste {player}!",
    "{player} est ici! Que les blocs tremblent!",
    "Et voici {player}, prêt à miner tout ce qui bouge!",
    "{player} a spawné! Est-ce que le serveur survivra?",
    "Alerte! Un nouveau joueur sauvage, {player}, est apparu!",
    "Pas de panique, {player} est là pour sauver le serveur!",
    "Les zombies ont peur... {player} est en ligne!",
    "Si vous voyez {player}, restez à l'écart on ne sait jamais!",
]

GOODBYE_MESSAGES = [
    "Au revoir {player}! Reviens vite avant que le serveur ne s'ennuie!",
    "{player} a quitté le serveur! Les mobs peuvent respirer... pour l'instant.",
    "{player} s'est déconnecté. Le serveur est un peu plus vide maintenant.",
    "Bye {player}! N'oublie pas de revenir miner quelques blocs!",
    "{player} a disparu... Mais où est-il parti?",
    "Déconnexion de {player}: C'est ciaw!",
    "C'est tout pour aujourd'hui pour {player}! À la prochaine!",
    "Le monde de Minecraft dit au revoir à {player}!",
    "Ne partez pas tous! Ah non, c'est juste {player} qui s'en va.",
    "Et voilà, {player} a quitté le serveur. Fin de la fête...",
    "{player} est parti, mais le creeper reste... Attention!",
    "Le serveur perd un aventurier... À bientôt, {player}!",
    "Déconnexion de {player}... Une autre aventure l'attend!",
    "{player} s'en va. On parie qu'il revient avec du café?",
    "{player} a quitté le serveur! Les moutons peuvent enfin se reposer.",
    "Bye {player}! N'oublie pas de fermer le portail du Nether en sortant!",
    "{player} s'est déco! Qui va s'occuper des creepers maintenant?",
    "Déconnexion de {player}. Le calme revient... pour combien de temps?",
    "{player} s'en va, mais ses constructions restent!",
    "À la prochaine, {player}! Le serveur attendra ton retour!",
]


class WelcomeCog(commands.Cog):
    """Gestion des messages de bienvenue et événements de joueurs"""
    
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Vérifie les messages pour les commandes"""
        # Ignorer les bots
        if message.author.bot:
            return
        
        # Vérifie si c'est une commande slash ou mention
        await self.bot.process_commands(message)

    async def send_welcome_message(self, channel: discord.TextChannel, player_name: str):
        """Envoie un message de bienvenue randomisé"""
        try:
            if not channel:
                logger.warning("Canal de bienvenue non configuré")
                return
            
            message = random.choice(WELCOME_MESSAGES)
            msg = message.replace("{player}", player_name)
            
            embed = discord.Embed(
                title="🎮 Nouveau joueur!",
                description=msg,
                color=discord.Color.green()
            )
            embed.set_thumbnail(url="https://craftheads.net/avatar/" + player_name + "/64.png")
            
            await channel.send(embed=embed)
            logger.info(f"✅ Message de bienvenue: {player_name}")
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi du message de bienvenue: {e}")

    async def send_goodbye_message(self, channel: discord.TextChannel, player_name: str):
        """Envoie un message d'au revoir randomisé"""
        try:
            if not channel:
                logger.warning("Canal d'au revoir non configuré")
                return
            
            message = random.choice(GOODBYE_MESSAGES)
            msg = message.replace("{player}", player_name)
            
            embed = discord.Embed(
                title="🚪 Joueur parti",
                description=msg,
                color=discord.Color.red()
            )
            embed.set_thumbnail(url="https://craftheads.net/avatar/" + player_name + "/64.png")
            
            await channel.send(embed=embed)
            logger.info(f"✅ Message d'au revoir: {player_name}")
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi du message d'au revoir: {e}")

    async def log_player_stats(self, player_name: str, session_duration_minutes: float, action: str):
        """Enregistre les stats d'un joueur"""
        try:
            channel_id = config.CHANNELS.get("logs")
            if not channel_id:
                return
            
            channel = self.bot.get_channel(channel_id)
            if not channel:
                return
            
            embed = discord.Embed(
                title=f"📊 Event Minecraft: {action}",
                color=discord.Color.blue()
            )
            embed.add_field(name="Joueur", value=f"`{player_name}`", inline=True)
            
            if action == "leave":
                hours = int(session_duration_minutes // 60)
                minutes = int(session_duration_minutes % 60)
                embed.add_field(
                    name="Durée session",
                    value=f"**{hours}h {minutes}m**",
                    inline=True
                )
            
            embed.set_footer(text=f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            await channel.send(embed=embed)
        except Exception as e:
            logger.debug(f"Impossible de logger les stats: {e}")


async def setup(bot):
    """Fonction requise par discord.py pour charger le cog."""
    await bot.add_cog(WelcomeCog(bot))
    logger.info("✅ WelcomeCog chargé")
