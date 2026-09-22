#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fabrique le sprite d'icônes de l'interface, à partir des SVG Lucide.

    python3 build_icones.py [dossier-des-svg]

Écrit `app/templates/_icones.html` : un seul `<svg>` caché contenant un `<symbol>` par
icône, inclus une fois dans la page. Les gabarits appellent ensuite
`{{ ic('documents') }}`, qui rend `<svg class="ic"><use href="#ic-documents"></use></svg>`.

Pourquoi un sprite et pas la CDN Lucide : l'application doit tourner sur un serveur de
l'État, éventuellement sans accès internet. Tout est embarqué, rien n'est appelé dehors.
Licence Lucide : ISC.
"""
import os
import re
import sys

ICI = os.path.dirname(os.path.abspath(__file__))
SOURCE = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ICI, "icones-source")
SORTIE = os.path.join(ICI, "app", "templates", "_icones.html")

# nom dans l'application → nom du fichier Lucide
ICONES = {
    "tableau": "layout-dashboard",
    "organisation": "building-2",
    "documents": "folder-open",
    "offres": "gift",
    "matching": "handshake",
    "annuaire": "book-open",
    "administration": "shield-check",
    "deconnexion": "log-out",
    "connexion": "log-in",
    "inscription": "user-plus",
    "deposer": "upload",
    "telecharger": "download",
    "lien": "link",
    "ouvrir": "external-link",
    "supprimer": "trash-2",
    "pdf": "file-text",
    "image": "image",
    "tableur": "file-spreadsheet",
    "presentation": "presentation",
    "fait": "circle-check",
    "attente": "clock",
    "ajouter": "plus",
    "voir": "eye",
    "membres": "users",
}


def corps(svg):
    """Ne garde que les formes : le <symbol> porte lui-même le viewBox et le style."""
    interieur = re.sub(r"(?s)^.*?<svg[^>]*>|</svg>\s*$", "", svg).strip()
    return re.sub(r"\s+", " ", interieur)


def main():
    symboles = []
    for nom, fichier in sorted(ICONES.items()):
        chemin = os.path.join(SOURCE, fichier + ".svg")
        if not os.path.exists(chemin):
            raise SystemExit("icône absente : " + chemin)
        with open(chemin) as fh:
            symboles.append('<symbol id="ic-%s" viewBox="0 0 24 24">%s</symbol>'
                            % (nom, corps(fh.read())))
    with open(SORTIE, "w") as fh:
        fh.write("{# Icônes Lucide (ISC), embarquées par build_icones.py. Ne pas éditer à la main. #}\n"
                 '<svg xmlns="http://www.w3.org/2000/svg" style="display:none" aria-hidden="true">\n  '
                 + "\n  ".join(symboles) + "\n</svg>\n")
    print("%s : %d icônes, %d Ko" % (SORTIE, len(symboles), os.path.getsize(SORTIE) // 1024))


if __name__ == "__main__":
    main()
