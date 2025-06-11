# database.py
import sqlalchemy
from sqlalchemy import (Table, Column, Integer, String, MetaData, DateTime,
                        create_engine)
from datetime import datetime

# Ne conectăm la un fișier de bază de date numit 'bot_database.db'
# SQLAlchemy îl va crea automat dacă nu există.
engine = create_engine("sqlite:///bot_database.db")
metadata = MetaData()

# Definim structura tabelului 'users'
# Aici vom stoca informațiile despre utilizatori
users_table = Table(
    "users",
    metadata,
    Column("id", Integer, primary_key=True),  # O cheie primară unică pentru fiecare rând
    Column("user_id", Integer, unique=True, nullable=False), # ID-ul unic de la Telegram
    Column("nickname", String(50)), # Pseudonimul ales de utilizator
    Column("age", Integer), # Vârsta utilizatorului
    Column("created_at", DateTime, default=datetime.utcnow) # Data creării profilului
)

def setup_database():
    """Creează tabelul în baza de date dacă nu există deja."""
    print("Pregătirea bazei de date...")
    metadata.create_all(engine)
    print("Baza de date este gata.")

def get_user(user_id: int):
    """Verifică dacă un utilizator există în baza de date."""
    with engine.connect() as connection:
        query = users_table.select().where(users_table.c.user_id == user_id)
        result = connection.execute(query).fetchone()
        return result

def add_user(user_id: int, nickname: str, age: int):
    """Adaugă un utilizator nou în baza de date."""
    with engine.connect() as connection:
        query = users_table.insert().values(user_id=user_id, nickname=nickname, age=age)
        connection.execute(query)
        # SQLAlchemy are nevoie de commit pentru a salva modificările
        connection.commit()