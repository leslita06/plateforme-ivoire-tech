#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Parcours de bout en bout contre une instance qui tourne (preview, données seed_demo).

    python3 tests_parcours.py http://127.0.0.1:8820

Chaque étape s'arrête à la première erreur : un parcours vert prouve que les pages
répondent ET que les enchaînements (inscription → code → connexion → dépôt → offre →
demande → matching → relation → admin) fonctionnent avec un vrai navigateur sans JS.
"""
import http.cookiejar
import re
import sys
import urllib.parse
import urllib.request
import uuid

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8820"
MDP = "Demo-2026-ivoire"


class Nav:
    def __init__(self):
        self.cj = http.cookiejar.CookieJar()
        self.o = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cj))
        self.dernier = ""

    def get(self, chemin, attendu=200):
        r = self.o.open(BASE + chemin)
        self.dernier = r.read().decode()
        assert r.status == attendu, "%s → %s" % (chemin, r.status)
        return self.dernier

    def post(self, chemin, **champs):
        data = urllib.parse.urlencode(champs, doseq=True).encode()
        r = self.o.open(urllib.request.Request(BASE + chemin, data=data))
        self.dernier = r.read().decode()
        return r.url, self.dernier

    def csrf(self):
        m = re.search(r'name="csrf" value="([0-9a-f]+)"', self.dernier)
        assert m, "pas de jeton csrf dans la page"
        return m.group(1)

    def connexion(self, email):
        url, _ = self.post("/connexion", email=email, mot_de_passe=MDP)
        assert url.endswith("/tableau") or "/admin" in url, "connexion %s → %s" % (email, url)
        return self


def ok(msg):
    print("  ✓", msg)


print("== accueil et inscription")
n = Nav()
assert "Créer un compte" in n.get("/")
suffixe = uuid.uuid4().hex[:6]
email = "test-%s@exemple.ci" % suffixe
# un nom unique par run : sinon l'admin valide la « Startup Test » d'un run précédent, plus ancienne
ORG = "Startup Test %s" % suffixe
url, html = n.post("/inscription", prenom="Test", nom="Parcours", fonction="CEO", email=email,
                   mot_de_passe=MDP, type="startup", org_nom=ORG, programme="next15")
code = re.search(r'class="code">(\d{6})<', html)
assert code, "le code de démonstration ne s'affiche pas"
url, html = n.post("/verifier", email=email, code=code.group(1))
assert url.endswith("/tableau?m=bienvenue"), url
assert "en attente de validation" in html
ok("inscription, code, vérification, tableau en attente")
n.get("/organisation")
n.post("/organisation", csrf=n.csrf(), nom=ORG, description="Une startup de test.", site="", ville="Abidjan",
       effectif="5", stade="amorcage", programme="next15", secteurs=["Fintech"], besoin_financement="150")
n.get("/organisation")
assert "Une startup de test." in n.dernier
ok("fiche organisation enregistrée")
n.get("/offres")
assert "Compte professionnel" in n.dernier and "Crédits cloud" in n.dernier and "Diagnostic comptable" not in n.dernier, "filtre de cible"
ok("catalogue filtré par cible (startup ne voit pas l'offre PME)")

print("== dépôt de document, multipart")
n.get("/documents")
csrf = n.csrf()
frontiere = "----frontiere%s" % uuid.uuid4().hex
corps = b""
for k, v in (("csrf", csrf), ("nom", "Présentation"), ("categorie", "deck"), ("visibilite", "investisseurs")):
    corps += ("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n" % (frontiere, k, v)).encode()
corps += ("--%s\r\nContent-Disposition: form-data; name=\"fichier\"; filename=\"deck.pdf\"\r\nContent-Type: application/pdf\r\n\r\n" % frontiere).encode()
corps += b"%PDF-1.4 test\n" + ("\r\n--%s--\r\n" % frontiere).encode()
r = n.o.open(urllib.request.Request(BASE + "/documents/deposer", data=corps, headers={"Content-Type": "multipart/form-data; boundary=" + frontiere}))
assert r.url.endswith("/documents?m=depose"), r.url
html = r.read().decode()
assert "Présentation" in html and "v1" in html
r = n.o.open(urllib.request.Request(BASE + "/documents/deposer", data=corps, headers={"Content-Type": "multipart/form-data; boundary=" + frontiere}))
assert "v2" in r.read().decode(), "le second dépôt sous le même nom doit faire une v2"
ok("dépôt, puis nouvelle version du même document")

print("== administration : validation")
a = Nav().connexion("admin@ivoire.tech")
a.get("/admin")
assert ORG in a.dernier and "BLOK Technology" in a.dernier
oid = re.search(r'/organisations/([0-9a-f]+)">%s<' % re.escape(ORG), a.dernier).group(1)
a.post("/admin/organisations/%s/statut" % oid, csrf=a.csrf(), statut="validee")
a.get("/admin/export/organisations.csv")
assert ORG in a.dernier and "mot_de_passe" not in a.dernier
ok("organisation validée, export CSV sans mot de passe")

print("== entreprise validée : demande d'offre, matching, relation")
n.get("/tableau")
assert "en attente de validation" not in n.dernier
n.get("/matching")
assert "Janngo Capital" in n.dernier and "Saviu Ventures" in n.dernier
premier = re.search(r'<strong>([^<]+)</strong></a><br>', n.dernier).group(1)
assert premier == "Saviu Ventures", "attendu Saviu en tête (secteur + stade + ticket), obtenu %s" % premier
ok("matching classé, Saviu en tête pour une fintech en amorçage à 150 M")
offre_id = re.search(r'/offres/([0-9a-f]+)">Crédits cloud', n.get("/offres")).group(1)
n.get("/offres/%s" % offre_id)
url, _ = n.post("/offres/%s/demander" % offre_id, csrf=n.csrf(), message="Nous déployons en octobre.")
assert url.endswith("m=demande_envoyee"), url
saviu = re.search(r'/organisations/([0-9a-f]+)"><strong>Saviu Ventures', n.get("/matching")).group(1)
url, _ = n.post("/relations/demander", csrf=n.csrf(), vers=saviu, message="Amorçage fintech, 150 M FCFA.")
assert url.endswith("m=relation_envoyee"), url
ok("demande d'offre et de mise en relation envoyées")

print("== partenaire : accepte la demande ; investisseur : accepte la relation")
p = Nav().connexion("odc@orange.ci")
p.get("/offres/%s" % offre_id)
did = re.search(r'/demandes/([0-9a-f]+)/repondre', p.dernier).group(1)
url, _ = p.post("/demandes/%s/repondre" % did, csrf=p.csrf(), statut="acceptee")
assert url.endswith("m=repondu")
p.get("/offres/nouvelle")
url, _ = p.post("/offres/nouvelle", csrf=p.csrf(), titre="Atelier produit", categorie="formation", description="Deux jours d'atelier produit avec les coachs du centre.",
                conditions="", cible="toutes", valide_jusqua="")
assert "m=cree" in url, url
nouvelle = re.search(r'/offres/([0-9a-f]+)\?m=cree', url).group(1)
p.get("/offres/%s" % nouvelle)
url, _ = p.post("/offres/%s/statut" % nouvelle, csrf=p.csrf(), statut="publiee")
assert url.endswith("m=publiee"), url
ok("partenaire : demande acceptée, offre créée puis publiée")
i = Nav().connexion("deals@saviu.vc")
i.get("/matching")
assert ORG in i.dernier and "reçue" in i.dernier
i.get("/tableau")
rid = re.search(r'/relations/([0-9a-f]+)/repondre', i.dernier).group(1)
url, _ = i.post("/relations/%s/repondre" % rid, csrf=i.csrf(), statut="acceptee")
assert url.endswith("m=repondu")
i.get("/organisations/%s" % oid)
assert "Présentation" in i.dernier, "l'investisseur validé doit voir le document ouvert aux investisseurs"
ok("investisseur : relation acceptée, document ouvert visible")
n.get("/tableau")
assert "acceptée" in n.dernier and "Atelier produit" in n.get("/offres")
ok("l'entreprise voit l'acceptation et la nouvelle offre")

print("== garde-fous")
anonyme = Nav()
r = anonyme.o.open(BASE + "/tableau")  # urllib suit le 303 : l'anonyme doit atterrir sur la connexion
assert "/connexion" in r.url and "Tableau de bord" not in r.read().decode(), "un anonyme a vu le tableau (%s)" % r.url
try:
    n.get("/admin")
    raise SystemExit("un membre a vu l'administration")
except urllib.error.HTTPError as e:
    assert e.code == 403
try:
    n.post("/relations/demander", csrf="faux", vers=saviu, message="x")
    raise SystemExit("csrf non vérifié")
except urllib.error.HTTPError as e:
    assert e.code == 400
ok("accès anonyme, admin et csrf refusés")
print("\nPARCOURS COMPLET OK")
