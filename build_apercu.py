#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Aperçu PDF de la plateforme : une page de présentation, puis un écran par page.

    python3 build_apercu.py [sortie.pdf]

Les images viennent de captures/ (voir captures.py). Chaque page est à la taille du
papier, l'image occupe la largeur et garde ses proportions.
"""
import base64
import os
import sys

from PIL import Image

from weasyprint import HTML

ICI = os.path.dirname(os.path.abspath(__file__))
CAPTURES = os.path.join(ICI, "captures")
SORTIE = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ICI, "apercu.pdf")

VERT = "#064534"
ORANGE = "#E94E1B"
CREME = "#FAF6EF"

ECRANS = [
    ("01-accueil", "La page d'accueil", "Chacun crée son compte lui-même. Les compteurs se remplissent au fil des inscriptions validées."),
    ("02-inscription", "La création de compte", "Type d'organisation, programme, contact. Un code à six chiffres arrive par email, et l'organisation passe en file de validation."),
    ("03-tableau-startup", "Le tableau de bord d'une entreprise", "Ses documents, ses demandes d'offres, ses mises en relation, et les dernières offres ouvertes."),
    ("04-offres", "Les offres des partenaires", "Filtrées par catégorie et par cible : une startup ne voit pas une offre réservée aux PME."),
    ("05-matching", "La correspondance avec les investisseurs", "Un score expliqué ligne par ligne : secteur, stade recherché, fourchette de ticket."),
    ("06-documents", "Les documents", "Un dépôt sous un nom déjà présent crée une version ; l'entreprise choisit qui peut voir quoi."),
    ("07-annuaire", "L'annuaire", "Toutes les organisations validées, avec leur fiche."),
    ("08-offres-partenaire", "Le poste de travail d'un partenaire", "Il publie ses offres, suit les demandes reçues, accepte ou refuse."),
    ("09-administration", "L'administration du Ministère", "Validation des comptes, modération des offres, journal des actions, exports CSV."),
]


LARGEUR_UTILE = 269.0   # A4 paysage moins les marges
HAUTEUR_IMAGE = 168.0   # ce qui reste sous le titre et la légende


def image64(nom):
    with open(os.path.join(CAPTURES, nom + ".png"), "rb") as fh:
        return base64.b64encode(fh.read()).decode()


def logo64(nom):
    with open(os.path.join(ICI, "app", "static", "logos", nom + ".png"), "rb") as fh:
        return base64.b64encode(fh.read()).decode()


def dimensions(nom):
    """Une capture plein écran est très haute : la borner par la HAUTEUR quand la largeur
    ne mord pas la première, sinon elle déborde sur une seconde page (ERRORS 31)."""
    l, h = Image.open(os.path.join(CAPTURES, nom + ".png")).size
    if LARGEUR_UTILE * h / l > HAUTEUR_IMAGE:
        return "height:%.1fmm;width:auto" % HAUTEUR_IMAGE
    return "width:100%"


def main():
    pages = []
    for (nom, titre, legende) in ECRANS:
        pages.append("""<section class="ecran">
  <h2>%s</h2><p class="legende">%s</p>
  <img style="%s" src="data:image/png;base64,%s">
</section>""" % (titre, legende, dimensions(nom), image64(nom)))

    html = """<!doctype html><html lang="fr"><head><meta charset="utf-8"><style>
