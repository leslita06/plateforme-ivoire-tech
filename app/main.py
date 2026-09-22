# -*- coding: utf-8 -*-
"""Plateforme d'accompagnement Ivoire Tech : partenaires, offres, matching, documents.

Demandée par Leslie le 22/09/26 (vocal 39884, topic Ministère) : « les partenaires vont
pouvoir mettre leurs offres, le matching, des VCs, des startups, des PME… télécharger des
documents et les mettre à jour… une plateforme qu'on ne va pas hoster chez moi, demain sur
les serveurs du gouvernement ivoirien… des règles de création de compte de manière
autonome ».

Parti pris : une application Python autoportante (FastAPI + SQLite + gabarits Jinja), sans
service tiers, sans framework front, déployable sur n'importe quel serveur Linux avec
Python 3.11+, ou en conteneur. Voir README.md pour le déploiement.

    uvicorn app.main:app --host 127.0.0.1 --port 8820
"""
import csv
import io
import os
import re
import time

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import auth, db, mailer
from .matching import (CATEGORIES_DOCS, CATEGORIES_OFFRES, PROGRAMMES, SECTEURS, STADES, STATUTS, TYPES_ORG,
                       libelle, liste, offre_visible_pour, score_investisseur)

HERE = os.path.dirname(os.path.abspath(__file__))
NOM_PLATEFORME = os.environ.get("PLATEFORME_NOM", "Plateforme Ivoire Tech")
BASE_URL = os.environ.get("PLATEFORME_BASE_URL", "http://127.0.0.1:8820")
PREVIEW = auth.ENV != "production"
TAILLE_MAX = 20 * 1024 * 1024
EXTENSIONS = {".pdf", ".pptx", ".docx", ".xlsx", ".png", ".jpg", ".jpeg"}
TYPES_ENTREPRISE = ("startup", "pme")

app = FastAPI(title=NOM_PLATEFORME, docs_url=None, redoc_url=None)
app.mount("/static", StaticFiles(directory=os.path.join(HERE, "static")), name="static")
templates = Jinja2Templates(directory=os.path.join(HERE, "templates"))
templates.env.globals.update(
    NOM=NOM_PLATEFORME, PREVIEW=PREVIEW, SECTEURS=SECTEURS, STADES=STADES, TYPES_ORG=TYPES_ORG,
    PROGRAMMES=PROGRAMMES, CATEGORIES_OFFRES=CATEGORIES_OFFRES, CATEGORIES_DOCS=CATEGORIES_DOCS,
    libelle=libelle, liste=liste, dict=dict,
)
def ic(nom, classe=""):
    """Une icône du sprite `_icones.html`. Jamais un glyphe unicode à la place d'une icône."""
    from markupsafe import Markup
    return Markup('<svg class="ic %s" aria-hidden="true"><use href="#ic-%s"></use></svg>' % (classe, nom))


EXTENSION_ICONE = {".pdf": "pdf", ".png": "image", ".jpg": "image", ".jpeg": "image",
                   ".xlsx": "tableur", ".pptx": "presentation", ".docx": "pdf"}
APERCU_DANS_LE_NAVIGATEUR = {".pdf": "application/pdf", ".png": "image/png",
                             ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}


def icone_document(d):
    if d["lien"]:
        return "lien"
    return EXTENSION_ICONE.get(os.path.splitext(d["fichier"])[1].lower(), "pdf")


def initiales(nom):
    """Faute de logo, les initiales de l'organisation : une pastille de couleur vaut
    mieux qu'un logo inventé ou qu'un glyphe générique."""
    mots = [m for m in re.split(r"[^0-9A-Za-zÀ-ÿ]+", nom or "") if m]
    return ("".join(m[0] for m in mots[:2]) or "?").upper()


templates.env.globals.update(ic=ic, icone_document=icone_document, initiales=initiales)
templates.env.filters["libelle"] = libelle
templates.env.filters["jour"] = lambda v: ("%s/%s/%s" % (v[8:10], v[5:7], v[0:4])) if v and len(v) == 10 and v[4] == "-" else (v or "")
templates.env.filters["statut"] = lambda v: STATUTS.get(v, (v or "").replace("_", " "))
templates.env.filters["date"] = lambda t: time.strftime("%d/%m/%Y", time.localtime(t or 0))
templates.env.filters["dateheure"] = lambda t: time.strftime("%d/%m/%Y %H:%M", time.localtime(t or 0))

db.initialiser()

# tentatives de connexion par adresse : cinq échecs, puis dix minutes d'attente
_tentatives = {}


# ───────────────────────────── helpers ─────────────────────────────
def courant(request):
    """Rend (utilisateur, organisation, session) ou (None, None, None)."""
    s = auth.lire_session(request.cookies.get("session"))
    if not s:
        return None, None, None
    c = db.connexion()
    u = c.execute("SELECT * FROM utilisateurs WHERE id = ? AND actif = 1", (s["u"],)).fetchone()
    org = c.execute("SELECT * FROM organisations WHERE id = ?", (u["org_id"],)).fetchone() if u and u["org_id"] else None
    c.close()
    if not u:
        return None, None, None
    return u, org, s


def exiger(request, admin=False):
    u, org, s = courant(request)
    if not u:
        raise HTTPException(status_code=303, headers={"Location": "/connexion?m=connexion_requise"})
    if admin and u["role"] != "admin":
        raise HTTPException(status_code=403, detail="Réservé aux administrateurs")
    return u, org, s


def verifier_csrf(s, csrf):
    if not s or csrf != s.get("csrf"):
        raise HTTPException(status_code=400, detail="Formulaire expiré, rechargez la page")


def page(request, gabarit, **ctx):
    u, org, s = courant(request)
    ctx.update(request=request, u=u, org=org, csrf=(s or {}).get("csrf", ""), m=request.query_params.get("m", ""))
    return templates.TemplateResponse(request, gabarit, ctx)


