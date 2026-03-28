# Dockerfile avec une stratégie multi-stage pour optimiser la taille de l'image finale
# étape build
FROM ghcr.io/astral-sh/uv:python3.11-bookworm AS builder

# Permet de définir ou on travaille en créant le dossier passé en argumen si il n'existe pas
# Si il n'est pas définis, on travaille à la racine du système ce qui pollue nos fichiers 
WORKDIR /app

# Récupère les fichiers de dépendances dans pyproject.toml
# et le lockerfile (générer automatiquement par uv) qui permet de geler les versions exact des dépendances
COPY pyproject.toml uv.lock ./

# permet de synchroniser le projet avec l'environement virtuel que l'on crée
# --no-install-project permet de récupérer seulement les dépendances et pas le code source
# --no-editable permet de ne pas être en mode edit et aisi faire une vrai copie de /app/
# --locked permet de dire à uv de ne pas mettre à jour automatiquement le uv.lock 
# --no-dev permet de ne pas embarquer en prod les dépendances optionnelles
RUN uv sync --no-install-project --no-editable --locked --no-dev

#étape run
FROM ghcr.io/astral-sh/uv:python3.11-bookworm-slim 

WORKDIR /app

# Définis dans le PATH le dossier pour l'environnement virtuel (définir un cache)
ENV PATH="/app/.venv/bin:$PATH"

# Dans l'étape run récupère le venv de l'étape build 
COPY --from=builder /app/.venv /app/.venv

# Récupère le code source 
COPY app ./app

# Ajoute l'utilisater appuser au groupe des utilisateur
RUN useradd -ms /bin/bash appuser

# Change recursivement sur tout les fichiers le propriétaire pour un utilisateur non-root
RUN chown -R appuser:appuser .

# Bascule sur appuser
USER appuser

# Compile le bytecode engendrer par python
RUN uv run python -m compileall .

# RUN chmod -R 555 ou 444(read only) /app à voir dans le futur si on le met en fonction de si celery et Fastapi ont besoin d'écrire des fichiers dans /app

# Expose le port 8000 pour les requêtes HTTP avec TCP pour que docker fâce le lien avec la machine utilisateur
EXPOSE 8000/tcp

# Lance uvicorn via uv, avec l'application FastAPI définie dans app/api/main.py, en écoutant sur toutes les interfaces réseau.
CMD ["uv", "run", "uvicorn", "app.api.main:app", "--host", "0.0.0.0", "--port", "8000"]