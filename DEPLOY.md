# Deploying shop-be to the VPS

Self-hosted Docker, behind the shared Caddy that already owns :80/:443.
This stack publishes **no host ports** and runs **no proxy of its own**.

---

## Blockers to clear before the first deploy

**1. There are no migration files in this repo.** `.gitignore` contains
`**/migrations/*`, so every app ships with only an empty `__init__.py`. Running
`migrate` against the fresh local Postgres will create Django's built-in tables
and *none* of your app tables — the app will start and then 500 on the first
query. Fix before deploying:

```bash
# remove the `**/migrations/*` line from .gitignore first, then:
python manage.py makemigrations users shop inventory sale expense common
git add apps/*/migrations/ && git commit -m "Track migrations"
```

Generate these against the **existing Azure schema** if you intend to move the
data later, so the initial migration matches what is already there.

**2. `.env.backup` is committed to git** with live Azure, Cloudinary and Twilio
credentials in plaintext. `.gitignore` has `*.env`, which does not match
`.env.backup`. Rotate all of those secrets, then:

```bash
git rm --cached .env.backup
echo ".env.backup" >> .gitignore
```

Removing it from HEAD does not remove it from history — treat every value in
that file as compromised and rotate it.

---

## Steps

### 1. Fill in the two placeholders

**Network name** — find the network the existing Caddy is attached to:

```bash
docker network ls
docker inspect <caddy-container> -f '{{range $k,$v := .NetworkSettings.Networks}}{{$k}}{{"\n"}}{{end}}'
```

Put that name in `docker-compose.yml` under `networks.proxy.name`, replacing
`REPLACE_ME_shared_caddy_network`. Leave `external: true` as is.

**Domain** — replace `shop.example.com` throughout `.env`.

### 2. Create the environment file

```bash
cp .env.example .env
```

Fill in `SECRET_KEY`, `DB_PASSWORD`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`,
and the Cloudinary/Twilio keys. `DB_NAME`, `DB_USER` and `DB_PASSWORD` must
match what you put inside `DATABASE_URL` — they are read by both the db
container and the app.

### 3. Build and start

```bash
docker compose build
docker compose up -d
docker compose logs -f web
```

The entrypoint waits for Postgres, runs `migrate`, runs `collectstatic`, then
execs gunicorn. A healthy start ends with gunicorn's boot lines.

### 4. Create an admin user

```bash
docker compose exec web python manage.py createsuperuser
```

### 5. Point Caddy at the container

The app listens on **port 8000** inside the container named
**`shop-be-web-1`**. That name is guaranteed by the `name: shop-be` line at the
top of `docker-compose.yml`, so it holds regardless of what the checkout
directory is called. Add to the shared Caddyfile:

```caddy
shop.example.com {
    reverse_proxy shop-be-web-1:8000
}
```

Caddy resolves that name over the shared network, so Caddy's container must be
on the same network you configured in step 1. Reload:

```bash
docker exec <caddy-container> caddy reload --config /etc/caddy/Caddyfile
```

Caddy sets `X-Forwarded-Proto` by default, which is what makes Django's
`SECURE_SSL_REDIRECT` behave correctly behind TLS termination.

---

## Coexisting with the FuelFlow stack on the same box

This stack is namespaced under the compose project `shop-be`, so nothing it
creates can collide with FuelFlow:

| Resource | This stack | Collides with `fuelflow*`? |
|---|---|---|
| Containers | `shop-be-web-1`, `shop-be-db-1` | No |
| Volume | `shop-be_pgdata` | No |
| Private network | `shop-be_internal` | No |
| Shared network | joined, `external: true` — never created | No |
| Host ports | **none published** | No |

The app's Postgres listens only on the internal network, so it does not contend
with FuelFlow's database for host port 5432. The only shared resource is the
Caddy proxy network, which this stack joins read-only — `external: true` means
compose will error out rather than create or modify it. `docker compose down`
here cannot remove a network FuelFlow depends on.

## Operations

```bash
docker compose logs -f web              # tail app logs
docker compose restart web              # restart app only
docker compose down                     # stop (named volume survives)
docker compose exec web python manage.py shell

# backup
docker compose exec db pg_dump -U "$DB_USER" "$DB_NAME" > backup-$(date +%F).sql
```

Database lives in the named volume `pgdata`. `docker compose down -v` deletes
it — do not use `-v` unless you mean to destroy the data.

## Deploying an update

```bash
git pull
docker compose build web
docker compose up -d web
```

Migrations and collectstatic re-run automatically on each container start.