def rediriger(url, m=None):
    return RedirectResponse(url + ("?m=" + m if m else ""), status_code=303)


def email_valide(e):
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", e or ""))


def envoyer_code(c, email, usage):
    code = auth.code_numerique()
    c.execute("INSERT INTO codes (id, email, code, usage, expire_at) VALUES (?, ?, ?, ?, ?)",
              (db.nouvel_id(), email, code, usage, db.maintenant() + 1800))
    objet = "%s : votre code" % NOM_PLATEFORME
    texte = ("Bonjour,\n\nVotre code %s est : %s\nIl est valable trente minutes.\n\n%s"
             % ("de vérification" if usage == "verification" else "de réinitialisation", code, NOM_PLATEFORME))
    parti = mailer.envoyer(email, objet, texte)
    return code if not parti else None   # en preview sans SMTP, le code s'affiche à l'écran


def code_valide(c, email, code, usage):
    r = c.execute("SELECT * FROM codes WHERE email = ? AND code = ? AND usage = ? AND utilise = 0 AND expire_at > ?",
                  (email, code, usage, db.maintenant())).fetchone()
    if not r:
        return False
    c.execute("UPDATE codes SET utilise = 1 WHERE id = ?", (r["id"],))
    return True


def entreprise_active(org):
    return org and org["type"] in TYPES_ENTREPRISE and org["statut"] == "validee"


# ───────────────────────────── accueil et comptes ─────────────────────────────
@app.get("/", response_class=HTMLResponse)
def accueil(request: Request):
    u, org, _ = courant(request)
    if u:
        return rediriger("/tableau")
    c = db.connexion()
    n = {k: c.execute("SELECT COUNT(*) FROM organisations WHERE type = ? AND statut = 'validee'", (k,)).fetchone()[0]
         for k, _ in TYPES_ORG}
    n["offres"] = c.execute("SELECT COUNT(*) FROM offres WHERE statut = 'publiee'").fetchone()[0]
    c.close()
    return page(request, "accueil.html", n=n)


@app.get("/inscription", response_class=HTMLResponse)
def inscription_form(request: Request):
    return page(request, "inscription.html", valeurs={})


@app.post("/inscription")
async def inscription(request: Request):
    f = await request.form()
    v = {k: (f.get(k) or "").strip() for k in ("email", "prenom", "nom", "fonction", "type", "org_nom", "programme")}
    v["email"] = v["email"].lower()
    mdp = f.get("mot_de_passe") or ""
    erreurs = []
    if not email_valide(v["email"]):
        erreurs.append("Adresse email invalide.")
    if not auth.mot_de_passe_acceptable(mdp):
        erreurs.append("Le mot de passe doit faire au moins dix caractères, avec une lettre et un chiffre.")
    if v["type"] not in dict(TYPES_ORG) or v["type"] == "administration":
        erreurs.append("Choisissez le type de votre organisation.")
    if len(v["org_nom"]) < 2:
        erreurs.append("Le nom de l'organisation est obligatoire.")
    if not v["prenom"] or not v["nom"]:
        erreurs.append("Prénom et nom sont obligatoires.")
    c = db.connexion()
    if c.execute("SELECT 1 FROM utilisateurs WHERE email = ?", (v["email"],)).fetchone():
        erreurs.append("Un compte existe déjà avec cette adresse. Connectez-vous ou réinitialisez votre mot de passe.")
    if erreurs:
        c.close()
        return page(request, "inscription.html", valeurs=v, erreurs=erreurs)
    org_id, user_id = db.nouvel_id(), db.nouvel_id()
    c.execute("INSERT INTO organisations (id, type, nom, programme, created_at) VALUES (?, ?, ?, ?, ?)",
              (org_id, v["type"], v["org_nom"], v["programme"] if v["type"] in TYPES_ENTREPRISE else "", db.maintenant()))
    c.execute("INSERT INTO utilisateurs (id, email, mot_de_passe, prenom, nom, fonction, role, org_id, created_at) "
              "VALUES (?, ?, ?, ?, ?, ?, 'membre', ?, ?)",
              (user_id, v["email"], auth.hacher(mdp), v["prenom"], v["nom"], v["fonction"], org_id, db.maintenant()))
    code_affiche = envoyer_code(c, v["email"], "verification")
    db.journaliser(c, v["email"], "inscription", "%s · %s" % (v["type"], v["org_nom"]))
    c.commit(); c.close()
    return page(request, "verifier.html", email=v["email"], code_affiche=code_affiche)


@app.get("/verifier", response_class=HTMLResponse)
def verifier_form(request: Request, email: str = ""):
    return page(request, "verifier.html", email=email.lower(), code_affiche=None)


@app.post("/verifier")
def verifier(request: Request, email: str = Form(...), code: str = Form(...)):
    email = email.strip().lower(); code = code.strip()
    c = db.connexion()
    if not code_valide(c, email, code, "verification"):
        c.close()
        return page(request, "verifier.html", email=email, code_affiche=None, erreur="Code invalide ou expiré.")
    c.execute("UPDATE utilisateurs SET email_verifie = 1, derniere_connexion = ? WHERE email = ?", (db.maintenant(), email))
    u = c.execute("SELECT id FROM utilisateurs WHERE email = ?", (email,)).fetchone()
    db.journaliser(c, email, "email_verifie")
    c.commit(); c.close()
    r = rediriger("/tableau", "bienvenue")
    r.set_cookie("session", auth.creer_session(u["id"]), httponly=True, samesite="lax", secure=not PREVIEW,
                 max_age=auth.DUREE_SESSION)
    return r


@app.post("/verifier/renvoyer")
def renvoyer_code(request: Request, email: str = Form(...)):
    email = email.strip().lower()
    c = db.connexion()
    u = c.execute("SELECT * FROM utilisateurs WHERE email = ? AND email_verifie = 0", (email,)).fetchone()
    code_affiche = envoyer_code(c, email, "verification") if u else None
    c.commit(); c.close()
    return page(request, "verifier.html", email=email, code_affiche=code_affiche, info="Un nouveau code a été envoyé.")


