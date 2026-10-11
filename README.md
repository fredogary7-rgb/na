# NAMARA

**Votre capital, une vision d'avenir.**

Plateforme financière et de gestion d'investissements destinée aux marchés
africains, opérant en franc CFA (**XOF** / **XAF**). Ce dépôt contient une
application **Flask** complète, structurée, testable et prête à recevoir des
intégrations de paiement réelles (SoleasPay) après configuration.

> ⚠️ Aucun paiement réel n'est activé par défaut. Les paiements réels et les
> produits d'investissement ne doivent être activés qu'après validation du cadre
> réglementaire applicable et fourniture de la documentation officielle du
> prestataire.

---

## Architecture

```
app/
  __init__.py           # application factory
  extensions.py         # SQLAlchemy, Migrate, CSRF, Login, Limiter
  constants.py          # pays, devises, opérateurs
  utils.py              # formatage FCFA, références
  models/               # 15 modèles SQLAlchemy
  services/             # finance (crédit/débit atomiques), paramètres, parrainage, investissement
  auth/                 # inscription, connexion, OTP, mot de passe oublié
  dashboard/            # tableau de bord, dépôts, retraits, transactions
  payments/             # fournisseurs + webhooks
  referrals/            # parrainage
  investments/          # investissements 120 jours
  admin/                # espace administrateur
  notifications/        # service de notifications
  public/               # pages publiques
  templates/            # vues Jinja2
  static/               # CSS, JS, images (logos)
config.py               # configurations dev / test / production
wsgi.py                 # point d'entrée WSGI
```

## Règles financières clés

- Les montants sont stockés en **entiers** dans la plus petite unité (1 unité = 1 FCFA).
- **Jamais** de nombres flottants pour les soldes.
- Les portefeuilles sont **séparés** : dépôts, bonus, revenus, commissions, retirable.
- Le **capital déposé** et le **bonus** ne sont **pas retirables** directement.
- Toute opération passe par le service financier central et génère une écriture
  comptable (`LedgerEntry`) immuable et idempotente.
- Un **dépôt** n'est crédité qu'après confirmation authentifiée du prestataire (webhook).
- Un **retrait** réserve les fonds de façon atomique et n'est « réussi » qu'après
  confirmation fiable ou traitement manuel audité.

## Démarrage local (développement)

Prérequis : Python 3.10+.

```bash
python -m venv .venv
# Windows :
.venv\Scripts\activate
# Linux/macOS :
source .venv/bin/activate

pip install -r requirements.txt

# Configurer l'environnement
copy .env.example .env        # (Windows) ou : cp .env.example .env

# Migrations de base de données
flask db init
flask db migrate -m "initial"
flask db upgrade

# Créer un compte administrateur (aucun mot de passe stocké en clair)
flask create-admin

# Lancer l'application (mode développement, SQLite)
flask run
```

L'application est alors disponible sur http://127.0.0.1:5000.

## Tests

```bash
pytest -q
```

Les tests utilisent SQLite et ne déclenchent jamais de paiement réel. Le
fournisseur `mock` est une simulation explicite réservée aux tests.

## Variables d'environnement

Voir `.env.example`. Les principales :

| Variable | Description |
|---|---|
| `SECRET_KEY` | Clé secrète Flask (obligatoire en production) |
| `DATABASE_URL` | URL SQLAlchemy (PostgreSQL en production) |
| `FLASK_ENV` | `development`, `testing` ou `production` |
| `PAYMENT_MODE` | `mock` (simulation) ou `soleaspay` |
| `SOLEASPAY_API_KEY` | Ajoutée ultérieurement (documentation officielle) |
| `SOLEASPAY_API_SECRET` | Ajoutée ultérieurement |
| `SOLEASPAY_BASE_URL` | Ajoutée ultérieurement |
| `SOLEASPAY_WEBHOOK_SECRET` | Ajoutée ultérieurement |
| `BONUS_INSCRIPTION` | Montant du bonus de bienvenue |
| `MIN_DEPOSIT` | Dépôt minimum |
| `MIN_WITHDRAWAL` | Retrait minimum |

## Production (PostgreSQL)

```bash
export DATABASE_URL="postgresql+psycopg2://user:password@host:5432/namara"
export FLASK_ENV=production
export SECRET_KEY="valeur-aleatoire-longue"
flask db upgrade
gunicorn -w 4 wsgi:app
```

Placez l'application derrière un reverse proxy HTTPS. Activez les en-têtes de
sécurité (HSTS, CSP) au niveau du proxy.

## Déploiement Railway

