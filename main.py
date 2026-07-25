"""
Application entry point.
Run with: python main.py
Optionally seed dev data: python main.py --seed
"""
import sys

from app import create_app
from app.db import seed_dev_data

app = create_app()

if __name__ == "__main__":
    if "--seed" in sys.argv:
        seed_dev_data()

    app.run(debug=True)