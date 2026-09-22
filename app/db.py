# -*- coding: utf-8 -*-
"""Base SQLite de la plateforme : schéma et petits helpers.

Un seul fichier, pas d'ORM : le jour où l'État l'héberge, l'équipe lit un schéma SQL et
des requêtes, pas une couche d'abstraction. Passer à PostgreSQL revient à remplacer ce
module (les requêtes sont en SQL standard, sans extension SQLite).
"""
import os
import sqlite3
import time
import uuid

RACINE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.environ.get("PLATEFORME_DATA", os.path.join(RACINE, "data"))
DB_PATH = os.path.join(DATA_DIR, "plateforme.sqlite3")
UPLOADS = os.path.join(DATA_DIR, "uploads")

SCHEMA = """
CREATE TABLE IF NOT EXISTS organisations (
  id TEXT PRIMARY KEY,
  type TEXT NOT NULL,                 -- startup | pme | partenaire | investisseur | administration
  nom TEXT NOT NULL,
  programme TEXT DEFAULT '',          -- next15 | scaleup | autre (startups et PME)
  secteurs TEXT DEFAULT '',           -- liste séparée par des virgules
  stade TEXT DEFAULT '',              -- idee | amorcage | croissance | scale
  description TEXT DEFAULT '',
  site TEXT DEFAULT '',
  ville TEXT DEFAULT '',
  effectif TEXT DEFAULT '',
  besoin_financement INTEGER DEFAULT 0,   -- millions de FCFA, 0 = pas de levée en cours
  ticket_min INTEGER DEFAULT 0,           -- investisseurs : fourchette de ticket, millions de FCFA
  ticket_max INTEGER DEFAULT 0,
  stades_cibles TEXT DEFAULT '',          -- investisseurs : stades recherchés
  statut TEXT NOT NULL DEFAULT 'en_attente',   -- en_attente | validee | refusee
  created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS utilisateurs (
  id TEXT PRIMARY KEY,
  email TEXT NOT NULL UNIQUE,
  mot_de_passe TEXT NOT NULL,
  prenom TEXT DEFAULT '',
  nom TEXT DEFAULT '',
  fonction TEXT DEFAULT '',
  role TEXT NOT NULL,                 -- membre | admin
  org_id TEXT REFERENCES organisations(id),
  email_verifie INTEGER NOT NULL DEFAULT 0,
  actif INTEGER NOT NULL DEFAULT 1,
  created_at REAL NOT NULL,
  derniere_connexion REAL
);
CREATE TABLE IF NOT EXISTS codes (
  id TEXT PRIMARY KEY,
  email TEXT NOT NULL,
  code TEXT NOT NULL,
  usage TEXT NOT NULL,                -- verification | reinitialisation
  expire_at REAL NOT NULL,
  utilise INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS documents (
  id TEXT PRIMARY KEY,
  org_id TEXT NOT NULL REFERENCES organisations(id),
  nom TEXT NOT NULL,
  categorie TEXT NOT NULL,            -- deck | business_plan | etats_financiers | statuts | autre
  version INTEGER NOT NULL DEFAULT 1,
  fichier TEXT NOT NULL DEFAULT '',   -- chemin relatif sous uploads/ (vide pour un lien)
  lien TEXT NOT NULL DEFAULT '',      -- adresse web, quand la ressource n'est pas un fichier déposé
  taille INTEGER NOT NULL,
  depose_par TEXT REFERENCES utilisateurs(id),
  visibilite TEXT NOT NULL DEFAULT 'prive',   -- prive | investisseurs | partenaires | tous
  created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS offres (
  id TEXT PRIMARY KEY,
  org_id TEXT NOT NULL REFERENCES organisations(id),
  titre TEXT NOT NULL,
  categorie TEXT NOT NULL,
  description TEXT NOT NULL,
  conditions TEXT DEFAULT '',
  cible TEXT NOT NULL DEFAULT 'toutes',   -- startup | pme | toutes
  valide_jusqua TEXT DEFAULT '',
  statut TEXT NOT NULL DEFAULT 'brouillon',   -- brouillon | publiee | archivee
  created_at REAL NOT NULL,
  updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS demandes_offre (
  id TEXT PRIMARY KEY,
  offre_id TEXT NOT NULL REFERENCES offres(id),
  org_id TEXT NOT NULL REFERENCES organisations(id),
  message TEXT DEFAULT '',
  statut TEXT NOT NULL DEFAULT 'en_attente',  -- en_attente | acceptee | refusee
  created_at REAL NOT NULL,
  UNIQUE(offre_id, org_id)
);
CREATE TABLE IF NOT EXISTS mises_en_relation (
  id TEXT PRIMARY KEY,
  de_org TEXT NOT NULL REFERENCES organisations(id),
  vers_org TEXT NOT NULL REFERENCES organisations(id),
  message TEXT DEFAULT '',
  statut TEXT NOT NULL DEFAULT 'en_attente',  -- en_attente | acceptee | refusee
  created_at REAL NOT NULL,
  UNIQUE(de_org, vers_org)
);
CREATE TABLE IF NOT EXISTS journal (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  quand REAL NOT NULL,
  qui TEXT,
  action TEXT NOT NULL,
  detail TEXT DEFAULT ''
);
"""


def connexion():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(UPLOADS, exist_ok=True)
    c = sqlite3.connect(DB_PATH, check_same_thread=False)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    c.execute("PRAGMA journal_mode = WAL")
    return c


# Colonnes ajoutées après coup : une base déjà en service ne se recrée pas, et
# `CREATE TABLE IF NOT EXISTS` ne la fait pas évoluer.
MIGRATIONS = [("documents", "lien", "TEXT NOT NULL DEFAULT ''")]


def initialiser():
    c = connexion()
    c.executescript(SCHEMA)
    for (table, colonne, definition) in MIGRATIONS:
        presentes = [r["name"] for r in c.execute("PRAGMA table_info(%s)" % table)]
        if colonne not in presentes:
            c.execute("ALTER TABLE %s ADD COLUMN %s %s" % (table, colonne, definition))
    c.commit()
    c.close()


def nouvel_id():
    return uuid.uuid4().hex


def maintenant():
    return time.time()


def journaliser(c, qui, action, detail=""):
    c.execute("INSERT INTO journal (quand, qui, action, detail) VALUES (?, ?, ?, ?)",
              (maintenant(), qui, action, detail))
