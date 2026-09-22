# -*- coding: utf-8 -*-
"""Le matching : un score lisible, expliqué à l'écran, jamais une boîte noire.

Entre une entreprise (startup ou PME) et un investisseur :
  · secteurs en commun : 3 points par secteur, plafonné à 6 ;
  · stade de l'entreprise dans les stades cibles de l'investisseur : 3 points ;
  · besoin de financement dans la fourchette de ticket : 3 points (1 si l'investisseur
    n'a pas renseigné de fourchette) ;
  · pas de levée en cours : le score est divisé par deux, l'investisseur peut quand
    même suivre l'entreprise.
Entre une entreprise et une offre partenaire : la cible (startup, PME, toutes).
"""

SECTEURS = ["Fintech", "Agritech", "Santé", "Éducation", "Logistique et mobilité", "Commerce et distribution",
            "Énergie et climat", "Industrie", "Immobilier et construction", "Médias et création",
            "Services aux entreprises", "Intelligence artificielle", "Autre"]
STATUTS = {"en_attente": "en attente", "validee": "validée", "refusee": "refusée",
           "publiee": "publiée", "brouillon": "brouillon", "archivee": "archivée",
           "acceptee": "acceptée", "declinee": "déclinée"}

STADES = [("idee", "Idée ou prototype"), ("amorcage", "Amorçage, premiers clients"),
          ("croissance", "Croissance, revenus réguliers"), ("scale", "Passage à l'échelle")]
CATEGORIES_OFFRES = [("cloud", "Cloud et infrastructure"), ("juridique", "Juridique"),
                     ("comptabilite", "Comptabilité et fiscalité"), ("banque", "Banque et paiement"),
                     ("formation", "Formation"), ("recrutement", "Recrutement"),
                     ("marketing", "Marketing et communication"), ("logistique", "Logistique"), ("autre", "Autre")]
CATEGORIES_DOCS = [("deck", "Présentation"), ("business_plan", "Business plan"),
                   ("etats_financiers", "États financiers"), ("statuts", "Statuts et documents légaux"),
                   ("autre", "Autre")]
TYPES_ORG = [("startup", "Startup"), ("pme", "PME"), ("partenaire", "Partenaire"),
             ("investisseur", "Investisseur"), ("administration", "Administration")]
PROGRAMMES = [("next15", "Ivoire Tech Next 15"), ("scaleup", "Ivoire Tech Scale Up"), ("autre", "Hors programme")]


def liste(s):
    return [x.strip() for x in (s or "").split(",") if x.strip()]


def libelle(code, table):
    return dict(table).get(code, code)


def score_investisseur(entreprise, investisseur):
    """Rend (score, explications)."""
    pts, pourquoi = 0, []
    communs = sorted(set(liste(entreprise["secteurs"])) & set(liste(investisseur["secteurs"])))
    if communs:
        pts += min(6, 3 * len(communs))
        pourquoi.append("secteur%s en commun : %s" % ("s" if len(communs) > 1 else "", ", ".join(communs)))
    if entreprise["stade"] and entreprise["stade"] in liste(investisseur["stades_cibles"]):
        pts += 3
        pourquoi.append("stade recherché")
    besoin = entreprise["besoin_financement"] or 0
    tmin, tmax = investisseur["ticket_min"] or 0, investisseur["ticket_max"] or 0
    if besoin and tmax and tmin <= besoin <= tmax:
        pts += 3
        pourquoi.append("besoin dans la fourchette de ticket")
    elif besoin and not tmax:
        pts += 1
    if not besoin:
        pts = pts // 2
        pourquoi.append("pas de levée en cours")
    return pts, pourquoi


def offre_visible_pour(entreprise, offre):
    return offre["cible"] == "toutes" or offre["cible"] == entreprise["type"]
