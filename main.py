"""Point d'entrée du Bot JMG v2 - UNE SEULE instance"""

import asyncio
import discord
from discord.ext import commands
import sys
from pathlib import Path

# Imports locaux
from config import config, validate_config
from utils import setup_logging, get_logger
from db import db

# Configuration du logging
setup_logging()
logger = get_logger(__name__)


class JMGBot(commands.Bot):
    """Classe principale du Bot Discord avec gestion complète."""
    
    def __init__(self):
        """Initialise le bot avec les configurations appropriées"""
        intents = discord.Intents.all()
        super().__init__(
            command_prefix=commands.when_mentioned,
            intents=intents,
            help_command=None
        )
        self.synced = False
        self.db = db

    async def setup_hook(self):
        """Charge les extensions au démarrage."""
        logger.info("🔧 Initialisation des extensions...")
        
        # Liste des cogs à charger (ordre importe: decorators/utilities d'abord)
        cogs_to_load = [
            'cogs.commands',
            'cogs.admin',
            'cogs.admin_economy',
            'cogs.crafty',
            'cogs.economy',
            'cogs.events',
            'cogs.minecraft',
            'cogs.welcome',
            'cogs.shop',
            'cogs.purchase',
            'cogs.minigames',
            'cogs.monitoring',
            'cogs.ticket_link'
        ]
        
        for cog in cogs_to_load:
            try:
                await self.load_extension(cog)
                logger.info(f"✅ Cog chargé : {cog}")
            except Exception as e:
                logger.error(f"❌ Erreur en chargeant {cog} : {e}", exc_info=True)
        
        # Synchronise les commandes slash avec Discord
        logger.info("🔄 Synchronisation des commandes slash...")
        try:
            synced = await self.tree.sync()
            logger.info(f"✅ {len(synced)} commandes slash synchronisées !")
            self.synced = True
        except Exception as e:
            logger.error(f"❌ Erreur lors de la synchronisation : {e}", exc_info=True)

    async def on_ready(self):
        """Événement appelé quand le bot est prêt."""
        if not self.synced:
            return
        
        logger.info("=" * 60)
        logger.info(f"🚀 Bot connecté en tant que : {self.user}")
        if self.user.id: # type: ignore
            logger.info(f"📊 ID Bot : {self.user.id}") # type: ignore
        else :
            logger.warning("⚠️  Impossible de récupérer l'ID du bot !")
        logger.info(f"📈 Serveurs : {len(self.guilds)}")
        logger.info("⚡ Prêt à recevoir des commandes !")
        logger.info("=" * 60)
        
        
        # Définir le statut
        activity = discord.Activity(
            type=discord.ActivityType.watching,
            name="CraftyCoin 💎"
        )
        await self.change_presence(activity=activity)


# Instance UNIQUE du bot (singleton pattern)
bot = None


async def initialize_bot():
    """Initialise le bot avec toutes les vérifications"""
    global bot
    
    try:
        # Valider la configuration
        logger.info("🔍 Vérification de la configuration...")
        validate_config()
        logger.info("✅ Configuration valide")
        
        # Initialiser la base de données
        logger.info("🗄️  Initialisation de la base de données...")
        db.init_db()
        logger.info("✅ Base de données initialisée")
        
        # Créer le bot
        logger.info("🤖 Création du bot Discord...")
        bot = JMGBot()
        logger.info("✅ Bot Discord créé")
        
        return bot
    except ValueError as e:
        logger.critical(f"❌ Erreur de configuration: {e}")
        sys.exit(1)
    except Exception as e:
        logger.critical(f"❌ Erreur lors de l'initialisation: {e}", exc_info=True)
        sys.exit(1)


async def main():
    """Fonction principale de démarrage."""
    global bot
    
    logger.info("=" * 60)
    logger.info("🎮 Démarrage de JMG Bot v2")
    logger.info("=" * 60)
    
    # Initialiser le bot
    bot = await initialize_bot()
    
    # Démarrer le bot
    try:
        async with bot:
            logger.info("🔌 Connexion à Discord...")
            await bot.start(config.BOT_TOKEN)
    except discord.LoginFailure:
        logger.critical("❌ Token Discord invalide!")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("⏹️  Arrêt du bot par l'utilisateur")
    except Exception as e:
        logger.critical(f"❌ Erreur critique: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("🔌 Fermeture des connexions...")
        db.close()
        logger.info("✅ Bot arrêté")



if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n⏹️  Bot arrêté")
    except Exception as e:
        logger.critical(f"❌ Erreur non gérée: {e}", exc_info=True)
        sys.exit(1)


