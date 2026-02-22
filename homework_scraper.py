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

# 1. Die Mail-Funktion (Jetzt mit HTML-Unterstützung!)
def send_mail(report_html):
    msg = EmailMessage()
    heute = datetime.date.today()
    msg['Subject'] = f"📚 Hausaufgaben Übersicht: {heute:%d.%m.%Y}"
    msg['From'] = os.getenv("EMAIL_SENDER")
    msg['To'] = os.getenv("EMAIL_RECEIVER")
    
    # Fallback für uralte Mail-Clients, die kein HTML können
    msg.set_content("Bitte aktiviere HTML in deinem E-Mail-Programm, um das Dashboard zu sehen.")
    
    # Das hübsche Dark-Mode HTML einsetzen
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
        # Basis-HTML für Fehlermeldungen, damit die Mail nicht kaputt geht
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

    if not hw_list:
        return f'<div style="background:#222; color:#fff; padding:20px;"><h3>Aktuell keine Hausaufgaben gefunden.</h3><pre style="color:#aaa;">{target_text}</pre></div>'

    # --- DIE SORTIERUNG ---
    heute_str = datetime.date.today().strftime("%d.%m.%Y")
    heute_neu = []
    weitere_aufgaben = []
    
    for hw in hw_list:
        if hw["aufgabe_datum"] == heute_str:
            heute_neu.append(hw)
        else:
            weitere_aufgaben.append(hw)

    # --- DAS NEUE, CLEANE E-MAIL-DESIGN (HTML ZUSAMMENBAU) ---
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
            # Wir formatieren den Text etwas, damit Zeilenumbrüche in HTML funktionieren
            safe_text = hw['text'].replace('\n', '<br>')
            html += f'<p style="margin: 0 0 10px 0; color: #d0d0d0; font-size: 14px;">-> <b style="color:#ffffff;">[{hw["fach"]}]</b> (Fällig am {hw["faellig_datum"]}):<br>{safe_text}</p>'
    else:
        html += '<p style="margin: 0; color: #d0d0d0; font-size: 14px;">-> Heute wurden (bisher) keine neuen Hausaufgaben ins System eingetragen.</p>'
    html += "</div>"

    # Sektion: Weitere fällige Aufgaben
    html += """
                <h3 style="margin: 0 0 20px 0; color: #ffffff; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; border-bottom: 1px solid #444444; padding-bottom: 8px;">
                    📅 Weitere fällige Aufgaben
                </h3>
    """
    if weitere_aufgaben:
        # Gruppieren nach Fälligkeitsdatum
        hw_by_date = {}
        for hw in weitere_aufgaben:
            if hw["faellig_datum"] not in hw_by_date:
                hw_by_date[hw["faellig_datum"]] = []
            hw_by_date[hw["faellig_datum"]].append(hw)
            
        for datum, hws in hw_by_date.items():
            html += f"""
                <div style="margin-bottom: 15px; background-color: #252526; padding: 15px; border-radius: 4px; border-left: 3px solid #4db8ff;">
                    <div style="font-family: 'Courier New', Courier, monospace; color: #4db8ff; margin-bottom: 10px; font-size: 13px; font-weight: bold;">{datum}</div>
            """
            for hw in hws:
                safe_text = hw['text'].replace('\n', '<br>')
                html += f"""
                    <div style="margin-bottom: 12px; display: table;">
                        <span style="background-color: #333333; padding: 3px 8px; border-radius: 3px; font-size: 12px; color: #ffffff; font-weight: bold; margin-right: 10px; display: table-cell; white-space: nowrap;">{hw['fach']}</span>
                        <span style="color: #cccccc; font-size: 14px; display: table-cell; padding-left: 10px;">{safe_text}</span>
                    </div>
                """
            html += "</div>"
    else:
        html += '<p style="color: #888888; font-size: 14px;">-> Keine weiteren Aufgaben offen!</p>'

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
            send_mail(report_html) # Übergibt nun das fertige HTML!
            
        except Exception as e:
            print(f"Fehler bei der Browser-Navigation: {e}")
            browser.close()

if __name__ == "__main__":
    run()
