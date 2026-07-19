"""Module de monitoring des logs Minecraft avec watchdog"""

import asyncio
import re
from pathlib import Path
from datetime import datetime
from typing import Optional, Callable, List
import logging

from utils import get_logger

logger = get_logger(__name__)


class MinecraftLogMonitor:
    """Monitore les logs Minecraft pour détecter les événements"""
    
    def __init__(self, log_file_path: str = None):
        """
        Initialise le moniteur de logs
        
        Args:
            log_file_path: Chemin vers le fichier logs.txt du serveur
        """
        self.log_file_path = log_file_path
        self.last_position = 0
        self.callbacks = {
            "player_join": [],
            "player_leave": [],
            "server_start": [],
            "server_stop": [],
            "player_login_command": [],
        }
        self.is_monitoring = False
        
        # Patterns regex pour détecter les événements
        self.patterns = {
            "player_join": [
                r"(\w+) joined the game",
                r"(\w+) \[.*\] logged in",
            ],
            "player_leave": [
                r"(\w+) left the game",
                r"(\w+) lost connection",
            ],
            "server_start": [
                r"Done \(\d+\.\d+s\)!",
                r"\[Server thread/INFO\]: TimingsManager:",
            ],
            "server_stop": [
                r"Stopping the server",
                r"\[Server thread/INFO\]: Stopping server",
            ],
            "player_login_command": [
                r"(\w+) executed command login (.+)",
            ],
        }

    def register_callback(self, event_type: str, callback: Callable):
        """
        Enregistre un callback pour un type d'événement
        
        Args:
            event_type: "player_join", "player_leave", "server_start", "server_stop"
            callback: Fonction async(username) pour player events, async() pour server events
        """
        if event_type in self.callbacks:
            self.callbacks[event_type].append(callback)
            logger.info(f"Callback enregistré pour: {event_type}")

    async def start(self):
        """Démarre le monitoring des logs"""
        if not self.log_file_path or not Path(self.log_file_path).exists():
            logger.warning(f"Fichier logs non trouvé: {self.log_file_path}")
            return
        
        logger.info(f"🔍 Démarrage du monitoring: {self.log_file_path}")
        self.is_monitoring = True
        self.last_position = Path(self.log_file_path).stat().st_size
        
        try:
            while self.is_monitoring:
                await self._check_logs()
                await asyncio.sleep(1)  # Vérifier chaque seconde
        except Exception as e:
            logger.error(f"Erreur lors du monitoring: {e}", exc_info=True)
        finally:
            self.is_monitoring = False
            logger.info("⏹️ Monitoring arrêté")

    async def stop(self):
        """Arrête le monitoring"""
        self.is_monitoring = False

    async def _check_logs(self):
        """Vérifie les nouveaux logs depuis la dernière position"""
        try:
            file_size = Path(self.log_file_path).stat().st_size
            
            # Si le fichier a été réinitialisé (restart), réinitialiser la position
            if file_size < self.last_position:
                logger.info("Fichier logs réinitialisé (file rotation ou server restart)")
                self.last_position = 0
            
            if file_size <= self.last_position:
                return
            
            # Lire les nouvelles lignes
            with open(self.log_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                f.seek(self.last_position)
                new_lines = f.readlines()
                self.last_position = f.tell()
            
            # Traiter chaque ligne
            for line in new_lines:
                await self._process_line(line.strip())
        
        except FileNotFoundError:
            logger.warning(f"Fichier logs non trouvé: {self.log_file_path}")
        except Exception as e:
            logger.error(f"Erreur lors de la lecture des logs: {e}", exc_info=True)

    async def _process_line(self, line: str):
        """Traite une ligne de log"""
        if not line:
            return
        
        # Vérifier player_join
        for pattern in self.patterns["player_join"]:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                username = match.group(1)
                await self._trigger_event("player_join", username)
                return
        
        # Vérifier player_leave
        for pattern in self.patterns["player_leave"]:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                username = match.group(1)
                await self._trigger_event("player_leave", username)
                return
        
        # Vérifier player_login_command
        for pattern in self.patterns["player_login_command"]:
            match = re.search(pattern, line, re.IGNORECASE)
            if match:
                username = match.group(1)
                password = match.group(2)
                await self._trigger_event("player_login_command", username, password)
                return
        
        # Vérifier server_start
        for pattern in self.patterns["server_start"]:
            if re.search(pattern, line, re.IGNORECASE):
                await self._trigger_event("server_start")
                return
        
        # Vérifier server_stop
        for pattern in self.patterns["server_stop"]:
            if re.search(pattern, line, re.IGNORECASE):
                await self._trigger_event("server_stop")
                return

    async def _trigger_event(self, event_type: str, username: str = None, password: str = None):
        """Déclenche les callbacks pour un événement"""
        callbacks = self.callbacks.get(event_type, [])
        
        if not callbacks:
            return
        
        for callback in callbacks:
            try:
                if event_type == "player_login_command":
                    await callback(username, password)
                elif username:
                    await callback(username)
                else:
                    await callback()
            except Exception as e:
                logger.error(f"Erreur dans callback {event_type}: {e}", exc_info=True)


# Instance globale (optionnelle)
monitor: Optional[MinecraftLogMonitor] = None


def get_monitor() -> MinecraftLogMonitor:
    """Obtient l'instance globale du moniteur"""
    global monitor
    if monitor is None:
        monitor = MinecraftLogMonitor()
    return monitor
