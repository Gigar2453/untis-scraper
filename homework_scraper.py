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

# 1. Die Mail-Funktion (ohne Anhang!)
def send_mail(report_text):
    msg = EmailMessage()
    heute = datetime.date.today()
    msg['Subject'] = f"📚 Hausaufgaben Übersicht: {heute:%d.%m.%Y}"
    msg['From'] = os.getenv("EMAIL_SENDER")
    msg['To'] = os.getenv("EMAIL_RECEIVER")
    
    msg.set_content(report_text)

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
        return f"Ich konnte den Bereich 'Bald fällig' in den Boxen nicht finden.\n\nHier ist der rohe Text:\n\n{raw_text[:1000]}"
        
    end_idx = raw_text.find("Verpasst", start_idx)
    if end_idx == -1:
        end_idx = raw_text.find("Abgeschlossen", start_idx)
    if end_idx == -1:
        end_idx = len(raw_text)
        
    target_text = raw_text[start_idx + len("Bald fällig"):end_idx]
    
    # --- DIE NEUE KREISSÄGE ---
    # Wir fischen jetzt ZUSÄTZLICH das Aufgabedatum (wie "18.02.2026") aus dem Text heraus!
    pattern = r'([A-ZÄÖÜ]{2,3})\s+[A-ZÄÖÜ]{2,4}\s+(\d{2}\.\d{2}\.202\d)\s+([A-Za-zäöüß]+,\s*\d{2}\.\d{2}\.202\d)\s+Hausaufgabe'
    parts = re.split(pattern, target_text)
    
    hw_list = []
    # Da wir jetzt eine Info mehr (Aufgabedatum) herausziehen, springen wir in 4er-Schritten
    for i in range(1, len(parts), 4):
        if i + 3 < len(parts):
            fach_abk = parts[i]
            aufgabe_datum = parts[i+1] # Das ist neu!
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
        return f"Es stehen aktuell keine Hausaufgaben an.\n\nRoher Text zur Kontrolle:\n\n{target_text}"

    # --- DIE SORTIERUNG (Heute neu vs. Später fällig) ---
    heute_str = datetime.date.today().strftime("%d.%m.%Y")
    
    heute_neu = []
    weitere_aufgaben = []
    
    for hw in hw_list:
        if hw["aufgabe_datum"] == heute_str:
            heute_neu.append(hw)
        else:
            weitere_aufgaben.append(hw)

    # --- DAS NEUE, CLEANE E-MAIL-DESIGN ---
    report = f"Hallo! Hier ist die tagesaktuelle Hausaufgaben-Übersicht für Josefine ({heute_str}):\n\n"
    
    report += "========================================\n"
    report += "🚨 HEUTE NEU AUFBEKOMMEN (Direkt erledigen!) 🚨\n"
    report += "========================================\n"
    if heute_neu:
        for hw in heute_neu:
            report += f"[{hw['fach']}] (Fällig am {hw['faellig_datum']}):\n"
            report += f"-> {hw['text']}\n\n"
    else:
        report += "-> Heute wurden (bisher) keine neuen Hausaufgaben ins System eingetragen.\n\n"
        
    report += "========================================\n"
    report += "📅 WEITERE FÄLLIGE AUFGABEN\n"
    report += "========================================\n"
    if weitere_aufgaben:
        # Die restlichen Aufgaben wieder schön nach Fälligkeit gruppieren
        hw_by_date = {}
        for hw in weitere_aufgaben:
            if hw["faellig_datum"] not in hw_by_date:
                hw_by_date[hw["faellig_datum"]] = []
            hw_by_date[hw["faellig_datum"]].append(hw)
            
        for datum, hws in hw_by_date.items():
            report += f"🗓️ {datum}\n"
            for hw in hws:
                report += f"   - {hw['fach']}: {hw['text']}\n"
            report += "\n"
    else:
        report += "-> Keine weiteren Aufgaben offen!\n"

    return report

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
            
            report_text = extract_homework_text(raw_text)
            
            # (Der Foto-Code wurde hier komplett gelöscht)
            
            browser.close()
            send_mail(report_text) # Wir übergeben nur noch den Text
            
        except Exception as e:
            print(f"Fehler bei der Browser-Navigation: {e}")
            browser.close()

if __name__ == "__main__":
    run()
