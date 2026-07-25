# Blood Donor Registry and Availability Search

A hospital-facing system to register donors, track donation history, compute
donation eligibility, search/filter donors, predict response likelihood via
a trained ML model, and answer natural-language-style queries through a
rule-based assistant.

## Tech Stack

- **Backend**: Python, Flask
- **Database**: SQLite (SQLAlchemy ORM; PostgreSQL-compatible schema)
- **ML**: scikit-learn (RandomForestClassifier)
- **Assistant**: Rule-based intent matching
- **Frontend**: Plain HTML / CSS / JavaScript (fetch-based, consumes the REST API)
- **Testing**: pytest

## Project Structure
app/
  services/              # service layer (search, donor management, ML, assistant)
  routes/              # Flask API blueprints (api.py)
  db/                  # database setup (database.py, models.py)
  ml/                  # ML pipeline (train.py, predict.py, models/*.pkl)
  utils/               # logging, helpers
  schemas/             # Pydantic schemas (optional, used via JSON)
  __init__.py          # app factory

static/              # CSS, JavaScript
templates/           # HTML templates
data/                # donor_history.csv (source)
ml_history.json      # training metadata (per training run)
requirements.txt


# 1. Activate venv
venv\Scripts\Activate.ps1

# 2. Install/confirm dependencies
pip install -r requirements.txt

# 3. Delete old dev DB (schema changed — gender field, etc.)
Remove-Item blood_donor.db -ErrorAction SilentlyContinue

# 4. Train the ML model
python -m app.ml.train

# 5. Seed realistic demo data
python -m app.seed

# 6. Run the app
python main.py