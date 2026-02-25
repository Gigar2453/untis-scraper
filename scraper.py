import os
import smtplib
from email.message import EmailMessage
import webuntis
import datetime
import urllib.request
import urllib.parse
import json
from zoneinfo import ZoneInfo

def send_mail(content, datum_fuer_betreff):
    msg = EmailMessage()
    msg.set_content(content)
    msg['Subject'] = f"Stundenplan & Zug-Check: {datum_fuer_betreff:%d.%m.%Y}"
    msg['From'] = os.getenv("EMAIL_SENDER")
    msg['To'] = os.getenv("EMAIL_RECEIVER")
    
    # Prüfen, ob eine CC-Adresse hinterlegt ist und hinzufügen
    cc_receiver = os.getenv("EMAIL_CC")
    if cc_receiver:
        msg['Cc'] = cc_receiver

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(os.getenv("EMAIL_SENDER"), os.getenv("EMAIL_PASSWORD"))
            smtp.send_message(msg)
        print("E-Mail erfolgreich versendet!")
    except Exception as e:
        print(f"Fehler beim E-Mail-Versand: {e}")

FACH_NAMEN = {
    "MA": "Mathe", "EK": "Erdkunde", "SP": "Sport", "DE": "Deutsch",
    "EN": "Englisch", "BI": "Biologie", "CH": "Chemie", "PH": "Physik",
    "GE": "Geschichte", "KU": "Kunst", "MU": "Musik", "RE": "Religion",
    "WN": "Werte und Normen", "PO": "Politik", "FR": "Französisch",
    "LA": "Latein", "SN": "Spanisch"
}

STUNDEN_NR = {
    "08:00": "1.", "08:50": "2.", "09:55": "3.",
    "10:45": "4.", "11:45": "5.", "12:35": "6."
}

def get_train_connections():
    try:
        headers = {'User-Agent': 'untis-scraper-github-Gigar2453'}
        
        # IDs für Agathenburg und Stade abfragen
        url_a = "https://v6.db.transport.rest/locations?query=Agathenburg&results=1"
        req_a = urllib.request.Request(url_a, headers=headers)
        with urllib.request.urlopen(req_a) as response:
            id_a = json.loads(response.read().decode())[0]['id']
            
        url_b = "https://v6.db.transport.rest/locations?query=Stade&results=1"
        req_b = urllib.request.Request(url_b, headers=headers)
        with urllib.request.urlopen(req_b) as response:
            id_b = json.loads(response.read().decode())[0]['id']
            
        # NEU: Wir setzen die Startzeit fest auf heute 06:20 Uhr deutscher Zeit!
        tz = ZoneInfo("Europe/Berlin")
        heute = datetime.datetime.now(tz)
        start_zeit = heute.replace(hour=6, minute=20, second=0, microsecond=0)
        start_zeit_str = urllib.parse.quote(start_zeit.isoformat())
        
        # NEU: Wir verbieten der API direkt Busse und Regionalzüge. Wir wollen nur S-Bahnen.
        url_j = f"https://v6.db.transport.rest/journeys?from={id_a}&to={id_b}&results=10&departure={start_zeit_str}&bus=false&regionalExpress=false&nationalExpress=false&national=false&regional=false"
        
        req_j = urllib.request.Request(url_j, headers=headers)
        with urllib.request.urlopen(req_j) as response:
            journeys = json.loads(response.read().decode()).get('journeys', [])
            
        train_text = "🚆 ZUGVERBINDUNG (Agathenburg -> Stade):\n"
        
        s_bahnen = []
        for j in journeys:
            legs = j.get('legs', [])
            if not legs:
                continue
            leg = legs[0]
            line_name = leg.get('line', {}).get('name', 'Zug')
            planned_dep = leg.get('plannedDeparture')
            
            if not planned_dep:
                continue
                
            time_str = planned_dep[11:16]
            
            # Unser Zeitfenster
            if time_str < "06:30" or time_str > "07:40":
                continue
            
            if "S" not in line_name: 
                continue
                
            s_bahnen.append(leg)
            
            # Stoppen, wenn wir 3 Bahnen haben
            if len(s_bahnen) == 3:
                break
        
        if not s_bahnen:
            return train_text + "-> Keine passenden S-Bahn Verbindungen zwischen 06:30 und 07:40 Uhr gefunden.\n\n"
            
        for leg in s_bahnen:
            line_name = leg.get('line', {}).get('name', 'S-Bahn')
            planned_dep = leg.get('plannedDeparture')
            delay_sec = leg.get('departureDelay')
            cancelled = leg.get('cancelled', False)
            
            if planned_dep:
                time_str = planned_dep[11:16]
                
                if cancelled:
                    status_str = " ❌ FÄLLT AUS!"
                elif delay_sec is not None:
                    delay_min = delay_sec // 60
                    if delay_min > 0:
                        status_str = f" (+{delay_min} Min Verspätung)"
                    elif delay_min < 0:
                        status_str = f" ({abs(delay_min)} Min früher)"
                    else:
                        status_str = " (Pünktlich)"
                else:
                    status_str = " (Pünktlich laut Plan)"
                
                train_text += f"- {time_str} Uhr | {line_name}{status_str}\n"
                
        return train_text + "\n"
        
    except Exception as e:
        return f"🚆 ZUGVERBINDUNG: Livedaten konnten nicht abgerufen werden ({e})\n\n"
