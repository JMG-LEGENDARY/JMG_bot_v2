# JMG Bot v2 - Guide Complet des Commandes

## 📋 Index des Commandes

### 💰 Économie (CraftyCoin)

#### `/solde`
Affiche votre solde actuel en CraftyCoins et vos stats.
- **Réponse**: Embed avec solde, classement, stats (messages, caractères, réponses, temps de jeu)
- **Cooldown**: 5 secondes
- **Multiplicateurs affichés**: Messages, Playtime, Réponses

#### `/classement`
Affiche le top 10 des utilisateurs avec le plus de CraftyCoins.
- **Réponse**: Embed avec classement avec médailles (🥇🥈🥉)
- **Cooldown**: 10 secondes

#### `/daily`
Réclame votre récompense quotidienne.
- **Récompense**: Base 10 CC × 1.5^(jours consécutifs)
- **Cooldown**: 1 heure
- **Effet**: Reset à minuit UTC
- **Bonus**: Affiche les jours consécutifs et la récompense du jour suivant

#### `/transfert <@utilisateur> <montant>`
Transférez des CraftyCoins à un autre utilisateur.
- **Validations**: 
  - Montant > 0
  - Solde suffisant
  - Pas d'auto-transfert
  - Pas vers des bots
- **Historique**: Crée une transaction pour chacun

---

### 🛒 Boutique & Achats

#### `/shop`
Affiche tous les items disponibles à la boutique, catégorisés.
- **Catégories**: Armes, Armure, Outils, Construction, Nourriture, Potions, Enchantements, Divers
- **Infos par item**: Nom, Prix, Description
- **Format**: Embeds avec pagination si beaucoup d'items

#### `/buy <item_id> [quantity]`
Achète un item de la boutique.
- **Paramètres**:
  - `item_id`: ID numérique de l'item
  - `quantity`: Quantité (défaut: 1)
- **Validations**:
  - Item existe et disponible
  - Solde suffisant
  - Respect limite d'achat par utilisateur
- **Résultat**: Achat en "pending", sera livré à la connexion Minecraft
- **Coût**: Débité immédiatement

#### `/inventory`
Affiche vos achats en attente de livraison.
- **Status possibles**: ⏳ pending, ✅ completed
- **Infos**: Item, Quantité, Statut
- **Livraison automatique**: À la connexion du joueur au serveur

---

### 🎮 Serveur Minecraft (Crafty)

#### `/status`
Affiche le statut du serveur Minecraft.
- **Infos**: 
  - État (🟢 EN LIGNE / 🔴 HORS LIGNE)
  - Joueurs en ligne / max
  - CPU %
  - RAM utilisée
- **Cooldown**: 10 secondes
- **Permissions**: N/A (tout le monde)

#### `/start` [Manager Minecraft]
Démarre le serveur Minecraft.
- **Permission requise**: Role Manager Minecraft
- **Confirmation**: Oui/Non
- **Feedback**: Message de succès/erreur avec raison

#### `/stop` [Manager Minecraft]
Arrête le serveur Minecraft.
- **Permission requise**: Role Manager Minecraft
- **Confirmation**: Bouton danger "Oui, arrêter"
- **Message préventif**: "Êtes-vous sûr?"
- **Timeout**: 30 secondes

#### `/restart` [Manager Minecraft]
Redémarre le serveur Minecraft.
- **Permission requise**: Role Manager Minecraft
- **Feedback**: Message + temps estimé

#### `/cmd <commande>` [Manager Crafty]
Envoie une commande au serveur Minecraft.
- **Permission requise**: Role Manager Crafty
- **Format**: Avec ou sans "/" (ajouté automatiquement)
- **Exemples**:
  - `/cmd say Bienvenue!`
  - `/cmd give @a diamond 64`
- **Retour**: Confirmation de succès/erreur

---

### 📊 Statistiques

#### `/playtime`
Affiche votre temps de jeu total sur Minecraft.
- **Infos**:
  - Temps total (format: Xh Ym)
  - Multiplicateur de gains
  - Gains totaux en CraftyCoin
- **Calcul**: Temps × 0.5 × multiplicateur
- **Cooldown**: 10 secondes

---

### ⚙️ Admin

#### `/say <message>` [Admin]
Fait dire quelque chose au bot.
- **Permission requise**: Administrator
- **Usage**: Annonces, tests
- **Format**: Texte libre (max 2000 caractères Discord)

---

## 🎯 Système d'Économie Détaillé

### Comment Gagner des CraftyCoins

