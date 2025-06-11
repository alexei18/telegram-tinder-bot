# main.py
import logging
import os
from telegram import Update
from telegram.ext import (Application, CommandHandler, ContextTypes, 
                          MessageHandler, ConversationHandler, filters)

# Importăm funcțiile noastre pentru baza de date
import database

# --- Pune token-ul tău aici ---
TOKEN = os.getenv("TELEGRAM_TOKEN")

# Configurăm logging pentru a vedea erorile mai ușor
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Definim "stările" conversației. Acestea ne spun la ce pas suntem.
NICKNAME, AGE = range(2)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Începe conversația de creare a profilului."""
    user = update.effective_user
    db_user = database.get_user(user.id)

    if db_user:
        await update.message.reply_text(f"Salut din nou, {db_user.nickname}! Profilul tău este deja creat.")
        return ConversationHandler.END # Încheiem conversația dacă userul există deja
    
    await update.message.reply_text(
        "Salut! Se pare că ești nou aici. Hai să-ți creăm un profil.\n"
        "Ce pseudonim ai vrea să folosești? (ex: Alex)"
    )
    return NICKNAME # Trecem la starea NICKNAME

async def get_nickname(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Salvează pseudonimul și cere vârsta."""
    nickname = update.message.text
    context.user_data['nickname'] = nickname # Salvăm temporar nickname-ul

    await update.message.reply_text(
        f"Super, {nickname}! Acum, ce vârstă ai? (Trebuie să ai minim 18 ani)"
    )
    return AGE # Trecem la starea AGE

async def get_age(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Salvează vârsta, creează profilul în DB și încheie conversația."""
    age_text = update.message.text
    try:
        age = int(age_text)
        if age < 18:
            await update.message.reply_text("Ne pare rău, trebuie să ai minim 18 ani. Te rog introdu o vârstă validă.")
            return AGE # Rămânem în starea AGE pentru a reîncerca
    except ValueError:
        await update.message.reply_text("Te rog introdu o vârstă validă, folosind doar cifre.")
        return AGE # Rămânem în starea AGE pentru a reîncerca

    # Acum avem toate datele, le salvăm în baza de date
    user = update.effective_user
    nickname = context.user_data['nickname']
    database.add_user(user_id=user.id, nickname=nickname, age=age)

    await update.message.reply_text(
        "Mulțumesc! Profilul tău a fost creat cu succes. "
        "În curând vei putea adăuga preferințe și căuta parteneri. /help pentru comenzi."
    )
    return ConversationHandler.END # Încheiem conversația

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Anulează conversația curentă."""
    await update.message.reply_text("Crearea profilului a fost anulată.")
    return ConversationHandler.END

def main() -> None:
    """Funcția principală care pornește bot-ul."""
    # Ne asigurăm că baza de date și tabelul sunt create la pornire
    database.setup_database()

    application = Application.builder().token(TOKEN).build()

    # Creăm un ConversationHandler pentru a gestiona fluxul de creare a profilului
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            NICKNAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_nickname)],
            AGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_age)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
    
    print("Bot-ul a pornit și ascultă...")
    application.run_polling()

if __name__ == "__main__":
    main()