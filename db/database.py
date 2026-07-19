"""Gestion de la base de données SQLAlchemy"""
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from contextlib import contextmanager
from config import config
from db.models import Base
import logging

logger = logging.getLogger(__name__)


class Database:
    """Gestionnaire de base de données"""
    
    def __init__(self, database_url: str = None):
        self.database_url = database_url or config.DATABASE_URL
        self.engine = create_engine(
            self.database_url,
            connect_args={"check_same_thread": False} if "sqlite" in self.database_url else {},
            echo=config.DEBUG
        )
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
    
    def init_db(self):
        """Crée toutes les tables et met à jour le schéma pour SQLite."""
        Base.metadata.create_all(bind=self.engine)
        self._ensure_sqlite_columns()
        logger.info("✅ Base de données initialisée")

    def _ensure_sqlite_columns(self):
        """Ajoute les colonnes optionnelles manquantes pour SQLite existant."""
        if "sqlite" not in self.database_url:
            return

        with self.engine.connect() as conn:
            try:
                existing_columns = conn.execute(
                    text("PRAGMA table_info(users);")
                ).fetchall()
                existing_names = {row[1] for row in existing_columns}

                columns_to_add = []
                if "password_hash" not in existing_names:
                    columns_to_add.append(
                        "ALTER TABLE users ADD COLUMN password_hash VARCHAR(256)"
                    )
                if "is_authenticated" not in existing_names:
                    columns_to_add.append(
                        "ALTER TABLE users ADD COLUMN is_authenticated BOOLEAN DEFAULT 0"
                    )
                if "is_whitelisted" not in existing_names:
                    columns_to_add.append(
                        "ALTER TABLE users ADD COLUMN is_whitelisted BOOLEAN DEFAULT 0"
                    )
                if "last_activity" not in existing_names:
                    columns_to_add.append(
                        "ALTER TABLE users ADD COLUMN last_activity DATETIME"
                    )

                for sql in columns_to_add:
                    logger.info(f"🔧 Ajout de la colonne SQLite manquante : {sql}")
                    conn.execute(text(sql))
            except Exception as e:
                logger.error(f"Erreur lors de la vérification des colonnes SQLite: {e}")
                raise
    
    @contextmanager
    def get_session(self) -> Session:
        """Context manager pour obtenir une session DB"""
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Erreur DB: {e}")
            raise
        finally:
            session.close()
    
    def close(self):
        """Ferme la connexion à la DB"""
        self.engine.dispose()
        logger.info("🔌 Connexion DB fermée")


# Instance globale
db = Database()


# --- Helpers pour usage facile ---

def get_or_create_user(session: Session, discord_id: int):
    """Récupère ou crée un utilisateur"""
    from db.models import User
    user = session.query(User).filter(User.discord_id == discord_id).first()
    if not user:
        user = User(discord_id=discord_id)
        session.add(user)
        session.commit()
    return user


def find_user_by_minecraft_username(session: Session, minecraft_username: str):
    """Récupère un utilisateur par pseudo Minecraft"""
    from db.models import User
    return session.query(User).filter(User.minecraft_username == minecraft_username).first()


def set_user_password(session: Session, user_id: int, password_hash: str):
    """Assigne un hash de mot de passe à un utilisateur."""
    from db.models import User
    user = session.query(User).filter(User.id == user_id).first()
    if not user:
        return None
    user.password_hash = password_hash
    user.is_authenticated = False
    session.commit()
    return user


def authenticate_user(session: Session, discord_id: int, password: str):
    """Authentifie un utilisateur Discord via mot de passe Minecraft."""
    from db.models import User
    from utils.helpers import verify_password

    user = session.query(User).filter(User.discord_id == discord_id).first()
    if not user or not user.password_hash:
        return None
    if verify_password(password, user.password_hash):
        user.is_authenticated = True
        session.commit()
        return user
    return None


def add_transaction(session: Session, user_id: int, amount: float, transaction_type: str, 
                   description: str = None, base_amount: float = None, multiplier: float = 1.0):
    """Ajoute une transaction et met à jour le solde utilisateur"""
    from db.models import User, Transaction
    
    user = session.query(User).filter(User.id == user_id).first()
    if not user:
        logger.error(f"Utilisateur {user_id} non trouvé")
        return None
    
    # Ajouter la transaction
    transaction = Transaction(
        user_id=user_id,
        amount=amount,
        transaction_type=transaction_type,
        description=description,
        base_amount=base_amount,
        multiplier_applied=multiplier
    )
    session.add(transaction)
    
    # Mettre à jour le solde
    user.craftycoin_balance += amount
    user.last_activity = __import__('datetime').datetime.utcnow()
    
    session.commit()
    logger.info(f"Transaction: user_id={user_id}, amount={amount}, type={transaction_type}")
    return transaction


def get_user_rank(session: Session, user_id: int) -> int:
    """Retourne le rang d'un utilisateur par nombre de coins"""
    from db.models import User
    user = session.query(User).filter(User.id == user_id).first()
    if not user:
        return 0
    
    rank = session.query(User).filter(User.craftycoin_balance > user.craftycoin_balance).count()
    return rank + 1


def get_leaderboard(session: Session, limit: int = 10):
    """Retourne le classement des top utilisateurs"""
    from db.models import User
    return session.query(User).order_by(User.craftycoin_balance.desc()).limit(limit).all()
