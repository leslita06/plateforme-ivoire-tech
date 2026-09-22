# Plateforme d'accompagnement Ivoire Tech

Une place unique où les entreprises accompagnées (startups Next 15, PME Scale Up), les
partenaires, les investisseurs et l'administration se retrouvent : les partenaires y
publient leurs offres, les entreprises y déposent leurs documents et les tiennent à jour,
et un moteur de correspondance rapproche les entreprises des investisseurs dont la thèse
colle à leur profil.

L'application est écrite pour être **hébergée ailleurs que chez nous**, sur les serveurs de
l'État ivoirien. Elle tient dans un dossier, n'appelle aucun service tiers, et se déploie
sur n'importe quel serveur Linux avec Python 3.11 ou plus récent, ou en conteneur.

---

## 1. Ce que la plateforme fait

### Comptes et organisations

Chacun crée son compte lui-même, sans intervention d'un administrateur : il choisit le
type de son organisation (startup, PME, partenaire, investisseur, administration), reçoit
un code à six chiffres par email, et accède à son tableau de bord. L'organisation reste
« en attente de validation » tant qu'un administrateur ne l'a pas confirmée, et n'apparaît
ni dans l'annuaire, ni dans les correspondances, avant cette validation. Un deuxième
membre de la même organisation rejoint la fiche existante au lieu d'en créer une seconde.

### Offres des partenaires

Un partenaire crée une offre (compte bancaire, crédits cloud, accompagnement juridique,
comptabilité, formation…), la décrit, fixe ses conditions, choisit sa cible (toutes les
entreprises, les startups seulement, les PME seulement) et une date de fin, puis la
publie. Une entreprise voit le catalogue filtré par ce qui la concerne, demande une offre
en un formulaire, et le partenaire accepte ou refuse depuis la fiche de l'offre. L'adresse
email de chacun n'est transmise à l'autre qu'au moment de l'acceptation.

### Documents

Chaque organisation dépose ses documents (présentation, comptes, business plan, statuts,
attestations) et choisit qui les voit : personne, les investisseurs validés, les
partenaires, ou toutes les organisations validées. Un dépôt sous un nom déjà utilisé crée
une **version** supplémentaire au lieu d'écraser la précédente, et l'historique reste
consultable. Formats acceptés : pdf, pptx, docx, xlsx, png, jpg, jusqu'à 20 Mo.

Une ressource n'est pas toujours un fichier : un **lien** (Google Doc, présentation en
ligne, site, vidéo) s'ajoute au même endroit, dans le second onglet, et reste à jour tout
seul au lieu d'une copie figée. Les PDF et les images s'ouvrent dans le navigateur, et le
bouton voisin force le téléchargement quand on veut le fichier sur son poste.

### Correspondance entreprises et investisseurs

Le score est explicable, ligne par ligne, et affiché comme tel aux deux parties :

| Critère | Points |
|---|---|
| Secteur commun | 3 points par secteur, plafonné à 6 |
| Stade recherché par l'investisseur | 3 points |
| Besoin de financement dans la fourchette de tickets | 3 points, ou 1 si la fourchette est proche |
| Entreprise sans levée en cours | le score est divisé par deux |

Une entreprise demande une mise en relation, l'investisseur accepte ou décline, et les
coordonnées ne circulent qu'après acceptation.

### Administration

Un administrateur valide ou suspend les organisations, change le rôle d'un compte, retire
une offre, lit le journal des actions et exporte en CSV les organisations, les comptes,
les offres, les demandes, les mises en relation et les documents. Aucun export ne contient
de mot de passe.

---

## 2. Choix techniques, et pourquoi

| Brique | Choix | Raison |
|---|---|---|
| Serveur | FastAPI sur uvicorn | Standard, documenté, tenu par une large communauté |
| Base | SQLite, un fichier | Aucune base à administrer ; le SQL est standard, la migration vers PostgreSQL ne touche qu'un module |
| Gabarits | Jinja, HTML rendu par le serveur | Les pages fonctionnent sans JavaScript, donc sur une connexion lente et sur un vieux navigateur |
| Mots de passe | scrypt, bibliothèque standard | Pas de dépendance de chiffrement à maintenir |
| Sessions | Cookie signé HMAC-SHA256, douze heures | Pas de stockage de session, donc pas de Redis |
| Emails | SMTP standard | L'État branche son propre relais |

Quatre dépendances en tout (`requirements.txt`). Le code fait environ 1 700 lignes, en
français, commentées, dans `app/`.

---

## 3. Déploiement sur un serveur de l'État

### 3.1 Sans conteneur, Debian ou Ubuntu

Installer Python et le serveur web :

    apt install python3 python3-venv nginx

Déposer le code dans `/opt/plateforme-ivoire-tech`, créer l'environnement et les
dépendances :

    python3 -m venv /opt/plateforme-ivoire-tech/venv
    /opt/plateforme-ivoire-tech/venv/bin/pip install -r /opt/plateforme-ivoire-tech/requirements.txt

Créer le dossier de données, qui appartient au compte de service :

    mkdir -p /var/lib/plateforme-ivoire-tech

Copier `.env.example` en `/etc/plateforme-ivoire-tech.env`, le remplir, et surtout générer
la clé de signature une bonne fois :

    python3 -c "import secrets; print(secrets.token_hex(32))"

Le fichier d'environnement contient un secret : il appartient à root et n'est lisible que
par lui (`chmod 600`).

### 3.2 Service systemd