@app.get("/connexion", response_class=HTMLResponse)
def connexion_form(request: Request):
    return page(request, "connexion.html")


@app.post("/connexion")
def connexion(request: Request, email: str = Form(...), mot_de_passe: str = Form(...)):
    email = email.strip().lower()
    echecs, depuis = _tentatives.get(email, (0, 0))
    if echecs >= 5 and time.time() - depuis < 600:
        return page(request, "connexion.html", erreur="Trop de tentatives. Réessayez dans dix minutes.")
    c = db.connexion()
    u = c.execute("SELECT * FROM utilisateurs WHERE email = ? AND actif = 1", (email,)).fetchone()
    if not u or not auth.verifier_mdp(mot_de_passe, u["mot_de_passe"]):
        _tentatives[email] = (echecs + 1, time.time())
        c.close()
        return page(request, "connexion.html", erreur="Email ou mot de passe incorrect.")
    _tentatives.pop(email, None)
    if not u["email_verifie"]:
        code_affiche = envoyer_code(c, email, "verification")
        c.commit(); c.close()
        return page(request, "verifier.html", email=email, code_affiche=code_affiche,
                    info="Votre adresse n'est pas encore vérifiée : un code vient de vous être envoyé.")
    c.execute("UPDATE utilisateurs SET derniere_connexion = ? WHERE id = ?", (db.maintenant(), u["id"]))
    db.journaliser(c, email, "connexion")
    c.commit(); c.close()
    r = rediriger("/tableau")
    r.set_cookie("session", auth.creer_session(u["id"]), httponly=True, samesite="lax", secure=not PREVIEW,
                 max_age=auth.DUREE_SESSION)
    return r


@app.post("/deconnexion")
def deconnexion(request: Request):
    r = rediriger("/", "deconnecte")
    r.delete_cookie("session")
    return r


@app.get("/mot-de-passe-oublie", response_class=HTMLResponse)
def oubli_form(request: Request):
    return page(request, "oubli.html", etape=1)


@app.post("/mot-de-passe-oublie")
def oubli(request: Request, email: str = Form(...)):
    email = email.strip().lower()
    c = db.connexion()
    u = c.execute("SELECT 1 FROM utilisateurs WHERE email = ? AND actif = 1", (email,)).fetchone()
    code_affiche = envoyer_code(c, email, "reinitialisation") if u else None
    c.commit(); c.close()
    # même écran que le compte existe ou non : on ne révèle pas quelles adresses sont inscrites
    return page(request, "oubli.html", etape=2, email=email, code_affiche=code_affiche)


@app.post("/reinitialiser")
def reinitialiser(request: Request, email: str = Form(...), code: str = Form(...), mot_de_passe: str = Form(...)):
    email = email.strip().lower()
    if not auth.mot_de_passe_acceptable(mot_de_passe):
        return page(request, "oubli.html", etape=2, email=email, code_affiche=None,
                    erreur="Le mot de passe doit faire au moins dix caractères, avec une lettre et un chiffre.")
    c = db.connexion()
    if not code_valide(c, email, code.strip(), "reinitialisation"):
        c.close()
        return page(request, "oubli.html", etape=2, email=email, code_affiche=None, erreur="Code invalide ou expiré.")
    c.execute("UPDATE utilisateurs SET mot_de_passe = ?, email_verifie = 1 WHERE email = ?", (auth.hacher(mot_de_passe), email))
    db.journaliser(c, email, "mot_de_passe_reinitialise")
    c.commit(); c.close()
    return rediriger("/connexion", "mdp_change")


# ───────────────────────────── tableau de bord et organisation ─────────────────────────────
@app.get("/tableau", response_class=HTMLResponse)
def tableau(request: Request):
    u, org, s = exiger(request)
    c = db.connexion()
    ctx = {}
    if u["role"] == "admin":
        c.close()
        return rediriger("/admin")
    ctx["docs"] = c.execute("SELECT COUNT(*) FROM documents WHERE org_id = ?", (org["id"],)).fetchone()[0]
    if org["type"] in TYPES_ENTREPRISE:
        ctx["offres"] = c.execute("SELECT o.*, g.nom AS partenaire FROM offres o JOIN organisations g ON g.id = o.org_id "
                                  "WHERE o.statut = 'publiee' AND (o.cible = 'toutes' OR o.cible = ?) "
                                  "ORDER BY o.updated_at DESC LIMIT 5", (org["type"],)).fetchall()
        ctx["demandes"] = c.execute("SELECT d.*, o.titre FROM demandes_offre d JOIN offres o ON o.id = d.offre_id "
                                    "WHERE d.org_id = ? ORDER BY d.created_at DESC", (org["id"],)).fetchall()
        ctx["relations"] = c.execute("SELECT r.*, g.nom AS autre FROM mises_en_relation r JOIN organisations g "
                                     "ON g.id = CASE WHEN r.de_org = ? THEN r.vers_org ELSE r.de_org END "
                                     "WHERE r.de_org = ? OR r.vers_org = ? ORDER BY r.created_at DESC",
                                     (org["id"], org["id"], org["id"])).fetchall()
    elif org["type"] == "partenaire":
        ctx["mes_offres"] = c.execute("SELECT * FROM offres WHERE org_id = ? ORDER BY updated_at DESC", (org["id"],)).fetchall()
        ctx["demandes"] = c.execute("SELECT d.*, o.titre, g.nom AS entreprise, g.type AS type_entreprise FROM demandes_offre d "
                                    "JOIN offres o ON o.id = d.offre_id JOIN organisations g ON g.id = d.org_id "
                                    "WHERE o.org_id = ? ORDER BY d.created_at DESC", (org["id"],)).fetchall()
    elif org["type"] == "investisseur":
        ctx["relations"] = c.execute("SELECT r.*, g.nom AS autre FROM mises_en_relation r JOIN organisations g "
                                     "ON g.id = CASE WHEN r.de_org = ? THEN r.vers_org ELSE r.de_org END "
                                     "WHERE r.de_org = ? OR r.vers_org = ? ORDER BY r.created_at DESC",
                                     (org["id"], org["id"], org["id"])).fetchall()
    c.close()
    return page(request, "tableau.html", **ctx)


