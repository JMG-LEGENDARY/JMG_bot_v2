"""Helpers et utilitaires pour JMG Bot"""

import hashlib
import base64
import os
import secrets
from typing import Optional
from datetime import datetime, timedelta
import difflib
import re


def hash_message(content: str) -> str:
    """Hash un message pour détection de copier-coller"""
    return hashlib.sha256(content.encode()).hexdigest()


def detect_copy_paste(current_message: str, previous_messages: list, threshold: float = 0.85) -> tuple[bool, float]:
    """Détecte si le message est un copier-coller"""
    if not previous_messages or not current_message:
        return False, 0.0
    
    # Normaliser les messages
    current_normalized = re.sub(r'\s+', ' ', current_message.lower()).strip()
    
    for prev_msg in previous_messages[-5:]:  # Vérifier les 5 derniers messages
        prev_normalized = re.sub(r'\s+', ' ', prev_msg.lower()).strip()
        similarity = difflib.SequenceMatcher(None, current_normalized, prev_normalized).ratio()
        if similarity >= threshold:
            return True, similarity
    
    return False, 0.0


def is_afk_in_voice(last_activity_time: datetime, timeout_minutes: int = 10) -> bool:
    """Vérifie si un utilisateur est AFK en vocal"""
    time_diff = datetime.utcnow() - last_activity_time
    return time_diff > timedelta(minutes=timeout_minutes)


def calculate_playtime_earning(playtime_minutes: float, multiplier: float = 1.0, 
                               rate: float = 0.5) -> float:
    """Calcule les gains depuis le temps de jeu"""
    # rate en coins par minute
    return (playtime_minutes * rate * multiplier)


def calculate_message_earning(character_count: int, multiplier: float = 1.0,
                             rate: float = 0.1) -> float:
    """Calcule les gains depuis les messages"""
    return (character_count * rate * multiplier)


def calculate_daily_reward(base_reward: int, consecutive_days: int, 
                          multiplier: float = 1.5) -> float:
    """Calcule la récompense quotidienne avec bonus"""
    bonus = base_reward * (multiplier ** (consecutive_days - 1))
    return bonus


def is_within_spam_window(last_message_time: datetime, spam_prevention_seconds: int = 5) -> bool:
    """Vérifie si le message est dans la fenêtre de spam"""
    time_diff = datetime.utcnow() - last_message_time
    return time_diff.total_seconds() < spam_prevention_seconds


def extract_minecraft_username_from_log(log_line: str) -> Optional[str]:
    """Extrait le nom d'utilisateur Minecraft depuis une ligne de log"""
    patterns = [
        r"\[MinecraftServer\]: (\w+) joined the game",
        r"\[MinecraftServer\]: (\w+) left the game",
        r"\[ServerGamePacketListenerImpl\]: (\w+) lost connection",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, log_line)
        if match:
            return match.group(1)
    return None


def format_minecraft_command(command_template: str, player_name: str) -> str:
    """Formate une commande Minecraft avec le nom du joueur"""
    return command_template.replace("{player}", player_name).replace("{joueur}", player_name)


def hash_password(password: str) -> str:
    """Hash un mot de passe avec PBKDF2-HMAC-SHA256."""
    salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 120000)
    return base64.b64encode(salt + key).decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    """Vérifie un mot de passe contre un hash stocké."""
    try:
        raw = base64.b64decode(password_hash.encode('utf-8'))
        salt = raw[:16]
        key = raw[16:]
        test_key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 120000)
        return secrets.compare_digest(test_key, key)
    except Exception:
        return False


def generate_temporary_password(length: int = 10) -> str:
    """Génère un mot de passe temporaire facile à communiquer."""
    alphabet = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def get_time_until_next_reset(reset_hour: int = 0) -> timedelta:
    """Calcule le temps jusqu'au prochain reset quotidien"""
    now = datetime.utcnow()
    reset_time = now.replace(hour=reset_hour, minute=0, second=0, microsecond=0)
    
    if now >= reset_time:
        reset_time += timedelta(days=1)
    
    return reset_time - now


def is_new_day(last_claim: datetime) -> bool:
    """Vérifie si c'est un nouveau jour depuis la dernière réclamation"""
    if last_claim is None:
        return True
    
    return datetime.utcnow().date() > last_claim.date()


def calculate_activity_score(messages: int, characters: int, responses: int,
                           playtime: float) -> float:
    """Calcule un score d'activité global"""
    message_score = messages * 10
    character_score = characters * 0.05
    response_score = responses * 25
    playtime_score = playtime * 0.5
    
    return message_score + character_score + response_score + playtime_score


def seconds_to_readable_time(seconds: float) -> str:
    """Convertit des secondes en format lisible"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    
    if hours > 0:
        return f"{hours}h {minutes}m"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"


def format_coins(amount: float) -> str:
    """Formate un montant de coins avec suffixe"""
    if amount >= 1_000_000:
        return f"{amount / 1_000_000:.1f}M CC"
    elif amount >= 1_000:
        return f"{amount / 1_000:.1f}K CC"
    else:
        return f"{amount:.0f} CC"