Fichier `/etc/systemd/system/plateforme-ivoire-tech.service` :

    [Unit]
    Description=Plateforme d'accompagnement Ivoire Tech
    After=network.target

    [Service]
    Type=exec
    User=plateforme
    Group=plateforme
    WorkingDirectory=/opt/plateforme-ivoire-tech
    EnvironmentFile=/etc/plateforme-ivoire-tech.env
    ExecStart=/opt/plateforme-ivoire-tech/venv/bin/uvicorn app.main:app \
      --host 127.0.0.1 --port 8000 --proxy-headers --forwarded-allow-ips '*'
    Restart=always
    RestartSec=5
    NoNewPrivileges=true
    PrivateTmp=true
    ProtectSystem=strict
    ProtectHome=true
    ReadWritePaths=/var/lib/plateforme-ivoire-tech

    [Install]
    WantedBy=multi-user.target

Puis `systemctl daemon-reload`, `systemctl enable --now plateforme-ivoire-tech`.

### 3.3 Nginx et HTTPS

L'application n'écoute qu'en local : c'est Nginx qui reçoit le trafic, termine le HTTPS et
relaie.

    server {
        listen 443 ssl http2;
        server_name plateforme.exemple.ci;

        ssl_certificate     /etc/ssl/certs/plateforme.pem;
        ssl_certificate_key /etc/ssl/private/plateforme.key;

        client_max_body_size 25m;   # les dépôts vont jusqu'à 20 Mo

        location / {
            proxy_pass http://127.0.0.1:8000;
            proxy_set_header Host $host;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }

    server {
        listen 80;
        server_name plateforme.exemple.ci;
        return 301 https://$host$request_uri;
    }

### 3.4 En conteneur

    cp .env.example .env    # à remplir
    docker compose up -d --build

Le conteneur écoute sur `127.0.0.1:8000` et écrit dans le volume `./data`. Le serveur web
du ministère se place devant, comme ci-dessus.

### 3.5 Sauvegarde

Tout l'état tient dans le dossier de données : la base `plateforme.sqlite3` et le dossier
`uploads/`. Une sauvegarde quotidienne, cohérente même application allumée :

    sqlite3 /var/lib/plateforme-ivoire-tech/plateforme.sqlite3 ".backup /sauvegardes/plateforme-$(date +%F).sqlite3"
    tar czf /sauvegardes/uploads-$(date +%F).tar.gz -C /var/lib/plateforme-ivoire-tech uploads

Restaurer revient à remettre ces deux éléments en place et à redémarrer le service.

### 3.6 Supervision

`GET /sante` répond `{"ok": true, "organisations": N}` quand l'application et sa base
tiennent. C'est l'adresse à donner à la sonde de l'hébergeur.

---

## 4. Variables d'environnement

Toutes sont décrites dans `.env.example`. Les trois qui comptent en production :

- `PLATEFORME_ENV=production` retire le bandeau d'essai et cesse d'afficher les codes de
  vérification à l'écran ;
- `PLATEFORME_SECRET` signe les sessions ; sans elle, l'application refuse de démarrer en
  production ;
- `PLATEFORME_DATA` désigne le dossier à sauvegarder.

Sans configuration SMTP, les emails ne partent pas : ils sont écrits dans
`data/courrier-sortant.log`. Cela convient à une recette, jamais à un service ouvert.

---

## 5. Sécurité

- Mots de passe hachés par scrypt, avec un sel par compte ; dix caractères minimum, une
  lettre et un chiffre.
- Cinq échecs de connexion sur une même adresse déclenchent dix minutes d'attente.
- Jeton anti-CSRF exigé sur chaque formulaire.
- Un document ne se télécharge que si le demandeur a le droit de le voir, contrôlé à
  chaque requête, et jamais par une adresse devinable : les fichiers passent par
  l'application, qui vérifie le droit avant de rendre le fichier.
- Les coordonnées ne circulent qu'après acceptation d'une mise en relation ou d'une
  demande d'offre.
- Le journal garde qui a fait quoi, et quand.

Avant l'ouverture au public, deux gestes restent à la charge de l'hébergeur : le
certificat HTTPS et la configuration du relais SMTP.

---

## 6. Recette

Démarrer une instance d'essai et poser un jeu de démonstration :

    ./run.sh
    python3 seed_demo.py

Le jeu contient douze organisations réelles du terrain ivoirien, un administrateur, des
offres et des thèses d'investissement, avec le même mot de passe pour tous les comptes,
indiqué par le script.

Vérifier que la chaîne complète fonctionne, du compte créé jusqu'à la mise en relation
acceptée :

    python3 tests_parcours.py http://127.0.0.1:8820

Le script parcourt l'application comme un navigateur sans JavaScript : inscription, code,
fiche, catalogue filtré, dépôt d'un document puis de sa version suivante, validation par
l'administrateur, correspondance, demande d'offre, mise en relation, réponses du
partenaire et de l'investisseur, et refus des accès anonyme, administrateur et sans jeton
anti-CSRF. Il se termine par `PARCOURS COMPLET OK`.

---

## 7. Organisation du code

    app/main.py        toutes les routes, du formulaire d'inscription aux exports CSV
    app/db.py          schéma SQLite et helpers de connexion
    app/auth.py        mots de passe, sessions, jetons anti-CSRF
    app/matching.py    référentiels (secteurs, stades) et calcul de correspondance
    app/mailer.py      envoi SMTP, ou journal quand rien n'est configuré
    app/templates/     gabarits Jinja, une page par écran
    app/static/        une feuille de style, aucune dépendance front
    app/templates/_icones.html  le sprite d'icônes, fabriqué par build_icones.py
    build_icones.py    assemble les icônes Lucide embarquées, sans appel à une CDN
    captures.py        captures d'écran de l'instance d'essai
    build_apercu.py    l'aperçu PDF, une page par écran
    seed_demo.py       jeu de démonstration
    tests_parcours.py  recette de bout en bout
