import os
import smtplib
from email.message import EmailMessage
import webuntis
import datetime
import urllib.request
import urllib.parse
import json

def send_mail(content, datum_fuer_betreff):
    msg = EmailMessage()
    msg.set_content(content)
    msg['Subject'] = f"Stundenplan & Zug-Check: {datum_fuer_betreff:%d.%m.%Y}"
    msg['From'] = os.getenv("EMAIL_SENDER")
    msg['To'] = os.getenv("EMAIL_RECEIVER")

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
        # IDs für Agathenburg und Stade abfragen
        url_a = "https://v6.db.transport.rest/locations?query=Agathenburg&results=1"
        req_a = urllib.request.Request(url_a, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req_a) as response:
            id_a = json.loads(response.read().decode())[0]['id']
            
        url_b = "https://v6.db.transport.rest/locations?query=Stade&results=1"
        req_b = urllib.request.Request(url_b, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req_b) as response:
            id_b = json.loads(response.read().decode())[0]['id']
            
        # Wir fragen extra 6 Verbindungen ab, damit wir genug haben, wenn wir die REs rauswerfen!
        url_j = f"https://v6.db.transport.rest/journeys?from={id_a}&to={id_b}&results=6"
        req_j = urllib.request.Request(url_j, headers={'User-Agent': 'Mozilla/5.0'})
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
            
            # --- DER FILTER ---
            # Wenn es keine S-Bahn ist (z.B. RE, Metronom, Bus), überspringen wir diese Verbindung
            if "RE" in line_name or "ME" in line_name or "Bus" in line_name:
                continue
            if "S" not in line_name: # Es muss ein S (S3, S5) im Namen sein
                continue
                
            s_bahnen.append(leg)
            
            # Wir wollen exakt die nächsten 3 S-Bahnen haben
            if len(s_bahnen) == 3:
                break
        
        if not s_bahnen:
            return train_text + "-> Keine S-Bahn Verbindungen in der nächsten Zeit gefunden.\n\n"
            
        # Die 3 gefilterten S-Bahnen hübsch in die Mail schreiben
        for leg in s_bahnen:
            line_name = leg.get('line', {}).get('name', 'S-Bahn')
            planned_dep = leg.get('plannedDeparture')
            delay_sec = leg.get('departureDelay')
            cancelled = leg.get('cancelled', False)
            
            if planned_dep:
                # Uhrzeit aus dem Datumsstempel herausschneiden
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
            
        heute = datetime.date.today()
        timetable = s.timetable(klasse=klasse_obj[0], start=heute, end=heute)
        timetable = sorted(timetable, key=lambda x: x.start)
        
        # Zug-Radar abrufen und oben in den Text packen
        report = get_train_connections()
        
        if not timetable:
            report += f"🏫 STUNDENPLAN:\nAm {heute:%d.%m.%Y} findet laut System kein Unterricht statt."
        else:
            report += f"🏫 STUNDENPLAN für Klasse {klasse_obj[0].name} am {heute:%d.%m.%Y}:\n\n"
            
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
        print(f"Fehler: {e}")

if __name__ == "__main__":
    run()
