import os
import smtplib
from email.message import EmailMessage
import webuntis
import datetime

def send_mail(content, datum_fuer_betreff):
    msg = EmailMessage()
    msg.set_content(content)
    # Betreff an das gesuchte Datum anpassen
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
        print("Login bei WebUntis erfolgreich!")

        ziel_klasse = "5e" # Hier steht dein kleines 'e'
        
        alle_klassen = s.klassen()
        klasse_obj = alle_klassen.filter(name=ziel_klasse)
        
        if not klasse_obj:
            print(f"Fehler: Klasse '{ziel_klasse}' nicht gefunden.")
            s.logout()
            return
            
        # --- HIER IST DIE ÄNDERUNG FÜR "MORGEN" ---
        morgen = datetime.date.today() + datetime.timedelta(days=1)
        
        # Wir fragen Untis explizit nach dem Plan für morgen
        timetable = s.timetable(klasse=klasse_obj[0], start=morgen, end=morgen)
        timetable = sorted(timetable, key=lambda x: x.start)
        
        if not timetable:
            report = f"Am {morgen:%d.%m.%Y} findet laut System kein Unterricht statt."
        else:
            report = f"Stundenplan für Klasse {klasse_obj[0].name} am {morgen:%d.%m.%Y}:\n\n"
            for lesson in timetable:
                status = "!! ENTFÄLLT !!" if lesson.code == "cancelled" else "Findet statt"
                fach = lesson.subjects[0].name if lesson.subjects else "Unbekannt"
                lehrer = lesson.teachers[0].name if lesson.teachers else "Unbekannt"
                raum = lesson.rooms[0].name if lesson.rooms else "Unbekannt"
                
                report += f"{lesson.start.strftime('%H:%M')} Uhr - {fach} bei {lehrer} in Raum {raum} -> {status}\n"
        
        s.logout()
        
        # Datum an die E-Mail-Funktion übergeben
        send_mail(report, morgen)
        
    except Exception as e:
        print(f"Fehler: {e}")

if __name__ == "__main__":
    run()
