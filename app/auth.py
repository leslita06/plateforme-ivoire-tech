# -*- coding: utf-8 -*-
"""Mots de passe, sessions et jetons anti-CSRF, sans dépendance externe.

  · mot de passe : scrypt (bibliothèque standard), sel aléatoire par utilisateur ;
  · session : cookie signé HMAC-SHA256 avec la clé secrète du déploiement, durée 12 h ;
  · CSRF : un jeton par session, exigé sur chaque formulaire POST.
La clé secrète vient de PLATEFORME_SECRET ; sans elle, l'application refuse de démarrer
en production (PLATEFORME_ENV=production) et en génère une éphémère ailleurs.
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import time

ENV = os.environ.get("PLATEFORME_ENV", "preview")
SECRET = os.environ.get("PLATEFORME_SECRET") or (secrets.token_hex(32) if ENV != "production" else None)
if SECRET is None:
    raise SystemExit("PLATEFORME_SECRET est obligatoire en production")
DUREE_SESSION = 12 * 3600
LONGUEUR_MIN_MDP = 10


def hacher(mdp):
    sel = secrets.token_bytes(16)
    h = hashlib.scrypt(mdp.encode(), salt=sel, n=2 ** 14, r=8, p=1, dklen=32)
    return "scrypt$%s$%s" % (base64.b64encode(sel).decode(), base64.b64encode(h).decode())


def verifier_mdp(mdp, stocke):
    try:
        _algo, sel, h = stocke.split("$")
        sel, h = base64.b64decode(sel), base64.b64decode(h)
    except Exception:
        return False
    calc = hashlib.scrypt(mdp.encode(), salt=sel, n=2 ** 14, r=8, p=1, dklen=32)
    return hmac.compare_digest(calc, h)


def mot_de_passe_acceptable(mdp):
    """Dix caractères au moins, avec une lettre et un chiffre : une règle qu'un usager
    comprend, pas une politique de caractères spéciaux que tout le monde contourne."""
    return len(mdp) >= LONGUEUR_MIN_MDP and any(ch.isalpha() for ch in mdp) and any(ch.isdigit() for ch in mdp)


def _b64(b):
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def creer_session(user_id):
    payload = json.dumps({"u": user_id, "exp": time.time() + DUREE_SESSION, "csrf": secrets.token_hex(16)}).encode()
    sig = hmac.new(SECRET.encode(), payload, hashlib.sha256).digest()
    return _b64(payload) + "." + _b64(sig)


def lire_session(cookie):
    if not cookie or "." not in cookie:
        return None
    try:
        p64, s64 = cookie.split(".", 1)
        payload, sig = _unb64(p64), _unb64(s64)
    except Exception:
        return None
    attendu = hmac.new(SECRET.encode(), payload, hashlib.sha256).digest()
    if not hmac.compare_digest(sig, attendu):
        return None
    d = json.loads(payload)
    if d.get("exp", 0) < time.time():
        return None
    return d


def code_numerique():
    return "%06d" % secrets.randbelow(1_000_000)
