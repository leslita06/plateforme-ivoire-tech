#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Récupère le logo officiel de chaque organisation qui a un site, et l'embarque.

    python3 recuperer_logos.py [--base data/plateforme.sqlite3]

Le logo vient du site de l'organisation elle-même (son favicon officiel, servi par
Google en 128 px), jamais d'un dessin refait ni d'un glyphe. Une organisation sans
site, ou dont le site ne rend pas d'icône exploitable, garde ses initiales : une
pastille de couleur vaut mieux qu'un faux logo.

Les fichiers sont écrits dans `app/static/logos-orgs/` et servis par l'application :
rien n'est appelé à l'extérieur au moment de l'affichage, l'État peut être hors ligne.
"""
import argparse
import io
import os
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import db  # noqa: E402

from PIL import Image  # noqa: E402

ICI = os.path.dirname(os.path.abspath(__file__))
DOSSIER = os.path.join(ICI, "app", "static", "logos-orgs")
SOURCE = "https://www.google.com/s2/favicons?domain=%s&sz=128"
TAILLE_MINI = 32  # en dessous, c'est une icône générique de navigateur, pas un logo


def domaine(site):
    if not site:
        return ""
    if "//" not in site:
        site = "https://" + site
    return urllib.parse.urlparse(site).netloc.replace("www.", "")


def _charger(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read()


def _icones_declarees(dom):
    """Le site dit lui-même où est son logo : <link rel="icon" href="…">."""
    import re
    page = _charger("https://" + dom).decode("utf-8", "replace")[:200000]
    trouves = re.findall(r'<link[^>]+rel="[^"]*icon[^"]*"[^>]*>', page, re.I)
    urls = []
    for balise in trouves:
        m = re.search(r'href="([^"]+)"', balise, re.I)
        if m:
            urls.append(urllib.parse.urljoin("https://" + dom + "/", m.group(1)))
    return urls


def telecharger(dom):
    """Trois sources, de la plus fiable à la plus brute. La première qui rend une
    image assez grande gagne ; un 404 sur l'une ne dit rien des autres."""
    soucis = []
    sources = [SOURCE % dom, "https://%s/favicon.ico" % dom]
    tardives = None
    while sources:
        url = sources.pop(0)
        if not sources and tardives is None:   # les deux directes ont échoué : on lit la page
            tardives = _essais_tardifs(dom, soucis)
            sources += tardives
        try:
            img = Image.open(io.BytesIO(_charger(url)))
        except Exception as e:
            soucis.append("%s : %s" % (url.split("/")[2], str(e)[:34]))
            continue
        if img.width < TAILLE_MINI:
            soucis.append("%d px" % img.width)
            continue
        return img.convert("RGBA"), None
    return None, " / ".join(soucis[:2])


def _essais_tardifs(dom, soucis):
    """Le site lui-même, interrogé seulement si les deux sources directes ont échoué."""
    try:
        return _icones_declarees(dom)
    except Exception as e:
        soucis.append("page : %s" % str(e)[:34])
        return []


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--base", default=os.environ.get("PLATEFORME_BASE"))
    args = a.parse_args()
    if args.base:
        os.environ["PLATEFORME_BASE"] = args.base

    os.makedirs(DOSSIER, exist_ok=True)
    c = db.connexion()
    orgs = c.execute("SELECT id, nom, site FROM organisations ORDER BY nom").fetchall()
    poses, sans = 0, []
    for o in orgs:
        dom = domaine(o["site"])
        if not dom:
            sans.append((o["nom"], "pas de site"))
            continue
        try:
            img, souci = telecharger(dom)
        except Exception as e:
            img, souci = None, str(e)[:60]
        if img is None:
            sans.append((o["nom"], souci))
            continue
        chemin = os.path.join(DOSSIER, "%s.png" % o["id"])
        img.save(chemin, optimize=True)
        c.execute("UPDATE organisations SET logo = ? WHERE id = ?",
                  ("logos-orgs/%s.png" % o["id"], o["id"]))
        poses += 1
        print("  %-34s %s (%d px)" % (o["nom"], dom, img.width))
    c.commit()
    c.close()
    for nom, raison in sans:
        print("  %-34s initiales : %s" % (nom, raison))
    print("%d logos posés, %d en initiales" % (poses, len(sans)))


if __name__ == "__main__":
    main()
