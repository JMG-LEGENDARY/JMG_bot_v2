"""
Monitoring Cog - Health checks and bot status monitoring
Commands: /bot-status (staff only), error webhooks
"""

import discord
from discord import app_commands
from discord.ext import commands, tasks
from datetime import datetime, time, timedelta, timezone
import psutil
import os
import re
import time

import asyncio
import threading
import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from requests import session
from sqlalchemy import func

import crafty_api
from db.database import db, get_leaderboard
from db.models import Transaction, User
from utils.logger import get_logger, relay_log
from utils.formatters import create_embed
from config import config
start_time = datetime.now(timezone.utc)
print(f"MonitoringCog loaded at {start_time.isoformat()}")

log = get_logger("monitoring")


class MonitoringCog(commands.Cog):
    """Bot monitoring and health checks"""

    def __init__(self, bot):
        self.bot = bot
        self.session = db  # 🛠️ CORRECTION 1 : db n'est pas "callable", on enlève les parenthèses
        self.start_time = start_time
        self.error_log = []
        self.max_errors = 100

        self.server_state = "unknown"
        self.online_players = set()
        self.player_metrics = {}
        self.server_metrics = {
            "joins": 0,
            "leaves": 0,
            "advancements": 0,
            "deaths": 0,
        }
        self.last_events = []
        self.server_start_time = None
        self.server_status_message_id = None
        self.server_last_update = None
        self.last_crafty_stats = {}

        print("[DEBUG WEB] Initialisation de FastAPI...")
        self.app = FastAPI(title="JMG_BOT v2 Internal API")
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],  # À restreindre en prod ex: ["http://localhost:3000"]
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

        # Liste des WebSockets clients connectés pour le Live Stream
        print("[DEBUG WEB] Enregistrement des routes de l'API...")
        self.connected_websockets = []
        self._setup_api_routes()

        print("[DEBUG WEB] Démarrage du thread Uvicorn...")
        # Lancement d'Uvicorn dans un thread séparé pour ne pas bloquer Discord
        self.api_thread = threading.Thread(target=self._run_api_server, daemon=True)
        self.api_thread.start()

    async def _get_loop_latency(self) -> float:
        """Mesure le retard d'exécution interne de la boucle Asyncio du bot (en ms)"""
        start_time = time.perf_counter()
        # On force la boucle à passer à la tâche suivante. 
        # Le temps d'attente révèle si la boucle est surchargée ou fluide.
        await asyncio.sleep(0) 
        end_time = time.perf_counter()
        latency_ms = (end_time - start_time) * 1000
        return round(latency_ms, 2)

    @tasks.loop(seconds=5)
    async def web_live_loop(self) -> None:
        """Tâche périodique rapide dédiée à l'actualisation du flux en temps réel"""
        await self.broadcast_live_update()

    @web_live_loop.before_loop
    async def before_web_live(self):
        await self.bot.wait_until_ready()

    def _run_api_server(self) -> None:
        """Démarre le serveur web sur le port 8000"""
        # Utilisation de uvicorn standard pour le thread dédié
        print("[DEBUG WEB] Le serveur Uvicorn va tenter d'écouter sur 0.0.0.0:8000")
        try:
            uvicorn.run(self.app, host="0.0.0.0", port=8000, log_level="info") # 'info' affichera les requêtes dans la console
        except Exception as e:
            print(f"[DEBUG WEB] CRASH d'Uvicorn : {e}")
        
        @self.app.get("/api/v1/status")
        def get_global_status():
            """Endpoint REST classique (Utile pour un premier chargement ou un check rapide)"""
            process = psutil.Process(os.getpid())
            uptime = datetime.now(timezone.utc) - self.start_time
            
            return {
                "bot": {
                    "status": "online",
                    "latency_ms": round(self.bot.latency * 1000, 1) if self.bot.latency else 0,
                    "uptime_seconds": int(uptime.total_seconds()),
                    "memory_mb": round(process.memory_info().rss / 1024 / 1024, 1),
                    "cpu_percent": round(process.cpu_percent(), 1),
                    "guilds_count": len(self.bot.guilds),
                    "recent_errors_count": len(self.error_log)
                },
                "minecraft_server": {
                    "state": self.server_state,
                    "online_players_count": len(self.online_players),
                    "online_players_list": list(sorted(self.online_players)),
                    "metrics": self.server_metrics,
                    "last_events": self.last_events[:6]
                },
                "crafty": self.last_crafty_stats
            }

        @self.app.websocket("/api/v1/live")
        async def websocket_endpoint(websocket: WebSocket):
            await websocket.accept()
            self.connected_websockets.append(websocket)
            print("[DEBUG WEB] Nouveau client WebSocket connecté ! Space-handshake réussi.")
            
            try:
                # On génère le dictionnaire de statut de manière propre
                process = psutil.Process(os.getpid())
                uptime = datetime.now(timezone.utc) - self.start_time
                
                initial_payload = {
                    "bot": {
                        "status": "online",
                        "latency_ms": round(self.bot.latency * 1000, 1) if self.bot.latency else 0,
                        "uptime_seconds": int(uptime.total_seconds()),
                        "memory_mb": round(process.memory_info().rss / 1024 / 1024, 1),
                        "cpu_percent": round(process.cpu_percent(), 1),
                        "guilds_count": len(self.bot.guilds),
                        "recent_errors_count": len(self.error_log)
                    },
                    "minecraft_server": {
                        "state": self.server_state,
                        "online_players_count": len(self.online_players),
                        "online_players_list": list(sorted(self.online_players)),
                        "metrics": self.server_metrics,
                        "last_events": self.last_events[:6]
                    },
                    "crafty": self.last_crafty_stats
                }
                
                # Envoi initial au format brut JSON
                await websocket.send_json(initial_payload)
                
                # Boucle de maintien d'écoute
                while True:
                    await websocket.receive_text()
                    
            except Exception as e:
                print(f"[DEBUG WEB] Erreur ou déconnexion sur le socket : {e}")
            finally:
                if websocket in self.connected_websockets:
                    self.connected_websockets.remove(websocket)
                print("[DEBUG WEB] Client WebSocket déconnecté.")

    async def broadcast_live_update(self) -> None:
        """Pousse les nouvelles métriques à tous les clients web connectés"""
        if not self.connected_websockets:
            return

        # Récupération des données fraîches via une fonction synchrone exécutée proprement
        # On extrait les données du bot de manière safe
        process = psutil.Process(os.getpid())
        uptime = datetime.now(timezone.utc) - self.start_time
        
        payload = {
            "bot": {
                "status": "online",
                "latency_ms": round(self.bot.latency * 1000, 1) if self.bot.latency else 0,
                "uptime_seconds": int(uptime.total_seconds()),
                "memory_mb": round(process.memory_info().rss / 1024 / 1024, 1),
                "cpu_percent": round(process.cpu_percent(), 1),
                "guilds_count": len(self.bot.guilds),
                "recent_errors_count": len(self.error_log)
            },
            "minecraft_server": {
                "state": self.server_state,
                "online_players_count": len(self.online_players),
                "online_players_list": list(sorted(self.online_players)),
                "metrics": self.server_metrics,
                "last_events": self.last_events[:6]
            },
            "crafty": self.last_crafty_stats
        }

        # Envoi asynchrone à tous les clients
        for ws in self.connected_websockets[:]:
            try:
                await ws.send_json(payload)
            except Exception:
                self.connected_websockets.remove(ws)

    @app_commands.command(name="bot-status", description="Affiche le statut système du bot")
    @app_commands.checks.has_permissions(manage_guild=True)
    async def status_bot(self, interaction: discord.Interaction):
        """
        Show bot status and health metrics (Staff only)
        
        Usage: /bot-status
        """
        
        # Calculate uptime
        uptime = datetime.now(timezone.utc) - self.start_time
        uptime_str = f"{uptime.days}d {uptime.seconds // 3600}h {(uptime.seconds // 60) % 60}m"
        
        with db.get_session() as session:
            user_count = session.query(User).count()
        
        # Get transaction stats (last 24h)
            yesterday = datetime.utcnow() - timedelta(days=1)
            txn_24h = session.query(Transaction).filter(
                Transaction.created_at >= yesterday
            ).count()
            
            total_coins = session.query(User).with_entities(
                func.sum(User.craftycoin_balance)
            ).scalar() or 0
        
        # Get resource usage
        process = psutil.Process(os.getpid())
        memory_usage = process.memory_info().rss / 1024 / 1024  # MB
        cpu_usage = process.cpu_percent(interval=1)
        
        embed = create_embed(
            title="🤖 Bot Status & Health",
            color=discord.Color.blue()
        )
        
        embed.add_field(name="Uptime", value=uptime_str, inline=True)
        embed.add_field(name="Latency", value=f"{self.bot.latency * 1000:.0f}ms", inline=True)
        embed.add_field(name="Servers", value=str(len(self.bot.guilds)), inline=True)
        
        embed.add_field(name="Users (DB)", value=str(user_count), inline=True)
        embed.add_field(name="Total CraftyCoin", value=f"{total_coins:.0f} CC", inline=True)
        embed.add_field(name="Transactions (24h)", value=str(txn_24h), inline=True)
        
        embed.add_field(name="Memory Usage", value=f"{memory_usage:.1f} MB", inline=True)
        embed.add_field(name="CPU Usage", value=f"{cpu_usage:.1f}%", inline=True)
        embed.add_field(name="Python Version", value=discord.__version__, inline=True)
        
        if self.error_log:
            embed.add_field(name="Recent Errors", value=str(len(self.error_log)), inline=True)
        
        embed.timestamp = datetime.utcnow()
        
        await interaction.response.send_message(embed=embed)
        log.info(f"📊 {interaction.user} checked bot status")

    @app_commands.command(name="bot-errors", description="Affiche les erreurs récentes du bot")
    @app_commands.checks.has_permissions(administrator=True)
    async def status_errors(self, interaction: discord.Interaction, limit: int = 10):
        """
        View recent errors (Admin only)
        
        Usage: /bot-errors [limit]
        """
        # 🛠️ CORRECTION 2 : Changement du nom de la méthode de 'bot_errors' en 'status_errors'
        # pour respecter la restriction sur les préfixes 'bot_' et 'cog_' dans discord.py
        
        if not self.error_log:
            embed = create_embed(
                title="✅ No Recent Errors",
                description="Bot is running smoothly!",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed)
            return
        
        embed = create_embed(
            title="⚠️  Recent Errors",
            description=f"Last {min(limit, len(self.error_log))} errors",
            color=discord.Color.gold()
        )
        
        for error in self.error_log[-limit:]:
            embed.add_field(
                name=error["command"],
                value=(
                    f"**Time:** {error['timestamp']}\n"
                    f"**User:** {error['user']}\n"
                    f"```{error['error'][:200]}```"
            ),
            inline=False
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def log_error(
        self,
        command_name: str,
        user: str,
        error: Exception
    ):
        """
        Store error in memory for monitoring
        """

        self.error_log.append({
            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            "command": command_name,
            "user": user,
            "error": str(error)
        })

        # Keep only last N errors
        if len(self.error_log) > self.max_errors:
            self.error_log.pop(0)

        log.error(
            f"Command Error | {command_name} | "
            f"User: {user} | Error: {error}"
        )

    @tasks.loop(minutes=10)
    async def health_check(self):
        """
        Periodic health monitoring
        """

        try:
            process = psutil.Process(os.getpid())

            memory_usage = process.memory_info().rss / 1024 / 1024
            cpu_usage = process.cpu_percent()

            # Alert thresholds
            if memory_usage > 1000:
                log.warning(
                    f"⚠️ High memory usage detected: "
                    f"{memory_usage:.1f} MB"
                )

            if cpu_usage > 80:
                log.warning(
                    f"⚠️ High CPU usage detected: "
                    f"{cpu_usage:.1f}%"
                )

            # Database test
            with db.get_session() as session:
                session.query(User).first()

            log.debug(
                f"Health Check | "
                f"RAM={memory_usage:.1f}MB | "
                f"CPU={cpu_usage:.1f}%"
            )

        except Exception as e:
            log.error(f"Health check failed: {e}")

    @health_check.before_loop
    async def before_health_check(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Traite les messages de logs Minecraft publiés dans le salon de logs."""
        logs_channel_id = config.CHANNELS.get("logs")

        if logs_channel_id is None or message.channel.id != logs_channel_id:
            return

        # Ignore les messages qui ne semblent pas contenir d'événement Minecraft.
        if "timed out!" not in message.content and "joined" not in message.content and "left" not in message.content and "just made the advancement" not in message.content:
            return

        updated = self._parse_minecraft_log_message(message.content)
        stats = {}
        try:
            stats = await crafty_api.obtenir_stats_crafty()
            if isinstance(stats, dict) and "erreur" in stats:
                stats = {"error": stats["erreur"]}
        except Exception as e:
            log.warning(f"Impossible de récupérer les stats Crafty: {e}")
            stats = {"error": str(e)}

        if stats:
            self.last_crafty_stats = stats

        if updated or stats:
            await self._refresh_status_embed(stats)
        
        if updated or stats:
            await self._refresh_status_embed(stats)
            # 🌐 NOUVEAU : Envoie l'info en live au Dashboard Cyberpunk !
            await self.broadcast_live_update()

        # Poster un message enrichi dans le channel logs pour vérifier l'interprétation
        """try:
            embed = discord.Embed(
                title="📊 Log Minecraft + Stats Crafty",
                description=f"```text\n{message.content}\n```",
                color=discord.Color.dark_blue()
            )
            if stats:
                if stats.get("error"):
                    embed.add_field(name="Crafty Error", value=stats["error"], inline=False)
                else:
                    embed.add_field(name="Crafty Statut", value=f"`{stats.get('running', False)}`", inline=True)
                    embed.add_field(name="Joueurs", value=f"{stats.get('online_players', '?')}/{stats.get('max_players', '?')}", inline=True)
                    if stats.get('cpu') is not None:
                        embed.add_field(name="CPU", value=f"{stats.get('cpu')}%", inline=True)
                    if stats.get('memory') is not None:
                        embed.add_field(name="RAM", value=str(stats.get('memory')), inline=True)
            await message.channel.send(embed=embed)
        except Exception as e:
            log.warning(f"Impossible d'envoyer l'embed de logs Minecraft enrichi: {e}")"""

    async def on_app_command_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError
    ):
        """
        Global slash command error handler
        """

        await self.log_error(
            command_name=getattr(
                interaction.command,
                "name",
                "Unknown"
            ),
            user=str(interaction.user),
            error=error
        )

        if app_commands.errors.MissingPermissions:
            embed = create_embed(
                title="❌ Permission refusée",
                description="Vous n'avez pas les permissions nécessaires.",
                color=discord.Color.red()
            )

        else:
            embed = create_embed(
                title="⚠️ Erreur",
                description=(
                    "Une erreur inattendue est survenue.\n"
                    "L'équipe technique a été notifiée."
                ),
                color=discord.Color.orange()
            )

        try:
            if interaction.response.is_done():
                await interaction.followup.send(
                    embed=embed,
                    ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    embed=embed,
                    ephemeral=True
                )
        except Exception:
            pass

    async def _ensure_status_message(self):
        """Assure qu'un embed de statut serveur existe dans le canal info serveur."""
        info_channel_id = config.CHANNELS.get("info_serveur")
        if not info_channel_id:
            log.warning("INFO_SERVEUR_CHANNEL non configuré, statut serveur désactivé.")
            return

        channel = self.bot.get_channel(info_channel_id)
        if not isinstance(channel, discord.TextChannel):
            log.warning("INFO_SERVEUR_CHANNEL introuvable ou non textuel.")
            return

        # Tenter de retrouver un message de statut déjà présent
        try:
            async for message in channel.history(limit=50):
                if message.author == self.bot.user and message.embeds:
                    embed = message.embeds[0]
                    if embed.title == "État du serveur Minecraft":
                        self.server_status_message_id = message.id
                        log.info("Message de statut serveur trouvé dans le canal info serveur.")
                        return
        except Exception as e:
            log.warning(f"Impossible de récupérer l'historique du canal info serveur: {e}")
            print("erreur lors de la récupération de l'historique du canal info serveur:", e)

        # Aucun message existant, créer un nouveau
        try:
            status_message = await channel.send(embed=self._build_server_status_embed())
            self.server_status_message_id = status_message.id
            log.info("Message de statut serveur créé dans le canal info serveur.")
        except Exception as e:
            log.error(f"Impossible de créer le message de statut serveur: {e}")

    def _parse_minecraft_log_message(self, content: str) -> bool:
        """Analyse le contenu d'un message de log pour mettre à jour l'état du serveur."""
        updated = False
        content = content.replace("MC.joinAPP —", "\nMC.joinAPP —")

        joins = re.findall(r"([A-Za-z0-9_]+) joined", content)
        leaves = re.findall(r"([A-Za-z0-9_]+) left", content)
        starts = re.search(r"Server Started!|Started!|MC\.joinAPP — .*Server Started!", content, re.IGNORECASE)
        crashes = re.search(r"Server Crash Detected|Crash Detected|Stopping the server|Stopping server", content, re.IGNORECASE)
        advancements = re.findall(r"([A-Za-z0-9_]+) just made the advancement ([^\n]+)", content)
        deaths = re.findall(r"([A-Za-z0-9_]+) (?:was .*|was killed .*|was squashed .*|was microwaved .*|experienced kinetic energy|was shot .*|got killed .*|got finished .*|was killed by .*)", content)

        if starts:
            self.server_state = "online"
            self.server_start_time = datetime.utcnow()
            self.server_last_update = datetime.utcnow()
            self.last_events.insert(0, "Serveur démarré")
            updated = True

        if crashes:
            self.server_state = "crash"
            self.server_last_update = datetime.utcnow()
            self.last_events.insert(0, "Crash serveur détecté")
            updated = True

        for username in joins:
            username = username.strip()
            if username:
                self.online_players.add(username)
                self.server_metrics["joins"] += 1
                self.player_metrics.setdefault(username, {"advancements": 0, "deaths": 0})
                self.last_events.insert(0, f"✅ {username} a rejoint")
                self.server_state = "online"
                updated = True

        for username in leaves:
            username = username.strip()
            if username and username in self.online_players:
                self.online_players.discard(username)
                self.server_metrics["leaves"] += 1
                self.last_events.insert(0, f"🔴 {username} a quitté")
                updated = True

        for username, advancement in advancements:
            username = username.strip()
            if username:
                self.server_metrics["advancements"] += 1
                self.player_metrics.setdefault(username, {"advancements": 0, "deaths": 0})
                self.player_metrics[username]["advancements"] += 1
                self.last_events.insert(0, f"🏆 {username} a obtenu: {advancement.strip()}")
                updated = True

        for username in deaths:
            username = username.strip()
            if username:
                self.server_metrics["deaths"] += 1
                self.player_metrics.setdefault(username, {"advancements": 0, "deaths": 0})
                self.player_metrics[username]["deaths"] += 1
                self.last_events.insert(0, f"💀 {username} est mort")
                updated = True

        if updated:
            self.server_last_update = datetime.utcnow()
            self.last_events = self.last_events[:10]

            if self.server_state == "unknown" and self.online_players:
                self.server_state = "online"

        return updated

    async def _refresh_status_embed(self, crafty_stats: dict = None):
        """Met à jour le message d'état serveur existant."""
        if crafty_stats:
            self.last_crafty_stats = crafty_stats

        if not self.server_status_message_id:
            await self._ensure_status_message()
            return

        info_channel_id = config.CHANNELS.get("info_serveur")
        if not info_channel_id:
            return

        channel = self.bot.get_channel(info_channel_id)
        if not isinstance(channel, discord.TextChannel):
            return

        try:
            message = await channel.fetch_message(self.server_status_message_id)
        except Exception:
            self.server_status_message_id = None
            await self._ensure_status_message()
            return

        try:
            await message.edit(embed=self._build_server_status_embed())
        except Exception as e:
            log.warning(f"Impossible de mettre à jour le message de statut serveur: {e}")

    def _build_server_status_embed(self) -> discord.Embed:
        """Construit l'embed de statut serveur Minecraft."""
        status_colors = {
            "online": discord.Color.green(),
            "unknown": discord.Color.greyple(),
            "crash": discord.Color.red(),
            "offline": discord.Color.red(),
            "unstable": discord.Color.orange(),
        }
        state_titles = {
            "online": "En ligne",
            "unknown": "Inconnu",
            "crash": "Crash détecté",
            "offline": "Hors ligne",
            "unstable": "Instable",
        }
        bars = {
            "online": "🟩🟩🟩🟩",
            "unknown": "🟥🟧🟨🟩",
            "crash": "🟥🟥🟥🟥",
            "offline": "🟥🟥🟥🟥",
            "unstable": "🟨🟧🟨🟧",
        }

        title = "État du serveur Minecraft"
        embed = discord.Embed(
            title=title,
            description=bars.get(self.server_state, bars["unknown"]),
            color=status_colors.get(self.server_state, discord.Color.greyple())
        )

        state_label = state_titles.get(self.server_state, "Inconnu")
        player_count = len(self.online_players)
        players_list = ", ".join(sorted(self.online_players)) if self.online_players else "Aucun joueur en ligne"
        start_time = self.server_start_time.isoformat(timespec='minutes') if self.server_start_time else "Nécessite un lancement"
        last_update = self.server_last_update.isoformat(timespec='minutes') if self.server_last_update else "Jamais"

        embed.add_field(name="Statut serveur", value=state_label, inline=False)
        embed.add_field(name="Joueurs en ligne", value=f"**{player_count}**", inline=True)
        embed.add_field(name="Liste des joueurs", value=players_list, inline=False)
        embed.add_field(name="Démarré depuis", value=start_time, inline=True)
        embed.add_field(name="Dernière mise à jour", value=last_update, inline=True)
        embed.add_field(
            name="Statistiques serveur",
            value=(
                f"Joins: **{self.server_metrics['joins']}**\n"
                f"Leaves: **{self.server_metrics['leaves']}**\n"
                f"Advancements: **{self.server_metrics['advancements']}**\n"
                f"Décès: **{self.server_metrics['deaths']}**"
            ),
            inline=False
        )

        if self.last_events:
            embed.add_field(
                name="Événements récents",
                value="\n".join(self.last_events[:6]),
                inline=False
            )

        if self.player_metrics:
            top_players = sorted(
                self.player_metrics.items(),
                key=lambda item: item[1]["advancements"] + item[1]["deaths"],
                reverse=True
            )[:5]
            player_summary = []
            for username, metrics in top_players:
                player_summary.append(
                    f"**{username}**: 🏆 {metrics['advancements']} | 💀 {metrics['deaths']}"
                )
            embed.add_field(
                name="Top joueurs (activités)",
                value="\n".join(player_summary),
                inline=False
            )

        if self.last_crafty_stats:
            if self.last_crafty_stats.get("error"):
                embed.add_field(name="Crafty Stats Error", value=self.last_crafty_stats["error"], inline=False)
            else:
                craft_status = "🟢 En ligne" if self.last_crafty_stats.get("running") else "🔴 Hors ligne"
                craft_players = f"{self.last_crafty_stats.get('online_players', '?')}/{self.last_crafty_stats.get('max_players', '?')}"
                craft_cpu = f"{self.last_crafty_stats.get('cpu')}%" if self.last_crafty_stats.get('cpu') is not None else "N/A"
                craft_memory = str(self.last_crafty_stats.get('memory', 'N/A'))
                craft_title = self.last_crafty_stats.get('name', 'Crafty Server')

                embed.add_field(
                    name="Crafty — Serveur",
                    value=f"**{craft_title}**",
                    inline=False
                )
                embed.add_field(
                    name="Crafty État",
                    value=craft_status,
                    inline=True
                )
                embed.add_field(
                    name="Crafty Joueurs",
                    value=craft_players,
                    inline=True
                )
                embed.add_field(
                    name="Crafty CPU",
                    value=craft_cpu,
                    inline=True
                )
                embed.add_field(
                    name="Crafty RAM",
                    value=craft_memory,
                    inline=True
                )

        embed.timestamp = datetime.utcnow()
        return embed

    async def _start_health_check(self):
        if not self.health_check.is_running():
            self.health_check.start()
        if not self.web_live_loop.is_running():
            self.web_live_loop.start()

    def _setup_api_routes(self):
        """Configure les routes de l'API FastAPI et le serveur de fichiers statiques"""
        
        @self.app.get("/")
        async def read_index():
            # Renvoie le fichier HTML principal du dashboard
            return FileResponse("web/index.html")

        # 🌐 ENDPOINT WEBSOCKET AVEC LE TYPAGE CORRECT ET LA SÉCURITÉ BYPASSÉE
        # On ne passe pas d'arguments de restriction ici pour laisser le middleware ou le handshake gérer
        @self.app.websocket("/api/v1/live")
        async def websocket_endpoint(websocket: WebSocket):
            # ⚡ L'ASTUCE : On accepte la connexion sans restriction d'en-tête Origin
            await websocket.accept(headers=[(b"access-control-allow-origin", b"*")])
            self.connected_websockets.append(websocket)
            print("[DEBUG WEB] Client WebSocket connecté avec succès via tunnel !")
            
            try:
                # Génération du dictionnaire de données initiales de manière sécurisée
                process = psutil.Process(os.getpid())
                uptime = datetime.now(timezone.utc) - self.start_time
                
                initial_payload = {
                    "bot": {
                        "status": "online",
                        "latency_ms": round(self.bot.latency * 1000, 1) if self.bot.latency else 0,
                        "uptime_seconds": int(uptime.total_seconds()),
                        "memory_mb": round(process.memory_info().rss / 1024 / 1024, 1),
                        "cpu_percent": round(process.cpu_percent(), 1),
                        "guilds_count": len(self.bot.guilds),
                        "recent_errors_count": len(self.error_log)
                    },
                    "minecraft_server": {
                        "state": self.server_state,
                        "online_players_count": len(self.online_players),
                        "online_players_list": list(sorted(self.online_players)),
                        "metrics": self.server_metrics,
                        "last_events": self.last_events[:6]
                    },
                    "crafty": self.last_crafty_stats
                }
                
                await websocket.send_json(initial_payload)
                
                # Boucle infinie pour maintenir la connexion active
                while True:
                    await websocket.receive_text()
                    
            except Exception as e:
                print(f"[DEBUG WEB] Fin de session ou erreur WebSocket : {e}")
            finally:
                if websocket in self.connected_websockets:
                    self.connected_websockets.remove(websocket)
                print("[DEBUG WEB] Client WebSocket déconnecté.")

        # Montage du dossier web pour charger monitoring.js
        print("[DEBUG WEB] Montage du dossier web pour les fichiers statiques...")
        self.app.mount("/web", StaticFiles(directory="web"), name="web")

        # Déclare une tâche récurrente toutes les 0.5 secondes
    @tasks.loop(seconds=0.5)
    async def web_broadcast_loop(self):
        """Envoie les statistiques mises à jour en temps réel (toutes les 0.5s)"""
        if not self.connected_websockets:
            return

        try:
            process = psutil.Process(os.getpid())
            uptime = datetime.now(timezone.utc) - self.start_time
            
            # 🔄 1. Calcul des latences dynamiques
            loop_latency = await self._get_loop_latency()
            discord_latency = round(self.bot.latency * 1000, 1) if self.bot.latency else 0.0
            
            # 🛡️ 2. Détermination de l'état de santé global du Bot
            # Si Discord est déconnecté ou si l'event loop met plus de 100ms à répondre, la réactivité est critique.
            if not self.bot.is_ready():
                health_status = "offline"
            elif loop_latency > 100.0:
                health_status = "unresponsive"
            elif loop_latency > 25.0:
                health_status = "lagging"
            else:
                health_status = "stable"

            payload = {
                "bot": {
                    "status": "online",
                    "health": health_status,               # Nouvel état global
                    "discord_latency_ms": discord_latency,  # Ping officiel Discord
                    "loop_latency_ms": loop_latency,        # Réactivité brute interne (ultra-dynamique)
                    "uptime_seconds": int(uptime.total_seconds()),
                    "memory_mb": round(process.memory_info().rss / 1024 / 1024, 1),
                    "cpu_percent": round(process.cpu_percent(), 1),
                    "guilds_count": len(self.bot.guilds),
                    "recent_errors_count": len(self.error_log)
                },
                "minecraft_server": {
                    "state": self.server_state,
                    "online_players_count": len(self.online_players),
                    "online_players_list": list(sorted(self.online_players)),
                    "metrics": self.server_metrics,
                    "last_events": self.last_events[:6]
                },
                "crafty": self.last_crafty_stats
            }

            for ws in list(self.connected_websockets):
                try:
                    await ws.send_json(payload)
                except Exception:
                    if ws in self.connected_websockets:
                        self.connected_websockets.remove(ws)

        except Exception as e:
            print(f"[DEBUG WEB] Erreur dans la boucle de diffusion rapide : {e}")

    @commands.Cog.listener()
    async def on_ready(self):
        # On lance la tâche de fond si elle ne tourne pas déjà
        if not self.web_broadcast_loop.is_running():
            self.web_broadcast_loop.start()
            print("[DEBUG WEB] Boucle de diffusion de données (5s) démarrée !")


async def setup(bot):
    """
    Load cog
    """

    await bot.add_cog(MonitoringCog(bot))