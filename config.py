"""Configuration centralisée avec support .env"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Charger les variables depuis .env
env_path = Path(__file__).parent / ".env"
load_dotenv(env_path)


class Config:
    """Configuration de base du bot"""
    
    # --- DISCORD BOT ---
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    MC_JOIN_TOKEN: str = os.getenv("MC_JOIN_TOKEN", "")
    MINECRAFT_LOG_PATH: str = os.getenv("MINECRAFT_LOG_PATH", "")

    # --- BOT Minecraft ---
    MC_JOIN_ID = int(os.getenv("MC_JOIN_ID", "0"))
    
    # --- CRAFTY API ---
    CRAFTY_BASE_URL: str = os.getenv("CRAFTY_BASE_URL", "https://100.111.101.28:8443")
    CRAFTY_API_TOKEN: str = os.getenv("CRAFTY_API_TOKEN", "")
    CRAFTY_SERVER_ID: str = os.getenv("CRAFTY_SERVER_ID", "")
    
    # --- DISCORD SERVER ---
    MCF_GUILD_ID: int = int(os.getenv("MCF_GUILD_ID", "0"))
    
    # --- CHANNELS ---
    CHANNELS = {
        "gestion_mc": int(os.getenv("GESTION_MC_CHANNEL", "0")),
        "gestion_console": int(os.getenv("GESTION_CONSOLE_CHANNEL", "0")),
        "gestion_debian": int(os.getenv("GESTION_DEBIAN_CHANNEL", "0")),
        "logs": int(os.getenv("LOGS_CHANNEL", "0")),
        "commands": int(os.getenv("COMMANDS_CHANNEL", "0")),
        "boutique": int(os.getenv("BOUTIQUE_CHANNEL", "0")),
        "economie": int(os.getenv("ECONOMIE_CHANNEL", "0")),
        "quetes": int(os.getenv("QUETES_CHANNEL", "0")),
        "info": int(os.getenv("INFO_CHANNEL", "0")),
        "info_serveur": int(os.getenv("INFO_SERVEUR_CHANNEL", "0")),
        "signalement": int(os.getenv("SIGNALEMENT_CHANNEL", "0")),
        "modo_only": int(os.getenv("MODO_ONLY_CHANNEL", "0")),
        "ticket_channel": int(os.getenv("TICKET_CHANNEL_ID", "0"))
    }
    
    # --- ROLES ---
    ROLES = {
        "manager_ultim": int(os.getenv("MANAGER_ULTIM_ROLE", "0")),
        "next_ban": int(os.getenv("NEXT_BAN_ROLE", "0")),
        "manager_minecraft": int(os.getenv("MANAGER_MINECRAFT_ROLE", "0")),
        "manager_discord": int(os.getenv("MANAGER_DISCORD_ROLE", "0")),
        "manager_crafty": int(os.getenv("MANAGER_CRAFTY_ROLE", "0")),
        "createurs": int(os.getenv("CREATEURS_ROLE", "0")),
        "membres_serveur": int(os.getenv("MEMBRES_SERVEUR_ROLE", "0")),
    }
    
    # --- DATABASE ---
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./jmg_bot.db")
    
    # --- ECONOMY SETTINGS ---
    MESSAGE_CHARACTER_RATE: float = float(os.getenv("MESSAGE_CHARACTER_RATE", "0.1"))
    VOICE_EARNING_RATE: float = float(os.getenv("VOICE_EARNING_RATE", "0.5"))
    DAILY_REWARD_BASE: int = int(os.getenv("DAILY_REWARD_BASE", "10"))
    DAILY_REWARD_MULTIPLIER: float = float(os.getenv("DAILY_REWARD_MULTIPLIER", "1.5"))
    SPAM_PREVENTION_TIME: int = int(os.getenv("SPAM_PREVENTION_TIME", "5"))
    ANTI_COPYPASTE_THRESHOLD: float = float(os.getenv("ANTI_COPYPASTE_THRESHOLD", "0.85"))
    
    # --- ENVIRONMENT ---
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

    TIMEOUTS = {
        "crafty_api": int(os.getenv("CRAFTY_API_TIMEOUT", "10"))
    }


def validate_config():
    """Valide que les tokens essentiels sont présents"""
    required = ["BOT_TOKEN", "CRAFTY_API_TOKEN", "CRAFTY_SERVER_ID"]
    missing = [var for var in required if not getattr(Config, var)]
    if missing:
        raise ValueError(f"Variables d'environnement manquantes: {', '.join(missing)}")
    return True


# Export pour usage facile
config = Config()

