#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Jeu de démonstration : un administrateur, des entreprises du portefeuille, des partenaires et
des investisseurs RÉELS (règle de Leslie du 21/09 : des vraies entreprises, des interlocuteurs
fictifs), quelques offres et une thèse par investisseur, pour que le matching ait quelque chose
à classer.

    python3 seed_demo.py            # n'écrit que si la base est vide
    python3 seed_demo.py --raz      # repart de zéro (preview seulement)

Comptes : mot de passe « Demo-2026-ivoire » pour tous.
"""
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app import auth, db  # noqa: E402

MDP = "Demo-2026-ivoire"

ORGS = [
    # (type, nom, programme, secteurs, stade, description, site, ville, besoin, tmin, tmax, stades_cibles)
    ("startup", "Jèko", "next15", "Fintech, Commerce et distribution", "croissance",
     "Paiement marchand en Côte d'Ivoire : les commerçants acceptent Orange Money, MTN, Wave, Moov, Visa et Mastercard depuis une application et la Jèko Box, et se constituent un historique financier.",
     "https://jeko.africa", "Abidjan", 650, 0, 0, ""),
    ("startup", "Djoli", "next15", "Agritech, Logistique et mobilité", "amorcage",
     "Place de marché B2B entre restaurants et producteurs agricoles : commande, livraison et paiement, avec un réseau de productrices.",
     "https://djoli.africa", "Abidjan", 300, 0, 0, ""),
    ("startup", "Flot", "next15", "Logistique et mobilité, Énergie et climat", "amorcage",
     "Mobilité électrique : location-vente de deux-roues électriques aux livreurs et aux chauffeurs, avec un réseau de recharge.",
     "https://flot.africa", "Abidjan", 450, 0, 0, ""),
    ("pme", "Danaya", "scaleup", "Fintech, Services aux entreprises", "croissance",
     "RegTech : vérification d'identité KYC et KYB, filtrage AML, pour les banques, les fintech et les assureurs de l'UEMOA.",
     "https://danaya.africa", "Abidjan", 0, 0, 0, ""),
    ("pme", "Revvo", "scaleup", "Commerce et distribution", "croissance",
     "Recommerce : smartphones reconditionnés, garantis, vendus en ligne et en boutique, avec paiement échelonné.",
     "https://revvo.africa", "Abidjan", 200, 0, 0, ""),
    ("partenaire", "Ecobank Côte d'Ivoire", "", "Fintech, Services aux entreprises", "",
     "Banque panafricaine, partenaire bancaire des programmes Ivoire Tech.", "https://ecobank.com", "Abidjan", 0, 0, 0, ""),
    ("partenaire", "Orange Digital Center Côte d'Ivoire", "", "Intelligence artificielle, Éducation", "",
     "Programmes de formation, incubation et mise en réseau des porteurs de projets numériques.", "https://orange.ci", "Abidjan", 0, 0, 0, ""),
    ("partenaire", "Cabinet CERIN", "", "Services aux entreprises", "",
     "Expertise comptable, fiscalité et conseil aux PME.", "", "Abidjan", 0, 0, 0, ""),
    ("investisseur", "Janngo Capital", "", "Fintech, Agritech, Santé, Logistique et mobilité", "",
     "Fonds panafricain, investit dans des entreprises technologiques à impact, avec un objectif de parité.",
     "https://janngo.africa", "Abidjan", 0, 200, 2000, "amorcage, croissance"),
    ("investisseur", "Saviu Ventures", "", "Fintech, Commerce et distribution, Logistique et mobilité", "",
     "Fonds d'amorçage dédié à l'Afrique francophone.", "https://saviu.vc", "Abidjan", 0, 100, 700, "amorcage"),
    ("investisseur", "Partech Africa", "", "Fintech, Intelligence artificielle, Commerce et distribution", "",
     "Fonds de capital-risque, séries A et B en Afrique.", "https://partechpartners.com", "Dakar", 0, 1500, 6000, "croissance, scale"),
]

OFFRES = [
    ("Ecobank Côte d'Ivoire", "Compte professionnel sans frais la première année", "banque",
     "Ouverture de compte accélérée pour les lauréates, frais de tenue de compte offerts douze mois, accès au TPE et au paiement marchand.",
     "Sur présentation de l'attestation de sélection au programme.", "toutes", "2027-06-30"),
    ("Orange Digital Center Côte d'Ivoire", "Crédits cloud et accompagnement technique", "cloud",
     "Crédits d'infrastructure et accès aux ateliers techniques du centre, avec un référent pour six mois.",
     "Startups Next 15 uniquement, projet déployé ou en cours de déploiement.", "startup", "2027-03-31"),
    ("Cabinet CERIN", "Diagnostic comptable et fiscal offert", "comptabilite",
     "Un diagnostic de deux jours sur la tenue des comptes, les obligations fiscales et le pilotage de trésorerie, restitué au dirigeant.",
     "PME Scale Up, sur rendez-vous.", "pme", ""),
]

UTILISATEURS = [
    # (email, prénom, nom, fonction, organisation, rôle)
    ("admin@ivoire.tech", "Naminsita", "Bakayoko", "Administration de la plateforme", None, "admin"),
    ("awa@jeko.africa", "Awa", "Koné", "Directrice des opérations", "Jèko", "membre"),
    ("moussa@djoli.africa", "Moussa", "Diabaté", "Cofondateur", "Djoli", "membre"),
    ("fanta@flot.africa", "Fanta", "Traoré", "Directrice générale", "Flot", "membre"),
    ("michel@danaya.africa", "Michel", "Edjoa", "Directeur technique", "Danaya", "membre"),
    ("yao@revvo.africa", "Yao", "Kouadio", "Directeur général", "Revvo", "membre"),
    ("partenariats@ecobank.ci", "Aïcha", "Bamba", "Responsable partenariats", "Ecobank Côte d'Ivoire", "membre"),
    ("odc@orange.ci", "Kader", "Ouattara", "Responsable programmes", "Orange Digital Center Côte d'Ivoire", "membre"),
    ("contact@cerin.ci", "Roger", "N'Guessan", "Expert-comptable associé", "Cabinet CERIN", "membre"),
    ("deals@janngo.africa", "Mariam", "Sylla", "Directrice d'investissement", "Janngo Capital", "membre"),
    ("deals@saviu.vc", "Ismaël", "Cissé", "Partner", "Saviu Ventures", "membre"),
    ("africa@partechpartners.com", "Clémence", "Aka", "Principal", "Partech Africa", "membre"),
]


# (organisation, nom du document, catégorie, visibilité, nombre de versions)
DOCUMENTS = [
    ("Jèko", "Présentation investisseurs", "deck", "investisseurs", 2),
    ("Jèko", "États financiers 2025", "etats_financiers", "investisseurs", 1),
    ("Jèko", "Attestation de sélection Next 15", "autre", "partenaires", 1),
    ("Djoli", "Présentation investisseurs", "deck", "investisseurs", 1),
    ("Flot", "Business plan 2026", "business_plan", "investisseurs", 1),
    ("Danaya", "Statuts", "statuts", "prive", 1),
]

# (entreprise, titre de l'offre, statut, message)
DEMANDES = [
    ("Jèko", "Compte professionnel sans frais la première année", "acceptee",
     "Nous ouvrons deux points de vente à Yopougon en novembre et cherchons un TPE."),
    ("Djoli", "Crédits cloud et accompagnement technique", "en_attente",
     "Notre place de marché double de volume chaque trimestre, l'infrastructure suit mal."),
    ("Revvo", "Diagnostic comptable et fiscal offert", "acceptee",
     "Nous passons de deux à cinq boutiques et voulons cadrer la fiscalité avant."),
]

# (entreprise, investisseur, statut, message)
RELATIONS = [
    ("Jèko", "Janngo Capital", "acceptee", "Série A en préparation, 650 M FCFA, paiement marchand."),
    ("Djoli", "Saviu Ventures", "en_attente", "Amorçage 300 M FCFA, place de marché agricole B2B."),
    ("Flot", "Saviu Ventures", "acceptee", "Amorçage 450 M FCFA, deux-roues électriques et recharge."),
]

PDF_FACTICE = (b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
               b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
               b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 595 842]>>endobj\n"
               b"% " + b"document de demonstration " * 4000 + b"\n"
               b"trailer<</Root 1 0 R>>\n%%EOF\n")


def main():
    raz = "--raz" in sys.argv
    if raz and auth.ENV == "production":
        raise SystemExit("--raz est interdit en production")
    if raz and os.path.exists(db.DATA_DIR):
        shutil.rmtree(db.DATA_DIR)
    db.initialiser()
    c = db.connexion()
    if c.execute("SELECT COUNT(*) FROM utilisateurs").fetchone()[0]:
        print("base non vide, rien à faire (--raz pour repartir de zéro)")
        return
    ids = {}
    for (t, nom, prog, sect, stade, desc, site, ville, besoin, tmin, tmax, stc) in ORGS:
        oid = db.nouvel_id(); ids[nom] = oid
        c.execute("INSERT INTO organisations (id, type, nom, programme, secteurs, stade, description, site, ville, besoin_financement, "
                  "ticket_min, ticket_max, stades_cibles, statut, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'validee',?)",
                  (oid, t, nom, prog, sect, stade, desc, site, ville, besoin, tmin, tmax, stc, db.maintenant()))
    mdp = auth.hacher(MDP)
    for (email, prenom, nom, fonction, orgnom, role) in UTILISATEURS:
        c.execute("INSERT INTO utilisateurs (id, email, mot_de_passe, prenom, nom, fonction, role, org_id, email_verifie, created_at) "
                  "VALUES (?,?,?,?,?,?,?,?,1,?)",
                  (db.nouvel_id(), email, mdp, prenom, nom, fonction, role, ids.get(orgnom), db.maintenant()))
    for (orgnom, titre, cat, desc, cond, cible, jusqua) in OFFRES:
        c.execute("INSERT INTO offres (id, org_id, titre, categorie, description, conditions, cible, valide_jusqua, statut, created_at, updated_at) "
                  "VALUES (?,?,?,?,?,?,?,?,'publiee',?,?)",
                  (db.nouvel_id(), ids[orgnom], titre, cat, desc, cond, cible, jusqua, db.maintenant(), db.maintenant()))
    membres = {}
    for (email, _p, _n, _f, orgnom, _r) in UTILISATEURS:
        if orgnom and orgnom not in membres:
            membres[orgnom] = c.execute("SELECT id FROM utilisateurs WHERE email = ?", (email,)).fetchone()[0]
    for (orgnom, nom, cat, vis, versions) in DOCUMENTS:
        for v in range(1, versions + 1):
            did = db.nouvel_id()
            dossier = os.path.join(db.UPLOADS, ids[orgnom]); os.makedirs(dossier, exist_ok=True)
            relatif = os.path.join(ids[orgnom], "%s_v%d.pdf" % (did, v))
            with open(os.path.join(db.UPLOADS, relatif), "wb") as fh:
                fh.write(PDF_FACTICE)
            c.execute("INSERT INTO documents (id, org_id, nom, categorie, version, fichier, taille, depose_par, visibilite, created_at) "
                      "VALUES (?,?,?,?,?,?,?,?,?,?)",
                      (did, ids[orgnom], nom, cat, v, relatif, len(PDF_FACTICE), membres.get(orgnom), vis, db.maintenant()))
    offres_par_titre = {r["titre"]: r["id"] for r in c.execute("SELECT id, titre FROM offres")}
    for (orgnom, titre, statut, message) in DEMANDES:
        c.execute("INSERT INTO demandes_offre (id, offre_id, org_id, message, statut, created_at) VALUES (?,?,?,?,?,?)",
                  (db.nouvel_id(), offres_par_titre[titre], ids[orgnom], message, statut, db.maintenant()))
    for (orgnom, investisseur, statut, message) in RELATIONS:
        c.execute("INSERT INTO mises_en_relation (id, de_org, vers_org, message, statut, created_at) VALUES (?,?,?,?,?,?)",
                  (db.nouvel_id(), ids[orgnom], ids[investisseur], message, statut, db.maintenant()))

    # une organisation en attente, pour montrer la file de validation
    c.execute("INSERT INTO organisations (id, type, nom, programme, secteurs, stade, description, statut, created_at) "
              "VALUES (?,?,?,?,?,?,?,'en_attente',?)",
              (db.nouvel_id(), "startup", "BLOK Technology", "next15", "Immobilier et construction, Commerce et distribution", "amorcage",
               "Place de marché de matériaux de construction, en attente de validation.", db.maintenant()))
    db.journaliser(c, "seed", "jeu_de_demonstration", "%d organisations, %d comptes, %d offres" % (len(ORGS) + 1, len(UTILISATEURS), len(OFFRES)))
    c.commit(); c.close()
    print("OK : %d organisations, %d comptes (mot de passe %s), %d offres, %d documents, %d demandes, %d relations"
          % (len(ORGS) + 1, len(UTILISATEURS), MDP, len(OFFRES), sum(d[4] for d in DOCUMENTS), len(DEMANDES), len(RELATIONS)))


if __name__ == "__main__":
    main()
