#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Captures d'écran de l'instance d'essai, pour montrer la plateforme sans y aller.

    python3 captures.py [http://127.0.0.1:8820]

Une image par écran dans captures/. Le navigateur défile jusqu'en bas avant la capture
pleine page, sinon les blocs chargés à la volée ne sont pas peints (ERRORS 59).
"""
import os
import sys

from playwright.sync_api import sync_playwright

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8820"
MDP = "Demo-2026-ivoire"
SORTIE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "captures")

# (fichier, compte de connexion ou None, chemin)
ECRANS = [
    ("01-accueil", None, "/"),
    ("02-inscription", None, "/inscription"),
    ("03-tableau-startup", "awa@jeko.africa", "/tableau"),
    ("04-offres", "awa@jeko.africa", "/offres"),
    ("05-matching", "awa@jeko.africa", "/matching"),
    ("06-documents", "awa@jeko.africa", "/documents"),
    ("07-annuaire", "awa@jeko.africa", "/annuaire"),
    ("08-offres-partenaire", "odc@orange.ci", "/offres"),
    ("09-administration", "admin@ivoire.tech", "/admin"),
]


def connecter(page, email):
    page.goto(BASE + "/connexion", wait_until="networkidle")
    page.fill('input[name="email"]', email)
    page.fill('input[name="mot_de_passe"]', MDP)
    page.click('form.formulaire button')
    page.wait_for_load_state("networkidle")


def main():
    os.makedirs(SORTIE, exist_ok=True)
    with sync_playwright() as p:
        nav = p.chromium.launch()
        compte = None
        ctx = nav.new_context(viewport={"width": 1366, "height": 900}, device_scale_factor=2)
        page = ctx.new_page()
        for (nom, email, chemin) in ECRANS:
            if email != compte:
                ctx.close()
                ctx = nav.new_context(viewport={"width": 1366, "height": 900}, device_scale_factor=2)
                page = ctx.new_page()
                if email:
                    connecter(page, email)
                compte = email
            r = page.goto(BASE + chemin, wait_until="networkidle")
            page.mouse.wheel(0, 4000)
            page.wait_for_timeout(300)
            page.mouse.wheel(0, -8000)
            page.wait_for_timeout(200)
            chemin_image = os.path.join(SORTIE, nom + ".png")
            page.screenshot(path=chemin_image, full_page=True)
            print("%-24s %s  %d Ko" % (nom, r.status, os.path.getsize(chemin_image) // 1024))
        ctx.close()
        nav.close()


if __name__ == "__main__":
    main()
