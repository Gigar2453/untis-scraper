import os
import smtplib
from email.message import EmailMessage
from webuntis_fetcher import WebUntisFetcher
from datetime import datetime

def send_mail(content):
    msg = EmailMessage()
    msg.set_content(content)
    msg['Subject'] = f"Stundenplan Check: {datetime.now():%d.%m.%Y}"
    msg['From'] = os.getenv("EMAIL_SENDER")
    msg['To'] = os.getenv("EMAIL_RECEIVER")

    # Wir nutzen den Gmail-Server
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(os.getenv("EMAIL_SENDER"), os.getenv("EMAIL_PASSWORD"))
            smtp.send_message(msg)
        print("E-Mail wurde erfolgreich versendet.")
    except Exception as e:
        print(f"Fehler beim E-Mail-Versand: {e}")

def run():
    # Hier ziehen wir uns alle Daten aus deinen GitHub Secrets
    fetcher = WebUntisFetcher(
        server=os.getenv("UNTIS_SERVER"),
        school=os.getenv("UNTIS_SCHOOL"),
        username=os.getenv("UNTIS_USER"),
        password=os.getenv("UNTIS_PASSWORD")
    )
    
    try:
        # Wir holen den Plan für heute
        timetable = fetcher.get_timetable(date=datetime.now())
        
        if not timetable:
            report = "Keine Daten gefunden oder heute findet kein Unterricht statt."
        else:
            report = f"Guten Morgen! Hier ist der Plan für das Athenaeum Stade ({datetime.now():%d.%m.%Y}):\n\n"
            for lesson in timetable:
                status = "!! ENTFÄLLT !!" if lesson.is_cancelled else "Findet statt"
                info = f" Info: {lesson.substitution_info}" if lesson.substitution_info else ""
                report += f"{lesson.start:%H:%M} - {lesson.subject} bei {lesson.teacher} in Raum {lesson.room}: {status}{info}\n"
        
        send_mail(report)
        
    except Exception as e:
        print(f"Fehler beim Auslesen von WebUntis: {e}")

if __name__ == "__main__":
    run()
