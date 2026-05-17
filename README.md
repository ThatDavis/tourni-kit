# Tourni-Kit

Getting a fully stocked IFAK can cost a pretty penny so a while ago I created a spreadsheet with the idea that if we just combine resources we could get a number of people to donate and bring your own bag to build out a kit. While the spreadsheet works it had a lot of my own idiosyncratic calculations for making things make sense so I decided to put this together.

The idea is an all-in-one spot for organizing your own IFAK assembly as well as tracking inventory for future events and allowing people to sign up without having to create an account. The idea was always to do these things at-cost so the minimum recommended donation is calculated from that. Additionally, Stop The Bleed supplies can get very expensive, and not everyone wants or needs them — so there is the option to stock or not stock STB and allow people to opt in when donating. The system itself does not handle payment, just lists a recommended donation. You can use Mailgun or any number of other services to enable email sending and this supports multiple administrators for small groups who want to get things going.

If you have any questions, thoughts, or feature requests feel free to reach out!

## Features

- **Inventory Management** — Track stock levels by item, with automatic per-kit cost calculations
- **Audit Logging** — Every inventory change is logged with who made it, when, and why
- **Build Session Scheduling** — Create events with capacity limits and auto-calculated minimum donations
- **Public Signup** — No login required for attendees to reserve a spot or join the waitlist
- **Opt-in Stop The Bleed** — Attendees can choose whether to include STB supplies in their kit
- **Kit Build Tracking** — Record who built a kit and automatically deduct inventory
- **Email Notifications** — SMTP support for signup confirmations and waitlist promotions
- **User Invites** — Invite other organizers via email with secure token links
- **Customizable About Page** — Edit the public "About" page content from the settings page
- **Customizable Theme** — Change site title, colors, and branding from the settings page
- **Category & Item Management** — Add new categories and items without touching the database

## Quick Start (Pre-built Image)

The easiest way to run Tourni-Kit is to pull the pre-built image from GitHub Container Registry:

```bash
# Pull the latest image
docker pull ghcr.io/thatdavis/tourni-kit:latest

# Run it (creates a local data/ directory for the SQLite database)
docker run -d \
  --name tourni-kit \
  -p 8001:8000 \
  -v $(pwd)/data:/app/data \
  -e SECRET_KEY=$(openssl rand -hex 32) \
  -e BASE_URL=http://localhost:8001 \
  ghcr.io/thatdavis/tourni-kit:latest

# Create the first admin user
docker exec -it tourni-kit python create_admin.py
```

The app will be available at `http://localhost:8001`.

### With Docker Compose

Create a `docker-compose.yml`:

```yaml
services:
  app:
    image: ghcr.io/thatdavis/tourni-kit:latest
    ports:
      - "8001:8000"
    volumes:
      - ./data:/app/data
    env_file:
      - .env
```

Copy `.env.example` to `.env`, edit as needed, then run:

```bash
docker-compose up -d
docker-compose exec app python create_admin.py
```

### Build from Source

If you prefer to build the image yourself:

```bash
# Clone the repo, then:
docker-compose up --build

# Create the first admin user
docker-compose exec app python create_admin.py
```

The public page shows an "About" link by default. Admins can access the dashboard directly at `/admin/login`.

## Configuration

Set these environment variables in a `.env` file or via `docker-compose.yml`:

| Variable | Description | Default |
|----------|-------------|---------|
| `SECRET_KEY` | JWT signing key | `change-me-in-production` |
| `DATABASE_URL` | SQLite database path | `sqlite:////app/data/ifak.db` |
| `BASE_URL` | Public URL for invite links | `http://localhost:8001` |
| `SMTP_HOST` | SMTP server host | (none) |
| `SMTP_PORT` | SMTP server port | `587` |
| `SMTP_USER` | SMTP username | (none) |
| `SMTP_PASSWORD` | SMTP password | (none) |
| `SMTP_FROM` | From email address | same as `SMTP_USER` |
| `SMTP_TLS` | Use TLS | `true` |

If SMTP is not configured, emails are logged to the console instead of sent.

## Manual Setup (without Docker)

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create the first admin user
python create_admin.py

# Run the server
python run.py
```

## Data Model

- **Items** are seeded from `IFAK_Share.csv` on first run
- **Stock** is stored as total individual units (e.g., 600 pills, 20 shears)
- When receiving inventory, admins enter packages and the app auto-converts to units
- When a kit is built, the app deducts `needed_per_kit` units from each item

## Tech Stack

- Python 3.11+ / FastAPI
- SQLite (single file)
- Jinja2 templates with customizable CSS
- JWT cookie-based auth for organizers
