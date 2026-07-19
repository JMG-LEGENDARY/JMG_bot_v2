"""Cog Events - Gestion des événements Discord (messages, vocal, etc.)"""

import re

import discord
from discord.ext import commands
from datetime import datetime, timedelta

from db import db, get_or_create_user, add_transaction, User
from utils import (
    detect_copy_paste, is_afk_in_voice, calculate_message_earning,
    hash_message, get_logger
)
from utils.logger import relay_log
from core.constants import EMOJI, ACTIVITY_MULTIPLIERS, TIMEOUTS
from core.decorators import log_command
from config import config

logger = get_logger(__name__)


class EventsCog(commands.Cog):
    """Gestion des événements Discord"""
    
    def __init__(self, bot):
        self.bot = bot
        self.user_message_history = {}  # Suivi des messages pour copier-coller
        self.voice_activity = {}  # Suivi de l'activité vocale

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Gère les messages reçus"""
        # Ignorer les bots et les commandes
        logs_channel_id = config.CHANNELS.get("logs")
        mc_bot_id = config.MC_JOIN_ID
        print(f"Message reçu: {message.author} dans {message.channel}: {message.content}\n {message.author.id} - {mc_bot_id}")
        
        if message.author.bot and message.author.id != mc_bot_id:
            return
        if message.content.startswith('/'):
            return
        
        if logs_channel_id and message.channel.id == logs_channel_id:
            if message.author.id != mc_bot_id:
                return

            # 1. Définition des patterns de recherche (Regex)
            match_join = re.search(r"(\w+)\s+joined", message.content)
            match_leave = re.search(r"(\w+)\s+(?:left|timed out!)", message.content)
            
            # Capturera "Pseudo [...] command: /login mon_mot_de_passe" (avec ou sans le slash)
            match_login = re.search(r"(\w+)\s+executed\s+command\s+`login\s+([^`]+)`", message.content)


            
            minecraft_cog = self.bot.get_cog("MinecraftCog")

            # 2. Cas A : Le joueur tente de se connecter / taper son mot de passe
            if match_login:
                username = match_login.group(1)
                password = match_login.group(2)
                print(f"Tentative de login détectée pour {username}")
                
                if minecraft_cog:
                    # On lance la fonction qui va Whitelister / Geler le joueur en attente du MDP
                    self.bot.loop.create_task(minecraft_cog._handle_player_login_command(username, password))
                else:
                    logger.error("Le Cog 'MinecraftCog' n'a pas pu être trouvé dans events.py")
                return

            # 3. Cas B : Le joueur vient de se connecter au serveur (Arrivée brute)
            if match_join:
                pseudo = match_join.group(1)
                print(f"Connexion détectée ! Pseudo : {pseudo}")
                
                if minecraft_cog:
                    # On lance la fonction qui va Whitelister / Geler le joueur en attente du MDP
                    self.bot.loop.create_task(minecraft_cog._handle_player_join(pseudo))
                else:
                    logger.error("Le Cog 'MinecraftCog' n'a pas pu être trouvé dans events.py")
                return

            # 4. Cas C : Le joueur quitte (Optionnel : tu pourras y ajouter ton _handle_player_leave plus tard)
            if match_leave:
                pseudo = match_leave.group(1)
                print(f"Déconnexion détectée ! Pseudo : {pseudo}")
                return
                    
                
            elif match_leave:
                pseudo = match_leave.group(1)
                print(f"Déconnexion détectée ! Pseudo : {pseudo}")
        
        # Ignorer les messages trop courts
        if len(message.content) < 3:
            return
        
        with db.get_session() as session:
            user = get_or_create_user(session, message.author.id)
            
            # --- DÉTECTION SPAM ---
            # Vérifier le copier-coller
            user_id = message.author.id
            if user_id not in self.user_message_history:
                self.user_message_history[user_id] = []
            
            is_copypaste, similarity = detect_copy_paste(
                message.content,
                self.user_message_history[user_id],
                threshold=config.ANTI_COPYPASTE_THRESHOLD
            )
            
            # Garder l'historique des 10 derniers messages
            msg_hash = hash_message(message.content)
            self.user_message_history[user_id].append(message.content)
            if len(self.user_message_history[user_id]) > 10:
                self.user_message_history[user_id].pop(0)
            
            if is_copypaste:
                logger.warning(f"🚨 Copier-coller détecté: {message.author} (similitude: {similarity:.1%})")
                # Penaliser ou ignorer
                return
            
            # --- DÉTECTION SPAM TEMPOREL ---
            current_time = datetime.utcnow()
            user.last_activity = current_time
            
            # Vérifier le spam prevention
            if hasattr(user, 'last_message_time'):
                time_diff = (current_time - user.last_message_time).total_seconds()
                if time_diff < config.SPAM_PREVENTION_TIME:
                    return
            
            # --- CALCUL DES GAINS ---
            # Caractères du message
            char_count = len(message.content)
            earning = calculate_message_earning(
                char_count,
                multiplier=user.message_multiplier,
                rate=config.MESSAGE_CHARACTER_RATE
            )
            
            # Mettre à jour les stats
            user.total_messages += 1
            user.total_characters += char_count
            
            # Transactor
            add_transaction(
                session,
                user.id,
                earning,
                "message",
                f"Message de {char_count} caractères",
                base_amount=char_count * config.MESSAGE_CHARACTER_RATE,
                multiplier=user.message_multiplier
            )
            
            user.last_message_time = current_time
            session.commit()
            
            logger.debug(f"Message: {message.author} → +{earning:.1f} CC ({char_count} chars)")
            """try:
                await relay_log(
                    self.bot,
                    "Message Discord",
                    f"**{message.author}** dans {message.channel.mention}\n{message.content}",
                    discord.Color.blurple()
                )
            except Exception:
                pass"""

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        if before.author.bot:
            return

        logs_channel_id = config.CHANNELS.get("logs")
        if logs_channel_id and before.channel.id == logs_channel_id:
            return

        if before.content == after.content and before.embeds == after.embeds:
            return

        description = f"**{before.author}** a modifié un message dans {before.channel.mention}\n"
        if before.content != after.content:
            description += f"**Avant:** {before.content or '*vide*'}\n**Après:** {after.content or '*vide*'}"
        if before.embeds != after.embeds:
            if before.content != after.content:
                description += "\n"
            description += "**Embed modifié ou ajoutée.**"

        try:
            await relay_log(
                self.bot,
                "Message édité",
                description,
                discord.Color.orange()
            )
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        if message.author.bot:
            return

        logs_channel_id = config.CHANNELS.get("logs")
        if logs_channel_id and message.channel.id == logs_channel_id:
            return

        try:
            await relay_log(
                self.bot,
                "Message supprimé",
                f"**{message.author}** a supprimé un message dans {message.channel.mention}\n{message.content or '*contenu non disponible*'}",
                discord.Color.red()
            )
        except Exception:
            pass

    @commands.Cog.listener()
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """Gère les changements d'état vocal"""
        
        user_id = member.id
        
        # --- REJOINDRE LE VOCAL ---
        if before.channel is None and after.channel is not None:
            logger.info(f"🎤 {member} a rejoint le vocal: {after.channel.name}")
            self.voice_activity[user_id] = {
                "joined_at": datetime.utcnow(),
                "last_activity": datetime.utcnow(),
                "channel": after.channel.name,
            }
        
        # --- QUITTER LE VOCAL ---
        elif before.channel is not None and after.channel is None:
            if user_id in self.voice_activity:
                voice_data = self.voice_activity[user_id]
                playtime_seconds = (datetime.utcnow() - voice_data["joined_at"]).total_seconds()
                
                logger.info(f"🎤 {member} a quitté le vocal après {playtime_seconds:.0f}s")
                
                with db.get_session() as session:
                    user = get_or_create_user(session, user_id)
                    
                    # Vérifier si AFK (pas d'activité depuis TIMEOUTS["afk_detection"] secondes)
                    is_afk = is_afk_in_voice(
                        voice_data["last_activity"],
                        timeout_minutes=TIMEOUTS["afk_detection"] / 60
                    )
                    
                    if is_afk:
                        # 10% du gain normal si AFK
                        multiplier = ACTIVITY_MULTIPLIERS["minecraft_afk_factor"]
                        logger.warning(f"⚠️ {member} était AFK en vocal")
                    else:
                        multiplier = 1.0
                    
                    # Calculer les gains
                    from utils import calculate_playtime_earning
                    earning = calculate_playtime_earning(
                        playtime_seconds / 60,  # en minutes
                        multiplier=user.playtime_multiplier * multiplier,
                        rate=config.VOICE_EARNING_RATE
                    )
                    
                    # Mettre à jour les stats
                    user.total_playtime_minutes += playtime_seconds / 60
                    
                    if earning > 0:
                        add_transaction(
                            session,
                            user.id,
                            earning,
                            "voice",
                            f"Temps vocal: {playtime_seconds / 60:.0f}m" + (" (AFK)" if is_afk else ""),
                            base_amount=playtime_seconds / 60 * config.VOICE_EARNING_RATE,
                            multiplier=user.playtime_multiplier * multiplier
                        )
                    
                    session.commit()
                    logger.debug(f"Voice earning: {member} → +{earning:.1f} CC")
                
                del self.voice_activity[user_id]
        
        # --- CHANGEMENTS D'ACTIVITÉ VOCALE (mute, deafen, stream) ---
        elif before.channel is not None and after.channel is not None:
            # Même channel, vérifier les changements
            if user_id in self.voice_activity:
                # Mettre à jour last_activity s'il y a un changement (ex: deafen)
                if before.self_mute != after.self_mute or before.self_deafened != after.self_deafened:
                    self.voice_activity[user_id]["last_activity"] = datetime.utcnow()
                    logger.debug(f"Activité vocale mise à jour: {member}")


async def setup(bot):
    """Fonction requise par discord.py pour charger le cog."""
    await bot.add_cog(EventsCog(bot))
    logger.info("✅ EventsCog chargé")
