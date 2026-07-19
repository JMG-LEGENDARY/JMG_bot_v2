# JMG Bot v2 🤖

Bot Discord pour gestion d'un serveur Minecraft avec système d'économie **CraftyCoin**.

---

## 📋 Fonctionnalités

- **Serveur Minecraft (Crafty / Serveur Minecraft)**  
  Gestion du serveur (démarrage / arrêt / statut) via l’intégration Crafty.
- **Économie CraftyCoin**  
  Attribution de CraftyCoins basée sur l’activité **Discord** et **Minecraft**, avec multiplicateurs paramétrables.
- **Shop**  
  Boutique d’items Minecraft achetables avec CraftyCoins, avec livraison automatique côté Minecraft.
- **Anti-spam**
  - Détection de copier-coller
  - Détection AFK en vocal
- **Événements Minecraft**
  - Détection des joueurs qui rejoignent / quittent
- **Messages personnalisés**
  - Bienvenue / au revoir randomisés

---

## 🏗️ Structure du Projet

```text
JMG_BOT v2/
├── main.py                 # Point d'entrée du bot (initialisation + sync slash)
├── config.py              # Configuration centralisée (.env)
├── crafty_api.py          # Intégration API Crafty
├── requirements.txt       # Dépendances Python
│
├── cogs/                  # Modules fonctionnalités (extensions Discord)
│   ├── commands.py        # Commandes générales (slash)
│   ├── admin.py           # Admin (autres actions)
│   ├── admin_economy.py   # Admin économie (CraftyCoin + shop admin)
│   ├── crafty.py          # Gestion du serveur Minecraft
│   ├── economy.py         # Système CraftyCoin (implémentation principale)
│   ├── minecraft.py       # Événements Minecraft
│   ├── events.py          # Events Discord/monitoring
│   ├── welcome.py         # Messages bienvenue/au revoir
│   ├── shop.py            # Shop joueur (commandes d'achat / catalogue)
│   ├── purchase.py       # Gestion pending purchases / livraison / statut
│   ├── minigames.py       # Minijeux / sessions (si applicable)
│   ├── monitoring.py      # Monitoring (vocal, anti-spam, etc.)
│   └── ticket_link.py    # Liaison ticket Discord <-> Minecraft (si applicable)
│
├── core/                  # Modules noyau
│   ├── decorators.py     # Décorateurs (checks, gestion d’erreurs, logs)
│   └── constants.py      # Constantes globales
│
├── db/                    # Base de données (SQLAlchemy)
│   ├── database.py       # Connexion + helpers SQLAlchemy
│   └── models.py         # Modèles SQLAlchemy (Users, Transactions, ShopItem, etc.)
│
├── utils/                 # Utilitaires
│   ├── logger.py         # Logger
│   ├── formatters.py     # Création d'Embeds Discord
│   └── helpers.py        # Fonctions utilitaires
│
└── logs/                  # Fichiers de log
```

---

## 🚀 Installation

### 1. Prérequis
- Python **3.10+**
- pip

### 2. Environnement virtuel
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# ou
venv\Scripts\activate     # Windows
```

### 3. Installer les dépendances
```bash
pip install -r requirements.txt
```

### 4. Configuration
```bash
cp .env.example .env
```

---

## 🧩 Configuration `.env`

Exemple (à compléter selon votre `.env.example`) :

```env
# Bot Discord
BOT_TOKEN=votre_token_ici
MC_JOIN_TOKEN=token_du_bot_minecraft

# Crafty
CRAFTY_BASE_URL=https://votre_ip:8443
CRAFTY_API_TOKEN=votre_token_crafty
CRAFTY_SERVER_ID=id_du_serveur

# Discord
MCF_GUILD_ID=id_du_serveur_discord

