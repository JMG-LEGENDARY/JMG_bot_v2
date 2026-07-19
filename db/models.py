"""Modèles de base de données SQLAlchemy pour JMG Bot v2"""

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class User(Base):
    """Utilisateur Discord avec données Minecraft"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    discord_id = Column(Integer, unique=True, nullable=False, index=True)
    minecraft_username = Column(String(50), unique=True, nullable=True)
    craftycoin_balance = Column(Float, default=0.0)
    password_hash = Column(String(256), nullable=True)
    is_authenticated = Column(Boolean, default=False)
    is_whitelisted = Column(Boolean, default=False)
    
    # Statistiques
    total_messages = Column(Integer, default=0)
    total_characters = Column(Integer, default=0)
    total_responses = Column(Integer, default=0)
    total_playtime_minutes = Column(Float, default=0.0)
    
    # Multiplicateurs personnalisés
    message_multiplier = Column(Float, default=1.0)
    playtime_multiplier = Column(Float, default=1.0)
    response_multiplier = Column(Float, default=1.0)
    
    # Récompense quotidienne
    last_daily_reward = Column(DateTime, nullable=True)
    consecutive_days = Column(Integer, default=0)
    
    # Métadonnées
    is_afk_voice = Column(Boolean, default=False)
    last_activity = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=datetime.utcnow)
    
    # Relations
    transactions = relationship("Transaction", back_populates="user", cascade="all, delete-orphan")
    #shop_items = relationship("ShopItem", secondary="pending_purchases", back_populates="purchased_by_users")
    pending_purchases = relationship("PendingPurchase", back_populates="user", cascade="all, delete-orphan")
    anti_spam_records = relationship("AntiSpamRecord", back_populates="user", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<User discord_id={self.discord_id} minecraft={self.minecraft_username}>"


class ShopItem(Base):
    """Article disponible à la boutique"""
    __tablename__ = "shop_items"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    price = Column(Float, nullable=False)
    minecraft_command = Column(String(500), nullable=False)  # /give {player} item
    
    # Métadonnées
    category = Column(String(50), default="misc")  # weapon, armor, building, etc.
    is_available = Column(Boolean, default=True)
    max_purchase_per_user = Column(Integer, default=None)  # None = unlimited
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=datetime.utcnow)
    
    # Relations
    purchases = relationship("PendingPurchase", back_populates="item", cascade="all, delete-orphan")
    #purchased_by_users = relationship("User", secondary="pending_purchases")
    
    def __repr__(self):
        return f"<ShopItem name={self.name} price={self.price}>"


class PendingPurchase(Base):
    """Achat en attente d'exécution (attend connexion joueur)"""
    __tablename__ = "pending_purchases"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    item_id = Column(Integer, ForeignKey("shop_items.id"), nullable=False)
    
    quantity = Column(Integer, default=1)
    status = Column(String(20), default="pending")  # pending, completed, failed, cancelled
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Relations
    user = relationship("User", back_populates="pending_purchases")
    item = relationship("ShopItem", back_populates="purchases")
    
    def __repr__(self):
        return f"<PendingPurchase user_id={self.user_id} item_id={self.item_id} status={self.status}>"


class Transaction(Base):
    """Historique des transactions CraftyCoin"""
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    amount = Column(Float, nullable=False)
    transaction_type = Column(String(50), nullable=False)  # message, voice, daily, game, shop, etc.
    description = Column(String(200), nullable=True)
    
    # Métadonnées
    multiplier_applied = Column(Float, default=1.0)
    base_amount = Column(Float, nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    
    # Relations
    user = relationship("User", back_populates="transactions")
    
    def __repr__(self):
        return f"<Transaction user_id={self.user_id} type={self.transaction_type} amount={self.amount}>"


class AntiSpamRecord(Base):
    """Enregistrement pour détection de copier-coller et spam"""
    __tablename__ = "anti_spam_records"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    
    message_hash = Column(String(64), nullable=False)
    content_similarity = Column(Float, default=0.0)  # 0-1, 1 = copie exacte
    
    is_flagged = Column(Boolean, default=False)
    flag_reason = Column(String(100), nullable=True)  # "copy_paste", "spam", etc.
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    
    # Relations
    user = relationship("User", back_populates="anti_spam_records")
    
    def __repr__(self):
        return f"<AntiSpamRecord user_id={self.user_id} flagged={self.is_flagged}>"


class DailyReward(Base):
    """Configuration des récompenses quotidiennes"""
    __tablename__ = "daily_rewards"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, unique=True, nullable=False, index=True)
    
    last_claimed = Column(DateTime, nullable=True)
    consecutive_days = Column(Integer, default=0)
    total_claimed = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=datetime.utcnow)


class VoiceActivity(Base):
    """Suivi des activités vocales pour détecter AFK"""
    __tablename__ = "voice_activity"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    
    joined_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    last_activity = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    
    is_muted = Column(Boolean, default=False)
    is_deafened = Column(Boolean, default=False)
    is_streaming = Column(Boolean, default=False)
    
    total_earning_minutes = Column(Float, default=0.0)
    
    # Relations
    __table_args__ = (
        {'sqlite_autoincrement': True},
    )


class GameSession(Base):
    """Session de jeu Minecraft pour suivi du playtime"""
    __tablename__ = "game_sessions"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=False, index=True)
    minecraft_username = Column(String(50), nullable=False)
    
    login_time = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    logout_time = Column(DateTime, nullable=True)
    
    afk_detected = Column(Boolean, default=False)
    total_playtime_minutes = Column(Float, default=0.0)
    
    def __repr__(self):
        return f"<GameSession username={self.minecraft_username} login={self.login_time}>"


class MiniGameSession(Base):
    """Session de mini-jeu (Dice, CoinFlip, Roulette)"""
    __tablename__ = "mini_game_sessions"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    game_type = Column(String(30), nullable=False)  # dice, coinflip, roulette
    bet_amount = Column(Float, nullable=False)
    result = Column(String(20), nullable=False)  # win, loss, tie
    winnings = Column(Float, default=0.0)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    
    def __repr__(self):
        return f"<MiniGameSession user={self.user_id} game={self.game_type} result={self.result}>"
