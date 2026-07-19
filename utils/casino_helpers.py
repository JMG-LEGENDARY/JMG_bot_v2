"""
Casino helpers - Rules enforcement, anti-farming, bet validation
"""

from datetime import datetime, timedelta
from db.database import db
from db.models import Transaction, MiniGameSession, User
from utils.logger import get_logger

log = get_logger("casino")


class CasinoRulesEngine:
    """Enforces casino rules and anti-farming measures"""

    # Configuration
    DAILY_LIMIT_CC = 5000
    PER_GAME_LIMIT_CC = 1000
    MIN_BALANCE_TO_PLAY = 100
    GAME_COOLDOWN_SECONDS = 30
    
    def __init__(self):
        self.session = db()

    def validate_bet(self, user_id: int, bet_amount: int) -> tuple[bool, str]:
        """
        Validate bet against all rules
        
        Returns: (is_valid, error_message)
        """
        
        # Get user
        user = self.session.query(User).filter(User.discord_id == user_id).first()
        if not user:
            return False, "User not found"
        
        # Check balance to play
        if user.craftycoin_balance < self.MIN_BALANCE_TO_PLAY:
            return False, f"Need {self.MIN_BALANCE_TO_PLAY} CC minimum to play"
        
        # Check per-game limit
        if bet_amount > self.PER_GAME_LIMIT_CC:
            return False, f"Maximum bet per game: {self.PER_GAME_LIMIT_CC} CC"
        
        # Check sufficient balance
        if user.craftycoin_balance < bet_amount:
            return False, f"Insufficient balance ({user.craftycoin_balance} CC)"
        
        # Check daily limit
        today = datetime.utcnow().date()
        today_start = datetime.combine(today, datetime.min.time())
        
        daily_spent = self.session.query(
            db.func.sum(MiniGameSession.bet_amount)
        ).filter(
            MiniGameSession.user_id == user.id,
            MiniGameSession.created_at >= today_start
        ).scalar() or 0
        
        if daily_spent + bet_amount > self.DAILY_LIMIT_CC:
            remaining = self.DAILY_LIMIT_CC - daily_spent
            return False, f"Daily limit reached. Can bet max {remaining} CC today"
        
        return True, "OK"

    def check_anti_farming(self, user_id: int, game_type: str) -> tuple[bool, str]:
        """
        Check for farming patterns (rapid wins, copied bets, etc)
        
        Returns: (is_legit, warning_message)
        """
        
        user = self.session.query(User).filter(User.discord_id == user_id).first()
        if not user:
            return False, "User not found"
        
        # Check win rate (should not exceed 60% - suspicious)
        last_10_games = self.session.query(MiniGameSession).filter(
            MiniGameSession.user_id == user.id,
            MiniGameSession.game_type == game_type
        ).order_by(MiniGameSession.created_at.desc()).limit(10).all()
        
        if len(last_10_games) >= 10:
            wins = len([g for g in last_10_games if g.result == "win"])
            win_rate = wins / 10
            
            if win_rate > 0.7:  # More than 70% wins in last 10 games
                log.warning(f"⚠️  Suspicious win rate: {user.discord_id} has {win_rate:.0%} win rate")
                return True, f"⚠️  Unusual win rate detected ({win_rate:.0%})"
        
        # Check for patterns (same bet amounts repeatedly)
        last_5_bets = self.session.query(MiniGameSession).filter(
            MiniGameSession.user_id == user.id
        ).order_by(MiniGameSession.created_at.desc()).limit(5).all()
        
        if len(last_5_bets) >= 5:
            bet_amounts = [g.bet_amount for g in last_5_bets]
            if len(set(bet_amounts)) == 1:  # All same bet amount
                log.warning(f"⚠️  Pattern detected: {user.discord_id} repeating bet amount")
        
        return True, "OK"

    def get_daily_remaining(self, user_id: int) -> float:
        """Get remaining daily betting limit"""
        user = self.session.query(User).filter(User.discord_id == user_id).first()
        if not user:
            return 0
        
        today = datetime.utcnow().date()
        today_start = datetime.combine(today, datetime.min.time())
        
        daily_spent = self.session.query(
            db.func.sum(MiniGameSession.bet_amount)
        ).filter(
            MiniGameSession.user_id == user.id,
            MiniGameSession.created_at >= today_start
        ).scalar() or 0
        
        return max(0, self.DAILY_LIMIT_CC - daily_spent)

    def log_game_session(self, user_id: int, game_type: str, bet: float, 
                        result: str, winnings: float = 0) -> MiniGameSession:
        """Create and log a game session"""
        
        user = self.session.query(User).filter(User.discord_id == user_id).first()
        if not user:
            raise ValueError("User not found")
        
        session = MiniGameSession(
            user_id=user.id,
            game_type=game_type,
            bet_amount=bet,
            result=result,
            winnings=winnings
        )
        
        self.session.add(session)
        self.session.commit()
        
        log.info(f"🎰 Game: {game_type} - User {user_id} - Bet {bet} CC - {result.upper()} - Won {winnings} CC")
        
        return session

    def get_user_stats(self, user_id: int) -> dict:
        """Get comprehensive user gaming stats"""
        
        user = self.session.query(User).filter(User.discord_id == user_id).first()
        if not user:
            return {}
        
        sessions = self.session.query(MiniGameSession).filter(
            MiniGameSession.user_id == user.id
        ).all()
        
        if not sessions:
            return {
                "total_games": 0,
                "wins": 0,
                "losses": 0,
                "ties": 0,
                "win_rate": 0,
                "total_bet": 0,
                "total_winnings": 0
            }
        
        wins = len([s for s in sessions if s.result == "win"])
        losses = len([s for s in sessions if s.result == "loss"])
        ties = len([s for s in sessions if s.result == "tie"])
        total_bet = sum([s.bet_amount for s in sessions])
        total_winnings = sum([s.winnings for s in sessions])
        
        return {
            "total_games": len(sessions),
            "wins": wins,
            "losses": losses,
            "ties": ties,
            "win_rate": wins / len(sessions) if sessions else 0,
            "total_bet": total_bet,
            "total_winnings": total_winnings,
            "net_profit": total_winnings - total_bet
        }


# Global instance
casino_engine = CasinoRulesEngine()