# Économie
MESSAGE_CHARACTER_RATE=0.1
VOICE_EARNING_RATE=0.5
```

⚠️ Ne mettez **jamais** vos tokens en dur dans le code.

---

## 🧠 Démarrage du bot (main.py)

Le bot :
1. **valide la configuration** via `validate_config()`
2. **initialise la base de données** via `db.init_db()`
3. charge les **cogs** dans `setup_hook()` (ordre de chargement important)
4. **sync** les commandes slash : `self.tree.sync()`

### Cogs chargés (liste actuelle)
Dans `main.py`, `setup_hook()` charge notamment :
- `cogs.admin_economy`
- `cogs.economy`
- `cogs.shop`
- `cogs.purchase`
- `cogs.monitoring`
- etc.

---

## 💰 Système d'Économie — CraftyCoin

### Principe général
- Les joueurs gagnent des **CraftyCoins** via leur activité.
- Les gains sont enregistrés en base via des **transactions**.
- Les soldes sont persistés dans la table **Users** (champ `craftycoin_balance`).

### Exemple (modèle de gains actuel — doc)
| Activité | Revenu de base | Multiplicateur |
|----------|------------------|----------------|
| Message Discord | `0.1 × caractères` | `1.0x` |
| Réponse aux gens | Même que message | `1.5x` |
| Aide apportée | Même que message | `2.0x` |
| Temps vocal | `0.5 par minute` | `1.0x` |
| Playtime Minecraft | Basé sur durée | `1.0x` |
| Récompense quotidienne | `10 CC` | `+1.5x par jour` |

> Les valeurs exactes viennent de `.env` + implémentation des cogs d’économie.

---

## 🔒 Anti-spam (résumé)
- **Copier-coller** : messages similaires à **> 85%** sont flaggés
- **AFK vocal** : timeout après **10 minutes** d’inactivité
- **Limite de messages** : anti-spam activé avec un délai minimum (~ **5s**)

---

## 🛒 Shop (joueur) — commandes & modèle

Le shop repose sur deux notions DB :
- **`ShopItem`** : catalogue des items disponibles (prix, catégorie, commande Minecraft, etc.)
- **`PendingPurchase`** : achats en attente de livraison

### Commande `/shop`
**But** : afficher la boutique (items groupés par `category`).

- Affiche uniquement les items avec `is_available == True`
- Si plusieurs catégories : plusieurs embeds (avec navigation *non implémentée* dans l’actuel code : callbacks `pass`).

### Commande `/buy`
**But** : acheter un item.

**Paramètres**
- `item_id` : ID de l’item (int)
- `quantity` : quantité (défaut `1`)

**Validations / logique**
- `quantity >= 1`
- item existe et est disponible
- limite d’achat par utilisateur si `max_purchase_per_user` est configuré
- vérifie que l’utilisateur est **authentifié Minecraft** (`/minecraft login`)
- vérifie le solde `craftycoin_balance`

**Effet**
- débite le solde
- crée un `PendingPurchase(status="pending")`
- répond avec un embed “achat en attente” (éphémère)

### Commande `/reclamer_achat`
**But** : réclamer la livraison de ses achats en attente.

**Validations**
- l’utilisateur doit être lié à un pseudo Minecraft
- l’utilisateur doit être authentifié

**Effet**
- appelle le cog `PurchaseCog` pour livrer les achats (si l’utilisateur est “online” en jeu)
- sinon : renvoie un embed expliquant que la livraison aura lieu à la prochaine connexion

### Commande `/inventory`
**But** : afficher tes achats en attente.

- liste les `PendingPurchase` avec `status in ("pending", "completed")` (d’après le code actuel)

> Remarque : le fichier contient aussi une boucle `check_pending_purchases` (toutes les 30s) mais avec `pass`/TODO ; la logique de livraison semble centrée sur la réclamation et/ou des events dans d’autres cogs.


---

## 🧾 Commandes — aperçu par cog

Les commandes ci-dessous sont des **commandes slash** (``/commande``). Le README documente en détail `cogs/admin_economy.py` et ajoute ici l’aperçu des autres commandes déjà présentes dans les cogs relues.

### Commandes générales (`cogs/commands.py`)
- `/ping` : affiche la latence du bot

### Économie (`cogs/economy.py`)
- `/solde` : affiche ton solde CraftyCoin + stats + multiplicateurs
- `/classement` : affiche le top 10 CraftyCoin
- `/daily` : réclame la récompense quotidienne (avec cooldown + streak)
- `/transfert` : transfère des CraftyCoins à un autre utilisateur

### Shop joueur (`cogs/shop.py`)
- `/shop` : affiche la boutique
- `/buy` : achète un item (crée `PendingPurchase`, débite le solde)
- `/reclamer_achat` : déclenche la livraison via `PurchaseCog` si connecté
- `/inventory` : affiche les achats en attente

### Tickets & Auth Minecraft (`cogs/ticket_link.py`)
- `setup-tickets` (admin) : déploie l’interface de tickets (boutons)
- Sous-groupe `minecraft` :
  - `/minecraft set_password` : définit / change un mot de passe
  - `/minecraft login` : authentifie et permet ensuite l’accès shop/achats

### Purchase (livraison) (`cogs/purchase.py`)
- Pas de commandes slash dédiées ici : le cog livre automatiquement les achats via une boucle/événements et/ou quand un joueur réclame.

### Monitoring (`cogs/monitoring.py`)
- `/bot-status` : status santé/bot (staff)
- `/bot-errors` : affiche les erreurs récentes (admin)

### Events Discord (`cogs/events.py`)
- Pas de commandes slash : calcule les gains message/anti-spam + gains vocal, et détecte certains events (logs Crafty).

### Mini-jeux / casino (`cogs/minigames.py`)
- `/dice` : jeu de dé + pari (avec chance de jackpot)
- `/coinflip` : pile ou face
- `/roulette` : roulette européenne
- `/stats` : affiche les statistiques de jeu d’un utilisateur

---

## 💎 Commandes admin économie (détaillées : `cogs/admin_economy.py`)

Toutes les commandes ci-dessous sont définies comme **commandes slash** et sont réservées à un admin via `@app_commands.checks.has_permissions(administrator=True)` (permission Discord : Administrateur).


### 1) `/admin-give`
**Description** : donne un montant de CraftyCoins à un utilisateur.

- **Paramètres**
  - `user` : discord.User
  - `amount` : int (doit être **> 0**)

**Comportement**
- Refuse si `amount <= 0`
- Récupère / crée l’utilisateur : `get_or_create_user(user.id, user.name)`
- Met à jour `craftycoin_balance += amount`
- Crée une transaction :
  - `transaction_type="admin_give"`
  - description : admin + montant
- Commit DB
- Répond avec un embed succès + log

**Exemple**
- `/admin-give user:@Bob amount:100`

---

### 2) `/admin-set`
**Description** : définit le solde CraftyCoins exact d’un utilisateur.

- **Paramètres**
  - `user` : discord.User
  - `amount` : int (doit être **>= 0**)

**Comportement**
- Refuse si `amount < 0`
- Calcule la différence : `diff = amount - old_balance`
- Met à jour : `craftycoin_balance = amount`
- Crée une transaction :
  - `transaction_type="admin_set"`
  - `amount=diff` (peut être positif ou négatif selon le cas)
- Commit DB + embed succès + log

**Exemple**
- `/admin-set user:@Bob amount:250`

---

### 3) `/admin-reset`
**Description** : remet le solde CraftyCoin de l’utilisateur à **0**, avec confirmation UI.

- **Paramètres**
  - `user` : discord.User

**Comportement**
- Envoie un embed **“⚠️ Confirm Reset”** + une `ResetConfirmationView` :
  - bouton **Confirmer** (danger)
  - bouton **Annuler**
- Gère :
  - timeout (`view.value is None`) → message “timed out”
  - annulé → message “Reset cancelled”
  - confirmé → `craftycoin_balance = 0` + transaction :
    - `transaction_type="admin_reset"`
    - `amount=-old_balance`
- Commit DB + embed succès + log

**Exemple**
- `/admin-reset user:@Bob`

---

### 4) `/admin-item-add`
**Description** : ajoute un item dans la boutique (shop).

- **Paramètres**
  - `name` : str
  - `price` : int (**> 0**)
  - `command` : str (commande Minecraft template)
  - `category` : str (par défaut `"misc"`)

**Contraintes**
- `price` doit être strictement positif
- La commande `command` doit contenir un placeholder :
  - **`{player}`** (obligatoire selon validation dans ce fichier)
  - (le fichier admin-item-edit accepte aussi `{joueur}` en plus)

**Comportement**
- Crée un `ShopItem` avec :
  - `is_available=True`
  - `minecraft_command=command`
  - `category=category`
- En cas de doublon (IntegrityError) :
  - rollback
  - embed “Item Already Exists”
- Embed succès + log

**Exemple**
- `/admin-item-add name:"Kit Miner" price:500 category:"mining" command:"give {player} minecraft:iron_pickaxe 1"`

---

### 5) `/admin-item-edit`
**Description** : modifie un item existant.

- **Paramètres**
  - `item_id` : int
  - `field` : str
  - `value` : str (format “*” permet “rest of line”)

**Champs supportés (case-insensitive)**
- `name`
- `price` (converti en int, doit être **> 0**)
- `command` (doit contenir `{player}` ou `{joueur}`)
- `category`
- `available` (valeurs acceptées :
  - true/1/yes/ou i
  - false/0/no/non)

**Comportement**
- Récupère l’item par ID
- Refuse si item introuvable
- Met à jour le champ ciblé
- Commit DB, gère IntegrityError
- Répond avec un embed récap + log

**Exemples**
- `/admin-item-edit item_id:12 field:price value:750`
- `/admin-item-edit item_id:12 field:available value:false`

---

### 6) `/admin-multiplier`
**Description** : règle les multiplicateurs d’économie d’un utilisateur.

- **Paramètres**
  - `user` : discord.User
  - `mult_type` : str
    - autorisé : `message`, `playtime`, `response`
  - `value` : float (doit être **>= 0**)

**Comportement**
- Valide `mult_type`
- Construit le champ :
  - `message_multiplier`
  - `playtime_multiplier`
  - `response_multiplier`
- Met à jour la valeur
- Commit DB + embed succès + log

**Exemple**
- `/admin-multiplier user:@Bob mult_type:message value:1.75`

---

### 7) `/admin-transactions`
**Description** : affiche l’historique des transactions d’un utilisateur (limité).

- **Paramètres**
  - `user` : discord.User
  - `limit` : int (par défaut `20`, affichage embed tronqué à 10 champs)

**Comportement**
- Récupère l’utilisateur
- Query transactions :
  - triées par `created_at desc`
  - limité à `limit`
- Si aucune transaction :
  - embed “No transactions…”
- Sinon :
  - embed “Last N transactions”
  - affiche jusqu’à 10 transactions avec :
    - `+` / `-`
    - emoji `📈` / `📉`
- log

**Exemple**
- `/admin-transactions user:@Bob limit:50`

---

## 🧱 Base de Données (résumé)

Utilisation de **SQLAlchemy + SQLite** (persistant) :

- **Users**
  - balance CraftyCoin (`craftycoin_balance`)
  - multiplicateurs (message/playtime/response)
  - etc.
- **ShopItems & PendingPurchases**
- **Transactions**
  - historique gains/pertes (admin inclus)
- **GameSessions** (playtime)
- **AntiSpamRecords** (copier-coller)
- **VoiceActivity** (AFK vocal)

---

## 📊 Logging

- Logs console + fichiers dans `logs/`
- Niveau configurable via `.env` (voir `utils/logger.py`)
- Erreurs et logs séparés (ex: `errors.log` si configuré)

---

## ⚠️ Sécurité

- Ne jamais commit le `.env`
- `.env` est ignoré via `.gitignore`
- utiliser `.env.example` comme référence de documentation

---

## 🛠️ Développement

### Ajouter un nouveau cog
```python
# cogs/my_feature.py
import discord
from discord.ext import commands
from core.decorators import log_command

class MyCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="mycommand")
    @log_command
    async def my_command(self, interaction: discord.Interaction):
        await interaction.response.send_message("Hello!")

async def setup(bot):
    await bot.add_cog(MyCog(bot))
```

### Ajouter une transaction (exemple)
```python
from db import db, add_transaction

with db.get_session() as session:
    add_transaction(
        session=session,
        user_id=user.id,
        amount=10.0,
        transaction_type="message",
        description="Message envoyé",
        multiplier=1.5
    )
```

---

## 📞 Support

Questions ? Contactez les Managers ou consultez les logs.

---

**Dernière mise à jour :** Juin 2026  
**Version :** 2.0.0
