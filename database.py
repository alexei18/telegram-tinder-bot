# database.py
import sqlalchemy
from sqlalchemy import (Table, Column, Integer, String, MetaData, DateTime,
                        create_engine, ForeignKey, Enum)
from datetime import datetime

engine = create_engine("sqlite:///bot_database.db")
metadata = MetaData()

# --- TABELE ---
users_table = Table(
    "users", metadata,
    Column("id", Integer, primary_key=True),
    Column("user_id", Integer, unique=True, nullable=False),
    Column("nickname", String(50)),
    Column("age", Integer),
    Column("created_at", DateTime, default=datetime.utcnow)
)

kinks_table = Table(
    "kinks", metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String(100), unique=True, nullable=False),
    Column("category", String(50), nullable=False)
)

user_kinks_table = Table(
    "user_kinks", metadata,
    Column("user_id", Integer, ForeignKey("users.user_id"), primary_key=True),
    Column("kink_id", Integer, ForeignKey("kinks.id"), primary_key=True)
)

# TABEL NOU: PENTRU SWIPES
swipes_table = Table(
    "swipes", metadata,
    Column("swiper_user_id", Integer, ForeignKey("users.user_id"), primary_key=True),
    Column("swiped_user_id", Integer, ForeignKey("users.user_id"), primary_key=True),
    Column("action", Enum("like", "nope", name="swipe_action_enum"), nullable=False),
    Column("timestamp", DateTime, default=datetime.utcnow)
)

# TABEL NOU: PENTRU RAPORTĂRI
reports_table = Table(
    "reports", metadata,
    Column("id", Integer, primary_key=True),
    Column("reporter_user_id", Integer, ForeignKey("users.user_id"), nullable=False),
    Column("reported_user_id", Integer, ForeignKey("users.user_id"), nullable=False),
    Column("timestamp", DateTime, default=datetime.utcnow)
)

PREDEFINED_KINKS = {
    "Roluri": ["Dominant(ă)", "Supus(ă)", "Switch", "Daddy/Mommy", "Pet", "Master/Slave"],
    "Dinamici": ["CNC", "Cuckolding", "BDSM", "Age Play", "Humiliation"],
    "Fetișuri": ["Picioare", "Latex/Piele", "Uniforme", "Bondage"]
}

def populate_kinks_if_empty():
    with engine.connect() as connection:
        count = connection.execute(sqlalchemy.select(sqlalchemy.func.count()).select_from(kinks_table)).scalar()
        if count == 0:
            print("Popularea bazei de date cu kink-uri predefinite...")
            for category, kinks in PREDEFINED_KINKS.items():
                for kink_name in kinks:
                    query = kinks_table.insert().values(name=kink_name, category=category)
                    connection.execute(query)
            connection.commit()

def setup_database():
    print("Pregătirea bazei de date...")
    metadata.create_all(engine)
    populate_kinks_if_empty()
    print("Baza de date este gata.")

# --- FUNCȚII UTILITARE (EXISTENTE ȘI NOI) ---
def get_user(user_id: int):
    with engine.connect() as connection:
        query = users_table.select().where(users_table.c.user_id == user_id)
        return connection.execute(query).fetchone()

def add_user(user_id: int, nickname: str, age: int):
    with engine.connect() as connection:
        query = users_table.insert().values(user_id=user_id, nickname=nickname, age=age)
        connection.execute(query)
        connection.commit()

def get_kinks_by_category(category: str):
    with engine.connect() as connection:
        query = sqlalchemy.select(kinks_table).where(kinks_table.c.category == category)
        return connection.execute(query).fetchall()

def get_user_kinks(user_id: int):
    """Returnează o listă cu numele kink-urilor unui utilizator."""
    with engine.connect() as connection:
        query = sqlalchemy.select(kinks_table.c.name).join(
            user_kinks_table, kinks_table.c.id == user_kinks_table.c.kink_id
        ).where(user_kinks_table.c.user_id == user_id)
        return [row[0] for row in connection.execute(query).fetchall()]

def get_user_kink_ids(user_id: int):
    with engine.connect() as connection:
        query = sqlalchemy.select(user_kinks_table.c.kink_id).where(user_kinks_table.c.user_id == user_id)
        return [row[0] for row in connection.execute(query).fetchall()]

def toggle_user_kink(user_id: int, kink_id: int):
    with engine.connect() as connection:
        query_select = sqlalchemy.select(user_kinks_table).where(user_kinks_table.c.user_id == user_id, user_kinks_table.c.kink_id == kink_id)
        exists = connection.execute(query_select).fetchone()
        if exists:
            query_delete = sqlalchemy.delete(user_kinks_table).where(user_kinks_table.c.user_id == user_id, user_kinks_table.c.kink_id == kink_id)
            connection.execute(query_delete)
        else:
            query_insert = user_kinks_table.insert().values(user_id=user_id, kink_id=kink_id)
            connection.execute(query_insert)
        connection.commit()

# --- FUNCȚII NOI PENTRU MATCHING ---
def find_potential_match(user_id: int):
    """Găsește un potențial partener pe care userul nu l-a văzut încă."""
    with engine.connect() as connection:
        # Subquery: Găsește toți userii pe care userul curent i-a văzut deja
        swiped_users_subquery = sqlalchemy.select(swipes_table.c.swiped_user_id).where(swipes_table.c.swiper_user_id == user_id)
        
        # Găsește un user care NU este userul curent ȘI NU este în lista celor văzuți
        query = users_table.select().where(
            users_table.c.user_id != user_id,
            users_table.c.user_id.not_in(swiped_users_subquery)
        ).limit(1) # Luăm doar unul per căutare
        
        result = connection.execute(query).fetchone()
        return result

def record_swipe(swiper_id: int, swiped_id: int, action: str):
    """Înregistrează o acțiune de swipe."""
    with engine.connect() as connection:
        # Folosim 'upsert' pentru a insera sau înlocui dacă există deja (deși nu ar trebui)
        query = sqlalchemy.dialects.sqlite.insert(swipes_table).values(
            swiper_user_id=swiper_id, swiped_user_id=swiped_id, action=action
        ).on_conflict_do_update(
            index_elements=['swiper_user_id', 'swiped_user_id'],
            set_=dict(action=action, timestamp=datetime.utcnow())
        )
        connection.execute(query)
        connection.commit()

def check_for_match(user1_id: int, user2_id: int) -> bool:
    """Verifică dacă există un 'like' reciproc între doi useri."""
    with engine.connect() as connection:
        # Căutăm like de la user1 la user2
        query1 = swipes_table.select().where(
            swipes_table.c.swiper_user_id == user1_id,
            swipes_table.c.swiped_user_id == user2_id,
            swipes_table.c.action == 'like'
        )
        match1 = connection.execute(query1).fetchone()

        # Căutăm like de la user2 la user1
        query2 = swipes_table.select().where(
            swipes_table.c.swiper_user_id == user2_id,
            swipes_table.c.swiped_user_id == user1_id,
            swipes_table.c.action == 'like'
        )
        match2 = connection.execute(query2).fetchone()

        return match1 is not None and match2 is not None

def record_report(reporter_id: int, reported_id: int):
    """Înregistrează o raportare."""
    with engine.connect() as connection:
        query = reports_table.insert().values(reporter_user_id=reporter_id, reported_user_id=reported_id)
        connection.execute(query)
        connection.commit()