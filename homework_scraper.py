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
    msg.set_content("Hallo! Anbei findest du das tagesaktuelle Foto der WebUntis-Hausaufgabenübersicht (inklusive dem Bereich 'Bald fällig').\n\nViele Grüße,\nDein Automatisierungs-Bot")

    # Das gemachte Foto an die E-Mail anhängen
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
        # Einen virtuellen Chrome-Browser im Hintergrund öffnen (Größe auf HD eingestellt, damit das Bild schön groß ist)
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(viewport={'width': 1600, 'height': 1200})
        page = context.new_page()
        
        try:
            # 1. Wir steuern direkt deinen Link an (Untis wird uns automatisch zum Login umlenken)
            ziel_url = "https://gym-athenaeum-stade.webuntis.com/student-homework"
            print("Navigiere zur Login-Seite...")
            page.goto(ziel_url)
            
            # 2. Login-Daten ausfüllen (Playwright ist so intelligent und wartet, bis die Felder auftauchen)
            page.fill('input[type="text"], input#user', os.getenv("UNTIS_USER"))
            page.fill('input[type="password"], input#pass', os.getenv("UNTIS_PASSWORD"))
            page.click('button[type="submit"], button#loginBtn')
            
            # 3. Warten, bis der Login erfolgreich war und wir auf der Hausaufgaben-Seite angekommen sind
            print("Login ausgeführt. Warte auf das Laden der Hausaufgaben-Tabelle...")
            page.wait_for_url("**/student-homework**", timeout=20000)
            
            # Dem Server noch 4 Sekunden Zeit geben, damit die bunten Blöcke ("Bald fällig") auch wirklich geladen sind
            page.wait_for_timeout(4000)
            
            # 4. Klick! Wir machen einen Screenshot der gesamten geladenen Seite
            screenshot_path = "hausaufgaben_screenshot.png"
            page.screenshot(path=screenshot_path, full_page=True)
            print("Screenshot erfolgreich geschossen!")
            
            # 5. Browser sauber schließen und E-Mail absenden
            browser.close()
            send_mail_with_attachment(screenshot_path)
            
        except Exception as e:
            print(f"Fehler bei der Browser-Navigation: {e}")
            browser.close()

if __name__ == "__main__":
    run()
