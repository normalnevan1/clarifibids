import subprocess
import os

env = os.environ.copy()
env['PGPASSWORD'] = 'nevan123*'

sql_commands = """
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS roles (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) UNIQUE NOT NULL,
    is_business_role BOOLEAN DEFAULT TRUE,
    description TEXT
);

INSERT INTO roles (name, is_business_role, description) VALUES
    ('Bidder', TRUE, 'Standard Indian Domestic Bidder'),
    ('Foreign Bidder', TRUE, 'International Bidder Regulations'),
    ('Department User', TRUE, 'Procuring Entity Official'),
    ('ADMIN', FALSE, 'System Administration')
ON CONFLICT (name) DO NOTHING;

CREATE TABLE IF NOT EXISTS query_categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(150) UNIQUE NOT NULL,
    description TEXT
);

INSERT INTO query_categories (name, description) VALUES
    ('Portal Guidelines & Procurement Terms', 'General terms, standard IST time, basic features'),
    ('Portal Usage & User Management', 'Bidder enrollment, login, registration, password recovery'),
    ('Technical Assistance', 'DSC detection, JRE setup, browser, OS, driver configuration'),
    ('Tender & Bid Information', 'Tender search, bid submission, BOQ, EMD fee, corrigenda, covers'),
    ('Security Information', 'Digital signatures, encryption, CA validity, tamper prevention'),
    ('Foreign Bidder Information', 'International vendor guidelines, foreign currency, foreign DSC')
ON CONFLICT (name) DO NOTHING;
"""

r = subprocess.run(
    [r'C:\Program Files\PostgreSQL\18\bin\psql.exe', '-U', 'postgres', '-d', 'clarifibids_db', '-h', '127.0.0.1', '-w', '-c', sql_commands],
    env=env,
    capture_output=True,
    text=True
)

print("OUT:\n", r.stdout)
if r.stderr:
    print("ERR:\n", r.stderr)
