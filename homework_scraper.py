import os
import smtplib
import datetime
from email.message import EmailMessage
from playwright.sync_api import sync_playwright

def send_mail(raw_text, image_path):
    msg = EmailMessage()
    heute = datetime.date.today()
    msg['Subject'] = f"🔍 DEBUG: Roher Text der Hausaufgaben-Seite"
    msg['From'] = os.getenv("EMAIL_SENDER")
    msg['To'] = os.getenv("EMAIL_RECEIVER")
    
    # Wir packen den exakten, ungefilterten Text direkt in die Mail
    mail_body = f"Hier ist der absolut rohe Text, den der Geister-Browser sieht:\n\n"
    mail_body += "="*40 + "\n\n"
    mail_body += raw_text
    mail_body += "\n\n" + "="*40 + "\n\nEnde des Textes."
    
    msg.set_content(mail_body)

    # Das Beweisfoto schicken wir trotzdem mit
    with open(image_path, 'rb') as f:
        img_data = f.read()
        msg.add_attachment(img_data, maintype='image', subtype='png', filename='Debug_Screenshot.png')

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as smtp:
            smtp.login(os.getenv("EMAIL_SENDER"), os.getenv("EMAIL_PASSWORD"))
            smtp.send_message(msg)
        print("Diagnose-E-Mail erfolgreich versendet!")
    except Exception as e:
        print(f"Fehler beim E-Mail-Versand: {e}")

def run():
    print("Starte den Geister-Browser im Diagnose-Modus...")
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
            
            # Ich habe die Wartezeit auf 8 Sekunden hochgesetzt, damit WebUntis wirklich fertig mit Laden ist!
            page.wait_for_timeout(8000)
            
            # Wir saugen den gesamten Text der Webseite auf (ohne Filter)
            print("Lese den rohen Text der Seite aus...")
            raw_text = page.inner_text("body")
            
            screenshot_path = "hausaufgaben_screenshot.png"
            page.screenshot(path=screenshot_path, full_page=True)
            
            browser.close()
            send_mail(raw_text, screenshot_path)
            
        except Exception as e:
            print(f"Fehler bei der Browser-Navigation: {e}")
            browser.close()

if __name__ == "__main__":
    run()
