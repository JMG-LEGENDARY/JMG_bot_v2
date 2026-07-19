"""Décorateurs pour JMG Bot"""

import discord
from discord.ext import commands
from functools import wraps
from config import config
from utils.logger import get_logger, relay_log
import logging

logger = get_logger(__name__)


def log_command(func):
    """Décorateur pour logger les commandes"""
    @wraps(func)
    async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
        logger.info(f"Commande: {func.__name__} - User: {interaction.user} - Guild: {interaction.guild}")
        try:
            result = await func(self, interaction, *args, **kwargs)
            try:
                await relay_log(
                    self.bot,
                    "Commande Discord",
                    f"Commande: {func.__name__}\nUtilisateur: {interaction.user}\nServeur: {interaction.guild}",
                    discord.Color.blue()
                )
            except Exception:
                pass
            return result
        except Exception as e:
            logger.error(f"Erreur dans {func.__name__}: {e}", exc_info=True)
            raise
    return wrapper


def require_role(role_name: str):
    """Décorateur pour vérifier si l'utilisateur a un rôle"""
    def decorator(func):
        @wraps(func)
        async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
            role_id = config.ROLES.get(role_name)
            if not role_id:
                logger.warning(f"Rôle {role_name} non trouvé dans config")
                await interaction.response.send_message("❌ Rôle non configuré", ephemeral=True)
                return
            
            member = interaction.user
            if not any(role.id == role_id for role in member.roles):
                logger.warning(f"Accès refusé: {member} n'a pas le rôle {role_name}")
                await interaction.response.send_message(
                    f"❌ Vous devez avoir le rôle pour accéder à cette commande",
                    ephemeral=True
                )
                return
            
            return await func(self, interaction, *args, **kwargs)
        return wrapper
    return decorator


def require_manager_minecraft():
    """Décorateur pour vérifier si c'est un Manager Minecraft"""
    def decorator(func):
        @wraps(func)
        async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
            role_id = config.ROLES.get("manager_minecraft")
            member = interaction.user
            
            if not any(role.id == role_id for role in member.roles):
                await interaction.response.send_message(
                    "❌ Seuls les Managers Minecraft peuvent utiliser cette commande",
                    ephemeral=True
                )
                return
            
            return await func(self, interaction, *args, **kwargs)
        return wrapper
    return decorator


def require_manager_discord():
    """Décorateur pour vérifier si c'est un Manager Discord"""
    def decorator(func):
        @wraps(func)
        async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
            role_id = config.ROLES.get("manager_discord")
            member = interaction.user
            
            if not any(role.id == role_id for role in member.roles):
                await interaction.response.send_message(
                    "❌ Seuls les Managers Discord peuvent utiliser cette commande",
                    ephemeral=True
                )
                return
            
            return await func(self, interaction, *args, **kwargs)
        return wrapper
    return decorator


def require_manager_crafty():
    """Décorateur pour vérifier si c'est un Manager Crafty"""
    def decorator(func):
        @wraps(func)
        async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
            role_id = config.ROLES.get("manager_crafty")
            member = interaction.user
            
            if not any(role.id == role_id for role in member.roles):
                await interaction.response.send_message(
                    "❌ Seuls les Managers Crafty peuvent utiliser cette commande",
                    ephemeral=True
                )
                return
            
            return await func(self, interaction, *args, **kwargs)
        return wrapper
    return decorator


def is_creator(func):
    """Décorateur pour vérifier si c'est un créateur"""
    @wraps(func)
    async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
        role_id = config.ROLES.get("createurs")
        member = interaction.user
        
        if not any(role.id == role_id for role in member.roles):
            await interaction.response.send_message(
                "❌ Seuls les créateurs peuvent utiliser cette commande",
                ephemeral=True
            )
            return
        
        return await func(self, interaction, *args, **kwargs)
    return wrapper


def defer_interaction(ephemeral: bool = False):
    """Décorateur pour différer automatiquement l'interaction"""
    def decorator(func):
        @wraps(func)
        async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
            await interaction.response.defer(ephemeral=ephemeral)
            return await func(self, interaction, *args, **kwargs)
        return wrapper
    return decorator


def handle_errors(func):
    """Décorateur pour gérer les erreurs gracieusement"""
    @wraps(func)
    async def wrapper(self, interaction: discord.Interaction, *args, **kwargs):
        try:
            return await func(self, interaction, *args, **kwargs)
        except discord.HTTPException as e:
            logger.error(f"Discord HTTP Error: {e}")
            try:
                await interaction.followup.send("❌ Erreur Discord", ephemeral=True)
            except:
                pass
        except Exception as e:
            logger.error(f"Erreur non gérée: {e}", exc_info=True)
            try:
                await interaction.followup.send(f"❌ Erreur: {str(e)[:100]}", ephemeral=True)
            except:
                pass
    return wrapper