@app.get("/organisation", response_class=HTMLResponse)
def organisation_form(request: Request):
    u, org, s = exiger(request)
    if not org:
        return rediriger("/admin")
    return page(request, "organisation.html")


@app.post("/organisation")
async def organisation(request: Request):
    u, org, s = exiger(request)
    f = await request.form()
    verifier_csrf(s, f.get("csrf"))
    champs = {k: (f.get(k) or "").strip() for k in ("nom", "description", "site", "ville", "effectif", "stade", "programme")}
    if len(champs["nom"]) < 2:
        return page(request, "organisation.html", erreur="Le nom est obligatoire.")
    secteurs = ", ".join(x for x in f.getlist("secteurs") if x in SECTEURS)
    stades_cibles = ", ".join(x for x in f.getlist("stades_cibles") if x in dict(STADES))

    def entier(k):
        try:
            return max(0, int(f.get(k) or 0))
        except ValueError:
            return 0

    c = db.connexion()
    c.execute("UPDATE organisations SET nom = ?, description = ?, site = ?, ville = ?, effectif = ?, stade = ?, programme = ?, "
              "secteurs = ?, stades_cibles = ?, besoin_financement = ?, ticket_min = ?, ticket_max = ? WHERE id = ?",
              (champs["nom"], champs["description"], champs["site"], champs["ville"], champs["effectif"],
               champs["stade"] if champs["stade"] in dict(STADES) else "",
               champs["programme"] if champs["programme"] in dict(PROGRAMMES) else "",
               secteurs, stades_cibles, entier("besoin_financement"), entier("ticket_min"), entier("ticket_max"), org["id"]))
    db.journaliser(c, u["email"], "organisation_modifiee", org["id"])
    c.commit(); c.close()
    return rediriger("/organisation", "enregistre")


# ───────────────────────────── documents ─────────────────────────────
@app.get("/documents", response_class=HTMLResponse)
def documents(request: Request):
    u, org, s = exiger(request)
    if not org:
        return rediriger("/admin")
    c = db.connexion()
    docs = c.execute("SELECT d.*, x.prenom, x.nom AS nom_deposant FROM documents d LEFT JOIN utilisateurs x ON x.id = d.depose_par "
                     "WHERE d.org_id = ? ORDER BY d.nom, d.version DESC", (org["id"],)).fetchall()
    c.close()
    return page(request, "documents.html", docs=docs)


@app.post("/documents/lien")
def deposer_lien(request: Request, lien: str = Form(...), nom: str = Form(""),
                 categorie: str = Form("autre"), visibilite: str = Form("prive"), csrf: str = Form("")):
    """Une ressource n'est pas toujours un fichier : un Google Doc, un Slides, un site se
    partagent par leur adresse, et la recopier en PDF ferait vivre une version périmée."""
    u, org, s = exiger(request)
    verifier_csrf(s, csrf)
    lien = (lien or "").strip()
    if not re.match(r"^https?://[^\s]+\.[^\s]+", lien):
        return rediriger("/documents", "lien_invalide")
    nom = (nom or lien.split("//", 1)[-1].split("/")[0]).strip()[:120]
    categorie = categorie if categorie in dict(CATEGORIES_DOCS) else "autre"
    visibilite = visibilite if visibilite in ("prive", "investisseurs", "partenaires", "tous") else "prive"
    c = db.connexion()
    prec = c.execute("SELECT MAX(version) FROM documents WHERE org_id = ? AND nom = ?", (org["id"], nom)).fetchone()[0] or 0
    c.execute("INSERT INTO documents (id, org_id, nom, categorie, version, fichier, lien, taille, depose_par, visibilite, created_at) "
              "VALUES (?, ?, ?, ?, ?, '', ?, 0, ?, ?, ?)",
              (db.nouvel_id(), org["id"], nom, categorie, prec + 1, lien, u["id"], visibilite, db.maintenant()))
    db.journaliser(c, u["email"], "lien_ajoute", "%s v%d" % (nom, prec + 1))
    c.commit(); c.close()
    return rediriger("/documents", "lien_ajoute")


@app.post("/documents/deposer")
async def deposer(request: Request, fichier: UploadFile = File(...), nom: str = Form(""), categorie: str = Form("autre"),
                  visibilite: str = Form("prive"), csrf: str = Form("")):
    u, org, s = exiger(request)
    verifier_csrf(s, csrf)
    ext = os.path.splitext(fichier.filename or "")[1].lower()
    if ext not in EXTENSIONS:
        return rediriger("/documents", "format_refuse")
    contenu = await fichier.read()
    if len(contenu) > TAILLE_MAX:
        return rediriger("/documents", "trop_gros")
    nom = (nom or os.path.splitext(fichier.filename)[0]).strip()[:120]
    categorie = categorie if categorie in dict(CATEGORIES_DOCS) else "autre"
    visibilite = visibilite if visibilite in ("prive", "investisseurs", "partenaires", "tous") else "prive"
    c = db.connexion()
    # un dépôt sous un nom déjà présent est une NOUVELLE VERSION : l'ancienne reste téléchargeable
    prec = c.execute("SELECT MAX(version) FROM documents WHERE org_id = ? AND nom = ?", (org["id"], nom)).fetchone()[0] or 0
    doc_id = db.nouvel_id()
    dossier = os.path.join(db.UPLOADS, org["id"]); os.makedirs(dossier, exist_ok=True)
    relatif = os.path.join(org["id"], "%s_v%d%s" % (doc_id, prec + 1, ext))
    with open(os.path.join(db.UPLOADS, relatif), "wb") as fh:
        fh.write(contenu)
    c.execute("INSERT INTO documents (id, org_id, nom, categorie, version, fichier, taille, depose_par, visibilite, created_at) "
              "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
              (doc_id, org["id"], nom, categorie, prec + 1, relatif, len(contenu), u["id"], visibilite, db.maintenant()))
    db.journaliser(c, u["email"], "document_depose", "%s v%d" % (nom, prec + 1))
    c.commit(); c.close()
    return rediriger("/documents", "depose")


