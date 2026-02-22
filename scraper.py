import os
import smtplib
from email.message import EmailMessage
import webuntis
import datetime

def send_mail(content):
    msg = EmailMessage()
    msg.set_content(content)
    msg['Subject'] = f"Stundenplan Check: {datetime.date.today():%d.%m.%Y}"
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
        # 1. Einloggen bei WebUntis
        s = webuntis.Session(
            server=os.getenv("UNTIS_SERVER"),
            school=os.getenv("UNTIS_SCHOOL"),
            username=os.getenv("UNTIS_USER"),
            password=os.getenv("UNTIS_PASSWORD"),
            useragent="MeinStundenplanScraper"
        )
        s.login()
        print("Login bei WebUntis erfolgreich!")

        # 2. Die Klasse deiner Tochter suchen (BITTE ANPASSEN!)
        ziel_klasse = "5e" # <--- HIER DEN KLASSENNAMEN EINTRAGEN
        
        klasse_obj = s.klassen().filter(name=ziel_klasse)
        if not klasse_obj:
            print(f"Fehler: Klasse '{ziel_klasse}' wurde im System nicht gefunden!")
            return
            
        # 3. Stundenplan für heute abrufen
        today = datetime.date.today()
        timetable = s.timetable(klasse=klasse_obj[0], start=today, end=today)
        
        # 4. Daten zeitlich sortieren
        timetable = sorted(timetable, key=lambda x: x.start)
        
        if not timetable:
            report = "Heute findet laut System kein Unterricht statt."
        else:
            report = f"Stundenplan für Klasse {ziel_klasse} am {today:%d.%m.%Y}:\n\n"
            for lesson in timetable:
                # Fällt die Stunde aus?
                status = "!! ENTFÄLLT !!" if lesson.code == "cancelled" else "Findet statt"
                
                # Daten aus den Listen extrahieren
                fach = lesson.subjects[0].name if lesson.subjects else "Unbekannt"
                lehrer = lesson.teachers[0].name if lesson.teachers else "Unbekannt"
                raum = lesson.rooms[0].name if lesson.rooms else "Unbekannt"
                
                report += f"{lesson.start.strftime('%H:%M')} Uhr - {fach} bei {lehrer} in Raum {raum} -> {status}\n"
        
        # 5. Ausloggen und Mail absenden
        s.logout()
        send_mail(report)
        
    except Exception as e:
        print(f"Fehler: {e}")

if __name__ == "__main__":
    run()
