import os
import smtplib
from email.message import EmailMessage
import webuntis
import datetime

# Dein bewährtes Wörterbuch
FACH_NAMEN = {
    "MA": "Mathe", "EK": "Erdkunde", "SP": "Sport", "DE": "Deutsch",
    "EN": "Englisch", "BI": "Biologie", "CH": "Chemie", "PH": "Physik",
    "GE": "Geschichte", "KU": "Kunst", "MU": "Musik", "RE": "Religion",
    "WN": "Werte und Normen", "PO": "Politik", "FR": "Französisch",
    "LA": "Latein", "SN": "Spanisch"
}

def send_mail(content):
    msg = EmailMessage()
    msg.set_content(content)
    msg['Subject'] = f"📚 Hausaufgaben-Update: {datetime.date.today():%d.%m.%Y}"
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
        
        heute = datetime.date.today()
        morgen = heute + datetime.timedelta(days=1)
        
        # Um die Fächer zu den Hausaufgaben zuzuordnen, laden wir kurz den Plan der Klasse
        ziel_klasse = "5e" 
        klasse_obj = s.klassen().filter(name=ziel_klasse)
        
        # Wir holen den Plan für +/- 14 Tage, um die Fächer zu "lernen"
        start_map = heute - datetime.timedelta(days=14)
        end_map = heute + datetime.timedelta(days=14)
        timetable = s.timetable(klasse=klasse_obj[0], start=start_map, end=end_map)
        
        # Kleines internes Lexikon: Welche ID gehört zu welchem Fach?
        lesson_to_subject = {}
        for lesson in timetable:
            if lesson.subjects:
                abk = lesson.subjects[0].name
                lesson_to_subject[lesson.lessonId] = FACH_NAMEN.get(abk, abk)

        # ---------------------------------------------------------
        # JETZT KOMMEN DIE HAUSAUFGABEN
        # ---------------------------------------------------------
        homeworks = s.homework(start=start_map, end=end_map)
        
        aufgegeben_heute = []
        faellig_morgen = []
        
        for hw in homeworks:
            # Datumsformate bereinigen (WebUntis liefert manchmal Datum mit Uhrzeit, wir brauchen nur den Tag)
            hw_date = hw.date.date() if hasattr(hw.date, 'date') else hw.date
            hw_due = hw.dueDate.date() if hasattr(hw.dueDate, 'date') else hw.dueDate
            
            # Fachnamen aus unserem internen Lexikon holen
            fach = lesson_to_subject.get(hw.lessonId, "Unbekanntes Fach")
            
            # Text der Hausaufgabe (manchmal schreiben Lehrer es in 'text', manchmal in 'remark')
            text = hw.text if hw.text else hw.remark
            if not text:
                text = "Kein Text hinterlegt."
                
            eintrag = f"- {fach}: {text}"
            
            # Filter 1: Wurde es HEUTE aufgegeben?
            if hw_date == heute:
                aufgegeben_heute.append(eintrag)
                
            # Filter 2: Ist es zu MORGEN fällig?
            if hw_due == morgen:
                faellig_morgen.append(eintrag)

        # ---------------------------------------------------------
        # E-MAIL TEXT ZUSAMMENBAUEN
        # ---------------------------------------------------------
        report = f"Hallo! Hier ist das Hausaufgaben-Update für Josefine ({heute:%d.%m.%Y}):\n\n"
        
        report += "📝 HEUTE AUFGEGEBEN:\n"
        if aufgegeben_heute:
            for item in aufgegeben_heute:
                report += item + "\n"
        else:
            report += "- Die Lehrer haben heute nichts Neues ins System eingetragen.\n"
            
        report += "\n⏰ FÄLLIG ZU MORGEN:\n"
        if faellig_morgen:
            for item in faellig_morgen:
                report += item + "\n"
        else:
            report += "- Keine Aufgaben zu morgen fällig!\n"

        s.logout()
        send_mail(report)
        
    except Exception as e:
        print(f"Fehler: {e}")

if __name__ == "__main__":
    run()