@app.get("/documents/{doc_id}/telecharger")
def telecharger(request: Request, doc_id: str, forcer: int = 0):
    u, org, s = exiger(request)
    c = db.connexion()
    d = c.execute("SELECT * FROM documents WHERE id = ?", (doc_id,)).fetchone()
    c.close()
    if not d:
        raise HTTPException(404)
    autorise = (u["role"] == "admin" or (org and org["id"] == d["org_id"]) or d["visibilite"] == "tous"
                or (org and d["visibilite"] == "investisseurs" and org["type"] == "investisseur" and org["statut"] == "validee")
                or (org and d["visibilite"] == "partenaires" and org["type"] == "partenaire" and org["statut"] == "validee"))
    if not autorise:
        raise HTTPException(403, "Ce document ne vous est pas ouvert")
    if d["lien"]:
        return RedirectResponse(d["lien"], status_code=303)
    chemin = os.path.join(db.UPLOADS, d["fichier"])
    ext = os.path.splitext(chemin)[1].lower()
    nom_fichier = "%s_v%d%s" % (d["nom"], d["version"], ext)
    # un PDF ou une image s'ouvre DANS le navigateur : forcer le téléchargement pour
    # regarder une pièce oblige à la sortir du poste, puis à la retrouver
    if ext in APERCU_DANS_LE_NAVIGATEUR and not forcer:
        return FileResponse(chemin, media_type=APERCU_DANS_LE_NAVIGATEUR[ext],
                            headers={"Content-Disposition": 'inline; filename="%s"' % nom_fichier})
    return FileResponse(chemin, filename=nom_fichier)


@app.post("/documents/{doc_id}/supprimer")
def supprimer_doc(request: Request, doc_id: str, csrf: str = Form("")):
    u, org, s = exiger(request)
    verifier_csrf(s, csrf)
    c = db.connexion()
    d = c.execute("SELECT * FROM documents WHERE id = ? AND org_id = ?", (doc_id, org["id"] if org else "")).fetchone()
    if d:
        if d["fichier"]:
            try:
                os.remove(os.path.join(db.UPLOADS, d["fichier"]))
            except OSError:
                pass
        c.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        db.journaliser(c, u["email"], "document_supprime", "%s v%d" % (d["nom"], d["version"]))
        c.commit()
    c.close()
    return rediriger("/documents", "supprime")


# ───────────────────────────── offres des partenaires ─────────────────────────────
@app.get("/offres", response_class=HTMLResponse)
def offres(request: Request, categorie: str = ""):
    u, org, s = exiger(request)
    c = db.connexion()
    if org and org["type"] == "partenaire":
        rows = c.execute("SELECT o.*, (SELECT COUNT(*) FROM demandes_offre d WHERE d.offre_id = o.id) AS n_demandes "
                         "FROM offres o WHERE o.org_id = ? ORDER BY o.updated_at DESC", (org["id"],)).fetchall()
        c.close()
        return page(request, "offres_partenaire.html", offres=rows)
    q = ("SELECT o.*, g.nom AS partenaire FROM offres o JOIN organisations g ON g.id = o.org_id WHERE o.statut = 'publiee'")
    args = []
    if org and org["type"] in TYPES_ENTREPRISE:
        q += " AND (o.cible = 'toutes' OR o.cible = ?)"; args.append(org["type"])
    if categorie in dict(CATEGORIES_OFFRES):
        q += " AND o.categorie = ?"; args.append(categorie)
    rows = c.execute(q + " ORDER BY o.updated_at DESC", args).fetchall()
    demandees = set()
    if org:
        demandees = {r["offre_id"] for r in c.execute("SELECT offre_id FROM demandes_offre WHERE org_id = ?", (org["id"],))}
    c.close()
    return page(request, "offres.html", offres=rows, categorie=categorie, demandees=demandees)


@app.get("/offres/nouvelle", response_class=HTMLResponse)
def offre_nouvelle(request: Request):
    u, org, s = exiger(request)
    if not org or org["type"] != "partenaire":
        raise HTTPException(403, "Réservé aux partenaires")
    return page(request, "offre_form.html", offre=None)


@app.post("/offres/nouvelle")
async def offre_creer(request: Request):
    u, org, s = exiger(request)
    if not org or org["type"] != "partenaire":
        raise HTTPException(403)
    f = await request.form()
    verifier_csrf(s, f.get("csrf"))
    v = {k: (f.get(k) or "").strip() for k in ("titre", "categorie", "description", "conditions", "cible", "valide_jusqua")}
    if len(v["titre"]) < 3 or len(v["description"]) < 10:
        return page(request, "offre_form.html", offre=v, erreur="Titre et description sont obligatoires.")
    oid = db.nouvel_id()
    c = db.connexion()
    c.execute("INSERT INTO offres (id, org_id, titre, categorie, description, conditions, cible, valide_jusqua, statut, created_at, updated_at) "
              "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'brouillon', ?, ?)",
              (oid, org["id"], v["titre"], v["categorie"] if v["categorie"] in dict(CATEGORIES_OFFRES) else "autre",
               v["description"], v["conditions"], v["cible"] if v["cible"] in ("startup", "pme", "toutes") else "toutes",
               v["valide_jusqua"], db.maintenant(), db.maintenant()))
    db.journaliser(c, u["email"], "offre_creee", v["titre"])
    c.commit(); c.close()
    return rediriger("/offres/%s" % oid, "cree")


