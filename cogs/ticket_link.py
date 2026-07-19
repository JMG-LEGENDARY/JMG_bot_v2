"""
Ticket System Cog - Gestion autonome des tickets (Aide & Liaison Minecraft)
"""

import discord
from discord import app_commands
from discord.ext import commands
import asyncio
from datetime import datetime
import secrets
from typing import cast, Union

from db.database import db, get_or_create_user, authenticate_user
from db.models import User
from utils.logger import get_logger, relay_log
from utils.formatters import create_embed
from utils.helpers import hash_password, generate_temporary_password
from config import config
import crafty_api

log = get_logger("tickets")

# Configuration des IDs (Conversion forcée en int pour parer les formats strings de la config)
ticket_channel_config = config.CHANNELS.get("ticket_channel")
try:
    TICKET_CHANNEL_ID = int(ticket_channel_config) if ticket_channel_config is not None else None
except (TypeError, ValueError):
    TICKET_CHANNEL_ID = None
    log.error("❌ L'ID 'ticket_channel' dans config est manquant ou invalide !")

CATEGORY_TICKETS_ID = None  # 💡 Mets l'ID d'une catégorie ici si tu veux les ranger

# Rôles Staff autorisés (Conversion forcée en int également)
STAFF_ROLES = []
for role_key in ["manager_minecraft", "manager_discord", "manager_crafty"]:
    role_val = config.ROLES.get(role_key)
    if role_val:
        try:
            STAFF_ROLES.append(int(role_val))
        except ValueError:
            log.error(f"❌ L'ID du rôle {role_key} dans la config n'est pas un entier valide : {role_val}")


