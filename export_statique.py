#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fige la démonstration en pages HTML navigables, publiables sur GitHub Pages.

    python3 export_statique.py [--base http://127.0.0.1:8820]

Pourquoi : GitHub Pages n'exécute rien, et la plateforme a besoin d'un serveur. Mais
une démonstration n'a pas besoin d'écrire : elle a besoin de se PARCOURIR. On visite
donc la vraie application avec chacun des quatre rôles, on enregistre le HTML réel de
chaque écran, et on réécrit les liens pour qu'ils pointent vers les fichiers voisins.
Le résultat se clique comme l'application, sans serveur, sans extinction.

Ce qui ne peut pas suivre : tout ce qui ÉCRIT (déposer un document, demander une offre,
valider un compte). Les formulaires sont donc neutralisés et portent un bandeau qui le
dit, plutôt que de rendre une erreur au visiteur.

Sortie : `site/demo/<role>/<page>.html`, plus `site/demo/index.html` qui présente les
quatre rôles.
"""
import argparse
import html
import os
import re
import shutil
import urllib.parse
import urllib.request
import http.cookiejar

ICI = os.path.dirname(os.path.abspath(__file__))
SORTIE = os.path.join(ICI, "site", "demo")
MOT_DE_PASSE = "Demo-2026-ivoire"

ROLES = [
    ("ministere", "admin@ivoire.tech", "Le Ministère",
     "Valider les comptes, modérer les offres, lire le journal, exporter."),
    ("startup", "awa@jeko.africa", "Une lauréate Next 15",
     "Jèko : sa fiche, ses documents, les offres, ses mises en relation."),
    ("partenaire", "partenariats@ecobank.ci", "Un partenaire",
     "Ecobank : ses offres publiées et les demandes reçues."),
    ("investisseur", "deals@janngo.africa", "Un investisseur",
     "Janngo Capital : les entreprises classées par correspondance."),
]

# Les écrans à parcourir. Le reste suit par les liens trouvés dans les pages.
DEPARTS = ["/tableau", "/organisation", "/documents", "/offres", "/matching", "/annuaire", "/admin"]

BANDEAU = """<div style="background:#fff8e6;border-bottom:1px solid #f0c674;padding:10px 16px;
font:14px/1.5 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:#7a5a12;text-align:center">
Démonstration figée de la plateforme, les données sont fictives. Vous pouvez circuler d'un écran à
l'autre ; ce qui écrit (déposer, demander, valider) ne fonctionne que sur la plateforme installée.
&nbsp; <a href="../index.html" style="color:#7a5a12;font-weight:600">Changer de rôle</a>
</div>"""


class Visiteur:
    def __init__(self, base):
        self.base = base
        self.cj = http.cookiejar.CookieJar()
        self.o = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cj))

    def connecter(self, email):
        self.o.open(self.base + "/connexion")
        r = self.o.open(self.base + "/connexion", data=urllib.parse.urlencode(
            {"email": email, "mot_de_passe": MOT_DE_PASSE}).encode())
        corps = r.read().decode()
        if "/connexion" in r.url:
            raise SystemExit("connexion refusée pour " + email)
        return corps

    def lire(self, chemin):
        try:
            r = self.o.open(self.base + chemin)
            return r.read().decode(), r.status
        except urllib.error.HTTPError as e:
            return "", e.code


def nom_fichier(chemin):
    """/offres/3 → offres-3.html, /tableau → tableau.html"""
    propre = chemin.strip("/").split("?")[0]
    return (propre.replace("/", "-") or "accueil") + ".html"


def reecrire(corps, pages, racine):
    """Fait pointer la page vers ses voisines figées, et neutralise ce qui écrit."""
    def lien(m):
        cible = m.group(1)
        if cible.startswith("/static/"):
            return 'href="%s%s"' % (racine, cible)
        fichier = nom_fichier(cible)
        if fichier in pages:
            return 'href="%s"' % fichier
        return 'href="#" data-hors-demo="%s"' % html.escape(cible)

    corps = re.sub(r'href="(/[^"#]*)"', lien, corps)
    corps = re.sub(r'src="(/static/[^"]*)"', lambda m: 'src="%s%s"' % (racine, m.group(1)), corps)
    corps = re.sub(r'<use href="#', '<use href="#', corps)
    # les formulaires ne partent nulle part : on coupe l'action et la soumission
    corps = re.sub(r'<form[^>]*>', lambda m: m.group(0)
                   .replace('method="post"', 'onsubmit="return false"')
                   .replace('action="/', 'data-action="/'), corps)
    corps = corps.replace("<body>", "<body>" + BANDEAU, 1)
    return corps


def exporter_role(base, cle, email, titre):
    v = Visiteur(base)
    v.connecter(email)
    dossier = os.path.join(SORTIE, cle)
    os.makedirs(dossier, exist_ok=True)

    # 1re passe : on collecte, 2de passe : on réécrit avec la liste complète en main.
    brut, file = {}, list(DEPARTS)
    vus = set()
    while file:
        chemin = file.pop(0)
        if chemin in vus or len(brut) > 40:
            continue
        vus.add(chemin)
        corps, statut = v.lire(chemin)
        if statut != 200 or not corps.strip():
            continue
        brut[nom_fichier(chemin)] = corps
        for trouve in re.findall(r'href="(/[a-z0-9][^"#?]*)"', corps):
            if (trouve not in vus and not trouve.startswith("/static/")
                    and "telecharger" not in trouve and "deconnexion" not in trouve
                    and "export" not in trouve):
                file.append(trouve)

    for fichier, corps in brut.items():
        with open(os.path.join(dossier, fichier), "w") as fh:
            # site/demo/<role>/page.html → site/static/ : deux crans à remonter
            fh.write(reecrire(corps, set(brut), "../.."))
    print("  %-14s %2d écrans (%s)" % (cle, len(brut), titre))
    return len(brut)


ACCUEIL = """<!doctype html>
<html lang="fr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Démonstration de la plateforme Ivoire Tech</title>
<link rel="icon" href="../logos/favicon.png">
<style>
 body {{ margin:0; font-family:-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
        color:#16241d; background:#f6f8f7; }}
 .marques {{ background:#fff; border-bottom:1px solid #dfe6e2; }}
 .marques div {{ max-width:880px; margin:0 auto; padding:14px 20px; display:flex;
                 align-items:center; justify-content:space-between; gap:18px; flex-wrap:wrap; }}
 .marques img.m {{ height:40px; }} .marques img.n {{ height:24px; }} .marques img.s {{ height:44px; }}
 .programmes {{ display:flex; align-items:center; gap:20px; }}
 main {{ max-width:880px; margin:0 auto; padding:44px 20px 60px; }}
 h1 {{ font-size:1.8rem; margin:0 0 10px; }}
 p.chapo {{ color:#5c6b64; margin:0 0 30px; max-width:42em; }}
 a.role {{ display:block; background:#fff; border:1px solid #dfe6e2; border-radius:10px;
           padding:18px 20px; margin:0 0 14px; text-decoration:none; color:inherit; }}
 a.role:hover {{ border-color:#0a7b4b; box-shadow:0 2px 10px rgba(10,60,40,.08); }}
 a.role strong {{ display:block; font-size:1.08rem; color:#0a7b4b; margin-bottom:3px; }}
 a.role span {{ color:#5c6b64; font-size:.95rem; }}
 .note {{ color:#5c6b64; font-size:.9rem; margin-top:26px; }}
 .note a {{ color:#0a7b4b; }}
</style></head><body>
<div class="marques"><div>
 <img class="m" src="../logos/ministere.png" alt="Ministère de la Transition Numérique et de l'Innovation Technologique">
 <span class="programmes"><img class="n" src="../logos/next15.png" alt="Ivoire Tech Next 15">
 <img class="s" src="../logos/scaleup.png" alt="Ivoire Tech Scale Up"></span>
</div></div>
<main>
 <h1>La plateforme, vue de l'intérieur</h1>
 <p class="chapo">Chaque rôle voit un espace différent. Choisissez par quels yeux la regarder,
 puis circulez d'un écran à l'autre comme dans la plateforme installée.</p>
 {roles}
 <p class="note">Les données sont fictives. Ce qui écrit (déposer un document, demander une offre,
 valider un compte) ne fonctionne que sur la plateforme installée sur un serveur.
 <br><a href="../index.html">Revenir à la présentation</a></p>
</main></body></html>
"""


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--base", default="http://127.0.0.1:8820")
    args = a.parse_args()

    shutil.rmtree(SORTIE, ignore_errors=True)
    os.makedirs(SORTIE)
    # les pages figées appellent /static/… : la feuille de style et les logos partent avec
    shutil.copytree(os.path.join(ICI, "app", "static"),
                    os.path.join(ICI, "site", "static"), dirs_exist_ok=True)
    total = 0
    cartes = []
    for cle, email, titre, texte in ROLES:
        total += exporter_role(args.base, cle, email, titre)
        cartes.append('<a class="role" href="%s/tableau.html"><strong>%s</strong>'
                      '<span>%s</span></a>' % (cle, titre, texte))

    with open(os.path.join(SORTIE, "index.html"), "w") as fh:
        fh.write(ACCUEIL.format(roles="\n ".join(cartes)))
    print("démo figée : %d écrans, 4 rôles" % total)


if __name__ == "__main__":
    main()
