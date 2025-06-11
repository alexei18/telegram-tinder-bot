# main.py
import logging
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler
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

# === SECȚIUNEA PENTRU GESTIONAREA PREFERINȚELOR ===

async def preferences_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Afișează meniul principal de categorii de preferințe."""
    keyboard = [
        [InlineKeyboardButton("Roluri", callback_data="category_Roluri")],
        [InlineKeyboardButton("Dinamici", callback_data="category_Dinamici")],
        [InlineKeyboardButton("Fetișuri", callback_data="category_Fetișuri")],
        [InlineKeyboardButton("❌ Închide", callback_data="close_menu")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Alege o categorie pentru a-ți edita preferințele:", reply_markup=reply_markup)

async def kink_list_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, category: str):
    """Afișează lista de kink-uri pentru o categorie specifică."""
    user_id = update.effective_user.id
    kinks_in_category = database.get_kinks_by_category(category)
    user_kink_ids = database.get_user_kink_ids(user_id)

    keyboard = []
    for kink in kinks_in_category:
        kink_id = kink.id
        kink_name = kink.name
        # Adăugăm un checkmark dacă user-ul are deja acest kink selectat
        text = f"✅ {kink_name}" if kink_id in user_kink_ids else kink_name
        keyboard.append([InlineKeyboardButton(text, callback_data=f"toggle_{kink_id}")])

    keyboard.append([InlineKeyboardButton("⬅️ Înapoi la Categorii", callback_data="back_to_categories")])
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Edităm mesajul existent în loc să trimitem unul nou
    await update.callback_query.edit_message_text(text=f"Editezi categoria: *{category}*", reply_markup=reply_markup, parse_mode='Markdown')

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Gestionează TOATE apăsările pe butoanele meniului."""
    query = update.callback_query
    await query.answer()  # Obligatoriu, confirmă primirea apăsării

    data = query.data

    if data.startswith("category_"):
        category = data.split("_")[1]
        await kink_list_menu(update, context, category)

    elif data.startswith("toggle_"):
        kink_id = int(data.split("_")[1])
        user_id = query.from_user.id
        database.toggle_user_kink(user_id, kink_id)

        # Reafișăm meniul pentru a reflecta schimbarea (checkmark-ul)
        # Extragem categoria din textul mesajului pentru a ști ce meniu să reafișăm
        category = query.message.text.split("*")[1]
        await kink_list_menu(update, context, category)

    elif data == "back_to_categories":
        # Recreăm meniul principal de categorii
        keyboard = [
            [InlineKeyboardButton("Roluri", callback_data="category_Roluri")],
            [InlineKeyboardButton("Dinamici", callback_data="category_Dinamici")],
            [InlineKeyboardButton("Fetișuri", callback_data="category_Fetișuri")],
            [InlineKeyboardButton("❌ Închide", callback_data="close_menu")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("Alege o categorie pentru a-ți edita preferințele:", reply_markup=reply_markup)

    elif data == "close_menu":
        await query.edit_message_text("Meniul a fost închis.")

    # === LOGICĂ NOUĂ PENTRU MATCHING ===
    elif data.startswith("like_"):
        await process_swipe(update, context, "like")

    elif data.startswith("nope_"):
        await process_swipe(update, context, "nope")

    elif data.startswith("report_"):
        reporter_id = query.from_user.id
        reported_id = int(data.split("_")[1])
        database.record_report(reporter_id, reported_id)
        await query.edit_message_text("Raportul a fost trimis. Mulțumim! Acum căutăm următorul profil...")
        # Căutăm imediat următorul profil
        next_potential_match = database.find_potential_match(reporter_id)
        if next_potential_match:
            await show_profile_card(update, context, next_potential_match)
        else:
            await query.edit_message_text("Nu am mai găsit pe nimeni nou pentru tine. Revino mai târziu!")
            
    elif data == "stop_matching":
        await query.edit_message_text("Procesul de matching a fost oprit.")





# === SECȚIUNEA PENTRU MATCHING ===

async def show_profile_card(update: Update, context: ContextTypes.DEFAULT_TYPE, profile_data):
    """Formatează și afișează profilul unui potențial partener."""
    profile_kinks = database.get_user_kinks(profile_data.user_id)
    kinks_text = ", ".join(profile_kinks) if profile_kinks else "Nicio preferință specificată"

    text = (
        f"Găsit un potențial partener:\n\n"
        f"👤 **Pseudonim:** {profile_data.nickname}\n"
        f"🎂 **Vârstă:** {profile_data.age}\n"
        f"✨ **Preferințe:** {kinks_text}"
    )

    keyboard = [
        [
            InlineKeyboardButton("❤️ Like", callback_data=f"like_{profile_data.user_id}"),
            InlineKeyboardButton("❌ Nope", callback_data=f"nope_{profile_data.user_id}")
        ],
        [InlineKeyboardButton("⚠️ Raportează", callback_data=f"report_{profile_data.user_id}")],
        [InlineKeyboardButton("🚪 Oprește matching-ul", callback_data="stop_matching")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Dacă a fost chemat dintr-o comandă, trimite un mesaj nou.
    # Dacă a fost chemat dintr-o apăsare de buton, editează mesajul existent.
    if update.callback_query:
        await update.callback_query.edit_message_text(text=text, reply_markup=reply_markup, parse_mode='HTML')
    else:
        await update.message.reply_text(text=text, reply_markup=reply_markup, parse_mode='HTML')


async def find_match_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Comanda care inițiază procesul de matching."""
    user_id = update.effective_user.id
    potential_match = database.find_potential_match(user_id)

    if potential_match:
        await show_profile_card(update, context, potential_match)
    else:
        await update.message.reply_text("Ne pare rău, nu am găsit pe nimeni nou pentru tine momentan. Încearcă mai târziu!")

async def process_swipe(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str):
    """Procesează o acțiune de 'like' sau 'nope'."""
    query = update.callback_query
    swiper_user = query.from_user
    swiped_user_id = int(query.data.split("_")[1])

    # 1. Înregistrăm acțiunea
    database.record_swipe(swiper_id=swiper_user.id, swiped_id=swiped_user_id, action=action)
    
    # 2. Dacă a fost 'like', verificăm dacă e match reciproc
    if action == 'like':
        is_match = database.check_for_match(swiper_user.id, swiped_user_id)
        if is_match:
            # Notificăm ambii useri!
            swiped_user_profile = database.get_user(swiped_user_id)
            await context.bot.send_message(
                chat_id=swiper_user.id,
                text=f"🎉 Este un Match! Ai o potrivire cu {swiped_user_profile.nickname}."
            )
            await context.bot.send_message(
                chat_id=swiped_user_id,
                text=f"🎉 Este un Match! Ai o potrivire cu {swiper_user.first_name}."
            )

    # 3. Căutăm și afișăm următorul profil
    next_potential_match = database.find_potential_match(swiper_user.id)
    if next_potential_match:
        await show_profile_card(update, context, next_potential_match)
    else:
        await query.edit_message_text("Nu am mai găsit pe nimeni nou pentru tine. Revino mai târziu!")

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
    application.add_handler(CommandHandler("preferinte", preferences_menu))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(CommandHandler("match", find_match_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    print("Bot-ul a pornit și ascultă...")
    application.run_polling()

if __name__ == "__main__":
    main()