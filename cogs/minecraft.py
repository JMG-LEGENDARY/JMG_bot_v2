"""Cog Minecraft - Événements et suivi du serveur Minecraft"""

import asyncio
import discord
from discord.ext import commands, tasks
import logging
from datetime import datetime

from discord import app_commands
from db import db, get_or_create_user, GameSession, User, add_transaction
from utils import get_logger, calculate_playtime_earning, format_coins
from utils.logger import relay_log
from utils.minecraft_monitor import MinecraftLogMonitor
from config import config
import crafty_api
from collections import defaultdict
from time import time

logger = get_logger(__name__)


class MinecraftCog(commands.Cog):
    """Gestion des événements Minecraft"""
    
    def __init__(self, bot):
        self.bot = bot
        self.monitor: MinecraftLogMonitor = None
        self.monitor_task = None
        # Rate limiting: {username: [timestamp1, timestamp2, ...]} pour tracker les tentatives /login
        self.login_attempts = defaultdict(list)
        # Constantes de rate limiting
        self.MAX_LOGIN_ATTEMPTS = 5
        self.LOGIN_ATTEMPT_WINDOW = 300  # 5 minutes en secondes

    @commands.Cog.listener()
    async def on_ready(self):
        """Initialise le suivi des logs au démarrage"""
        logger.info("🎮 MinecraftCog prêt")
        
        # Démarrer le monitoring si configuré
        if config.MINECRAFT_LOG_PATH:
            await self.start_monitoring(config.MINECRAFT_LOG_PATH)

    async def start_monitoring(self, log_path: str):
        """Démarre le monitoring des logs Minecraft"""
        if self.monitor is not None:
            logger.warning("Monitoring déjà actif")
            return
        
        self.monitor = MinecraftLogMonitor(log_path)
        self.monitor.register_callback("player_join", self._handle_player_join)
        self.monitor.register_callback("player_leave", self._handle_player_leave)
        self.monitor.register_callback("player_login_command", self._handle_player_login_command)
        
        logger.info(f"📍 Monitoring des logs: {log_path}")
        self.monitor_task = asyncio.create_task(self.monitor.start())
    
    def _check_login_rate_limit(self, username: str) -> tuple[bool, int]:
        """
        Vérifie si le joueur a dépassé le rate limit de /login.
        Retourne (is_allowed, attempts_left)
        """
        current_time = time()
        # Nettoyer les tentatives expirées
        self.login_attempts[username] = [
            ts for ts in self.login_attempts[username]
            if current_time - ts < self.LOGIN_ATTEMPT_WINDOW
        ]
        
        attempts_count = len(self.login_attempts[username])
        
        if attempts_count >= self.MAX_LOGIN_ATTEMPTS:
            return False, 0
        
        # Enregistrer la nouvelle tentative
        self.login_attempts[username].append(current_time)
        return True, self.MAX_LOGIN_ATTEMPTS - attempts_count - 1
    
    def _reset_player_session(self, username: str):
        """Réinitialise la session d'un joueur (réinitialise l'authentification)"""
        with db.get_session() as session:
            user = session.query(User).filter(User.minecraft_username == username).first()
            if user:
                user.is_authenticated = False
                session.commit()
        
        # Nettoyer les tentatives de login précédentes
        if username in self.login_attempts:
            del self.login_attempts[username]

    async def _handle_player_join(self, username: str):
        """Gère l'événement d'un joueur qui rejoint"""
        logger.info(f"🟢 {username} a rejoint le serveur")
        print(f"🟢 {username} a rejoint le serveur")
        
        try:
            # Réinitialiser la session du joueur (is_authenticated = False)
            self._reset_player_session(username)
            
            with db.get_session() as session:
                # Vérifier si le joueur est enregistré
                print(f"🔍 Vérification de l'enregistrement de {username}")
                user = session.query(User).filter(User.minecraft_username == username).first()
                
                if not user:
                    print(f"⚠️ {username} n'est pas enregistré, kick automatique")
                    # Joueur non enregistré → kick immédiatement
                    logger.warning(f"⚠️ {username} n'est pas enregistré, kick automatique")
                    kick_cmd = f'/kick {username} [Sécurité] Tu n\'es pas whitelisté.'
                    await crafty_api.envoyer_commande(kick_cmd)
                    try:
                        await relay_log(
                            self.bot,
                            "Minecraft - Kick",
                            f"❌ {username} n'était pas enregistré, kick automatique",
                            discord.Color.orange()
                        )
                    except Exception:
                        pass
                    return
                
                # Joueur enregistré → créer une session de jeu
                game_session = GameSession(
                    user_id=user.id,
                    minecraft_username=username,
                    login_time=datetime.utcnow()
                )
                session.add(game_session)
                session.commit()
                
                # Envoyer le /tellraw pour demander le mot de passe
                tellraw_cmd = f'/tellraw {username} {{"text":"[Sécurité] Connecte-toi avec : /login <ton_mot_de_passe>","color":"red"}}'
                await crafty_api.envoyer_commande(tellraw_cmd)
                
                # Appliquer un effet de freeze (blindness + slowness)
                freeze_effects = [
                    f'/effect give {username} minecraft:blindness 999999 0 true',
                    f'/effect give {username} minecraft:darkness 999999 0 true',
                    
                    # Paralysie totale (Déplacement + Minage + Attaque)
                    f'/effect give {username} minecraft:slowness 999999 255 true',
                    f'/effect give {username} minecraft:mining_fatigue 999999 255 true',
                    f'/effect give {username} minecraft:weakness 999999 255 true',
                    
                    # Invincibilité + Invisibilité (Les monstres ne le calculent plus et ne peuvent pas le tuer)
                    f'/effect give {username} minecraft:resistance 999999 255 true',
                    f'/effect give {username} minecraft:invisibility 999999 0 true'
                ]
                for effect_cmd in freeze_effects:
                    await crafty_api.envoyer_commande(effect_cmd)
                await crafty_api.envoyer_commande(f'/gamemode adventure {username}')    
                
                logger.info(f"🔒 {username} est freezé en attente d'authentification")
                try:
                    await relay_log(
                        self.bot,
                        "Minecraft - Authentification",
                        f"🔒 {username} attend l'authentification",
                        discord.Color.yellow()
                    )
                except Exception:
                    pass
        
        except Exception as e:
            logger.error(f"Erreur dans _handle_player_join: {e}", exc_info=True)

    async def _handle_player_leave(self, username: str):
        """Gère l'événement d'un joueur qui quitte"""
        logger.info(f"🔴 {username} a quitté le serveur")
        
        try:
            with db.get_session() as session:
                # Mettre à jour la session de jeu (logout)
                last_session = (
                    session.query(GameSession)
                    .filter(GameSession.minecraft_username == username)
                    .filter(GameSession.logout_time.is_(None))
                    .order_by(GameSession.id.desc())
                    .first()
                )
                
                if last_session:
                    last_session.logout_time = datetime.utcnow()
                    playtime_seconds = (last_session.logout_time - last_session.login_time).total_seconds()
                    playtime_minutes = playtime_seconds / 60
                    last_session.total_playtime_minutes = playtime_minutes
                    
                    # Créditer les gains au joueur
                    user = session.query(User).filter(User.minecraft_username == username).first()
                    if user:
                        earning = calculate_playtime_earning(
                            playtime_minutes,
                            multiplier=user.playtime_multiplier,
                            rate=config.VOICE_EARNING_RATE
                        )
                        
                        if earning > 0:
                            add_transaction(
                                session, user.id, earning, "playtime",
                                f"Temps de jeu: {playtime_minutes:.0f}m",
                                base_amount=playtime_minutes * config.VOICE_EARNING_RATE,
                                multiplier=user.playtime_multiplier
                            )
                        
                        user.total_playtime_minutes += playtime_minutes
                    
                    session.commit()
                
                # Envoyer un message d'au revoir
                channel_id = config.CHANNELS.get("gestion_mc")
                if channel_id:
                    try:
                        channel = self.bot.get_channel(channel_id)
                        if channel:
                            welcome_cog = self.bot.get_cog("WelcomeCog")
                            if welcome_cog:
                                session_time = playtime_minutes if last_session else 0
                                await welcome_cog.send_goodbye_message(channel, username)
                                await welcome_cog.log_player_stats(username, session_time, "leave")
                    except Exception as e:
                        logger.error(f"Erreur lors de l'envoi du message d'au revoir: {e}")

            try:
                await relay_log(
                    self.bot,
                    "Minecraft - Déconnexion",
                    f"🔴 {username} a quitté le serveur",
                    discord.Color.red()
                )
            except Exception:
                pass
        
        except Exception as e:
            logger.error(f"Erreur dans _handle_player_leave: {e}", exc_info=True)

    async def _handle_player_login_command(self, username: str, password: str):
        """Gère la commande /login d'un joueur"""
        logger.info(f"🔐 {username} a tenté la commande /login")
        
        try:
            from utils.helpers import verify_password
            
            # Vérifier le rate limiting
            is_allowed, attempts_left = self._check_login_rate_limit(username)
            
            if not is_allowed:
                logger.warning(f"⚠️ {username} a dépassé le rate limit pour /login")
                tellraw_cmd = f'/tellraw {username} {{"text":"[Sécurité] Trop de tentatives. Réessaie dans 5 minutes.","color":"dark_red"}}'
                await crafty_api.envoyer_commande(tellraw_cmd)
                
                try:
                    await relay_log(
                        self.bot,
                        "Minecraft - Rate Limit",
                        f"⚠️ {username} a dépassé le rate limit /login",
                        discord.Color.red()
                    )
                except Exception:
                    pass
                return
            
            with db.get_session() as session:
                user = session.query(User).filter(User.minecraft_username == username).first()
                
                if not user or not user.password_hash:
                    logger.warning(f"⚠️ {username} a tenté /login mais n'a pas de hash")
                    tellraw_cmd = f'/tellraw {username} {{"text":"[Sécurité] Erreur d\'authentification","color":"red"}}'
                    await crafty_api.envoyer_commande(tellraw_cmd)
                    return
                
                # Vérifier le mot de passe
                if verify_password(password, user.password_hash):
                    # Mot de passe correct → authentification réussie
                    user.is_authenticated = True
                    session.commit()
                    
                    logger.info(f"✅ {username} authentifié avec succès")
                    
                    # Nettoyer les tentatives de login
                    if username in self.login_attempts:
                        del self.login_attempts[username]
                    
                    # Enlever les effets de freeze
                    effect_clear_cmd = f'/effect clear {username}'
                    await crafty_api.envoyer_commande(effect_clear_cmd)
                    await crafty_api.envoyer_commande(f'/gamemode survival {username}')
                    
                    # Message de succès
                    tellraw_cmd = f'/tellraw {username} {{"text":"[Sécurité] Authentification réussie ! Tu peux jouer.","color":"green"}}'
                    await crafty_api.envoyer_commande(tellraw_cmd)
                    
                    try:
                        await relay_log(
                            self.bot,
                            "Minecraft - Authentification Réussie",
                            f"✅ {username} s'est authentifié avec succès",
                            discord.Color.green()
                        )
                    except Exception:
                        pass
                else:
                    # Mot de passe incorrect
                    logger.warning(f"⚠️ {username} a entré un mauvais mot de passe (tentatives restantes: {attempts_left})")
                    msg = f"Mot de passe incorrect" if attempts_left > 0 else "Trop de tentatives"
                    tellraw_cmd = f'/tellraw {username} {{"text":"[Sécurité] {msg}","color":"red"}}'
                    await crafty_api.envoyer_commande(tellraw_cmd)
                    
                    try:
                        await relay_log(
                            self.bot,
                            "Minecraft - Authentification Échouée",
                            f"❌ {username} a entré un mauvais mot de passe ({attempts_left} tentatives restantes)",
                            discord.Color.orange()
                        )
                    except Exception:
                        pass
        
        except Exception as e:
            logger.error(f"Erreur dans _handle_player_login_command: {e}", exc_info=True)

    @app_commands.command(name="playtime", description="Affiche votre temps de jeu Minecraft")
    @app_commands.checks.cooldown(1, 10, key=lambda i: i.user.id)
    async def playtime(self, interaction: discord.Interaction):
        """Affiche le temps de jeu total d'un utilisateur"""
        await interaction.response.defer(ephemeral=True)
        
        with db.get_session() as session:
            user = session.query(User).filter(User.discord_id == interaction.user.id).first()
            if not user:
                embed = discord.Embed(
                    title="❌ Utilisateur non trouvé",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
                return
            
            # Calculer le temps total
            total_seconds = user.total_playtime_minutes * 60
            hours = int(total_seconds // 3600)
            minutes = int((total_seconds % 3600) // 60)
            
            earning = user.total_playtime_minutes * config.VOICE_EARNING_RATE * user.playtime_multiplier
            
            embed = discord.Embed(
                title="🎮 Temps de jeu Minecraft",
                color=discord.Color.green()
            )
            embed.add_field(name="Temps total", value=f"**{hours}h {minutes}m**", inline=True)
            embed.add_field(name="Multiplicateur", value=f"**{user.playtime_multiplier}x**", inline=True)
            embed.add_field(
                name="Gains totaux",
                value=f"**{format_coins(earning)}**",
                inline=False
            )
            
            await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot):
    """Fonction requise par discord.py pour charger le cog."""
    await bot.add_cog(MinecraftCog(bot))
    logger.info("✅ MinecraftCog chargé")
