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
    # 1. Startpunkt suchen
    start_idx = raw_text.find("Bald fällig")
    if start_idx == -1:
        return f"Ich konnte den Bereich 'Bald fällig' in den Boxen nicht finden.\n\nHier ist zur Sicherheit das, was ich gesehen habe:\n\n{raw_text[:1000]}\n\n(Und das Foto ist im Anhang!)"
        
    end_idx = raw_text.find("Verpasst", start_idx)
    if end_idx == -1:
        end_idx = raw_text.find("Abgeschlossen", start_idx)
    if end_idx == -1:
        end_idx = len(raw_text)
        
    target_text = raw_text[start_idx + len("Bald fällig"):end_idx]
    
    # 2. Die magische Kreissäge aus unserem vorherigen Versuch
    pattern = r'([A-ZÄÖÜ]{2,3})[A-ZÄÖÜ]{2,4}\d{2}\.\d{2}\.202\d([A-Za-zäöüß]+,\s*\d{2}\.\d{2}\.202\d)Hausaufgabe'
    parts = re.split(pattern, target_text)
    
    hw_list = []
    for i in range(1, len(parts), 3):
        if i + 2 < len(parts):
            fach_abk = parts[i]
            datum = parts[i+1]
            text = parts[i+2].strip()
            
            fach = FACH_NAMEN.get(fach_abk, fach_abk)
            hw_list.append({"fach": fach, "datum": datum, "text": text})

    if not hw_list:
        return f"Ich habe den Block gefunden, konnte ihn aber nicht zerschneiden.\n\nHier ist der rohe Text:\n\n{target_text}\n\n(Foto im Anhang!)"

    # 3. Das schöne Design
    hw_by_date = {}
    for hw in hw_list:
        if hw["datum"] not in hw_by_date:
            hw_by_date[hw["datum"]] = []
        hw_by_date[hw["datum"]].append(hw)

    report = "Hallo! Hier sind die Hausaufgaben für Josefine, die bald fällig sind:\n\n"
    for datum, hws in hw_by_date.items():
        report += f"📅 {datum}\n"
        for hw in hws:
            report += f"   - {hw['fach']} Hausaufgabe: {hw['text']}\n"
        report += "\n"

    report += "\nZur Sicherheit findest du den Original-Screenshot weiterhin im Anhang."
    return report

def run():
    print("Starte den Geister-Browser...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1600, 'height': 1200})
        page = context.new_page()
