import os
import smtplib
from email.message import EmailMessage
import webuntis
import datetime

def send_mail(content, datum_fuer_betreff):
    msg = EmailMessage()
    msg.set_content(content)
    msg['Subject'] = f"Stundenplan Check: {datum_fuer_betreff:%d.%m.%Y}"
    msg['From'] = os.getenv("EMAIL_SENDER")
    msg['To'] = os.getenv("EMAIL_RECEIVER")

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(os.getenv("EMAIL_SENDER"), os.getenv("EMAIL_PASSWORD"))
            smtp.send_message(msg)
        print("E-Mail erfolgreich versendet!")
    except Exception as e:
        print(f"Fehler beim E-Mail-Versand: {e}")

# --- NEU: Unser Übersetzungs-Wörterbuch für Fächer ---
FACH_NAMEN = {
    "MA": "Mathe",
    "EK": "Erdkunde",
    "SP": "Sport",
    "DE": "Deutsch",
    "EN": "Englisch",
    "BI": "Biologie",
    "CH": "Chemie",
    "PH": "Physik",
    "GE": "Geschichte",
    "KU": "Kunst",
    "MU": "Musik",
    "RE": "Religion",
    "WN": "Werte und Normen",
    "PO": "Politik",
    "FR": "Französisch",
    "LA": "Latein",
    "SN": "Spanisch"
}

# --- NEU: Zuordnung der Uhrzeiten zu den Schulstunden ---
STUNDEN_NR = {
    "08:00": "1.",
    "08:50": "2.",
    "09:55": "3.",
    "10:45": "4.",
    "11:45": "5.",
    "12:35": "6."
}

def run():
    try:
        s = webuntis.Session(
            server=os.getenv("UNTIS_SERVER"),
            school=os.getenv("UNTIS_SCHOOL"),
            username=os.getenv("UNTIS_USER"),
            password=os.getenv("UNTIS_PASSWORD"),
            useragent="MeinStundenplanScraper"
        )
        s.login()
        
        ziel_klasse = "5e" 
        klasse_obj = s.klassen().filter(name=ziel_klasse)
        
        if not klasse_obj:
            s.logout()
            return
            
        morgen = datetime.date.today() + datetime.timedelta(days=1)
        timetable = s.timetable(klasse=klasse_obj[0], start=morgen, end=morgen)
        timetable = sorted(timetable, key=lambda x: x.start)
        
        if not timetable:
            report = f"Am {morgen:%d.%m.%Y} findet laut System kein Unterricht statt."
        else:
            report = f"Stundenplan für Klasse {klasse_obj[0].name} am {morgen:%d.%m.%Y}:\n\n"
            
            for lesson in timetable:
                start_zeit = lesson.start.strftime('%H:%M')
                end_zeit = lesson.end.strftime('%H:%M')
                fach_abk = lesson.subjects[0].name if lesson.subjects else "Unbekannt"
                
                # --- NEU: Der Filter für die AGs und Nachmittag ---
                # Wenn die Stunde um 13:50 oder später anfängt ODER eine "AG" ist, überspringen!
                if start_zeit >= "13:50" or "AG" in fach_abk:
                    continue
                
                # Fach-Abkürzung in den vollen Namen übersetzen
                # (Findet er es nicht im Wörterbuch, nimmt er einfach die Abkürzung)
                fach_voll = FACH_NAMEN.get(fach_abk, fach_abk)
                
                # Schulstunde ermitteln (1., 2. etc.)
                stunde = STUNDEN_NR.get(start_zeit, "?.")
                
                lehrer = lesson.teachers[0].name if lesson.teachers else "Unbekannt"
                raum = lesson.rooms[0].name if lesson.rooms else "Unbekannt"
                status = "!! ENTFÄLLT !!" if lesson.code == "cancelled" else "Findet statt"
                
                # --- NEU: Das aufgeräumte Design ---
                report += f"{stunde} Stunde {start_zeit} - {end_zeit} | {fach_voll} bei {lehrer} in Raum {raum} -> {status}\n"
        
        s.logout()
        send_mail(report, morgen)
        
    except Exception as e:
        print(f"Fehler: {e}")

if __name__ == "__main__":
    run()
