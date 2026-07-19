"""Configuration du logging pour JMG Bot v2"""

import logging
import logging.handlers
from pathlib import Path
from datetime import datetime
from config import config
import sys
import discord


def setup_logging():
    """Configure le logging avec fichiers et console"""
    
    # Créer le dossier logs s'il n'existe pas
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    
    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, config.LOG_LEVEL))
    
    # Format
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Handler console
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # Handler fichier (rotation)
    file_handler = logging.handlers.RotatingFileHandler(
        logs_dir / "bot.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
    
    # Handler fichier pour erreurs
    error_handler = logging.handlers.RotatingFileHandler(
        logs_dir / "errors.log",
        maxBytes=10 * 1024 * 1024,
        backupCount=5
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    root_logger.addHandler(error_handler)
    
    return root_logger


async def relay_log(bot, title: str, description: str, color: discord.Color = discord.Color.dark_grey()):
    """Relaye un message de log vers le salon Discord configuré."""
    if bot is None:
        return

    logs_channel_id = config.CHANNELS.get("logs")
    if not logs_channel_id:
        return

    if len(description) > 4000:
        description = description[:4000] + "..."

    try:
        channel = bot.get_channel(logs_channel_id)
        if not channel or not isinstance(channel, discord.TextChannel):
            return

        embed = discord.Embed(
            title=title,
            description=description,
            color=color
        )
        embed.timestamp = datetime.utcnow()
        await channel.send(embed=embed)
    except Exception as e:
        logging.getLogger(__name__).warning(f"Impossible d'envoyer le log Discord: {e}")


def get_logger(name: str) -> logging.Logger:
    """Obtient un logger nommé"""
    return logging.getLogger(name)
