"""Cog Purchase - Gestion des achats automatiques à la connexion Minecraft"""

import discord
from discord.ext import commands, tasks
from datetime import datetime
import logging

from db import db, GameSession, PendingPurchase, User
from utils import get_logger
from utils.logger import relay_log
import crafty_api
from config import config

logger = get_logger(__name__)


class PurchaseCog(commands.Cog):
    """Gestion des livraisons d'achats quand les joueurs se connectent"""
    
    def __init__(self, bot):
        self.bot = bot
        self.active_sessions = {}  # username -> discord_user_id
        self.deliver_purchases.start()

    @tasks.loop(seconds=30)
    async def deliver_purchases(self):
        """Vérifie périodiquement s'il y a des achats à livrer"""
        try:
            with db.get_session() as session:
                # Trouver les joueurs actuellement en ligne (sessions sans logout)
                active_sessions = session.query(GameSession).filter(
                    GameSession.logout_time.is_(None)
                ).all()
                
                for game_session in active_sessions:
                    # Trouver les achats en attente pour ce joueur
                    pending_purchases = session.query(PendingPurchase).join(
                        User
                    ).filter(
                        User.minecraft_username == game_session.minecraft_username,
                        PendingPurchase.status == "pending"
                    ).all()
                    
                    for purchase in pending_purchases:
                        await self._deliver_purchase(session, purchase, game_session.minecraft_username)
        
        except Exception as e:
            logger.error(f"Erreur dans deliver_purchases: {e}", exc_info=True)

    @deliver_purchases.before_loop
    async def before_deliver(self):
        await self.bot.wait_until_ready()

    async def deliver_purchases_for_username(self, username: str) -> int:
        """Livre les achats en attente pour un pseudo Minecraft donné."""
        delivered = 0
        with db.get_session() as session:
            pending_purchases = session.query(PendingPurchase).join(User).filter(
                User.minecraft_username == username,
                PendingPurchase.status == "pending"
            ).all()
            for purchase in pending_purchases:
                await self._deliver_purchase(session, purchase, username)
                delivered += 1
        return delivered

    async def deliver_pending_for_discord_user(self, discord_id: int) -> tuple[int, bool]:
        """Tente de livrer les achats d'un utilisateur Discord si il est en jeu."""
        with db.get_session() as session:
            user = session.query(User).filter(User.discord_id == discord_id).first()
            if not user or not user.minecraft_username:
                return 0, False

            is_online = session.query(GameSession).filter(
                GameSession.minecraft_username == user.minecraft_username,
                GameSession.logout_time.is_(None)
            ).count() > 0

            pending_purchases = session.query(PendingPurchase).filter(
                PendingPurchase.user_id == user.id,
                PendingPurchase.status == "pending"
            ).all()

            if not pending_purchases:
                return 0, is_online

            if not is_online:
                return len(pending_purchases), False

            delivered = 0
            for purchase in pending_purchases:
                await self._deliver_purchase(session, purchase, user.minecraft_username)
                delivered += 1
            return delivered, True

    async def _deliver_purchase(self, session, purchase, minecraft_username: str):
        """Livre un achat à un joueur"""
        try:
            item = purchase.item
            
            # Formatter la commande avec le nom du joueur
            command = item.minecraft_command.replace("{player}", minecraft_username).replace("{joueur}", minecraft_username)
            
            # Envoyer la commande
            for _ in range(purchase.quantity):
                result = await crafty_api.envoyer_commande(command)
                
                if not result.get("success"):
                    logger.error(f"Erreur livraison: {result}")
                    purchase.status = "failed"
                    purchase.error_message = result.get("erreur", "Erreur inconnue")
                    session.commit()
                    return
            
            # Marquer comme livré
            purchase.status = "completed"
            purchase.completed_at = datetime.utcnow()
            session.commit()
            
            # Log et notification
            logger.info(f"✅ Achat livré: {minecraft_username} → {item.name} x{purchase.quantity}")
            try:
                await relay_log(
                    self.bot,
                    "Achat livré",
                    f"✅ {minecraft_username} a reçu **{item.name}** x{purchase.quantity}",
                    discord.Color.green()
                )
            except Exception:
                pass
            
            # Envoyer une notification Discord
            try:
                user_obj = await self.bot.fetch_user(purchase.user_id)
                embed = discord.Embed(
                    title="📦 Achat livré!",
                    description=f"Vous avez reçu **{item.name}** x{purchase.quantity} en jeu!",
                    color=discord.Color.green()
                )
                await user_obj.send(embed=embed)
            except Exception as e:
                logger.debug(f"Impossible d'envoyer DM de notification: {e}")
        
        except Exception as e:
            logger.error(f"Erreur lors de la livraison: {e}", exc_info=True)
            purchase.status = "failed"
            purchase.error_message = str(e)
            session.commit()

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Quand un utilisateur rejoint le serveur Discord"""
        # Cette fonction est surtout pour les futurs événements
        logger.info(f"Utilisateur Discord rejoint: {member}")

    # Intégration avec MinecraftCog pour les événements Minecraft
    async def on_minecraft_player_join(self, username: str):
        """Appelé quand un joueur Minecraft se connecte"""
        logger.info(f"🎮 Joueur Minecraft connecté: {username}")
        # Les achats seront livrés par deliver_purchases


async def setup(bot):
    """Fonction requise par discord.py pour charger le cog."""
    await bot.add_cog(PurchaseCog(bot))
    logger.info("✅ PurchaseCog chargé")
