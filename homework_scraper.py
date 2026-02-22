import os
import smtplib
import datetime
import re
from email.message import EmailMessage
from playwright.sync_api import sync_playwright

FACH_NAMEN = {
    "MA": "Mathe", "EK": "Erdkunde", "SP": "Sport", "DE": "Deutsch",
    "EN": "Englisch", "BI": "Biologie", "CH": "Chemie", "PH": "Physik",
    "GE": "Geschichte", "KU": "Kunst", "MU": "Musik", "RE": "Religion",
    "WN": "Werte und Normen", "PO": "Politik", "FR": "Französisch",
    "LA": "Latein", "SN": "Spanisch", "AG": "AG"
}

def send_mail(report_html):
    msg = EmailMessage()
    heute = datetime.date.today()
    msg['Subject'] = f"📚 Hausaufgaben Übersicht: {heute:%d.%m.%Y}"
    msg['From'] = os.getenv("EMAIL_SENDER")
    msg['To'] = os.getenv("EMAIL_RECEIVER")
    
    msg.set_content("Bitte aktiviere HTML in deinem E-Mail-Programm, um das Dashboard zu sehen.")
    msg.add_alternative(report_html, subtype='html')

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(os.getenv("EMAIL_SENDER"), os.getenv("EMAIL_PASSWORD"))
            smtp.send_message(msg)
        print("E-Mail erfolgreich versendet!")
    except Exception as e:
        print(f"Fehler beim E-Mail-Versand: {e}")


