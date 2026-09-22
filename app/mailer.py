# -*- coding: utf-8 -*-
"""Envoi des emails de la plateforme (codes de vérification, notifications).

En preview, sans SMTP configuré, les messages sont écrits dans data/courrier-sortant.log
et le code s'affiche à l'écran : on teste le parcours complet sans serveur mail.
En production, PLATEFORME_SMTP_HOST / PORT / USER / PASSWORD / FROM sont obligatoires.
"""
import os
import smtplib
import time
from email.message import EmailMessage

from . import db

HOST = os.environ.get("PLATEFORME_SMTP_HOST")
PORT = int(os.environ.get("PLATEFORME_SMTP_PORT", "587"))
USER = os.environ.get("PLATEFORME_SMTP_USER")
PASSWORD = os.environ.get("PLATEFORME_SMTP_PASSWORD")
FROM = os.environ.get("PLATEFORME_SMTP_FROM", "plateforme@ivoire.tech")
NOM_EXPEDITEUR = os.environ.get("PLATEFORME_NOM", "Plateforme Ivoire Tech")


def configure():
    return bool(HOST and USER and PASSWORD)


def envoyer(a, objet, texte):
    """Rend True si un email est réellement parti, False s'il n'a été que journalisé."""
    if not configure():
        os.makedirs(db.DATA_DIR, exist_ok=True)
        with open(os.path.join(db.DATA_DIR, "courrier-sortant.log"), "a", encoding="utf-8") as f:
            f.write("=== %s | à %s | %s\n%s\n\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), a, objet, texte))
        return False
    m = EmailMessage()
    m["Subject"] = objet
    m["From"] = "%s <%s>" % (NOM_EXPEDITEUR, FROM)
    m["To"] = a
    m.set_content(texte)
    with smtplib.SMTP(HOST, PORT, timeout=30) as s:
        s.starttls()
        s.login(USER, PASSWORD)
        s.send_message(m)
    return True
