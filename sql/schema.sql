-- ============================================================
-- Blood Donor Registry — Reference Schema
-- Mirrors app/models.py exactly. This file is for documentation
-- and manual inspection only; the application creates tables via
-- SQLAlchemy (app/db.py:init_db()), not by executing this file.
-- ============================================================

CREATE TABLE IF NOT EXISTS donors (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name       TEXT NOT NULL,
    date_of_birth   DATE NOT NULL,
    blood_group     TEXT NOT NULL,
    phone           TEXT NOT NULL UNIQUE,
    area            TEXT NOT NULL,
    is_available    BOOLEAN NOT NULL DEFAULT 1,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT ck_donor_blood_group_valid
        CHECK (blood_group IN ('A+','A-','B+','B-','AB+','AB-','O+','O-')),
    CONSTRAINT ck_donor_dob_not_future
        CHECK (date_of_birth <= CURRENT_DATE)
);

CREATE INDEX IF NOT EXISTS idx_donor_blood_group ON donors (blood_group);
CREATE INDEX IF NOT EXISTS idx_donor_area ON donors (area);
CREATE INDEX IF NOT EXISTS idx_donor_blood_group_area ON donors (blood_group, area);


CREATE TABLE IF NOT EXISTS donations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    donor_id        INTEGER NOT NULL,
    donation_date   DATE NOT NULL,
    volume_ml       INTEGER,
    location        TEXT,
    created_at      TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_donation_donor
        FOREIGN KEY (donor_id) REFERENCES donors(id),
    CONSTRAINT ck_donation_date_not_future
        CHECK (donation_date <= CURRENT_DATE),
    CONSTRAINT ck_donation_volume_positive
        CHECK (volume_ml IS NULL OR volume_ml > 0)
);

CREATE INDEX IF NOT EXISTS idx_donation_donor_id_date
    ON donations (donor_id, donation_date DESC);

-- Note: SQLite requires "PRAGMA foreign_keys = ON;" per connection for the
-- fk_donation_donor constraint above to actually be enforced. The app
-- enables this automatically via a SQLAlchemy connect event in app/db.py.
PRAGMA foreign_keys = ON;