@page { size: A4 landscape; margin: 12mm 14mm; }
body { font-family: "DejaVu Sans", sans-serif; color: #1b2a25; font-size: 10pt; margin: 0; }
h1 { color: %(vert)s; font-size: 22pt; margin: 0 0 2mm; }
h2 { color: %(vert)s; font-size: 13pt; margin: 0 0 1mm; }
.chapeau { color: #4a5a54; font-size: 11pt; margin: 0 0 6mm; }
.garde { background: %(creme)s; padding: 10mm; border-radius: 3mm; }
.colonnes { display: flex; gap: 8mm; }
.colonnes > div { flex: 1; }
h3 { color: %(vert)s; font-size: 10.5pt; margin: 4mm 0 1mm; }
ul { margin: 0; padding-left: 5mm; }
li { margin-bottom: 1.2mm; }
.bandeau { background: %(vert)s; color: #fff; padding: 4mm 6mm; border-radius: 2mm; margin-top: 6mm; }
.bandeau b { color: #ffd9c9; }
.ecran { page-break-before: always; text-align: center; }
.ecran h2, .ecran .legende { text-align: left; }
.legende { color: #4a5a54; margin: 0 0 3mm; }
img { border: 0.3mm solid #dcd5c8; border-radius: 1.5mm; }
.marques { display: flex; align-items: center; justify-content: space-between; margin: 0 0 7mm; }
.marques img { display: inline-block; vertical-align: middle; }
.m-ministere { height: 13mm; }
.m-next15 { height: 7mm; margin-right: 7mm; }
.m-scaleup { height: 12mm; }
.pied { position: fixed; bottom: 0; left: 0; right: 0; color: #8c968f; font-size: 7.5pt; }
</style></head><body>
<div class="pied">Plateforme d'accompagnement Ivoire Tech, Ministère de la Transition Numérique et de l'Innovation Technologique</div>

<div class="marques">
  <img class="m-ministere" src="data:image/png;base64,%(ministere)s">
  <span><img class="m-next15" src="data:image/png;base64,%(next15)s">
  <img class="m-scaleup" src="data:image/png;base64,%(scaleup)s"></span>
</div>
<h1>Plateforme d'accompagnement Ivoire Tech</h1>
<p class="chapeau">L'espace commun des startups Next 15, des PME Scale Up, des partenaires et des investisseurs.</p>

<div class="garde">
<div class="colonnes">
<div>
<h3>Ce que chacun y fait</h3>
<ul>
<li><b>Les entreprises</b> tiennent leur fiche à jour, déposent leurs documents avec leur historique de versions, activent les offres des partenaires et demandent des mises en relation.</li>
<li><b>Les partenaires</b> publient leurs offres, choisissent leur cible et leur durée, puis acceptent ou refusent les demandes.</li>
<li><b>Les investisseurs</b> déclarent leur thèse, reçoivent les entreprises classées par correspondance et lisent les documents qu'elles ont ouverts.</li>
<li><b>Le Ministère</b> valide les comptes, modère les offres, lit le journal des actions et exporte tout en CSV.</li>
</ul>
</div>
<div>
<h3>Comment elle est faite</h3>
<ul>
<li>Chacun crée son compte lui-même, avec vérification par code ; l'accès n'est ouvert qu'après validation.</li>
<li>Les coordonnées ne circulent qu'après un double accord.</li>
<li>Une application Python autoportante, quatre dépendances, une base dans un fichier, aucun service tiers.</li>
<li>Elle s'installe sur un serveur de l'État en une heure, avec ou sans conteneur, et se sauvegarde en copiant un dossier.</li>
</ul>
<h3>Ce qui reste à décider</h3>
<ul>
<li>Le nom de domaine et le certificat.</li>
<li>Le relais email du Ministère.</li>
<li>Qui administre au quotidien.</li>
</ul>
</div>
</div>
<div class="bandeau">Les pages qui suivent sont des captures de l'instance d'essai, avec des organisations réelles du terrain ivoirien et des données fictives. <b>Rien n'est encore ouvert au public.</b></div>
</div>

%(pages)s
</body></html>""" % {"vert": VERT, "orange": ORANGE, "creme": CREME, "pages": "\n".join(pages),
     "ministere": logo64("ministere"), "next15": logo64("next15"), "scaleup": logo64("scaleup")}

    HTML(string=html, base_url=ICI).write_pdf(SORTIE)
    print("%s  %d Ko" % (SORTIE, os.path.getsize(SORTIE) // 1024))


if __name__ == "__main__":
    main()
