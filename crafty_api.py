"""API Crafty - Intégration Crafty Controller v2"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Union
from urllib.parse import parse_qs, urlparse

import aiohttp

from config import config
from utils import get_logger

# Initialisation du logger
logger = get_logger(__name__)


# --- CONFIGURATION ---
CRAFTY_BASE_URL = config.CRAFTY_BASE_URL.rstrip("/")
SERVER_ID = config.CRAFTY_SERVER_ID

HEADERS: Dict[str, str] = {
    "Authorization": f"Bearer {config.CRAFTY_API_TOKEN}",
    "Content-Type": "application/json",
}


async def _request(
    method: str,
    path: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    json: Optional[Dict[str, Any]] = None,
    data: Optional[Any] = None,
) -> Dict[str, Any]:
    """Client générique Crafty v2 (retourne toujours un dict)."""
    if not SERVER_ID:
        return {"success": False, "erreur": "ID de serveur manquant dans la configuration"}
    timeout_val = config.TIMEOUTS.get("crafty_api_timeout", 10)
    url = f"{CRAFTY_BASE_URL}{path}"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.request(
                method=method,
                url=url,
                headers=HEADERS,
                params=params,
                json=json,
                data=data,
                ssl=False,
                timeout=aiohttp.ClientTimeout(total=timeout_val)
            ) as resp:
                # Crafty renvoie souvent { data: ... } en JSON
                if resp.status in (200, 201):
                    try:
                        payload = await resp.json()
                        if isinstance(payload, dict) and "data" in payload:
                            return {"success": True, "data": payload.get("data"), "raw": payload}
                        return {"success": True, "data": payload, "raw": payload}
                    except Exception:
                        text = await resp.text()
                        return {"success": True, "data": text}

                # Certains endpoints d'action renvoient 204
                if resp.status == 204:
                    return {"success": True, "data": None}

                # Erreurs
                err_text = None
                try:
                    err_text = await resp.text()
                except Exception:
                    err_text = None

                if resp.status == 401:
                    return {"success": False, "erreur": "Token Crafty invalide (401)"}

                return {
                    "success": False,
                    "erreur": f"Erreur Crafty ({resp.status})" + (f": {err_text}" if err_text else ""),
                }

    except asyncio.TimeoutError:
        return {"success": False, "erreur": "Timeout: Crafty ne répond pas"}
    except Exception as e:
        logger.error(f"Erreur lors de l'appel à Crafty ({method} {path}): {e}")
        return {"success": False, "erreur": f"Impossible de joindre Crafty: {e}"}


async def obtenir_stats_crafty() -> Dict[str, Any]:
    """Interroge l'API Crafty pour obtenir les stats du serveur."""
    res = await _request("GET", f"/api/v2/servers/{SERVER_ID}/stats")
    if not res.get("success"):
        return {"erreur": res.get("erreur", "Erreur inconnue")}
    return res.get("data") or {}

async def obtenir_utilisateurs() -> Dict[str, Any]:
    """Interroge l'API Crafty pour obtenir les utilisateurs configurés."""
    res = await _request("GET", f"/api/v2/users")
    if not res.get("success"):
        return {"erreur": res.get("erreur", "Erreur inconnue")}
    return res.get("data") or {}


async def demarrer_serveur() -> Dict[str, Any]:
    """Démarre le serveur Minecraft."""
    res = await _request("POST", f"/api/v2/servers/{SERVER_ID}/action/start_server")
    if res.get("success"):
        return {"success": True, "message": "Serveur en cours de démarrage..."}
    return {"success": False, "erreur": res.get("erreur", "Erreur inconnue")}


async def arreter_serveur() -> Dict[str, Any]:
    """Arrête le serveur Minecraft."""
    res = await _request("POST", f"/api/v2/servers/{SERVER_ID}/action/stop_server")
    if res.get("success"):
        return {"success": True, "message": "Serveur arrêt en cours..."}
    return {"success": False, "erreur": res.get("erreur", "Erreur inconnue")}


async def redemarrer_serveur() -> Dict[str, Any]:
    """Redémarre le serveur Minecraft."""
    res = await _request("POST", f"/api/v2/servers/{SERVER_ID}/action/restart_server")
    if res.get("success"):
        return {"success": True, "message": "Serveur en cours de redémarrage..."}
    return {"success": False, "erreur": res.get("erreur", "Erreur inconnue")}

async def creer_sauvegarde() -> Dict[str, Any]:
    """Crée une nouvelle sauvegarde du serveur Minecraft."""
    res = await _request("POST", f"/api/v2/servers/{SERVER_ID}/action/backup_server")
    if res.get("success"):
        return {"success": True, "message": "Sauvegarde en cours de création..."}
    return {"success": False, "erreur": res.get("erreur", "Erreur inconnue")}

async def envoyer_commande(commande: str) -> Dict[str, Any]:
    """Envoie une commande au serveur Minecraft."""
    commande = (commande or "").strip()
    if not commande:
        return {"success": False, "erreur": "Commande vide"}

    res = await _request(
        "POST",
        f"/api/v2/servers/{SERVER_ID}/stdin",
        data=commande
    )

    if res.get("success"):
        logger.info(f"✅ Commande envoyée: {commande}")
        return {"success": True, "message": "Commande envoyée", "command": commande}
    return {"success": False, "erreur": res.get("erreur", "Erreur inconnue")}


async def obtenir_logs() -> Any:
    """Récupère les logs du serveur."""
    res = await _request("GET", f"/api/v2/servers/{SERVER_ID}/logs")
    if not res.get("success"):
        logger.error(f"Erreur logs Crafty: {res.get('erreur')}")
        return []
    return res.get("data") or []

