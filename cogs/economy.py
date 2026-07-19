"""Cog Economy - Système CraftyCoin"""

import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import logging

from db import db, get_or_create_user, add_transaction, get_user_rank, get_leaderboard, User
from utils import (
    format_craftycoin_embed, format_leaderboard_embed, format_transaction_embed,
    format_error_embed, format_success_embed, calculate_daily_reward, is_new_day,
    format_coins, get_logger
)
from core.decorators import log_command, defer_interaction, handle_errors
from core.constants import EMOJI, TIMEOUTS

logger = get_logger(__name__)


class EconomyCog(commands.Cog):
    """Gestion du système d'économie CraftyCoin"""
    
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="solde", description="Affiche votre solde CraftyCoin")
    @app_commands.checks.cooldown(1, 5, key=lambda i: i.user.id)
    @defer_interaction(ephemeral=True)
    @log_command
    @handle_errors
    async def solde(self, interaction: discord.Interaction):
        """Affiche le solde CraftyCoin d'un utilisateur"""
        with db.get_session() as session:
            user = get_or_create_user(session, interaction.user.id)
            rank = get_user_rank(session, user.id)
            
            embed = format_craftycoin_embed(
                user_balance=user.craftycoin_balance,
                rank=rank,
                nickname=interaction.user.display_name
            )
            
            # Ajouter des stats
            embed.add_field(name="Messages", value=f"📝 {user.total_messages}", inline=True)
            embed.add_field(name="Caractères", value=f"✏️ {user.total_characters}", inline=True)
            embed.add_field(name="Réponses", value=f"💬 {user.total_responses}", inline=True)
            embed.add_field(
                name="Temps de jeu",
                value=f"🎮 {user.total_playtime_minutes:.0f}m",
                inline=True
            )
            
            embed.set_footer(text=f"Multiplicateurs: Messages {user.message_multiplier:.1f}x | "
                                 f"Temps {user.playtime_multiplier:.1f}x | "
                                 f"Réponses {user.response_multiplier:.1f}x")
            
            await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="classement", description="Affiche le classement des top 10")
    @app_commands.checks.cooldown(1, 10, key=lambda i: i.user.id)
    @defer_interaction(ephemeral=True)
    @log_command
    @handle_errors
    async def classement(self, interaction: discord.Interaction):
        """Affiche le classement des utilisateurs par CraftyCoin"""
        with db.get_session() as session:
            leaderboard_users = get_leaderboard(session, limit=10)
            
            if not leaderboard_users:
                embed = format_error_embed("Classement vide", "Aucun utilisateur n'a de CraftyCoins")
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # Formater pour l'embed
            leaderboard_data = [
                (user.discord_id, user.craftycoin_balance) for user in leaderboard_users
            ]
            
            embed = discord.Embed(
                title="🏆 Classement CraftyCoin",
                color=discord.Color.gold()
            )
            
            medals = ["🥇", "🥈", "🥉"]
            for idx, (user, balance) in enumerate(zip(leaderboard_users, range(len(leaderboard_users)))):
                medal = medals[idx] if idx < 3 else f"#{idx + 1}"
                try:
                    user_obj = await self.bot.fetch_user(user.discord_id)
                    username = user_obj.name
                except:
                    username = f"ID:{user.discord_id}"
                
                embed.add_field(
                    name=f"{medal} {username}",
                    value=f"**{format_coins(user.craftycoin_balance)}**",
                    inline=False
                )
            
            await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="daily", description="Réclamer votre récompense quotidienne")
    @app_commands.checks.cooldown(1, 3600, key=lambda i: i.user.id)  # 1 heure cooldown
    @defer_interaction(ephemeral=True)
    @log_command
    @handle_errors
    async def daily_reward(self, interaction: discord.Interaction):
        """Réclame la récompense quotidienne CraftyCoin"""
        with db.get_session() as session:
            user = get_or_create_user(session, interaction.user.id)
            
            # Vérifier si c'est un nouveau jour
            if not is_new_day(user.last_daily_reward):
                time_until = user.last_daily_reward.replace(hour=0, minute=0, second=0, microsecond=0)
                from datetime import timedelta
                time_until += timedelta(days=1)
                seconds_left = (time_until - datetime.utcnow()).total_seconds()
                
                hours = int(seconds_left // 3600)
                minutes = int((seconds_left % 3600) // 60)
                
                embed = format_error_embed(
                    "Récompense quotidienne déjà reçue",
                    f"Revenez dans **{hours}h {minutes}m**"
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # Mettre à jour les jours consécutifs
            if is_new_day(user.last_daily_reward):
                user.consecutive_days += 1
            else:
                user.consecutive_days = 1
            
            # Calculer la récompense
            from config import config
            reward = calculate_daily_reward(
                config.DAILY_REWARD_BASE,
                user.consecutive_days,
                config.DAILY_REWARD_MULTIPLIER
            )
            
            # Ajouter la transaction
            add_transaction(
                session,
                user.id,
                reward,
                "daily",
                f"Récompense quotidienne (jour {user.consecutive_days})",
                base_amount=config.DAILY_REWARD_BASE,
                multiplier=config.DAILY_REWARD_MULTIPLIER ** (user.consecutive_days - 1)
            )
            
            user.last_daily_reward = datetime.utcnow()
            session.commit()
            
            # Notification
            embed = discord.Embed(
                title="✅ Récompense reçue!",
                color=discord.Color.green()
            )
            embed.add_field(name="Montant", value=f"**+{format_coins(reward)}**", inline=True)
            embed.add_field(name="Jours consécutifs", value=f"**{user.consecutive_days}** 🔥", inline=True)
            embed.set_footer(text=f"Demain: +{format_coins(calculate_daily_reward(config.DAILY_REWARD_BASE, user.consecutive_days + 1, config.DAILY_REWARD_MULTIPLIER))}")
            
            await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="transfert", description="Transférer des CraftyCoins à quelqu'un")
    @app_commands.describe(destinataire="Personne qui reçoit les coins", montant="Nombre de coins à transférer")
    @app_commands.checks.cooldown(1, 30, key=lambda i: i.user.id)
    @defer_interaction(ephemeral=False)
    @log_command
    @handle_errors
    async def transfert(self, interaction: discord.Interaction, destinataire: discord.User, montant: float):
        """Transfère des CraftyCoins à un autre utilisateur"""
        
        # Validations
        if destinataire.bot:
            embed = format_error_embed("Erreur", "Vous ne pouvez pas transférer à un bot")
            await interaction.followup.send(embed=embed)
            return
        
        if destinataire.id == interaction.user.id:
            embed = format_error_embed("Erreur", "Vous ne pouvez pas vous transférer à vous-même")
            await interaction.followup.send(embed=embed)
            return
        
        if montant <= 0:
            embed = format_error_embed("Erreur", "Le montant doit être positif")
            await interaction.followup.send(embed=embed)
            return
        
        with db.get_session() as session:
            sender = get_or_create_user(session, interaction.user.id)
            recipient = get_or_create_user(session, destinataire.id)
            
            # Vérifier le solde
            if sender.craftycoin_balance < montant:
                embed = format_error_embed(
                    "Solde insuffisant",
                    f"Vous n'avez que **{format_coins(sender.craftycoin_balance)}**"
                )
                await interaction.followup.send(embed=embed)
                return
            
            # Effectuer le transfert
            sender.craftycoin_balance -= montant
            recipient.craftycoin_balance += montant
            
            # Enregistrer les transactions
            add_transaction(
                session, sender.id, -montant, "transfer",
                f"Transfert à {destinataire.name}"
            )
            add_transaction(
                session, recipient.id, montant, "transfer",
                f"Transfert de {interaction.user.name}"
            )
            
            # Notification
            embed = discord.Embed(
                title="✅ Transfert effectué",
                color=discord.Color.green()
            )
            embed.add_field(name="Destinataire", value=destinataire.mention, inline=True)
            embed.add_field(name="Montant", value=f"**-{format_coins(montant)}**", inline=True)
            embed.add_field(name="Nouveau solde", value=f"**{format_coins(sender.craftycoin_balance)}**", inline=False)
            
            await interaction.followup.send(embed=embed)
            logger.info(f"Transfert: {interaction.user.name} → {destinataire.name}: {montant} CC")


async def setup(bot):
    """Fonction requise par discord.py pour charger le cog."""
    await bot.add_cog(EconomyCog(bot))
    logger.info("✅ EconomyCog chargé")