class TicketButtonsView(discord.ui.View):
    """Vue persistante contenant les boutons de création de ticket"""
    def __init__(self):
        # timeout=None rend la vue persistante (survit aux reboots du bot)
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Demander de l'aide", 
        style=discord.ButtonStyle.secondary, 
        custom_id="ticket_help",
        emoji="❓"
    )
    async def ticket_help(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await self.create_ticket_channel(interaction, ticket_type="aide")

    @discord.ui.button(
        label="Se connecter à Minecraft", 
        style=discord.ButtonStyle.success, 
        custom_id="ticket_minecraft",
        emoji="🎮"
    )
    async def ticket_minecraft(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        await self.create_ticket_channel(interaction, ticket_type="minecraft")

    async def create_ticket_channel(self, interaction: discord.Interaction, ticket_type: str):
        guild = interaction.guild
        user = interaction.user
        if guild is None:
            await interaction.followup.send(
                "❌ Impossible de créer le ticket : ce salon n'est pas associé à un serveur.",
                ephemeral=True
            )
            return

        # Base des permissions : Personne ne voit le salon sauf...
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
        }
        
        # ...les rôles de Staff configurés
        for role_id in STAFF_ROLES:
            role = guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)

        # Récupération de la catégorie optionnelle
        category = cast(discord.CategoryChannel | None, guild.get_channel(CATEGORY_TICKETS_ID)) if CATEGORY_TICKETS_ID else None
        
        # Création du salon textuel personnalisé
        channel_name = f"{ticket_type}-{user.name}"
        ticket_channel = await guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites,
            reason=f"Ticket {ticket_type} créé par {user.name}"
        )
        
        await interaction.followup.send(f"✅ Ton ticket a été créé ici : {ticket_channel.mention}", ephemeral=True)
        try:
            await relay_log(
                interaction.client,
                "Ticket Discord",
                f"🎫 {user} a créé le ticket `{ticket_type}` dans {ticket_channel.mention}",
                discord.Color.dark_grey()
            )
        except Exception:
            pass
        
        # Redirection du comportement selon le bouton cliqué
        if ticket_type == "aide":
            await self.handle_help_ticket(ticket_channel, user)
        elif ticket_type == "minecraft":
            await self.handle_minecraft_ticket(ticket_channel, user, interaction.client)

    async def handle_help_ticket(
        self,
        channel: discord.TextChannel,
        user: Union[discord.User, discord.Member]
    ):
        embed = create_embed(
            title="❓ Ticket d'Assistance",
            description=f"Bonjour {user.mention},\n\nUn membre de l'équipe de management va t'installer et répondre à ta demande sous peu. Laisse un message décrivant ton problème.",
            color=discord.Color.blue()
        )
        await channel.send(embed=embed)

    async def handle_minecraft_ticket(
        self,
        channel: discord.TextChannel,
        user: Union[discord.User, discord.Member],
        bot: discord.Client
    ):
        embed = create_embed(
            title="🔗 Liaison de compte Minecraft",
            description=(
                f"Bienvenue dans ton ticket {user.mention} !\n\n"
                "Pour rejoindre notre serveur et lier ton compte Discord à la boutique, "
                "veuillez répondre ci-dessous avec votre **pseudo Minecraft exact uniquement**.\n\n"
                "⚠️ *Pas d'espace, pas d'emojis ni de caractères spéciaux.*"
            ),
            color=discord.Color.green()
        )
        await channel.send(embed=embed)
        guild = channel.guild
        if guild is None:
            await channel.send(
                "❌ Impossible de récupérer les informations du serveur. Réessaie plus tard."
            )
            return

        def check(message):
            return message.author.id == user.id and message.channel.id == channel.id

        try:
            # Attente de la réponse du joueur (Timeout 5 minutes)
            msg = await bot.wait_for("message", check=check, timeout=300.0)
            minecraft_pseudo = msg.content.strip()

            # Sécurité syntaxe pseudo Minecraft
            if len(minecraft_pseudo) > 16 or " " in minecraft_pseudo:
                embed_error = create_embed(
                    title="❌ Pseudo invalide",
                    description="Un pseudo Minecraft valide fait 16 caractères maximum et ne contient pas d'espace. Ferme ce ticket et réessaie.",
                    color=discord.Color.red()
                )
                await channel.send(embed=embed_error)
                return

            # Synchronisation ORM Base de données
            with db.get_session() as session:
                # 🔍 1. Vérification si le pseudo est déjà utilisé par un AUTRE utilisateur
                existing_user = session.query(User).filter(
                    User.minecraft_username == minecraft_pseudo
                ).first()

                if existing_user and existing_user.discord_id != user.id:
                    embed_taken = create_embed(
                        title="❌ Pseudo déjà utilisé",
                        description=(
                            f"Le pseudo Minecraft **{minecraft_pseudo}** est déjà lié à un autre compte Discord.\n\n"
                            "Si tu penses qu'il s'agit d'une erreur ou de ton ancien compte, contacte un administrateur."
                        ),
                        color=discord.Color.red()
                    )
                    await channel.send(embed=embed_taken)
                    return

                # 🔍 2. Recherche ou création du profil de l'utilisateur actuel
                user_data = get_or_create_user(session, user.id)
                user_data.minecraft_username = minecraft_pseudo  # type: ignore[assignment]
                user_data.is_authenticated = False  # type: ignore[assignment]
                user_data.is_whitelisted = False  # type: ignore[assignment]

                # Générer un mot de passe temporaire de première connexion
                temporary_password = generate_temporary_password(10)
                user_data.password_hash = hash_password(temporary_password)  # type: ignore[assignment]
                session.commit()
                user_record_id = user_data.id

            # 🎮 3. Bot-managed whitelist: juste enregistrement en DB, pas d'ajout automatique
            whitelist_status = "Ton pseudo est enregistré en base de données. Tu devras te connecter avec ton mot de passe une fois en jeu."

            # Envoi du mot de passe temporaire en DM
            dm_message = (
                f"Bonjour {user.name},\n\n"
                f"Ton compte Discord est lié au pseudo Minecraft **{minecraft_pseudo}**.\n"
                f"Ton mot de passe temporaire est : **{temporary_password}**\n\n"
                "Quand tu rejoins le serveur, tu recevras un message te demandant de te connecter avec:\n"
                "`/login <ton_mot_de_passe>`\n\n"
                "Tu pourras ensuite personnaliser ton mot de passe avec `/minecraft set_password <nouveau_mot_de_passe>`."
            )

            try:
                await user.send(dm_message)
            except Exception as dm_err:
                log.warning(f"Impossible d'envoyer le DM à {user}: {dm_err}")
                await channel.send(
                    "⚠️ Je n'ai pas pu t'envoyer le mot de passe en DM. "
                    "Assure-toi que tes messages privés sont ouverts."
                )

            # Ajouter le rôle de membre serveur si configuré
            membres_role_id = config.ROLES.get("membres_serveur")
            if membres_role_id:
                role = guild.get_role(int(membres_role_id))
                member = guild.get_member(user.id)
                if role and member:
                    try:
                        await member.add_roles(role, reason="Liaison Minecraft réussie")
                        await channel.send(f"✅ Rôle {role.name} attribué avec succès.")
                    except Exception as role_err:
                        log.warning(f"Impossible d'ajouter le rôle Membres Serveur à {user}: {role_err}")
                        await channel.send(
                            "⚠️ Impossible d'ajouter automatiquement le rôle Membres Serveur. "
                            "Demande à un administrateur de vérifier le rôle."
                        )

            embed_success = create_embed(
                title="✅ Whitelist & Liaison OK",
                description=(
                    f"Ton compte Discord est lié au joueur : **{minecraft_pseudo}**.\n\n"
                    f"{whitelist_status}\n\n"
                    "Un mot de passe temporaire t'a été envoyé en DM. "
                    "Utilise `/minecraft login <mot_de_passe>` pour te connecter."
                ),
                color=discord.Color.green()
            )
            await channel.send(embed=embed_success)
            try:
                await relay_log(
                    bot,
                    "Liaison Minecraft",
                    f"🔗 {user} a lié son compte à **{minecraft_pseudo}**",
                    discord.Color.green()
                )
            except Exception:
                pass
            log.info(f"🔗 Liaison réussie via bouton : {user.name} ↔ {minecraft_pseudo}")

        except asyncio.TimeoutError:
            await channel.send("⏳ Temps écoulé ! Le processus s'est arrêté. Tu peux fermer ce salon.")
        except Exception as e:
            log.error(f"Erreur lors de la liaison automatique : {e}", exc_info=True)


