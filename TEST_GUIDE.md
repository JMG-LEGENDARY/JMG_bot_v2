# Guide de Test - Système d'Authentification Minecraft

## ✅ Pré-requis

1. **Base de données** : Au moins un utilisateur avec pseudo Minecraft et password_hash
   ```sql
   INSERT INTO users (minecraft_username, password_hash, is_whitelisted)
   VALUES ('TestPlayer', 'hash_du_mot_de_passe', 1);
   ```

2. **Configuration** : `.env` contient
   ```
   CRAFTY_BASE_URL=https://100.82.172.73:8443
   CRAFTY_API_TOKEN=<votre_token>
   CRAFTY_SERVER_ID=6fd40185-e660-4620-b6a8-7f9654770b68
   LOGS_CHANNEL=1324057375845646408
   ```

3. **Bot en running** : `python3 main.py`

4. **Minecraft Server** : Crafty server running et logs générant

## 🧪 Scénarios de Test

### Test 1: Player Join - Non Enregistré ❌

**Setup:**
- Ouvrir Minecraft
- Joindre le serveur avec un pseudo NON dans la DB (ex: `UnknownPlayer`)

**Résultat attendu:**
- ✅ Kicked immédiatement avec message "[Sécurité] Tu n'es pas whitelisté."
- ✅ Logs Discord: `❌ Kick automatique - UnknownPlayer`

**Vérification:**
```
[Terminal du serveur]
UnknownPlayer left the game (kicked by an operator)

[Discord LOGS_CHANNEL]
Minecraft - Kick
❌ UnknownPlayer n'était pas enregistré, kick automatique
```

---

### Test 2: Player Join - Enregistré 🔒

**Setup:**
- Joindre avec pseudo enregistré (ex: `TestPlayer`)

**Résultat attendu:**
- ✅ Rejoint le serveur
- ✅ Écran noir (blindness effect)
- ✅ Impossible de bouger (slowness effect)
- ✅ Message tellraw rouge: "[Sécurité] Connecte-toi avec : /login <ton_mot_de_passe>"
- ✅ Logs Discord: `🔒 TestPlayer attend l'authentification`

**Vérification:**
```
[Écran Minecraft]
- Écran noir avec message rouge en bas
- Impossible de se déplacer

[Discord LOGS_CHANNEL]
Minecraft - Authentification
🔒 TestPlayer attend l'authentification
```

---

### Test 3: Login - Bon Mot de Passe ✅

**Setup:**
- From Test 2, taper: `/login monMotDePasse123`

**Résultat attendu:**
- ✅ Écran revient à la normale (effects cleared)
- ✅ Message tellraw vert: "[Sécurité] Authentification réussie ! Tu peux jouer."
- ✅ Peut se déplacer normalement
- ✅ Logs Discord: `✅ TestPlayer s'est authentifié avec succès`

**Vérification:**
```
[Écran Minecraft]
- Vision normale
- Peut bouger
- Message vert: "Authentification réussie ! Tu peux jouer."

[Terminal serveur]
TestPlayer issued server command: /login monMotDePasse123

[Discord LOGS_CHANNEL]
Minecraft - Authentification Réussie
✅ TestPlayer s'est authentifié avec succès
```

---

### Test 4: Login - Mauvais Mot de Passe ❌

**Setup:**
- From Test 2, taper: `/login wrongPassword`

**Résultat attendu:**
- ✅ Reste freezé (blindness + slowness actif)
- ✅ Message tellraw rouge: "[Sécurité] Mot de passe incorrect"
- ✅ Logs Discord: `❌ Mot de passe incorrect (4 tentatives restantes)`

**Vérification:**
```
[Écran Minecraft]
- Reste noir
- Impossible de bouger
- Message rouge: "Mot de passe incorrect"

[Discord LOGS_CHANNEL]
Minecraft - Authentification Échouée
❌ TestPlayer a entré un mauvais mot de passe (4 tentatives restantes)
```

---

### Test 5: Rate Limiting - 5+ Tentatives 🚫