| Activité | Gain | Multiplicateur | Exemple |
|----------|------|---|---|
| Messages Discord | 0.1 × caractères | `message_multiplier` | 100 chars = 10 CC |
| Réponses aux gens | Même + bonus | `response_multiplier` (1.5x) | 100 chars + 50% = 15 CC |
| Aide (futur) | Même + bonus | `help_multiplier` (2.0x) | 100 chars × 2 = 20 CC |
| Temps vocal | 0.5 par minute | `playtime_multiplier` | 1h = 30 CC |
| Playtime Minecraft | 0.5 par minute | `playtime_multiplier` | 2h = 60 CC |
| Récompense quotidienne | 10 CC base | 1.5^(jours) | Jour 1: 10 CC, Jour 2: 15 CC, Jour 3: 22.5 CC |

### Anti-Spam & Sécurité

1. **Détection copier-coller**:
   - Similitude > 85% = flaggé et ignoré
   - Regarde les 5 derniers messages
   - Hash SHA-256 pour comparaison

2. **AFK en vocal**:
   - Détection après 10 min d'inactivité
   - Revient à 10% du gain normal
   - Détecte: mute, deafen, stream

3. **Spam prevention**:
   - Min 5 secondes entre messages
   - Limite par utilisateur

4. **Achat sans limite** (future):
   - Limite configurable par item
   - Cooldown entre achats

---

## 💎 Multiplicateurs Personnalisés

Chaque utilisateur peut avoir des multiplicateurs différents:

```
Utilisateur A:
  message_multiplier: 1.0x (défaut)
  playtime_multiplier: 1.0x (défaut)
  response_multiplier: 1.0x (défaut)

Utilisateur B (VIP):
  message_multiplier: 1.2x
  playtime_multiplier: 1.5x
  response_multiplier: 2.0x
```

### Comment obtenir des multiplicateurs?
- Récompenses (à implémenter)
- Niveaux/prestige
- Events
- Commandes mods

---

## 🎁 Exemple de Flow Achat

### User: JMG
1. `/shop` → Affiche tous les items
2. Sees: "diamond_pickaxe - 500 CC"
3. `/buy 1` → "Achat en attente de 500 CC"
4. Solde: 1000 CC → 500 CC
5. **JMG rejoint le serveur Minecraft**
6. Bot envoie: `/give JMG diamond_pickaxe 1`
7. `/inventory` → "✅ diamond_pickaxe (completed)"

---

## 🔔 Statuts & Événements

### Messages Discord Envoyés Automatiquement

- ✅ Achat confirmé (DM utilisateur)
- ✅ Achat livré (DM utilisateur)
- ✅ Transaction effectuée (solo)
- ✅ Classement mis à jour (quand TOP 10 change?)

### Événements Minecraft

- 🟢 Joueur rejoint → Message de bienvenue randomisé
- 🔴 Joueur quitte → Message d'au revoir randomisé
- ⏳ Playtime calculée → Coins crédités

### Logs

Tous les événements sont loggés:
- console (avec timestamps)
- `logs/bot.log` (rotation 10MB)
- `logs/errors.log` (erreurs uniquement)

---

## 🛠️ Configuration

Tous les paramètres sont dans `.env`:

```env
# Taux d'earning
MESSAGE_CHARACTER_RATE=0.1
VOICE_EARNING_RATE=0.5

# Récompense quotidienne
DAILY_REWARD_BASE=10
DAILY_REWARD_MULTIPLIER=1.5

# Anti-spam
SPAM_PREVENTION_TIME=5
ANTI_COPYPASTE_THRESHOLD=0.85
```

---

## 📞 Résolution de Problèmes

### "Vous n'êtes pas autorisé"
- Vérifiez que vous avez le bon rôle
- Contact: Managers

### "Solde insuffisant"
- `/solde` pour voir votre balance
- Gagnez des coins via messages/playtime
- Récompense quotidienne avec `/daily`

### "Item indisponible"
- L'item n'existe pas ou a été retiré de la vente
- Contact: Managers pour plus d'items

### Achat non reçu
- Vérifiez `/inventory`
- Assurez-vous que Minecraft username est lié
- Si problème persiste, contact: Managers

---

## 📋 Permissions Requises

| Commande | Permission | Rôle Discord |
|----------|---|---|
| /solde | N/A | Tous |
| /classement | N/A | Tous |
| /daily | N/A | Tous |
| /transfert | N/A | Tous |
| /shop | N/A | Tous |
| /buy | N/A | Tous |
| /inventory | N/A | Tous |
| /playtime | N/A | Tous |
| /status | N/A | Tous |
| /start | Manager Minecraft | manager_minecraft |
| /stop | Manager Minecraft | manager_minecraft |
| /restart | Manager Minecraft | manager_minecraft |
| /cmd | Manager Crafty | manager_crafty |
| /say | Administrator | Administrateur Discord |

---

**Dernière mise à jour**: Juin 2026 | **Version**: 2.0.0
