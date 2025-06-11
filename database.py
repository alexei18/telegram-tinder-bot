# database.py
import sqlalchemy
from sqlalchemy import (Table, Column, Integer, String, MetaData, DateTime,
                        create_engine, ForeignKey)
from datetime import datetime

engine = create_engine("sqlite:///bot_database.db")
metadata = MetaData()

# --- TABELE EXISTENTE ---
users_table = Table(
    "users",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("user_id", Integer, unique=True, nullable=False),
    Column("nickname", String(50)),
    Column("age", Integer),
    Column("created_at", DateTime, default=datetime.utcnow)
)

# --- TABELE NOI ---
# Tabelul care stochează TOATE kink-urile posibile
kinks_table = Table(
    "kinks",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String(100), unique=True, nullable=False), # Numele kink-ului, ex: "CNC"
    Column("category", String(50), nullable=False) # Categoria, ex: "Dinamici"
)

# Tabelul care leagă utilizatorii de kink-urile lor (relație Many-to-Many)
user_kinks_table = Table(
    "user_kinks",
    metadata,
    Column("user_id", Integer, ForeignKey("users.user_id"), primary_key=True),
    Column("kink_id", Integer, ForeignKey("kinks.id"), primary_key=True)
)

# --- LISTA PREDEFINITĂ DE KINK-URI ---
PREDEFINED_KINKS = {
    "Roluri": ["Dominant(ă)", "Supus(ă)", "Switch", "Daddy/Mommy", "Pet", "Master/Slave"],
    "Dinamici": ["CNC", "Cuckolding", "BDSM", "Age Play", "Humiliation"],
    "Fetișuri": ["Picioare", "Latex/Piele", "Uniforme", "Bondage"]
}

def populate_kinks_if_empty():
    """Adaugă kink-urile predefinite în baza de date dacă tabelul este gol."""
    with engine.connect() as connection:
        count = connection.execute(sqlalchemy.select(sqlalchemy.func.count()).select_from(kinks_table)).scalar()
        if count == 0:
            print("Popularea bazei de date cu kink-uri predefinite...")
            for category, kinks in PREDEFINED_KINKS.items():
                for kink_name in kinks:
                    query = kinks_table.insert().values(name=kink_name, category=category)
                    connection.execute(query)
            connection.commit()
            print("Kink-urile au fost adăugate.")

def setup_database():
    """Creează toate tabelele și populează kink-urile."""
    print("Pregătirea bazei de date...")
    metadata.create_all(engine)
    populate_kinks_if_empty() # Adăugăm și popularea aici
    print("Baza de date este gata.")

# --- FUNCȚII EXISTENTE MODIFICATE/NEMODIFICATE ---
def get_user(user_id: int):
    with engine.connect() as connection:
        query = users_table.select().where(users_table.c.user_id == user_id)
        return connection.execute(query).fetchone()

def add_user(user_id: int, nickname: str, age: int):
    with engine.connect() as connection:
        query = users_table.insert().values(user_id=user_id, nickname=nickname, age=age)
        connection.execute(query)
        connection.commit()

# --- FUNCȚII NOI PENTRU GESTIONAREA KINK-URILOR ---
def get_kinks_by_category(category: str):
    """Returnează toate kink-urile dintr-o anumită categorie."""
    with engine.connect() as connection:
        query = sqlalchemy.select(kinks_table).where(kinks_table.c.category == category)
        return connection.execute(query).fetchall()

def get_user_kink_ids(user_id: int):
    """Returnează o listă cu ID-urile kink-urilor unui utilizator."""
    with engine.connect() as connection:
        query = sqlalchemy.select(user_kinks_table.c.kink_id).where(user_kinks_table.c.user_id == user_id)
        return [row[0] for row in connection.execute(query).fetchall()]

def toggle_user_kink(user_id: int, kink_id: int):
    """Adaugă sau șterge o preferință pentru un utilizator."""
    with engine.connect() as connection:
        # Verificăm dacă legătura există deja
        query_select = sqlalchemy.select(user_kinks_table).where(
            user_kinks_table.c.user_id == user_id,
            user_kinks_table.c.kink_id == kink_id
        )
        exists = connection.execute(query_select).fetchone()

        if exists:
            # Dacă există, o ștergem
            query_delete = sqlalchemy.delete(user_kinks_table).where(
                user_kinks_table.c.user_id == user_id,
                user_kinks_table.c.kink_id == kink_id
            )
            connection.execute(query_delete)
        else:
            # Dacă nu există, o adăugăm
            query_insert = user_kinks_table.insert().values(user_id=user_id, kink_id=kink_id)
            connection.execute(query_insert)
        
        connection.commit()