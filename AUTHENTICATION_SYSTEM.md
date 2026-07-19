# Système d'Authentification Minecraft

## 📋 Vue d'ensemble

Le bot gère maintenant une authentification à deux niveaux :
1. **Vérification d'enregistrement** : À la connexion, le bot vérifie que le joueur est dans la DB
2. **Authentification par mot de passe** : Le joueur doit entrer `/login <password>` pour jouer

## 🔄 Flux de connexion

### Scénario 1 : Joueur NON enregistré
```
1. Joueur rejoint le serveur
2. Bot cherche le pseudo dans la DB
3. Pseudo NON trouvé → `/kick Pseudo [Sécurité] Tu n'es pas whitelisté.`
4. Logs Discord : ❌ Kick automatique
```

### Scénario 2 : Joueur enregistré, première connexion
```
1. Joueur rejoint le serveur
2. Bot cherche le pseudo dans la DB → trouvé
3. Bot réinitialise is_authenticated = False (même s'il était True avant)
4. GameSession créée (login_time enregistré)
5. Bot applique les effets de freeze :
   - /effect give Pseudo blindness 999999 0 true
   - /effect give Pseudo slowness 999999 2 true
6. Bot envoie : /tellraw Pseudo {"text":"[Sécurité] Connecte-toi avec : /login <ton_mot_de_passe>","color":"red"}
7. Logs Discord : 🔒 En attente d'authentification
```

### Scénario 3 : Joueur entre la bonne commande `/login`
```
1. Bot détecte : [HH:MM:SS] [Server thread/INFO]: Pseudo issued server command: /login bonMotDePasse
2. Rate limiting check : OK (< 5 tentatives en 5 min)
3. Password hash check : ✅ Valide
4. Bot met à jour : is_authenticated = True
5. Bot exécute : /effect clear @a[name=Pseudo]
6. Bot envoie : /tellraw Pseudo {"text":"[Sécurité] Authentification réussie ! Tu peux jouer.","color":"green"}
7. Logs Discord : ✅ Authentification réussie
```

### Scénario 4 : Joueur entre la mauvaise commande `/login`
```
1. Bot détecte : /login mauvaisMotDePasse
2. Rate limiting check : OK
3. Password hash check : ❌ Invalide
4. Bot envoie : /tellraw Pseudo {"text":"[Sécurité] Mot de passe incorrect","color":"red"}
5. Logs Discord : ❌ Mot de passe incorrect (X tentatives restantes)
6. Joueur reste freezé
```

### Scénario 5 : Trop de tentatives (Rate Limit)
```
1. Joueur tente 5 fois de suite avec un mauvais mot de passe en 5 minutes
2. À la 6ème tentative, rate limiting activé
3. Bot envoie : /tellraw Pseudo {"text":"[Sécurité] Trop de tentatives. Réessaie dans 5 minutes.","color":"dark_red"}
4. Logs Discord : ⚠️ Rate limit dépassé
5. Le compteur se réinitialise après 5 minutes
```

### Scénario 6 : Joueur quitte et revient
```
1. Joueur était authentifié (is_authenticated = True)
2. Joueur quitte le serveur → _handle_player_leave() appelé
3. Joueur rejoint → _handle_player_join() appelé
4. _reset_player_session() → is_authenticated = False
5. Compteur de tentatives de /login nettoyé
6. Bot freeze le joueur à nouveau, demande le /login
```

## 🔐 Sécurité

### Protections implémentées
- ✅ **Hash des mots de passe** : Stockés en hash SHA256 + salt
- ✅ **Rate limiting** : 5 tentatives max par 5 minutes par joueur
- ✅ **Réinitialisation de session** : Chaque reconnexion demande une nouvelle auth
- ✅ **Freeze effect** : Blindness + Slowness empêchent le mouvement
- ✅ **Logs complets** : Toutes les tentatives loggées sur Discord

### Points à surveiller
- ⚠️ Les tentatives de /login sont comptées globalement, pas par joueur (géré par `self.login_attempts[username]`)
- ⚠️ Si le joueur relance le bot, le compteur de rate limiting se réinitialise
- ⚠️ Les effets de freeze ne sont jamais appliqués à un joueur déjà authentifié

## 🧪 Tests à effectuer

### Test 1 : Kick des joueurs non enregistrés
```bash
# 1. Créer un compte Discord lié
# 2. Créer un pseudo Minecraft dans le ticket (ex: NotRegistered)
# 3. Se connecter avec un pseudo DIFFÉRENT (ex: UnknownPlayer)
# Résultat attendu : Kicked immédiatement
```

### Test 2 : Freeze et prompt de login
```bash
# 1. Se connecter avec le pseudo correct
# 2. Vérifier : écran noir (blindness), impossible de bouger (slowness)
# 3. Vérifier le /tellraw rouge à l'écran
# 4. Vérifier les logs Discord
```

### Test 3 : Authentification réussie
```bash
# 1. Après le freeze, taper : /login correctpassword
# 2. Vérifier : écran normal, peut bouger
# 3. Vérifier le /tellraw vert à l'écran
# 4. Vérifier les logs Discord verts
```

### Test 4 : Mauvais mot de passe
```bash
# 1. Taper : /login wrongpassword
# 2. Vérifier : reste freezé
# 3. Vérifier le /tellraw rouge "incorrect"
# 4. Vérifier les logs Discord
```

### Test 5 : Rate limiting
```bash
# 1. Taper 5 fois : /login wrongpassword
# 2. À la 6ème tentative : message "Trop de tentatives"
# 3. Vérifier logs Discord : ⚠️ Rate limit
# 4. Attendre 5 minutes ou relancer le bot
```

### Test 6 : Reconnexion
```bash
# 1. S'authentifier avec /login
# 2. Quitter le serveur (/leave ou crash)
# 3. Rejoin le serveur
# 4. Vérifier : freeze à nouveau, compteur de /login réinitialisé
```

## 📊 Structure des données

### Table `users`
```python
- minecraft_username : str  # Pseudo Minecraft
- password_hash      : str  # SHA256 + salt
- is_authenticated   : bool # État auth actuel (réinitialisé à chaque join)
- is_whitelisted     : bool # Est dans la liste blanche
- last_activity      : datetime
```

### Tracking en mémoire
```python
self.login_attempts = {
    "PlayerName": [timestamp1, timestamp2, ...],  # Max 5 tentatives
    # Expirent après 5 minutes (300s)
}
```

## 🔧 Code clé

### Réinitialisation de session
```python
def _reset_player_session(self, username: str):
    """Réinitialise is_authenticated=False et nettoie le compteur"""
    with db.get_session() as session:
        user = session.query(User).filter(User.minecraft_username == username).first()
        if user:
            user.is_authenticated = False  # Reset
            session.commit()
    
    if username in self.login_attempts:
        del self.login_attempts[username]  # Nettoyer compteur
```

### Rate limiting
```python
def _check_login_rate_limit(self, username: str) -> tuple[bool, int]:
    """Retourne (is_allowed, attempts_left)"""
    # Nettoie les tentatives > 5 minutes
    # Si >= 5 tentatives : refuser
    # Sinon : ajouter timestamp et autoriser
```

### Handlers
- `_handle_player_join()` : Vérification + freeze
- `_handle_player_leave()` : Cleanup de session
- `_handle_player_login_command()` : Auth + validation

## 📝 Changelog depuis la dernière version

### Améliorations
- ✅ Rate limiting (5 tentatives par 5 minutes)
- ✅ Reset de session à chaque reconnexion
- ✅ Logs détaillés des tentatives échouées
- ✅ Gestion des erreurs améliorée
- ✅ Messages d'erreur distincts pour brute-force et password incorrect

### Bugfixes
- ✅ Player join handler toujours freeze même si précédemment auth
- ✅ Compteur de rate limiting jamais expiré avant
- ✅ Manque de gestion des sessions après quitter/revenir

