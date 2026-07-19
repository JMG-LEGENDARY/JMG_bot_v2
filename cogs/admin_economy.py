import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timezone
import sqlalchemy.exc  # Importation essentielle pour capturer les erreurs de base de données

from db.database import db, get_or_create_user, add_transaction, get_leaderboard
from core.decorators import require_role, is_creator, handle_errors
from db.models import User, Transaction, ShopItem
from utils.logger import get_logger
from utils.formatters import create_embed

log = get_logger("admin_economy")


# --- Vue pour la confirmation du Reset ---
class ResetConfirmationView(discord.ui.View):
    def __init__(self, author: discord.User, timeout: float = 30.0):
        super().__init__(timeout=timeout)
        self.author = author
        self.value = None  # True si Confirm, False si Cancel, None si Timeout

    @discord.ui.button(label="Confirmer", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("Tu ne peux pas utiliser ce bouton !", ephemeral=True)
            return
        self.value = True
        self.stop()

    @discord.ui.button(label="Annuler", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.author:
            await interaction.response.send_message("Tu ne peux pas utiliser ce bouton !", ephemeral=True)
            return
        self.value = False
        self.stop()


class AdminEconomyCog(commands.Cog):
    """Administrative commands for economy management"""

    def __init__(self, bot):
        self.bot = bot
        self.session = db.get_session()  # Session DB pour ce cog

    @app_commands.command(name="admin-give", description="Give CraftyCoin to a user (Admin only)")
    @app_commands.checks.has_permissions(administrator=True)
    async def admin_give(self, interaction: discord.Interaction, user: discord.User, amount: int):
        """Give CraftyCoin to a user (Admin only)"""
        if amount <= 0:
            embed = create_embed(
                title="❌ Invalid Amount",
                description="Amount must be positive",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        user_obj = get_or_create_user(user.id, user.name)
        old_balance = user_obj.craftycoin_balance
        user_obj.craftycoin_balance += amount
        
        add_transaction(
            user_id=user_obj.id,
            amount=amount,
            transaction_type="admin_give",
            description=f"Admin gave {amount} CC (admin: {interaction.user.name})"
        )
        
        with self.session as session:
            session.add(user_obj)
            session.commit()
        
        embed = create_embed(title="✅ CraftyCoin Distributed", color=discord.Color.green())
        embed.add_field(name="User", value=user.mention, inline=True)
        embed.add_field(name="Amount", value=f"+{amount} CC", inline=True)
        embed.add_field(name="Old Balance", value=f"{old_balance} CC", inline=True)
        embed.add_field(name="New Balance", value=f"{user_obj.craftycoin_balance} CC", inline=True)
        embed.add_field(name="Admin", value=interaction.user.mention, inline=True)
        embed.timestamp = datetime.now(timezone.utc)
        
        await interaction.response.send_message(embed=embed)
        log.info(f"🎁 Admin {interaction.user} gave {amount} CC to {user} (balance: {old_balance} → {user_obj.craftycoin_balance})")

    @app_commands.command(name="admin-set", description="Set CraftyCoin balance for a user (Admin only)")
    @app_commands.checks.has_permissions(administrator=True)
    async def admin_set(self, interaction: discord.Interaction, user: discord.User, amount: int):
        """Set CraftyCoin balance for a user (Admin only)"""
        if amount < 0:
            embed = create_embed(
                title="❌ Invalid Amount",
                description="Amount cannot be negative",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        user_obj = get_or_create_user(user.id, user.name)
        old_balance = user_obj.craftycoin_balance
        diff = amount - old_balance
        user_obj.craftycoin_balance = amount
        
        add_transaction(
            user_id=user_obj.id,
            amount=diff,
            transaction_type="admin_set",
            description=f"Admin set balance to {amount} CC (was {old_balance} CC, admin: {interaction.user.name})"
        )
        
        with self.session as session:
            session.add(user_obj)
            session.commit()
        
        embed = create_embed(title="✅ Balance Set", color=discord.Color.green())
        embed.add_field(name="User", value=user.mention, inline=True)
        embed.add_field(name="Old Balance", value=f"{old_balance} CC", inline=True)
        embed.add_field(name="New Balance", value=f"{amount} CC", inline=True)
        embed.add_field(name="Difference", value=f"{diff:+.0f} CC", inline=True)
        embed.add_field(name="Admin", value=interaction.user.mention, inline=True)
        embed.timestamp = datetime.now(timezone.utc)
        
        await interaction.response.send_message(embed=embed)
        log.info(f"⚙️  Admin {interaction.user} set {user}'s balance to {amount} CC (was {old_balance} CC)")

    @app_commands.command(name="admin-reset", description="Reset CraftyCoin balance to 0 (Admin only)")
    @app_commands.checks.has_permissions(administrator=True)
    async def admin_reset(self, interaction: discord.Interaction, user: discord.User):
        """Reset CraftyCoin balance to 0 (Admin only)"""
        user_obj = get_or_create_user(user.id, user.name)
        old_balance = user_obj.craftycoin_balance
        
        embed = create_embed(
            title="⚠️  Confirm Reset",
            description=f"Reset {user.mention}'s balance from {old_balance} CC to 0?\nThis cannot be undone!",
            color=discord.Color.gold()
        )
        
        view = ResetConfirmationView(author=interaction.user, timeout=30.0)
        await interaction.response.send_message(embed=embed, view=view)
        
        msg = await interaction.original_response()
        await view.wait()
        
        for item in view.children:
            item.disabled = True
        await msg.edit(view=view)

        if view.value is None:  # Timeout
            embed_timeout = create_embed(
                title="⏱️ Timeout",
                description="Reset confirmation timed out",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed_timeout)
            
        elif view.value is True:  # Confirmé
            user_obj.craftycoin_balance = 0
            add_transaction(
                user_id=user_obj.id,
                amount=-old_balance,
                transaction_type="admin_reset",
                description=f"Admin reset balance from {old_balance} CC to 0 (admin: {interaction.user.name})"
            )
            with self.session as session:
                session.add(user_obj)
                session.commit()

            embed_success = create_embed(title="✅ Balance Reset", color=discord.Color.green())
            embed_success.add_field(name="User", value=user.mention, inline=True)
            embed_success.add_field(name="Old Balance", value=f"{old_balance} CC", inline=True)
            embed_success.add_field(name="New Balance", value="0 CC", inline=True)
            embed_success.add_field(name="Admin", value=interaction.user.mention, inline=True)
            embed_success.timestamp = datetime.now(timezone.utc)
            await interaction.followup.send(embed=embed_success)
            log.info(f"🔄 Admin {interaction.user} reset {user}'s balance from {old_balance} CC to 0")
            
        else:  # Annulé
            embed_cancel = create_embed(title="❌ Cancelled", description="Reset cancelled", color=discord.Color.red())
            await interaction.followup.send(embed=embed_cancel)

    @app_commands.command(name="admin-item-add", description="Add item to shop (Admin only)")
    @app_commands.checks.has_permissions(administrator=True)
    async def admin_item_add(self, interaction: discord.Interaction, name: str, price: int, command: str, category: str = "misc"):
        """Add item to shop (Admin only)"""
        if price <= 0:
            embed = create_embed(title="❌ Invalid Price", description="Price must be positive", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        if "{player}" not in command:
            embed = create_embed(title="❌ Invalid Command", description="Command must contain {player} placeholder", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        item = ShopItem(name=name, price=price, minecraft_command=command, category=category, is_available=True)
        
        try:
            with self.session as session:
                session.add(item)
                session.commit()
        except sqlalchemy.exc.IntegrityError:
            self.session.rollback()  # Annule la transaction corrompue
            embed = create_embed(
                title="❌ Item Already Exists", 
                description=f"An item named `{name}` is already in the shop database. Choose a unique name or use `/admin-item-edit`.", 
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        embed = create_embed(title="✅ Item Added", color=discord.Color.green())
        embed.add_field(name="Name", value=name, inline=True)
        embed.add_field(name="Price", value=f"{price} CC", inline=True)
        embed.add_field(name="Category", value=category, inline=True)
        embed.add_field(name="Command", value=f"`{command}`", inline=False)
        embed.add_field(name="Admin", value=interaction.user.mention, inline=True)
        embed.timestamp = datetime.now(timezone.utc)
        
        await interaction.response.send_message(embed=embed)
        log.info(f"🛒 Admin {interaction.user} added item: {name} ({price} CC)")

    @app_commands.command(name="admin-item-edit", description="Edit an existing shop item (Admin only)")
    @app_commands.checks.has_permissions(administrator=True)
    async def admin_item_edit(self, interaction: discord.Interaction, item_id: int, field: str, *, value: str):
        """Edit an existing shop item (Admin only)"""
        with self.session as session:
            item = session.query(ShopItem).filter(ShopItem.id == item_id).first()
        if not item:
            embed = create_embed(title="❌ Item introuvable", description=f"Aucun item trouvé avec l'ID {item_id}.", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        field = field.lower()
        if field == "name":
            item.name = value
        elif field == "price":
            try:
                price_value = int(value)
                if price_value <= 0:
                    raise ValueError
                item.price = price_value
            except ValueError:
                embed = create_embed(title="❌ Prix invalide", description="Le prix doit être un entier strictement positif.", color=discord.Color.red())
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
        elif field == "command":
            if "{player}" not in value and "{joueur}" not in value:
                embed = create_embed(title="❌ Commande invalide", description="La commande doit contenir le placeholder {player} ou {joueur}.", color=discord.Color.red())
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            item.minecraft_command = value
        elif field == "category":
            item.category = value
        elif field == "available":
            normalized = value.strip().lower()
            if normalized in ["true", "1", "yes", "oui"]:
                item.is_available = True
            elif normalized in ["false", "0", "no", "non"]:
                item.is_available = False
            else:
                embed = create_embed(title="❌ Valeur invalide", description="Utilise true/false ou oui/non pour available.", color=discord.Color.red())
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
        else:
            embed = create_embed(title="❌ Champ inconnu", description="Champs valides: name, price, command, category, available.", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        try:
            with self.session as session:
                session.add(item)
                session.commit()
        except sqlalchemy.exc.IntegrityError:
            self.session.rollback()
            embed = create_embed(
                title="❌ Nom déjà utilisé", 
                description="Ce nom d'item existe déjà dans la base de données.", 
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        embed = create_embed(title="✅ Item mis à jour", color=discord.Color.green())
        embed.add_field(name="ID", value=str(item.id), inline=True)
        embed.add_field(name="Name", value=item.name, inline=True)
        embed.add_field(name="Price", value=f"{item.price} CC", inline=True)
        embed.add_field(name="Category", value=item.category, inline=True)
        embed.add_field(name="Available", value=str(item.is_available), inline=True)
        await interaction.response.send_message(embed=embed)
        log.info(f"✏️ Admin {interaction.user} edited item {item.id} field {field}")

    @app_commands.command(name="admin-multiplier", description="Set multiplier for user (Admin only)")
    @app_commands.checks.has_permissions(administrator=True)
    async def admin_multiplier(self, interaction: discord.Interaction, user: discord.User, mult_type: str, value: float):
        """Set multiplier for user (Admin only)"""
        if mult_type.lower() not in ["message", "playtime", "response"]:
            embed = create_embed(title="❌ Invalid Type", description="Use: message, playtime, or response", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        if value < 0:
            embed = create_embed(title="❌ Invalid Multiplier", description="Multiplier cannot be negative", color=discord.Color.red())
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        user_obj = get_or_create_user(user.id, user.name)
        mult_type = mult_type.lower() + "_multiplier"
        old_value = getattr(user_obj, mult_type)
        setattr(user_obj, mult_type, value)
        
        with self.session as session:
            session.add(user_obj)
            session.commit()
        
        embed = create_embed(title="✅ Multiplier Updated", color=discord.Color.green())
        embed.add_field(name="User", value=user.mention, inline=True)
        embed.add_field(name="Type", value=mult_type.replace("_", " ").title(), inline=True)
        embed.add_field(name="Old Value", value=f"{old_value}x", inline=True)
        embed.add_field(name="New Value", value=f"{value}x", inline=True)
        embed.add_field(name="Admin", value=interaction.user.mention, inline=True)
        embed.timestamp = datetime.now(timezone.utc)
        
        await interaction.response.send_message(embed=embed)
        log.info(f"📊 Admin {interaction.user} set {user}'s {mult_type} to {value}x")

    @app_commands.command(name="admin-transactions", description="View user's transaction history (Admin only)")
    @app_commands.checks.has_permissions(administrator=True)
    async def admin_transactions(self, interaction: discord.Interaction, user: discord.User, limit: int = 20):
        """View user's transaction history (Admin only)"""
        user_obj = get_or_create_user(user.id, user.name)
        
        transactions = self.session.query(Transaction).filter(
            Transaction.user_id == user_obj.id
        ).order_by(Transaction.created_at.desc()).limit(limit).all()
        
        if not transactions:
            embed = create_embed(title="📊 Transaction History", description=f"No transactions for {user.mention}", color=discord.Color.blue())
            await interaction.response.send_message(embed=embed)
            return
        
        embed = create_embed(title="📊 Transaction History", description=f"Last {len(transactions)} transactions", color=discord.Color.blue())
        
        for txn in transactions[:10]:
            sign = "+" if txn.amount > 0 else "-"
            emoji = "📈" if txn.amount > 0 else "📉"
            
            embed.add_field(
                name=f"{emoji} {txn.transaction_type.upper()}",
                value=f"{sign}{abs(txn.amount)} CC · {txn.created_at.strftime('%Y-%m-%d %H:%M')}",
                inline=False
            )
        
        embed.set_footer(text=f"Showing {min(10, len(transactions))} of {len(transactions)} transactions")
        await interaction.response.send_message(embed=embed)
        log.info(f"📊 Admin {interaction.user} viewed {user}'s transactions")


async def setup(bot):
    await bot.add_cog(AdminEconomyCog(bot))
    log.info("✅ AdminEconomyCog loaded")