@app.get("/offres/{oid}", response_class=HTMLResponse)
def offre(request: Request, oid: str):
    u, org, s = exiger(request)
    c = db.connexion()
    o = c.execute("SELECT o.*, g.nom AS partenaire, g.site AS site_partenaire, g.description AS desc_partenaire "
                  "FROM offres o JOIN organisations g ON g.id = o.org_id WHERE o.id = ?", (oid,)).fetchone()
    if not o:
        c.close(); raise HTTPException(404)
    proprietaire = org and org["id"] == o["org_id"]
    if o["statut"] != "publiee" and not proprietaire and u["role"] != "admin":
        c.close(); raise HTTPException(404)
    demandes = []
    ma_demande = None
    if proprietaire or u["role"] == "admin":
        demandes = c.execute("SELECT d.*, g.nom AS entreprise, g.type AS type_entreprise, g.site, g.description AS desc_entreprise "
                             "FROM demandes_offre d JOIN organisations g ON g.id = d.org_id WHERE d.offre_id = ? "
                             "ORDER BY d.created_at DESC", (oid,)).fetchall()
    elif org:
        ma_demande = c.execute("SELECT * FROM demandes_offre WHERE offre_id = ? AND org_id = ?", (oid, org["id"])).fetchone()
    c.close()
    return page(request, "offre.html", o=o, proprietaire=proprietaire, demandes=demandes, ma_demande=ma_demande)


@app.post("/offres/{oid}/modifier")
async def offre_modifier(request: Request, oid: str):
    u, org, s = exiger(request)
    f = await request.form()
    verifier_csrf(s, f.get("csrf"))
    c = db.connexion()
    o = c.execute("SELECT * FROM offres WHERE id = ? AND org_id = ?", (oid, org["id"] if org else "")).fetchone()
    if not o:
        c.close(); raise HTTPException(404)
    v = {k: (f.get(k) or "").strip() for k in ("titre", "categorie", "description", "conditions", "cible", "valide_jusqua")}
    c.execute("UPDATE offres SET titre = ?, categorie = ?, description = ?, conditions = ?, cible = ?, valide_jusqua = ?, updated_at = ? WHERE id = ?",
              (v["titre"] or o["titre"], v["categorie"] if v["categorie"] in dict(CATEGORIES_OFFRES) else o["categorie"],
               v["description"] or o["description"], v["conditions"], v["cible"] if v["cible"] in ("startup", "pme", "toutes") else o["cible"],
               v["valide_jusqua"], db.maintenant(), oid))
    db.journaliser(c, u["email"], "offre_modifiee", oid)
    c.commit(); c.close()
    return rediriger("/offres/%s" % oid, "enregistre")


@app.post("/offres/{oid}/statut")
def offre_statut(request: Request, oid: str, statut: str = Form(...), csrf: str = Form("")):
    u, org, s = exiger(request)
    verifier_csrf(s, csrf)
    if statut not in ("brouillon", "publiee", "archivee"):
        raise HTTPException(400)
    c = db.connexion()
    o = c.execute("SELECT o.*, g.statut AS statut_org FROM offres o JOIN organisations g ON g.id = o.org_id WHERE o.id = ?", (oid,)).fetchone()
    if not o or (u["role"] != "admin" and (not org or org["id"] != o["org_id"])):
        c.close(); raise HTTPException(404)
    if statut == "publiee" and o["statut_org"] != "validee":
        c.close()
        return rediriger("/offres/%s" % oid, "partenaire_non_valide")
    c.execute("UPDATE offres SET statut = ?, updated_at = ? WHERE id = ?", (statut, db.maintenant(), oid))
    db.journaliser(c, u["email"], "offre_" + statut, oid)
    c.commit(); c.close()
    return rediriger("/offres/%s" % oid, statut)


@app.post("/offres/{oid}/demander")
def offre_demander(request: Request, oid: str, message: str = Form(""), csrf: str = Form("")):
    u, org, s = exiger(request)
    verifier_csrf(s, csrf)
    if not entreprise_active(org):
        return rediriger("/offres/%s" % oid, "compte_non_valide")
    c = db.connexion()
    o = c.execute("SELECT * FROM offres WHERE id = ? AND statut = 'publiee'", (oid,)).fetchone()
    if not o or not offre_visible_pour(org, o):
        c.close(); raise HTTPException(404)
    c.execute("INSERT OR IGNORE INTO demandes_offre (id, offre_id, org_id, message, created_at) VALUES (?, ?, ?, ?, ?)",
              (db.nouvel_id(), oid, org["id"], message.strip()[:1000], db.maintenant()))
    db.journaliser(c, u["email"], "offre_demandee", oid)
    # le partenaire est prévenu par email
    for p in c.execute("SELECT email FROM utilisateurs WHERE org_id = ? AND actif = 1", (o["org_id"],)):
        mailer.envoyer(p["email"], "%s : une entreprise s'intéresse à votre offre" % NOM_PLATEFORME,
                       "%s a demandé à bénéficier de votre offre « %s ».\n\nRépondre : %s/offres/%s" % (org["nom"], o["titre"], BASE_URL, oid))
    c.commit(); c.close()
    return rediriger("/offres/%s" % oid, "demande_envoyee")