def extract_homework_text(raw_text):
    start_idx = raw_text.find("Bald fällig")
    if start_idx == -1:
        return f'<div style="background:#222; color:#fff; padding:20px;"><h3>Fehler: Bereich "Bald fällig" nicht gefunden.</h3><pre style="color:#ff5555;">{raw_text[:1000]}</pre></div>'
        
    end_idx = raw_text.find("Verpasst", start_idx)
    if end_idx == -1:
        end_idx = raw_text.find("Abgeschlossen", start_idx)
    if end_idx == -1:
        end_idx = len(raw_text)
        
    target_text = raw_text[start_idx + len("Bald fällig"):end_idx]
    
    # --- DIE NEUE KREISSÄGE ---
    pattern = r'([A-ZÄÖÜ]{2,3})\s+[A-ZÄÖÜ]{2,4}\s+(\d{2}\.\d{2}\.202\d)\s+([A-Za-zäöüß]+,\s*\d{2}\.\d{2}\.202\d)\s+Hausaufgabe'
    parts = re.split(pattern, target_text)
    
    hw_list = []
    for i in range(1, len(parts), 4):
        if i + 3 < len(parts):
            fach_abk = parts[i]
            aufgabe_datum = parts[i+1]
            faellig_datum = parts[i+2]
            text = parts[i+3].strip()
            
            fach = FACH_NAMEN.get(fach_abk, fach_abk)
            hw_list.append({
                "fach": fach, 
                "aufgabe_datum": aufgabe_datum, 
                "faellig_datum": faellig_datum, 
                "text": text
            })

    heute = datetime.date.today()
    heute_str = heute.strftime("%d.%m.%Y")
    
    # Wenn wirklich GAR NICHTS im System steht (Ferien etc.)
    if not hw_list:
        return f'<div style="background:#121212; color:#fff; padding:20px;"><h3>🎉 Keine einzige Aufgabe im System. Zurücklehnen!</h3></div>'

    # --- DIE SORTIERUNG ---
    heute_neu = []
    weitere_aufgaben = []
    for hw in hw_list:
        if hw["aufgabe_datum"] == heute_str:
            heute_neu.append(hw)
        else:
            weitere_aufgaben.append(hw)

    # --- KALENDER-LOGIK: Montag bis Freitag generieren ---
    if heute.weekday() >= 5: # Samstag/Sonntag -> Fokus auf nächste Woche
        montag = heute + datetime.timedelta(days=(7 - heute.weekday()))
    else: # Montag bis Freitag -> Fokus auf aktuelle Woche
        montag = heute - datetime.timedelta(days=heute.weekday())
        
    tage_namen = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
    hw_by_date = {}
    
    # 1. Platzhalter für Montag bis Freitag erstellen
    for i in range(5):
        d = montag + datetime.timedelta(days=i)
        datum_str = d.strftime("%d.%m.%Y")
        tag_name = tage_namen[d.weekday()]
        anzeige_titel = f"{tag_name}, {datum_str}"
        hw_by_date[datum_str] = {"titel": anzeige_titel, "aufgaben": [], "date_obj": d}

    # 2. Die gefundenen Aufgaben einsortieren
    for hw in weitere_aufgaben:
        # hw["faellig_datum"] ist z.B. "Montag, 23.02.2026" -> Wir wollen nur "23.02.2026"
        datum_nur = hw["faellig_datum"].split(",")[-1].strip()
        
        # Falls eine Aufgabe außerhalb von Mo-Fr liegt (z.B. in 2 Wochen), fügen wir den Tag hinzu
        if datum_nur not in hw_by_date:
            try:
                d_obj = datetime.datetime.strptime(datum_nur, "%d.%m.%Y").date()
            except:
                d_obj = datetime.date.max 
            hw_by_date[datum_nur] = {"titel": hw["faellig_datum"], "aufgaben": [], "date_obj": d_obj}
            
        hw_by_date[datum_nur]["aufgaben"].append(hw)

    # Nach Datum sortieren, damit alles in der richtigen Reihenfolge bleibt
    sorted_dates = sorted(hw_by_date.keys(), key=lambda k: hw_by_date[k]["date_obj"])


    # --- DAS E-MAIL-DESIGN (HTML ZUSAMMENBAU) ---
    html = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #121212; color: #e0e0e0; padding: 20px; line-height: 1.5;">
        <div style="max-width: 650px; margin: 0 auto; background-color: #1e1e1e; border: 1px solid #333333; border-radius: 6px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.5);">
            <div style="background-color: #252526; padding: 20px; border-bottom: 2px solid #ff9800;">
                <h2 style="margin: 0; color: #ffffff; font-size: 18px; text-transform: uppercase; letter-spacing: 1.5px;">Hausaufgaben-Dashboard</h2>
                <p style="margin: 8px 0 0 0; color: #888888; font-family: 'Courier New', Courier, monospace; font-size: 13px;">
                    > User: Josefine | Date: {heute_str} | Status: Sync Complete
                </p>
            </div>
            <div style="padding: 25px;">
    """

    # Sektion: Heute Neu
    html += """
                <div style="margin-bottom: 30px; background-color: #2a1b1b; border-left: 4px solid #ff5252; padding: 15px; border-radius: 0 4px 4px 0;">
                    <h3 style="margin: 0 0 8px 0; color: #ff5252; font-size: 14px; text-transform: uppercase; letter-spacing: 1px;">🚨 Heute neu aufbekommen</h3>
    """
    if heute_neu:
        for hw in heute_neu:
            safe_text = hw['text'].replace('\n', '<br>')
            html += f'<p style="margin: 0 0 10px 0; color: #d0d0d0; font-size: 14px;">-> <b style="color:#ffffff;">[{hw["fach"]}]</b> (Fällig am {hw["faellig_datum"]}):<br>{safe_text}</p>'
    else:
        html += '<p style="margin: 0; color: #d0d0d0; font-size: 14px;">-> Heute wurden (bisher) keine neuen Hausaufgaben ins System eingetragen.</p>'
    html += "</div>"

    # Sektion: Weitere fällige Aufgaben
    html += """
                <h3 style="margin: 0 0 20px 0; color: #ffffff; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; border-bottom: 1px solid #444444; padding-bottom: 8px;">
                    📅 Übersicht (Aktuelle Woche)
                </h3>
    """
    
    # Die Wochentage durchgehen und ausgeben
    for datum_str in sorted_dates:
        tages_daten = hw_by_date[datum_str]
        titel = tages_daten["titel"]
        aufgaben = tages_daten["aufgaben"]
        
        html += f"""
            <div style="margin-bottom: 15px; background-color: #252526; padding: 15px; border-radius: 4px; border-left: 3px solid #4db8ff;">
                <div style="font-family: 'Courier New', Courier, monospace; color: #4db8ff; margin-bottom: 10px; font-size: 13px; font-weight: bold;">{titel}</div>
        """
        
        # Prüfung: Sind Aufgaben für den Tag vorhanden?
        if not aufgaben:
             html += """
                <div style="margin-bottom: 0; display: table;">
                    <span style="color: #666666; font-size: 14px; font-style: italic;">Keine Hausaufgaben. 🎉</span>
                </div>
             """
        else:
            for hw in aufgaben:
                safe_text = hw['text'].replace('\n', '<br>')
                html += f"""
                    <div style="margin-bottom: 12px; display: table;">
                        <span style="background-color: #333333; padding: 3px 8px; border-radius: 3px; font-size: 12px; color: #ffffff; font-weight: bold; margin-right: 10px; display: table-cell; white-space: nowrap;">{hw['fach']}</span>
                        <span style="color: #cccccc; font-size: 14px; display: table-cell; padding-left: 10px;">{safe_text}</span>
                    </div>
                """
        html += "</div>"

    # HTML Footer
    html += """
            </div>
        </div>
    </div>
    """
    return html


def run():
    print("Starte den Geister-Browser...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1600, 'height': 1200})
        page = context.new_page()
        
        try:
            print("Navigiere zur Login-Seite...")
            page.goto("https://gym-athenaeum-stade.webuntis.com/WebUntis/?school=gym-athenaeum-stade")
            
            page.fill('input[type="text"], input#user', os.getenv("UNTIS_USER"))
            page.fill('input[type="password"], input#pass', os.getenv("UNTIS_PASSWORD"))
            page.click('button[type="submit"], button#loginBtn')
            
            print("Login ausgeführt. Warte auf das Dashboard...")
            page.wait_for_load_state("networkidle", timeout=20000)
            
            print("Navigiere zur Hausaufgaben-Übersicht...")
            page.goto("https://gym-athenaeum-stade.webuntis.com/student-homework")
            page.wait_for_load_state("networkidle", timeout=20000)
            page.wait_for_timeout(5000)
            
            print("Sauge Text aus allen Bereichen der Webseite ab...")
            raw_text = ""
            
            try:
                raw_text += page.inner_text("body") + "\n"
            except:
                pass
                
            for frame in page.frames:
                try:
                    text = frame.inner_text("body")
                    if text:
                        raw_text += text + "\n"
                except:
                    continue
            
            report_html = extract_homework_text(raw_text)
            
            browser.close()
            send_mail(report_html)
            
        except Exception as e:
            print(f"Fehler bei der Browser-Navigation: {e}")
            browser.close()

if __name__ == "__main__":
    run()
