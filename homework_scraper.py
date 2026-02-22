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
    "LA": "Latein", "SN": "Spanisch"
}

def send_mail(report_text, image_path):
    msg = EmailMessage()
    heute = datetime.date.today()
    msg['Subject'] = f"📚 Hausaufgaben Übersicht: {heute:%d.%m.%Y}"
    msg['From'] = os.getenv("EMAIL_SENDER")
    msg['To'] = os.getenv("EMAIL_RECEIVER")
    
    msg.set_content(report_text)

    with open(image_path, 'rb') as f:
        img_data = f.read()
        msg.add_attachment(img_data, maintype='image', subtype='png', filename=f'Hausaufgaben_{heute:%d_%m_%Y}.png')

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(os.getenv("EMAIL_SENDER"), os.getenv("EMAIL_PASSWORD"))
            smtp.send_message(msg)
        print("E-Mail erfolgreich versendet!")
    except Exception as e:
        print(f"Fehler beim E-Mail-Versand: {e}")

# --- NEU: DER REGEX-SPÜRHUND ---
def extract_homework_text(raw_text):
    # 1. Wir schneiden uns nur den Block "Bald fällig" heraus
    start_idx = raw_text.find("Bald fällig")
    if start_idx == -1:
        return "Konnte den Bereich 'Bald fällig' auf der Seite nicht finden.\n\nZur Sicherheit ist das Foto im Anhang."

    end_idx = raw_text.find("Verpasst", start_idx)
    if end_idx == -1:
        end_idx = raw_text.find("Erledigt", start_idx)
    if end_idx == -1:
        end_idx = len(raw_text)

    target_text = raw_text[start_idx:end_idx]

    # 2. Wir suchen gezielt nach Daten im Format "Montag, 23.02.2026"
    date_pattern = r'(Montag|Dienstag|Mittwoch|Donnerstag|Freitag|Samstag|Sonntag),\s*\d{1,2}\.\d{1,2}\.202\d'
    date_matches = list(re.finditer(date_pattern, target_text))

    if not date_matches:
        return "Es konnten keine Aufgaben unter 'Bald fällig' gefunden werden (Kein Fälligkeitsdatum erkannt).\n\nZur Sicherheit ist das Foto im Anhang."

    hw_list = []
    
    # 3. Wir gehen jedes gefundene Datum durch
    for i, match in enumerate(date_matches):
        datum = match.group(0)

        # Der Hausaufgaben-Text steht zwischen diesem Datum und dem NÄCHSTEN Datum
        start_pos = match.end()
        end_pos = date_matches[i+1].start() if i + 1 < len(date_matches) else len(target_text)
        chunk = target_text[start_pos:end_pos]

        # Wir löschen das Wort "Hausaufgabe", falls es am Anfang steht
        chunk = re.sub(r'^\s*Hausaufgabe', '', chunk, flags=re.IGNORECASE).strip()

        # Welches Fach ist es? Wir suchen im Text VOR dem Datum nach Fach-Kürzeln (EK, DE etc.)
        prev_pos = date_matches[i-1].end() if i > 0 else 0
        pre_text = target_text[prev_pos:match.start()]

        fach = "Unbekannt"
        # Spürhund sucht nach Wörtern mit 2-3 Großbuchstaben im vorherigen Abschnitt
        words = re.findall(r'\b[A-ZÄÖÜ]{2,3}\b', pre_text)
        for w in reversed(words): # Wir nehmen das Fach, das am nächsten am Datum steht
            if w in FACH_NAMEN:
                fach = FACH_NAMEN[w]
                break

        # Aufräumen: Wir löschen kleine Reste (z.B. "DE SMH 18.02.2026") am Ende des Textes
        chunk = re.sub(r'\b[A-ZÄÖÜ]{2,3}\s+(?:[A-ZÄÖÜ]{2,3}\s+)?\d{1,2}\.\d{1,2}\.202\d\s*$', '', chunk).strip()

        # Zeilenumbrüche glätten, damit es schön lesbar ist
        chunk = " ".join(chunk.split())
        
        if not chunk:
            chunk = "Siehe Screenshot für Details."

        hw_list.append({
            "fach": fach,
            "datum": datum,
            "text": chunk
        })

    # 4. Text schön formatieren
    hw_by_date = {}
    for hw in hw_list:
        if hw["datum"] not in hw_by_date:
            hw_by_date[hw["datum"]] = []
        hw_by_date[hw["datum"]].append(hw)

    report = "Hallo! Hier sind die Hausaufgaben für Josefine, die bald fällig sind:\n\n"
    for datum, hws in hw_by_date.items():
        report += f"📅 {datum}\n"
        for hw in hws:
            report += f"   - {hw['fach']}: {hw['text']}\n"
        report += "\n"

    report += "\nZur Sicherheit findest du den Original-Screenshot weiterhin im Anhang."
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
            
            # --- Text absaugen und durch den Regex-Filter jagen ---
            print("Lese den Text der Seite aus...")
            raw_text = page.inner_text("body")
            report_text = extract_homework_text(raw_text)
            
            screenshot_path = "hausaufgaben_screenshot.png"
            page.screenshot(path=screenshot_path, full_page=True)
            
            browser.close()
            send_mail(report_text, screenshot_path)
            
        except Exception as e:
            print(f"Fehler bei der Browser-Navigation: {e}")
            browser.close()

if __name__ == "__main__":
    run()