@app.post("/demandes/{did}/repondre")
def demande_repondre(request: Request, did: str, statut: str = Form(...), csrf: str = Form("")):
    u, org, s = exiger(request)
    verifier_csrf(s, csrf)
    if statut not in ("acceptee", "refusee"):
        raise HTTPException(400)
    c = db.connexion()
    d = c.execute("SELECT d.*, o.org_id AS partenaire_id, o.titre FROM demandes_offre d JOIN offres o ON o.id = d.offre_id WHERE d.id = ?", (did,)).fetchone()
    if not d or (u["role"] != "admin" and (not org or org["id"] != d["partenaire_id"])):
        c.close(); raise HTTPException(404)
    c.execute("UPDATE demandes_offre SET statut = ? WHERE id = ?", (statut, did))
    db.journaliser(c, u["email"], "demande_" + statut, did)
    for p in c.execute("SELECT email FROM utilisateurs WHERE org_id = ? AND actif = 1", (d["org_id"],)):
        mailer.envoyer(p["email"], "%s : réponse à votre demande" % NOM_PLATEFORME,
                       "Votre demande sur l'offre « %s » a été %s.\n\n%s/offres/%s" % (d["titre"], statut, BASE_URL, d["offre_id"]))
    c.commit(); c.close()
    return rediriger("/offres/%s" % d["offre_id"], "repondu")


# ───────────────────────────── matching et mises en relation ─────────────────────────────
@app.get("/matching", response_class=HTMLResponse)
def matching(request: Request):
    u, org, s = exiger(request)
    if not org or org["type"] not in TYPES_ENTREPRISE + ("investisseur",):
        return rediriger("/tableau")
    c = db.connexion()
    if org["type"] == "investisseur":
        cibles = c.execute("SELECT * FROM organisations WHERE type IN ('startup', 'pme') AND statut = 'validee'").fetchall()
        classes = sorted(((score_investisseur(e, org), e) for e in cibles), key=lambda t: -t[0][0])
    else:
        cibles = c.execute("SELECT * FROM organisations WHERE type = 'investisseur' AND statut = 'validee'").fetchall()
        classes = sorted(((score_investisseur(org, i), i) for i in cibles), key=lambda t: -t[0][0])
    relations = {}
    for r in c.execute("SELECT * FROM mises_en_relation WHERE de_org = ? OR vers_org = ?", (org["id"], org["id"])):
        relations[r["vers_org"] if r["de_org"] == org["id"] else r["de_org"]] = r
    c.close()
    return page(request, "matching.html", classes=classes, relations=relations)


@app.post("/relations/demander")
def relation_demander(request: Request, vers: str = Form(...), message: str = Form(""), csrf: str = Form("")):
    u, org, s = exiger(request)
    verifier_csrf(s, csrf)
    if not org or org["statut"] != "validee":
        return rediriger("/matching", "compte_non_valide")
    c = db.connexion()
    cible = c.execute("SELECT * FROM organisations WHERE id = ? AND statut = 'validee'", (vers,)).fetchone()
    if not cible or cible["id"] == org["id"]:
        c.close(); raise HTTPException(404)
    c.execute("INSERT OR IGNORE INTO mises_en_relation (id, de_org, vers_org, message, created_at) VALUES (?, ?, ?, ?, ?)",
              (db.nouvel_id(), org["id"], vers, message.strip()[:1000], db.maintenant()))
    db.journaliser(c, u["email"], "relation_demandee", "%s → %s" % (org["nom"], cible["nom"]))
    for p in c.execute("SELECT email FROM utilisateurs WHERE org_id = ? AND actif = 1", (vers,)):
        mailer.envoyer(p["email"], "%s : demande de mise en relation" % NOM_PLATEFORME,
                       "%s souhaite entrer en relation avec vous.\n\n%s\n\nRépondre : %s/tableau" % (org["nom"], message.strip()[:1000], BASE_URL))
    c.commit(); c.close()
    return rediriger("/matching", "relation_envoyee")


@app.post("/relations/{rid}/repondre")
def relation_repondre(request: Request, rid: str, statut: str = Form(...), csrf: str = Form("")):
    u, org, s = exiger(request)
    verifier_csrf(s, csrf)
    if statut not in ("acceptee", "refusee"):
        raise HTTPException(400)
    c = db.connexion()
    r = c.execute("SELECT * FROM mises_en_relation WHERE id = ? AND vers_org = ?", (rid, org["id"] if org else "")).fetchone()
    if not r:
        c.close(); raise HTTPException(404)
    c.execute("UPDATE mises_en_relation SET statut = ? WHERE id = ?", (statut, rid))
    db.journaliser(c, u["email"], "relation_" + statut, rid)
    if statut == "acceptee":
        # les deux parties reçoivent les coordonnées de l'autre : la plateforme met en relation, elle ne s'interpose pas
        for a, b in ((r["de_org"], r["vers_org"]), (r["vers_org"], r["de_org"])):
            contacts = c.execute("SELECT prenom, nom, email, fonction FROM utilisateurs WHERE org_id = ? AND actif = 1", (b,)).fetchall()
            nom_b = c.execute("SELECT nom FROM organisations WHERE id = ?", (b,)).fetchone()["nom"]
            texte = "Mise en relation acceptée avec %s.\n\nContacts :\n%s" % (
                nom_b, "\n".join("· %s %s, %s, %s" % (x["prenom"], x["nom"], x["fonction"], x["email"]) for x in contacts))
            for p in c.execute("SELECT email FROM utilisateurs WHERE org_id = ? AND actif = 1", (a,)):
                mailer.envoyer(p["email"], "%s : mise en relation acceptée" % NOM_PLATEFORME, texte)
    c.commit(); c.close()
    return rediriger("/tableau", "repondu")


@app.get("/annuaire", response_class=HTMLResponse)
def annuaire(request: Request, type: str = ""):
    u, org, s = exiger(request)
    c = db.connexion()
    q, args = "SELECT * FROM organisations WHERE statut = 'validee' AND type != 'administration'", []
    if type in dict(TYPES_ORG):
        q += " AND type = ?"; args.append(type)
    rows = c.execute(q + " ORDER BY type, nom", args).fetchall()
    c.close()
    return page(request, "annuaire.html", orgs=rows, type=type)


