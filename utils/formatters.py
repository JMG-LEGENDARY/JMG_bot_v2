"""Formateurs pour les embeds et messages Discord"""

import discord
from datetime import datetime, timezone
from typing import List, Tuple


def format_craftycoin_embed(user_balance: float, rank: int = None, nickname: str = None) -> discord.Embed:
    """Crée un embed montrant le solde CraftyCoin"""
    embed = discord.Embed(
        title="💰 Solde CraftyCoin",
        description=f"**{user_balance:.0f}** CraftyCoins",
        color=discord.Color.gold()
    )
    if nickname:
        embed.set_author(name=nickname)
    if rank:
        embed.add_field(name="Classement", value=f"#{rank}", inline=True)
    return embed


def format_leaderboard_embed(leaderboard: List[Tuple[str, float, int]]) -> discord.Embed:
    """Crée un embed du classement"""
    embed = discord.Embed(
        title="🏆 Classement CraftyCoin",
        color=discord.Color.gold()
    )
    
    medals = ["🥇", "🥈", "🥉"]
    for idx, (name, balance, rank) in enumerate(leaderboard):
        medal = medals[idx] if idx < 3 else f"#{idx + 1}"
        embed.add_field(
            name=f"{medal} {name}",
            value=f"**{balance:.0f}** CC",
            inline=False
        )
    
    return embed


def format_shop_item_embed(item_name: str, price: float, description: str = None) -> discord.Embed:
    """Crée un embed pour un item de boutique"""
    embed = discord.Embed(
        title=f"🛒 {item_name}",
        description=description or "Item de la boutique",
        color=discord.Color.blurple()
    )
    embed.add_field(name="Prix", value=f"**{price:.0f}** CC", inline=True)
    return embed


def format_transaction_embed(transaction_type: str, amount: float, 
                            multiplier: float = 1.0, reason: str = None) -> discord.Embed:
    """Crée un embed pour une transaction"""
    emoji_map = {
        "message": "💬",
        "voice": "🎤",
        "daily": "📅",
        "game": "🎮",
        "shop": "🛒",
        "bonus": "⭐",
        "penalty": "⚠️"
    }
    
    emoji = emoji_map.get(transaction_type, "💰")
    
    embed = discord.Embed(
        title=f"{emoji} Transaction",
        color=discord.Color.green() if amount > 0 else discord.Color.red()
    )
    
    embed.add_field(name="Montant", value=f"**{amount:+.0f}** CC", inline=True)
    embed.add_field(name="Multiplicateur", value=f"**{multiplier:.1f}x**", inline=True)
    
    if reason:
        embed.add_field(name="Raison", value=reason, inline=False)
    
    return embed


def format_server_status_embed(is_online: bool, players: int, max_players: int,
                              cpu: float = None, memory: str = None) -> discord.Embed:
    """Crée un embed du statut serveur Minecraft"""
    status_text = "🟢 EN LIGNE" if is_online else "🔴 HORS LIGNE"
    color = discord.Color.green() if is_online else discord.Color.red()
    
    embed = discord.Embed(
        title="Statut Serveur Minecraft",
        color=color
    )
    
    embed.add_field(name="État", value=status_text, inline=True)
    embed.add_field(name="Joueurs", value=f"**{players}/{max_players}**", inline=True)
    
    if cpu is not None:
        embed.add_field(name="CPU", value=f"**{cpu:.1f}%**", inline=True)
    if memory is not None:
        embed.add_field(name="RAM", value=memory, inline=True)
    
    return embed


def format_error_embed(error_message: str, error_type: str = "Erreur") -> discord.Embed:
    """Crée un embed d'erreur"""
    embed = discord.Embed(
        title=f"❌ {error_type}",
        description=error_message,
        color=discord.Color.red()
    )
    return embed


def format_success_embed(title: str, message: str = None) -> discord.Embed:
    """Crée un embed de succès"""
    embed = discord.Embed(
        title=f"✅ {title}",
        description=message or "",
        color=discord.Color.green()
    )
    return embed

def create_embed(title: str, description: str = None, color: discord.Color = discord.Color.blue()):
    """Génère un embed Discord standardisé pour le bot"""
    embed = discord.Embed(
        title=title, 
        description=description, 
        color=color, 
        timestamp=datetime.now(timezone.utc)
    )
    embed.set_footer(text="JMG Bot v2")
    return embed