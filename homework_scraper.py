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
    
    target_text = target_text.replace("Noch nicht abgeschlossen", "")
    
    pattern = r'([A-ZÄÖÜ]{2,3})\s*[A-ZÄÖÜ]{2,4}\s*(\d{2}\.\d{2}\.202\d)\s*([A-Za-zäöüß]+,\s*\d{2}\.\d{2}\.202\d)\s*Hausaufgabe'
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
    tage_namen = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]
    
    if not hw_list:
        return f'<div style="background:#121212; color:#fff; padding:20px;"><h3>🎉 Keine einzige Aufgabe im System. Zurücklehnen!</h3></div>'

    # =========================================================================
    # NEUE ZEIT-LOGIK (DIE INTELLIGENTEN FILTER)
    # =========================================================================
    
    # 1. Filter für "Diese Woche aufgegeben" (Immer Montag bis Freitag der aktuellen Woche)
    montag_assigned = heute - datetime.timedelta(days=heute.weekday())
    freitag_assigned = montag_assigned + datetime.timedelta(days=4)

    # 2. Filter für "Noch Fällig" (Immer ab morgen!)
    start_due = heute + datetime.timedelta(days=1)
    
    if heute.weekday() <= 3: 
        # MONTAG bis DONNERSTAG: Wir zeigen nur Fälligkeiten bis diesen Freitag!
        end_due = montag_assigned + datetime.timedelta(days=4)
    else:
        # FREITAG bis SONNTAG: Wir zeigen Fälligkeiten der kompletten nächsten Woche!
        montag_next = heute + datetime.timedelta(days=(7 - heute.weekday()))
        end_due = montag_next + datetime.timedelta(days=4)

    # Dictionary für die Fälligkeiten aufbauen (leere Tage vorbereiten)
    hw_by_date = {}
    current_d = start_due
    while current_d <= end_due:
        if current_d.weekday() <= 4: # Wir klammern das Wochenende in der Anzeige aus
            datum_str = current_d.strftime("%d.%m.%Y")
            tag_name = tage_namen[current_d.weekday()]
            hw_by_date[datum_str] = {"titel": f"{tag_name}, {datum_str}", "aufgaben": [], "date_obj": current_d}
        current_d += datetime.timedelta(days=1)

    # Aufgaben in unsere cleveren Filter einsortieren
    diese_woche_aufgegeben = []
    
    for hw in hw_list:
        try:
            a_date = datetime.datetime.strptime(hw["aufgabe_datum"], "%d.%m.%Y").date()
        except:
            a_date = datetime.date.min
            
        f_datum_nur = hw["faellig_datum"].split(",")[-1].strip()
        try:
            f_date = datetime.datetime.strptime(f_datum_nur, "%d.%m.%Y").date()
        except:
            f_date = datetime.date.max

        # Logik A: Wurde es DIESE WOCHE aufgegeben?
        if montag_assigned <= a_date <= freitag_assigned:
            diese_woche_aufgegeben.append(hw)

        # Logik B: Ist es in unserem Zielfenster (ab morgen bis Ende der Anzeige-Woche)?
        if start_due <= f_date <= end_due:
            if f_datum_nur in hw_by_date:
                hw_by_date[f_datum_nur]["aufgaben"].append(hw)

    diese_woche_aufgegeben = sorted(diese_woche_aufgegeben, key=lambda x: datetime.datetime.strptime(x["aufgabe_datum"], "%d.%m.%Y").date())
    sorted_dates = sorted(hw_by_date.keys(), key=lambda k: hw_by_date[k]["date_obj"])

    # =========================================================================
    # HTML ZUSAMMENBAU
    # =========================================================================
    
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

    # Sektion: Diese Woche aufgegeben (Neues, schickeres Design)
    html += """
                <div style="margin-bottom: 30px; background-color: #2a1b1b; border-left: 4px solid #ff5252; padding: 15px; border-radius: 0 4px 4px 0;">
                    <h3 style="margin: 0 0 15px 0; color: #ff5252; font-size: 14px; text-transform: uppercase; letter-spacing: 1px;">📝 In dieser Woche aufgegeben</h3>
    """
    if diese_woche_aufgegeben:
        for i, hw in enumerate(diese_woche_aufgegeben):
            safe_text = hw['text'].replace('\n', '<br>')
            
            # Wochentag für das Aufgabedatum ermitteln
            try:
                a_date_obj = datetime.datetime.strptime(hw["aufgabe_datum"], "%d.%m.%Y").date()
                wochentag = tage_namen[a_date_obj.weekday()]
                anzeige_datum = f"{wochentag}, {hw['aufgabe_datum']}"
            except:
                anzeige_datum = hw['aufgabe_datum']
                
            # Eine feine Trennlinie unter jeden Eintrag, außer den letzten
            border_style = "border-bottom: 1px solid rgba(255, 82, 82, 0.2); margin-bottom: 12px; padding-bottom: 12px;" if i < len(diese_woche_aufgegeben) - 1 else "margin-bottom: 0;"
            
            html += f"""
                <div style="{border_style}">
                    <div style="margin-bottom: 6px;">
                        <span style="color: #ff8a80; font-weight: bold; font-size: 13px;">📅 {anzeige_datum}</span>
                        <span style="color: #aaaaaa; font-size: 12px; margin-left: 8px; font-style: italic;">(Fällig: {hw['faellig_datum']})</span>
                    </div>
                    <div style="display: table;">
                        <span style="background-color: #ff5252; padding: 2px 6px; border-radius: 3px; font-size: 11px; color: #1e1e1e; font-weight: bold; margin-right: 10px; display: table-cell; white-space: nowrap;">{hw['fach']}</span>
                        <span style="color: #e0e0e0; font-size: 14px; display: table-cell; padding-top: 1px;">{safe_text}</span>
                    </div>
                </div>
            """
    else:
        html += '<p style="margin: 0; color: #d0d0d0; font-size: 14px;">-> Bisher wurden diese Woche keine Aufgaben ins System eingetragen.</p>'
    html += "</div>"

    # Sektion: Weitere fällige Aufgaben
    html += """
                <h3 style="margin: 0 0 20px 0; color: #ffffff; font-size: 14px; text-transform: uppercase; letter-spacing: 1px; border-bottom: 1px solid #444444; padding-bottom: 8px;">
                    📅 Noch fällig (Ab Morgen)
                </h3>
    """
    
    if not sorted_dates:
         html += """
            <div style="margin-bottom: 15px; background-color: #252526; padding: 15px; border-radius: 4px; border-left: 3px solid #4db8ff; text-align: center;">
                <span style="color: #4db8ff; font-size: 15px; font-weight: bold;">Keine ausstehenden Aufgaben mehr im Planungszeitraum! 🎉</span>
            </div>
         """
    else:
        for datum_str in sorted_dates:
            tages_daten = hw_by_date[datum_str]
            titel = tages_daten["titel"]
            aufgaben = tages_daten["aufgaben"]
            
            html += f"""
                <div style="margin-bottom: 15px; background-color: #252526; padding: 15px; border-radius: 4px; border-left: 3px solid #4db8ff;">
                    <div style="font-family: 'Courier New', Courier, monospace; color: #4db8ff; margin-bottom: 10px; font-size: 13px; font-weight: bold;">{titel}</div>
            """
            
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

    html += """
            </div>
        </div>
    </div>
    """
    return html


def run():
    print("Starte den Geister-Browser auf GitHub Actions...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True) 
        
        context = browser.new_context(
            viewport={'width': 1600, 'height': 1200},
            locale='de-DE',
            timezone_id='Europe/Berlin'
        )
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
            page.wait_for_timeout(3000) 
            
            print("Versuche den Zeitraum auf '2025/2026' umzustellen...")
            try:
                target_frame = None
                
                for f in page.frames:
                    if f.locator('.Select-control').count() > 0:
                        target_frame = f
                        break
                
                if target_frame:
                    print("Iframe gefunden! Öffne das Dropdown-Menü...")
                    target_frame.locator('.Select-control').first.click()
                    page.wait_for_timeout(1000) 
                    print("Klicke auf 2025/2026...")
                    target_frame.get_by_text("2025/2026", exact=True).first.click()
                    print("Zeitraum erfolgreich umgestellt! Lade neue Daten...")
                    page.wait_for_load_state("networkidle", timeout=15000)
                    page.wait_for_timeout(3000)
                else:
                    print("Fehler: Konnte das WebUntis-Iframe nicht finden!")
            except Exception as drop_e:
                print(f"Achtung: Dropdown-Klick fehlgeschlagen. Fehler: {drop_e}")

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
