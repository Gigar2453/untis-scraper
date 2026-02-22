import os
import smtplib
import datetime
from email.message import EmailMessage
from playwright.sync_api import sync_playwright

def send_mail_with_attachment(image_path):
    msg = EmailMessage()
    heute = datetime.date.today()
    msg['Subject'] = f"📚 Hausaufgaben Übersicht: {heute:%d.%m.%Y}"
    msg['From'] = os.getenv("EMAIL_SENDER")
    msg['To'] = os.getenv("EMAIL_RECEIVER")
    msg.set_content("Hallo!\n\nAnbei findest du das tagesaktuelle Foto der WebUntis-Hausaufgabenübersicht (inklusive dem Bereich 'Bald fällig').\n\nViele Grüße,\nDein Automatisierungs-Bot")

    with open(image_path, 'rb') as f:
        img_data = f.read()
        msg.add_attachment(img_data, maintype='image', subtype='png', filename=f'Hausaufgaben_{heute:%d_%m_%Y}.png')

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(os.getenv("EMAIL_SENDER"), os.getenv("EMAIL_PASSWORD"))
            smtp.send_message(msg)
        print("E-Mail mit Screenshot erfolgreich versendet!")
    except Exception as e:
        print(f"Fehler beim E-Mail-Versand: {e}")

def run():
    print("Starte den Geister-Browser...")
    with sync_playwright() as p:
        # Browser in HD-Auflösung starten
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1600, 'height': 1200})
        page = context.new_page()
        
        try:
            # 1. Zur normalen Schul-Startseite navigieren
            print("Navigiere zur Login-Seite...")
            page.goto("https://gym-athenaeum-stade.webuntis.com/WebUntis/?school=gym-athenaeum-stade")
            
            # 2. Login-Daten ausfüllen
            page.fill('input[type="text"], input#user', os.getenv("UNTIS_USER"))
            page.fill('input[type="password"], input#pass', os.getenv("UNTIS_PASSWORD"))
            page.click('button[type="submit"], button#loginBtn')
            
            # 3. Wir warten, bis der Login komplett durch ist (Netzwerk beruhigt sich)
            print("Login ausgeführt. Warte auf das Dashboard...")
            page.wait_for_load_state("networkidle", timeout=20000)
            
            # 4. JETZT lenken wir den Browser explizit zu den Hausaufgaben
            print("Navigiere zur Hausaufgaben-Übersicht...")
            page.goto("https://gym-athenaeum-stade.webuntis.com/student-homework")
            
            # Wir warten wieder, bis die Seite fertig geladen ist
            page.wait_for_load_state("networkidle", timeout=20000)
            
            # Wir geben der Seite noch 5 Extra-Sekunden, um die gelben und roten Boxen sicher zu zeichnen
            page.wait_for_timeout(5000)
            
            # 5. Screenshot schießen
            screenshot_path = "hausaufgaben_screenshot.png"
            page.screenshot(path=screenshot_path, full_page=True)
            print("Screenshot erfolgreich geschossen!")
            
            browser.close()
            send_mail_with_attachment(screenshot_path)
            
        except Exception as e:
            print(f"Fehler bei der Browser-Navigation: {e}")
            browser.close()

if __name__ == "__main__":
    run()