**Setup:**
- From Test 2, taper 5x: `/login wrongPassword`

**À la 6ème tentative:**
- Message tellraw dark_red: "[Sécurité] Trop de tentatives. Réessaie dans 5 minutes."
- Logs Discord: `⚠️ Rate limit dépassé`
- Plus aucune tentative de password acceptée pendant 5 minutes

**Vérification:**
```
[Écran Minecraft - 6ème tentative]
Message dark red: "Trop de tentatives. Réessaie dans 5 minutes."

[Discord LOGS_CHANNEL]
Minecraft - Rate Limit
⚠️ TestPlayer a dépassé le rate limit /login

[Après 5 minutes]
- Les tentatives sont à nouveau acceptées
```

---

### Test 6: Session Reset - Rejoin ↻

**Setup:**
- From Test 3 (player authentifié), quitter le serveur
- `/leave` ou attendre timeout
- Rejoin le serveur

**Résultat attendu:**
- ✅ Freezé à nouveau (blindness + slowness réappliqué)
- ✅ Message tellraw: "[Sécurité] Connecte-toi avec : /login <ton_mot_de_passe>"
- ✅ Compteur de rate limiting réinitialisé à 0
- ✅ Logs Discord: `🔒 TestPlayer attend l'authentification`

**Vérification:**
```
[1ère reconnexion]
- Freezé immédiatement
- Compteur de /login reset
- Peut faire 5 tentatives à nouveau

[Discord LOGS_CHANNEL]
Minecraft - Authentification
🔒 TestPlayer attend l'authentification
```

---

## 🔄 Flux Complet de Test

```
1. UnknownPlayer rejoin → kicked ❌
2. TestPlayer rejoin → freezé 🔒
3. Taper /login mauvais → "incorrect" ❌
4. Taper /login mauvais → "incorrect" ❌
5. Taper /login mauvais → "incorrect" ❌
6. Taper /login mauvais → "incorrect" ❌
7. Taper /login mauvais → "incorrect" ❌
8. Taper /login mauvais → "Trop de tentatives" 🚫
9. Attendre 5+ minutes
10. Taper /login correct → authentifié ✅
11. Quitter serveur et rejoin → freezé à nouveau 🔒
```

## 📊 Checklist de Validation

- [ ] Test 1: Non-registered player kicked
- [ ] Test 2: Registered player frozen
- [ ] Test 3: Correct password unfreezes
- [ ] Test 4: Wrong password stays frozen
- [ ] Test 5: Rate limit after 5 attempts
- [ ] Test 6: Session reset on rejoin
- [ ] All Discord logs posted correctly
- [ ] No crashes/exceptions in bot logs
- [ ] Minecraft logs parsed correctly

## 🐛 Debugging

### Bot ne detects pas le /login command
- Vérifier pattern regex dans `utils/minecraft_monitor.py`
- Vérifier que Minecraft log format matches: `[HH:MM:SS] [Server thread/INFO]: Username issued server command: /login password`
- Check: `logger.debug()` statements dans `minecraft_monitor.py`

### Effects non appliquées
- Vérifier `CRAFTY_API_TOKEN` est valide
- Vérifier `CRAFTY_SERVER_ID` pointe le bon serveur
- Tester manuellement: `/effect give @s blindness`

### Discord logs ne s'affichent pas
- Vérifier `LOGS_CHANNEL` ID dans `.env`
- Vérifier que le bot peut écrire dans ce channel
- Check `relay_log()` errors dans bot console

### Password verification fails
- Vérifier `verify_password()` function dans `utils/helpers.py`
- Vérifier que `password_hash` en DB est un vrai hash (pas plaintext)
- Test manuellement: `verify_password('test', stored_hash)`

## 📞 Support

Si problèmes lors du test:
1. Vérifier console du bot pour exceptions
2. Vérifier Discord channel pour erreurs relay_log()
3. Vérifier serveur Minecraft logs pour message du /login
4. Activer DEBUG=True dans `.env` pour plus de logs

---

**Version:** Phase 3 Authentication Complete
**Last Updated:** 2026-07-05
