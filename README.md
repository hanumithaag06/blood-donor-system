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

## Implementation Steps

# 1. Activate venv
venv\Scripts\Activate.ps1

# 2. Install/confirm dependencies
pip install -r requirements.txt

# 3. Train the ML model
python -m app.ml.train

# 4. Seed realistic demo data
python -m app.seed

# 5. Run the app
python main.py
