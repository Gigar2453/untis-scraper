import os
import smtplib
import datetime
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

def extract_homework_text(raw_text):
    # Alle Tabulatoren durch Zeilenumbrüche ersetzen, damit jede Info sicher in einer eigenen Zeile steht!
    raw_text = raw_text.replace('\t', '\n')
    lines = [line.strip() for line in raw_text.split('\n') if line.strip()]
    
    in_bald_faellig = False
    collecting_text = False
    current_hw = None
    hw_list = []
    
    for line in lines:
        # Fehlertolerante Suche (es reicht, wenn das Wort in der Zeile vorkommt)
        if "Bald fällig" in line:
            in_bald_faellig = True
            continue
            
        if in_bald_faellig and ("Verpasst" in line or "Erledigt" in line or "Vergangene" in line):
            break
            
        if in_bald_faellig:
            # 1. Ist es ein Fachkürzel?
            if line in FACH_NAMEN or (len(line) <= 3 and line.isupper() and line.isalpha()):
                if current_hw:
                    hw_list.append(current_hw)
                fach_name = FACH_NAMEN.get(line, line)
                current_hw = {"fach": fach_name, "datum": "Unbekannt", "text": ""}
                collecting_text = False
                
            elif current_hw:
                # 2. Ist es das Datum? (Fälligkeitsdatum überschreibt automatisch das Aufgabedatum)
                if "202" in line and ("." in line):
                    current_hw["datum"] = line
                    
                # 3. Das Startsignal für den Aufgabentext
                elif "Hausaufgabe" in line:
                    collecting_text = True
                    
                # 4. Den eigentlichen Text einsammeln
                elif collecting_text:
                    current_hw["text"] += line + " "

    if current_hw:
        hw_list.append(current_hw)
        
    if not hw_list:
        return "Es konnten keine Aufgaben unter 'Bald fällig' gefunden werden.\n\nZur Sicherheit ist das Foto der Seite im Anhang."
        
    hw_by_date = {}
    for hw in hw_list:
        datum = hw["datum"]
        if datum not in hw_by_date:
            hw_by_date[datum] = []
        hw_by_date[datum].append(hw)
        
    report = "Hallo! Hier sind die Hausaufgaben für Josefine, die bald fällig sind:\n\n"
    for datum, hws in hw_by_date.items():
        report += f"📅 {datum}\n"
        for hw in hws:
            text = hw['text'].strip() if hw['text'] else "Siehe Screenshot für Details."
            report += f"   - {hw['fach']} Hausaufgabe: {text}\n"
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