def run():
    print("Starte den Scraper...")
    try:
        s = webuntis.Session(
            server=os.getenv("UNTIS_SERVER"),
            school=os.getenv("UNTIS_SCHOOL"),
            username=os.getenv("UNTIS_USER"),
            password=os.getenv("UNTIS_PASSWORD"),
            useragent="MeinStundenplanScraper"
        )
        s.login()
        
        # --- NEU: Wir suchen nach der exakten Schüler-ID statt der Klasse ---
        student_id = 10970 
        student_liste = s.students().filter(id=student_id)
        
        if not student_liste:
            s.logout()
            print("Fehler: Konnte die Schüler-ID 10970 nicht finden!")
            return
            
        student_obj = student_liste[0]
        heute = datetime.date.today()
        
        # HIER DER MAGISCHE BEFEHL: Wir rufen den Plan für "student" ab, nicht für "klasse"
        timetable = s.timetable(student=student_obj, start=heute, end=heute)
        timetable = sorted(timetable, key=lambda x: x.start)
        
        report = get_train_connections()
        
        if not timetable:
            report += f"🏫 STUNDENPLAN:\nAm {heute:%d.%m.%Y} findet laut System kein Unterricht statt."
        else:
            # Überschrift etwas angepasst
            report += f"🏫 PERSÖNLICHER STUNDENPLAN am {heute:%d.%m.%Y}:\n\n"
            
            for lesson in timetable:
                start_zeit = lesson.start.strftime('%H:%M')
                end_zeit = lesson.end.strftime('%H:%M')
                fach_abk = lesson.subjects[0].name if lesson.subjects else "Unbekannt"
                
                if start_zeit >= "13:50" or "AG" in fach_abk:
                    continue
                
                fach_voll = FACH_NAMEN.get(fach_abk, fach_abk)
                stunde = STUNDEN_NR.get(start_zeit, "?.")
                
                lehrer = lesson.teachers[0].name if lesson.teachers else "Unbekannt"
                raum = lesson.rooms[0].name if lesson.rooms else "Unbekannt"
                status = "!! ENTFÄLLT !!" if lesson.code == "cancelled" else "Findet statt"
                
                report += f"{stunde} Stunde {start_zeit} - {end_zeit} | {fach_voll} bei {lehrer} in Raum {raum} -> {status}\n"
        
        s.logout()
        send_mail(report, heute)
        
    except Exception as e:
        print(f"Fehler in Untis-Abfrage: {e}")

# Das ist der fehlende Startschuss!
if __name__ == "__main__":
    run()
