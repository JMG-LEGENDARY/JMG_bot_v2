"""Constantes globales pour JMG Bot"""

# Régex pour Minecraft logs
MINECRAFT_LOG_PATTERNS = {
    "player_joined": [
        r"\[MinecraftServer\]: (\w+) joined the game",
        r"(\w+) a rejoint le jeu",
    ],
    "player_left": [
        r"\[MinecraftServer\]: (\w+) left the game",
        r"\[ServerGamePacketListenerImpl\]: (\w+) lost connection",
    ],
    "server_start": [
        r"Done \(\d+\.\d+s\)",
        r"le serveur minecraft a démarré",
    ],
    "server_stop": [
        r"Stopping the server",
        r"le serveur minecraft est arrêté",
    ]
}

# Emojis
EMOJI = {
    "success": "✅",
    "error": "❌",
    "warning": "⚠️",
    "info": "ℹ️",
    "online": "🟢",
    "offline": "🔴",
    "coin": "💰",
    "craftycoin": "💎",
    "shop": "🛒",
    "trophy": "🏆",
    "microphone": "🎤",
    "chat": "💬",
    "gamepad": "🎮",
}

# Messages prédéfinis
MESSAGES = {
    "not_authorized": "❌ Vous n'êtes pas autorisé à faire ça",
    "command_error": "❌ Une erreur est survenue",
    "not_configured": "⚙️ Cette fonctionnalité n'est pas configurée",
    "processing": "⏳ Traitement en cours...",
}

# Limites
LIMITS = {
    "max_message_length": 2000,  # Discord limit
    "max_items_per_embed": 25,
    "max_leaderboard_entries": 20,
}

# Timeouts (en secondes)
TIMEOUTS = {
    "afk_detection": 600,  # 10 minutes
    "spam_prevention": 5,
    "crafty_api_timeout": 10,
    "message_delete_delay": 30,
}

# Multiplicateurs d'activité
ACTIVITY_MULTIPLIERS = {
    "message": 1.0,
    "response": 1.5,  # +50% pour répondre aux gens
    "help": 2.0,      # Double pour aider
    "playtime": 1.0,
    "minecraft_afk_factor": 0.1,  # Si AFK, 10% du gain normal
}

# Catégories de shop
SHOP_CATEGORIES = {
    "weapons": "Armes",
    "armor": "Armure",
    "tools": "Outils",
    "building": "Construction",
    "food": "Nourriture",
    "potions": "Potions",
    "enchantments": "Enchantements",
    "misc": "Divers",
}

# Status du serveur
SERVER_STATUS = {
    "online": "EN LIGNE",
    "offline": "HORS LIGNE",
    "starting": "DÉMARRAGE",
    "stopping": "ARRÊT",
    "error": "ERREUR",
}

# Status des achats
PURCHASE_STATUS = {
    "pending": "En attente",
    "completed": "Complété",
    "failed": "Échoué",
    "cancelled": "Annulé",
}
