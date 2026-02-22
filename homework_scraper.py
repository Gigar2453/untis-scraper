import os
import smtplib
from email.message import EmailMessage
import webuntis
import datetime

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
        
        ziel_klasse = "5e" 
        klasse_obj = s.klassen().filter(name=ziel_klasse)
        
        if not klasse_obj:
            s.logout()
            return
            
        start_map = heute - datetime.timedelta(days=14)
        end_map = heute + datetime.timedelta(days=14)
        timetable = s.timetable(klasse=klasse_obj[0], start=start_map, end=end_map)
        
        # SICHERES MAPPING AUFBAUEN (Fängt alle Namensänderungen ab)
        lesson_to_subject = {}
        for lesson in timetable:
            if lesson.subjects:
                abk = lesson.subjects[0].name
                # Wir fragen Python sicher nach der ID, egal wie die Bibliothek sie gerade nennt
                l_id = getattr(lesson, 'lesson_id', getattr(lesson, 'lsid', getattr(lesson, 'lsnumber', None)))
                if l_id:
                    lesson_to_subject[l_id] = FACH_NAMEN.get(abk, abk)

        # HAUSAUFGABEN ABRUFEN
        homeworks = s.homework(start=start_map, end=end_map)
        
        aufgegeben_heute = []
        faellig_morgen = []
        
        for hw in homeworks:
            # Sicheres Auslesen der Daten ohne Absturzgefahr
            hw_date_raw = getattr(hw, 'date', None)
            hw_due_raw = getattr(hw, 'due_date', getattr(hw, 'dueDate', None))
            
            if not hw_date_raw or not hw_due_raw:
                continue
                
            # In reines Datumsobjekt konvertieren
            hw_date = hw_date_raw.date() if hasattr(hw_date_raw, 'date') else hw_date_raw
            hw_due = hw_due_raw.date() if hasattr(hw_due_raw, 'date') else hw_due_raw
            
            # Fach zur Aufgabe heraussuchen
            hw_l_id = getattr(hw, 'lesson_id', getattr(hw, 'lessonId', None))
            fach = lesson_to_subject.get(hw_l_id, "Schulaufgabe")
            
            # Text extrahieren (Manchmal ist das Textfeld leer, dann nutzen wir die "Bemerkung")
            text = getattr(hw, 'text', '')
            remark = getattr(hw, 'remark', '')
            anzeige_text = text if text else remark
            if not anzeige_text:
                anzeige_text = "Siehe Untis für genaue Details."
                
            eintrag = f"- {fach}: {anzeige_text}"
            
            # Einsortieren in die richtige Liste
            if hw_date == heute:
                aufgegeben_heute.append(eintrag)
            if hw_due == morgen:
                faellig_morgen.append(eintrag)

        # E-MAIL TEXT ZUSAMMENBAUEN
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