class TicketsCog(commands.Cog):
    """Cog principal pour gérer l'initialisation du système de tickets"""
    minecraft_group = app_commands.Group(
        name="minecraft",
        description="Commandes de liaison et d'authentification Minecraft"
    )

    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        # Enregistre la vue pour qu'elle intercepte les clics même après un reboot du bot
        self.bot.add_view(TicketButtonsView())
        log.info("🔒 Vue persistante des tickets enregistrée")

    @minecraft_group.command(name="set_password", description="Définit ton mot de passe Minecraft")
    @app_commands.describe(nouveau_mot_de_passe="Ton nouveau mot de passe sécurisé")
    async def set_password(self, interaction: discord.Interaction, nouveau_mot_de_passe: str):
        await interaction.response.defer(ephemeral=True)

        if len(nouveau_mot_de_passe) < 8:
            await interaction.followup.send(
                "❌ Le mot de passe doit comporter au moins 8 caractères.",
                ephemeral=True
            )
            return

        with db.get_session() as session:
            user = session.query(User).filter(User.discord_id == interaction.user.id).first()
            if not user or not user.minecraft_username:
                await interaction.followup.send(
                    "❌ Tu dois d'abord lier ton compte Minecraft via le ticket de connexion.",
                    ephemeral=True
                )
                return

            user.password_hash = hash_password(nouveau_mot_de_passe)
            user.is_authenticated = False
            session.commit()

        await interaction.followup.send(
            "✅ Ton mot de passe a été mis à jour. "
            "Utilise maintenant `/minecraft login <mot_de_passe>` pour t'authentifier.",
            ephemeral=True
        )

    @minecraft_group.command(name="login", description="Se connecter avec ton mot de passe Minecraft")
    @app_commands.describe(mot_de_passe="Ton mot de passe Minecraft")
    async def login(self, interaction: discord.Interaction, mot_de_passe: str):
        await interaction.response.defer(ephemeral=True)

        with db.get_session() as session:
            user = session.query(User).filter(User.discord_id == interaction.user.id).first()
            if not user or not user.minecraft_username:
                await interaction.followup.send(
                    "❌ Tu dois d'abord lier ton compte Minecraft via le ticket de connexion.",
                    ephemeral=True
                )
                return

            if not user.password_hash:
                await interaction.followup.send(
                    "❌ Aucun mot de passe n'a encore été défini. Utilise `/minecraft set_password <mot_de_passe>`.",
                    ephemeral=True
                )
                return

            authenticated = authenticate_user(session, interaction.user.id, mot_de_passe)
            if not authenticated:
                await interaction.followup.send(
                    "❌ Mot de passe incorrect. Vérifie et réessaie.",
                    ephemeral=True
                )
                return

        await interaction.followup.send(
            "✅ Authentification réussie ! Tu peux maintenant utiliser la boutique et réclamer tes achats.",
            ephemeral=True
        )

    @app_commands.command(name="setup-tickets", description="Déploie le panel de boutons de tickets (Admin only)")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_tickets(self, interaction: discord.Interaction):
        """Commande permettant d'injecter l'embed et les boutons dans le bon salon"""
        if not TICKET_CHANNEL_ID:
            await interaction.response.send_message(
                "❌ Impossible de déployer : l'ID du salon est mal configuré.", 
                ephemeral=True
            )
            return

        if interaction.guild is None:
            await interaction.response.send_message(
                "❌ Impossible de déployer : ce salon n'est pas associé à un serveur.",
                ephemeral=True
            )
            return

        target_channel = interaction.guild.get_channel(TICKET_CHANNEL_ID)
        if not target_channel or not isinstance(target_channel, discord.TextChannel):
            await interaction.response.send_message(
                f"❌ Le salon configuré (ID: {TICKET_CHANNEL_ID}) est introuvable ou non accessible.", 
                ephemeral=True
            )
            return

        embed = create_embed(
            title="🎫 Support & Connexion Serveur",
            description=(
                "Bienvenue sur l'interface d'accès de notre communauté !\n\n"
                "**❓ Demander de l'aide** : Ouvre un ticket d'assistance pour toute question ou problème.\n"
                "**🎮 Se connecter à Minecraft** : Lance le processus de Whitelist et lie ton compte pour utiliser la boutique Discord."
            ),
            color=discord.Color.purple()
        )
        
        # Envoi de l'interface avec les boutons dans le salon configuré
        await target_channel.send(embed=embed, view=TicketButtonsView())
        await interaction.response.send_message("✅ Panel de tickets déployé avec succès !", ephemeral=True)


async def setup(bot):
    await bot.add_cog(TicketsCog(bot))
    log.info("✅ TicketsCog chargé")