Le dépôt contient les fichiers nécessaires au déploiement sur
[Railway](https://railway.app) :

- `Procfile` — commande de démarrage (migrations puis `gunicorn`).
- `nixpacks.toml` — version Python 3.12.
- `railway.json` — healthcheck (`/health`) et politique de redémarrage.

### Étapes

1. **Créer le service** : dans Railway → *New Project* → *Deploy from GitHub repo*,
   sélectionnez `fredogary7-rgb/na`.
2. **Nom de domaine** : connectez `namara.win` (Railway → *Settings* → *Networking*
   → *Custom Domain*). Railway provisionne automatiquement le certificat HTTPS.
3. **Base de données** : ajoutez un plugin **PostgreSQL** dans Railway. Il fournit
   automatiquement `DATABASE_URL`.
4. **Variables d'environnement** (dans Railway, pas dans un fichier) :
   - `FLASK_ENV=production`
   - `SECRET_KEY` (valeur aléatoire longue)
   - `DATABASE_URL` (fournie par le plugin PostgreSQL)
   - `PAYMENT_MODE=mock` (tant que SoleasPay n'est pas configuré)
   - `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`
   - `TELEGRAM_WEBHOOK_URL=https://namara.win/support/telegram/webhook`
   - `TELEGRAM_MODE=webhook`
5. **Déployer**. Le `Procfile` lance `flask db upgrade` avant `gunicorn` (les
   migrations sont appliquées à chaque déploiement — retirez cette étape de la
   commande si vous préférez migrer manuellement).
6. **Après le premier déploiement**, exécutez une fois (Railway → *Shell* ou
   commande locale avec l'URL publique) :

   ```bash
   flask seed-faq                 # FAQ de support
   flask telegram-set-webhook     # active le webhook Telegram
   flask create-admin             # premier administrateur (interactif)
   ```

### Healthcheck

Railway appelle `/health` qui vérifie la connexion à la base de données.

## Sauvegardes

Sauvegardez régulièrement la base PostgreSQL (`pg_dump`) et conservez les
journaux. Les écritures financières sont immuables : toute correction passe par
des écritures compensatrices, jamais par la suppression d'opérations.

## État des intégrations

- **SoleasPay** : non intégré. La documentation officielle de l'API est requise
  avant toute implémentation (URL, paramètres, signatures, réponses).
- **SMS / e-mail** : interfaces prêtes, aucun fournisseur configuré (no-op).
- **Bonus / parrainage / investissements** : désactivés par défaut, en attente
  de validation réglementaire.

---

## Service client (Telegram + chat web)

Le service client NAMARA est accessible par **Telegram** (bot `@narama_bot`) et
par une **page de chat dédiée** sur le site web (`/support/chat`). Les deux canaux
partagent la même base de conversations (`SupportConversation` / `SupportMessage`),
traitée depuis l'espace administrateur (`Admin → Service client`).

### Variables d'environnement

| Variable | Description |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Token du bot (BotFather). **Ne jamais le committer.** |
| `TELEGRAM_WEBHOOK_SECRET` | Secret d'en-tête du webhook (chaîne aléatoire). |
| `TELEGRAM_WEBHOOK_URL` | URL HTTPS publique du webhook (`https://namara.win/support/telegram/webhook`). |
| `TELEGRAM_ADMIN_CHAT_ID` | (Optionnel) chat_id pour les alertes d'assistance. |
| `TELEGRAM_MODE` | `off` (désactivé), `webhook` (production) ou `polling` (développement). |
| `SUPPORT_ATTACHMENT_MAX_BYTES` | Taille max d'une pièce jointe (défaut 2 000 000). |
| `SUPPORT_MESSAGE_MAX_LENGTH` | Longueur max d'un message (défaut 2 000). |
| `AI_API_KEY` | (Optionnel) clé du fournisseur d'IA (niveau 3). Vide = IA désactivée. |
| `AI_BASE_URL` | URL de base de l'API compatible OpenAI (défaut `https://api.openai.com/v1`). |
| `AI_MODEL` | Nom du modèle (défaut `gpt-4o-mini`). |
| `AI_TIMEOUT` | Délai max (secondes) d'appel à l'IA (défaut `10`). |

### Créer un nouveau token (BotFather)

1. Ouvrez Telegram et discutez avec **@BotFather**.
2. Envoyez `/newbot`, suivez les instructions (nom, nom d'utilisateur `@narama_bot`).
3. **Révoquez tout ancien token divulgué** (`/revoke`) et utilisez le nouveau.
4. Copiez le token dans votre `.env` (jamais dans le code).

### Configuration du bot

```bash
# 1. Appliquer les migrations (tables de support)
flask db upgrade

# 2. Insérer les FAQ par défaut
flask seed-faq

# 3. Production — configurer le webhook (nécessite une URL HTTPS publique)
flask telegram-set-webhook

# 3 bis. Développement local — polling (un seul processus)
flask telegram-poll
```

> Ne lancez **pas** `webhook` et `polling` en même temps.

### Commandes du bot

`/start`, `/help`, `/contact`, `/status <référence>`, `/cancel`, `/privacy`,
ainsi que des **boutons interactifs** pour les catégories (compte, dépôt,
retrait, produits, parrainage, technique, parler à un conseiller).

### Chat web

Le widget « 💬 Assistance » est injecté automatiquement sur toutes les pages.
Il identifie le visiteur via un identifiant de session aléatoire stocké dans le
navigateur (aucune donnée personnelle collectée inutilement). Un visiteur
connecté voit sa conversation rattachée à son compte.

### Sécurité

- Webhook Telegram : vérification du secret d'en-tête
  `X-Telegram-Bot-Api-Secret-Token` + déduplication par `update_id`.
- Conversations privées protégées par `session_hash` (non devinable).
- Le bot ne demande **jamais** de mot de passe, OTP, PIN, CVV ou token.
- Le support ne modifie jamais un solde ni ne valide un paiement : il ne fait
  qu'informer, orienter et transmettre aux personnes autorisées.

