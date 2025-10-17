_# Deployment & Infrastructure Guide

**Objective:** Establish a production-ready deployment strategy by implementing database migrations, creating a production-grade Dockerfile, and setting up a CI/CD pipeline.

---

## 1. The Problem: Lack of Production Infrastructure

The current setup is suitable only for local development. It is missing key components required for a reliable, scalable, and maintainable production environment:

1.  **No Database Migrations:** Schema changes require manual intervention and risk data loss.
2.  **Development-focused Dockerfile:** The container setup is not optimized for security or performance.
3.  **No CI/CD Pipeline:** Deployments are manual, error-prone, and slow.

## 2. The Solution: Production-Grade Infrastructure

We will implement three core components: Alembic for database migrations, a multi-stage Dockerfile for a lean production image, and a basic CI/CD pipeline using GitHub Actions.

### Step 1: Implement Database Migrations with Alembic

Alembic is the standard tool for managing SQLAlchemy database schemas. It allows you to version your schema and apply changes incrementally.

#### A. Install Alembic

```bash
pip install alembic
```

#### B. Initialize Alembic

Run this command in your project's root directory.

```bash
alembic init alembic
```

This creates an `alembic` directory and an `alembic.ini` file.

#### C. Configure Alembic

Edit `alembic/env.py` to connect to your database and discover your models.

```python
# alembic/env.py

from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Import your models' Base
from src.services.database import Base
from config.settings import settings

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
fileConfig(config.config_file_name)

# Set the database URL from your application settings
config.set_main_option('sqlalchemy.url', f"postgresql://{settings.DB_USER}:{settings.DB_PASSWORD}@{settings.DB_HOST}/{settings.DB_NAME}")

# add your model's MetaData object here
# for 'autogenerate' support
target_metadata = Base.metadata

# ... (rest of the file remains the same)
```

#### D. Create Your First Migration

Now that Alembic is configured, it can compare your SQLAlchemy models to the database and generate a migration script.

```bash
alembic revision --autogenerate -m "Initial schema creation"
```

This will create a new file in `alembic/versions/` containing the Python code to create all your tables.

#### E. Apply the Migration

To apply the migration and create the tables in your database, run:

```bash
alembic upgrade head
```

From now on, whenever you change your SQLAlchemy models, you will run the `revision` and `upgrade` commands to safely evolve your database schema.

### Step 2: Create a Production-Ready Dockerfile

A multi-stage Dockerfile creates a small, secure, and efficient final image by separating the build environment from the runtime environment.

```Dockerfile
# Dockerfile

# --- Build Stage ---
# Use a full Python image to install dependencies
FROM python:3.11-slim as builder

WORKDIR /app

# Install poetry for dependency management
RUN pip install poetry

# Copy only the dependency definition files
COPY poetry.lock pyproject.toml ./

# Install dependencies into a virtual environment
RUN poetry config virtualenvs.in-project true && \
    poetry install --no-dev --no-interaction --no-ansi

# --- Final Stage ---
# Use a minimal base image for the final container
FROM python:3.11-slim

WORKDIR /app

# Set non-root user for security
RUN useradd --create-home appuser
USER appuser

# Copy the virtual environment from the builder stage
COPY --from=builder /app/.venv ./.venv

# Copy the application code
COPY . .

# Make the virtual environment's Python the default
ENV PATH=\"/app/.venv/bin:$PATH\"

# Expose the port the app runs on
EXPOSE 8000

# Run the application using a production-grade server like uvicorn
CMD [\"uvicorn\", \"api.main:app\", \"--host\", \"0.0.0.0\", \"--port\", \"8000\"]

```

### Key Features of this Dockerfile:

-   **Multi-Stage Build:** The `builder` stage installs dependencies, but only the final, clean virtual environment is copied to the final image.
-   **Lean Final Image:** The final image doesn't contain the build tools (like `poetry`), making it smaller and more secure.
-   **Non-Root User:** The application runs as `appuser`, which is a critical security best practice to limit the potential impact of a container compromise.
-   **Production Server:** It uses `uvicorn` to run the FastAPI application, which is suitable for production.

### Step 3: Create a Basic CI/CD Pipeline

GitHub Actions can automate testing and deployment. Create a workflow file to define the pipeline.

```yaml
# .github/workflows/ci-cd.yml

name: CI/CD Pipeline

on:
  push:
    branches:
      - main

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install poetry
          poetry install

      - name: Run tests
        run: |
          poetry run pytest

  build-and-push:
    runs-on: ubuntu-latest
    needs: test # This job only runs if the 'test' job succeeds
    steps:
      - name: Checkout code
        uses: actions/checkout@v3

      - name: Log in to Docker Hub
        uses: docker/login-action@v2
        with:
          username: ${{ secrets.DOCKER_USERNAME }}
          password: ${{ secrets.DOCKER_PASSWORD }}

      - name. Build and push Docker image
        uses: docker/build-push-action@v4
        with:
          context: .
          push: true
          tags: yourdockerhub/rcm-agent-system:latest

  deploy:
    runs-on: ubuntu-latest
    needs: build-and-push # This job only runs after the image is built
    steps:
      - name: Deploy to production
        uses: appleboy/ssh-action@master
        with:
          host: ${{ secrets.PROD_HOST }}
          username: ${{ secrets.PROD_USERNAME }}
          key: ${{ secrets.PROD_SSH_KEY }}
          script: |
            docker pull yourdockerhub/rcm-agent-system:latest
            docker-compose -f /path/to/your/docker-compose.prod.yml up -d
            echo "Deployment successful!"

```

### How This Pipeline Works:

1.  **Trigger:** It runs automatically on every push to the `main` branch.
2.  **Test Job:** It checks out the code, installs dependencies, and runs the `pytest` suite. If any test fails, the pipeline stops.
3.  **Build and Push Job:** If tests pass, it builds the production Docker image and pushes it to a container registry (like Docker Hub).
4.  **Deploy Job:** After the image is successfully pushed, this job securely connects to your production server via SSH and runs a script to pull the latest image and restart the services.

## 3. How to Apply These Fixes

1.  **Alembic:** Follow the steps to initialize and configure Alembic. Create an initial migration and apply it.
2.  **Dockerfile:** Create the `Dockerfile` in your project root.
3.  **CI/CD:** Create the `.github/workflows/ci-cd.yml` file. You will also need to configure secrets (`DOCKER_USERNAME`, `PROD_HOST`, etc.) in your GitHub repository settings.

By implementing these infrastructure components, you establish a reliable, automated, and scalable foundation for deploying and maintaining your RCM Agent System in a production environment.

