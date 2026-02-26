import os
import smtplib
from email.message import EmailMessage
import webuntis
import datetime
import urllib.request
import urllib.parse
import json
from zoneinfo import ZoneInfo

def send_mail(plain_content, html_content, datum_fuer_betreff):
    msg = EmailMessage()
    msg['Subject'] = f"Stundenplan & Zug-Check: {datum_fuer_betreff:%d.%m.%Y}"
    msg['From'] = os.getenv("EMAIL_SENDER")
    msg['To'] = os.getenv("EMAIL_RECEIVER")
    
    # Prüfen, ob eine CC-Adresse hinterlegt ist und hinzufügen
    cc_receiver = os.getenv("EMAIL_CC")
    if cc_receiver:
        msg['Cc'] = cc_receiver

    # Wir schicken beide Versionen mit (Fallback & HTML)
    msg.set_content(plain_content)
    msg.add_alternative(html_content, subtype='html')

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
    "WN": "Werte u. Normen", "PO": "Politik", "FR": "Französisch",
    "LA": "Latein", "SN": "Spanisch"
}

STUNDEN_NR = {
    "08:00": "1.", "08:50": "2.", "09:55": "3.",
    "10:45": "4.", "11:45": "5.", "12:35": "6."
}

def get_train_connections():
    plain_text = "🚆 ZUGVERBINDUNG (Agathenburg -> Stade):\n"
    html_text = ""
    
    try:
        # Tarnung als normaler Windows-Browser
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        
        # NEU: Wir nutzen das extrem stabile DBF-Projekt (IRIS Backend). 
        # Das liest direkt die echten digitalen Abfahrtstafeln aus!
        url = "https://dbf.finalrewind.org/Agathenburg.json?version=3"
        
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode())
            
        departures = data.get('departures', [])
        
        verbindungen = []
        for dep in departures:
            # Nur Züge in Richtung Stade / Cuxhaven
            dest = dep.get('destination', '')
            if 'Stade' not in dest and 'Cuxhaven' not in dest:
                continue
                
            train_name = dep.get('train', '')
            
            # DBF liefert die Zeiten als Format "HH:MM"
            time_str = dep.get('scheduledDeparture', '')
            if not time_str:
                continue
                
            # --- 1. TÜRSTEHER: Nur das exakte Zeitfenster (06:35 - 07:25 Uhr) ---
            if time_str < "06:35" or time_str > "07:25":
                continue
                
            # --- 2. TÜRSTEHER: RE und IC fliegen rigoros raus ---
            if "RE" in train_name.upper() or "IC" in train_name.upper():
                continue
                
            verbindungen.append(dep)
            # Wir stoppen, wenn wir die 3 relevanten Züge (06:40, 07:00, 07:20) haben
            if len(verbindungen) == 3:
                break
        
        if not verbindungen:
            plain_text += "-> Keine passenden S-Bahnen gefunden.\n\n"
            html_text = "<div class='item' style='color: #888;'>Keine regulären Abfahrten (S5) im Zeitraum gefunden.</div>"
            return plain_text, html_text
            
        for dep in verbindungen:
            train_name = dep.get('train', 'S-Bahn')
            time_str = dep.get('scheduledDeparture', '')
                
            # Verspätungen auslesen
            delay_min = dep.get('delayDeparture')
            if delay_min is None:
                delay_min = dep.get('delay')
                
            # Ausfälle auslesen
            cancelled = dep.get('isCancelled', False)
            if not cancelled:
                cancelled = dep.get('cancelled', False)
            
            if cancelled:
                status_str = "❌ FÄLLT AUS!"
                css_class = "text-bad"
            elif delay_min is not None:
                try:
                    delay_min = int(delay_min)
                    if delay_min > 0:
                        status_str = f"+{delay_min} Min Verspätung"
                        css_class = "text-bad"
                    elif delay_min < 0:
                        status_str = f"{abs(delay_min)} Min früher"
                        css_class = "text-ok"
                    else:
                        status_str = "Pünktlich"
                        css_class = "text-ok"
                except:
                    status_str = "Pünktlich"
                    css_class = "text-ok"
            else:
                status_str = "Pünktlich (Plan)"
                css_class = "text-ok"
            
            plain_text += f"- {time_str} Uhr | {train_name} ({status_str})\n"
            
            html_text += f"""
            <div class='item'>
                <span style='color: #fff; font-size: 15px;'>{time_str} Uhr</span> | 
                <span class='badge'>{train_name}</span> 
                <span class='{css_class}'>{status_str}</span>
            </div>
            """
            
        return plain_text + "\n", html_text
        
    except Exception as e:
        return f"Fehler Bahn: {e}\n\n", f"<div class='item text-bad'>Kritischer API-Fehler: {str(e)}</div>"
        
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
        
        student_id = 10970 
        student_liste = s.students().filter(id=student_id)
        
        if not student_liste:
            s.logout()
            print("Fehler: Konnte die Schüler-ID nicht finden!")
            return
            
        student_obj = student_liste[0]
        heute = datetime.date.today()
        
        timetable = s.timetable(student=student_obj, start=heute, end=heute)
        timetable = sorted(timetable, key=lambda x: x.start)
        
        plain_trains, html_trains = get_train_connections()
        plain_report = plain_trains
        html_timetable = ""
        
        if not timetable:
            plain_report += f"🏫 STUNDENPLAN:\nAm {heute:%d.%m.%Y} findet kein Unterricht statt."
            html_timetable = "<div class='item' style='color: #2ecc71;'>Kein Unterricht heute! 🎉</div>"
        else:
            plain_report += f"🏫 PERSÖNLICHER STUNDENPLAN am {heute:%d.%m.%Y}:\n\n"
            
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
                
                if lesson.code == "cancelled":
                    status_plain = "!! ENTFÄLLT !!"
                    status_html = "ENTFÄLLT"
                    css_status = "text-bad"
                else:
                    status_plain = "Findet statt"
                    status_html = "Findet statt"
                    css_status = "text-ok"
                
                plain_report += f"{stunde} Stunde {start_zeit} - {end_zeit} | {fach_voll} bei {lehrer} in Raum {raum} -> {status_plain}\n"
                
                # HTML Block für EINE Stunde
                html_timetable += f"""
                <div class='item'>
                    <div class='time-text'>{stunde} Stunde ({start_zeit} - {end_zeit})</div>
                    <div style='color: #eee;'>
                        <span class='badge'>{fach_voll}</span> bei {lehrer} in Raum <span class='text-hl'>{raum}</span> 
                        <span class='{css_status}'>-> {status_html}</span>
                    </div>
                </div>
                """
        
        s.logout()
        
        # --- HIER WIRD DAS DESIGN ZUSAMMENGEBAUT ---
        html_final = f"""
        <!DOCTYPE html>
        <html>
        <head>
        <style>
            body {{ background-color: #121212; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; color: #ddd; margin: 0; padding: 20px; line-height: 1.5; }}
            .wrapper {{ background-color: #1a1a1a; max-width: 650px; margin: 0 auto; border-radius: 8px; border-top: 4px solid #ff9800; box-shadow: 0 4px 15px rgba(0,0,0,0.5); padding: 25px; }}
            .terminal-header {{ font-family: monospace; color: #777; font-size: 13px; border-bottom: 1px dashed #444; padding-bottom: 12px; margin-bottom: 25px; }}
            .section {{ background-color: #222; padding: 18px; border-radius: 6px; margin-bottom: 25px; }}
            .train-border {{ border-left: 4px solid #e74c3c; }}
            .school-border {{ border-left: 4px solid #3498db; }}
            .section-title {{ font-weight: bold; color: #fff; text-transform: uppercase; margin-top: 0; margin-bottom: 15px; font-size: 15px; letter-spacing: 1px; }}
            .item {{ background-color: #2a2a2a; padding: 12px 15px; margin-bottom: 10px; border-radius: 4px; border-left: 2px solid #555; }}
            .badge {{ display: inline-block; background-color: #444; color: #fff; padding: 3px 8px; border-radius: 3px; font-size: 13px; font-weight: bold; margin-right: 8px; }}
            .text-hl {{ color: #f39c12; font-weight: bold; }}
            .text-ok {{ color: #2ecc71; font-size: 13px; float: right; font-weight: bold; }}
            .text-bad {{ color: #e74c3c; font-weight: bold; font-size: 13px; float: right; }}
            .time-text {{ color: #999; font-size: 12px; margin-bottom: 6px; letter-spacing: 0.5px; text-transform: uppercase; }}
        </style>
        </head>
        <body>
            <div class="wrapper">
                <div class="terminal-header">
                    > User: Josefine | Date: {heute:%d.%m.%Y} | Status: Sync Complete
                </div>
                
                <div class="section train-border">
                    <h3 class="section-title">🚆 Zugverbindungen</h3>
                    {html_trains}
                </div>

                <div class="section school-border">
                    <h3 class="section-title">🏫 Stundenplan</h3>
                    {html_timetable}
                </div>
            </div>
        </body>
        </html>
        """
        
        send_mail(plain_report, html_final, heute)
        
    except Exception as e:
        print(f"Fehler in Untis-Abfrage: {e}")

if __name__ == "__main__":
    run()