@app.get("/organisations/{oid}", response_class=HTMLResponse)
def fiche(request: Request, oid: str):
    u, org, s = exiger(request)
    c = db.connexion()
    o = c.execute("SELECT * FROM organisations WHERE id = ?", (oid,)).fetchone()
    if not o or (o["statut"] != "validee" and u["role"] != "admin" and (not org or org["id"] != oid)):
        c.close(); raise HTTPException(404)
    vis = ["tous"]
    if org and org["type"] == "investisseur" and org["statut"] == "validee":
        vis.append("investisseurs")
    if org and org["type"] == "partenaire" and org["statut"] == "validee":
        vis.append("partenaires")
    if u["role"] == "admin" or (org and org["id"] == oid):
        vis += ["prive", "investisseurs", "partenaires"]
    docs = c.execute("SELECT * FROM documents WHERE org_id = ? AND visibilite IN (%s) ORDER BY nom, version DESC"
                     % ",".join("?" * len(vis)), [oid] + vis).fetchall()
    offres_ = c.execute("SELECT * FROM offres WHERE org_id = ? AND statut = 'publiee'", (oid,)).fetchall() if o["type"] == "partenaire" else []
    membres = c.execute("SELECT prenom, nom, fonction FROM utilisateurs WHERE org_id = ? AND actif = 1", (oid,)).fetchall()
    c.close()
    return page(request, "fiche.html", o=o, docs=docs, offres=offres_, membres=membres)


# ───────────────────────────── administration ─────────────────────────────
@app.get("/admin", response_class=HTMLResponse)
def admin(request: Request):
    u, org, s = exiger(request, admin=True)
    c = db.connexion()
    stats = {k: c.execute("SELECT COUNT(*) FROM organisations WHERE type = ? AND statut = 'validee'", (k,)).fetchone()[0] for k, _ in TYPES_ORG}
    stats["utilisateurs"] = c.execute("SELECT COUNT(*) FROM utilisateurs").fetchone()[0]
    stats["offres"] = c.execute("SELECT COUNT(*) FROM offres WHERE statut = 'publiee'").fetchone()[0]
    stats["demandes"] = c.execute("SELECT COUNT(*) FROM demandes_offre").fetchone()[0]
    stats["relations"] = c.execute("SELECT COUNT(*) FROM mises_en_relation").fetchone()[0]
    stats["documents"] = c.execute("SELECT COUNT(*) FROM documents").fetchone()[0]
    attente = c.execute("SELECT o.*, (SELECT email FROM utilisateurs x WHERE x.org_id = o.id LIMIT 1) AS email, "
                        "(SELECT email_verifie FROM utilisateurs x WHERE x.org_id = o.id LIMIT 1) AS verifie "
                        "FROM organisations o WHERE o.statut = 'en_attente' ORDER BY o.created_at").fetchall()
    orgs = c.execute("SELECT o.*, (SELECT COUNT(*) FROM utilisateurs x WHERE x.org_id = o.id) AS n_membres "
                     "FROM organisations o WHERE o.statut != 'en_attente' ORDER BY o.type, o.nom").fetchall()
    offres_ = c.execute("SELECT o.*, g.nom AS partenaire FROM offres o JOIN organisations g ON g.id = o.org_id ORDER BY o.updated_at DESC LIMIT 50").fetchall()
    journal = c.execute("SELECT * FROM journal ORDER BY id DESC LIMIT 40").fetchall()
    c.close()
    return page(request, "admin.html", stats=stats, attente=attente, orgs=orgs, offres=offres_, journal=journal)


@app.post("/admin/organisations/{oid}/statut")
def admin_statut(request: Request, oid: str, statut: str = Form(...), csrf: str = Form("")):
    u, org, s = exiger(request, admin=True)
    verifier_csrf(s, csrf)
    if statut not in ("validee", "refusee", "en_attente"):
        raise HTTPException(400)
    c = db.connexion()
    o = c.execute("SELECT * FROM organisations WHERE id = ?", (oid,)).fetchone()
    if not o:
        c.close(); raise HTTPException(404)
    c.execute("UPDATE organisations SET statut = ? WHERE id = ?", (statut, oid))
    db.journaliser(c, u["email"], "organisation_" + statut, o["nom"])
    for p in c.execute("SELECT email FROM utilisateurs WHERE org_id = ? AND actif = 1", (oid,)):
        mailer.envoyer(p["email"], "%s : votre compte" % NOM_PLATEFORME,
                       "Le compte de %s est %s.\n\n%s/tableau" % (o["nom"], "validé" if statut == "validee" else "refusé" if statut == "refusee" else "remis en attente", BASE_URL))
    c.commit(); c.close()
    return rediriger("/admin", "statut_change")


@app.post("/admin/utilisateurs/{uid}/role")
def admin_role(request: Request, uid: str, role: str = Form(...), csrf: str = Form("")):
    u, org, s = exiger(request, admin=True)
    verifier_csrf(s, csrf)
    if role not in ("membre", "admin") or uid == u["id"]:
        raise HTTPException(400)
    c = db.connexion()
    c.execute("UPDATE utilisateurs SET role = ? WHERE id = ?", (role, uid))
    db.journaliser(c, u["email"], "role_" + role, uid)
    c.commit(); c.close()
    return rediriger("/admin", "role_change")


@app.get("/admin/export/{table}.csv")
def admin_export(request: Request, table: str):
    u, org, s = exiger(request, admin=True)
    if table not in ("organisations", "utilisateurs", "offres", "demandes_offre", "mises_en_relation", "documents"):
        raise HTTPException(404)
    c = db.connexion()
    rows = c.execute("SELECT * FROM %s" % table).fetchall()
    c.close()
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    if rows:
        cols = [k for k in rows[0].keys() if k != "mot_de_passe"]
        w.writerow(cols)
        for r in rows:
            w.writerow([r[k] for k in cols])
    return Response(buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": "attachment; filename=%s.csv" % table})


@app.get("/sante")
def sante():
    """Sonde de supervision : l'hébergeur vérifie que l'application et sa base répondent."""
    c = db.connexion()
    n = c.execute("SELECT COUNT(*) FROM organisations").fetchone()[0]
    c.close()
    return {"ok": True, "organisations": n}
