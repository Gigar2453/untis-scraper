def get_train_connections():
    plain_text = "🚆 ZUGVERBINDUNG (Agathenburg -> Stade):\n"
    html_text = ""
    
    try:
        headers = {'User-Agent': 'untis-scraper-github-Gigar2453'}
        
        id_a = "8000424" # Agathenburg
        id_b = "8000096" # Stade
        
        tz = ZoneInfo("Europe/Berlin")
        heute = datetime.datetime.now(tz)
        start_zeit = heute.replace(hour=6, minute=20, second=0, microsecond=0)
        start_zeit_str = urllib.parse.quote(start_zeit.isoformat())
        
        # URL entschlackt: Wir erlauben alles (auch SEV-Busse oder REs)!
        url_j = f"https://v6.db.transport.rest/journeys?from={id_a}&to={id_b}&results=10&departure={start_zeit_str}"
        
        req_j = urllib.request.Request(url_j, headers=headers)
        
        with urllib.request.urlopen(req_j, timeout=15) as response:
            journeys = json.loads(response.read().decode()).get('journeys', [])
            
        verbindungen = []
        for j in journeys:
            legs = j.get('legs', [])
            if not legs:
                continue
            leg = legs[0]
            
            # Name auslesen (z.B. "S 3" oder "Bus SEV")
            line_name = leg.get('line', {}).get('name')
            if not line_name:
                line_name = leg.get('line', {}).get('productName', 'Zug')
                
            planned_dep = leg.get('plannedDeparture')
            
            if not planned_dep:
                continue
                
            time_str = planned_dep[11:16]
            
            # Filter: Nur Abfahrten zwischen 06:20 und 07:50 Uhr
            if time_str < "06:20" or time_str > "07:50":
                continue
                
            verbindungen.append(leg)
            if len(verbindungen) == 3: # Wir zeigen maximal 3 Verbindungen
                break
        
        if not verbindungen:
            plain_text += "-> Keine Verbindungen im Zeitraum gefunden.\n\n"
            html_text = "<div class='item' style='color: #888;'>Keine Abfahrten zwischen 06:20 und 07:50 Uhr gefunden.</div>"
            return plain_text, html_text
            
        for leg in verbindungen:
            line_name = leg.get('line', {}).get('name', 'Zug')
            planned_dep = leg.get('plannedDeparture')
            delay_sec = leg.get('departureDelay')
            cancelled = leg.get('cancelled', False)
            
            if planned_dep:
                time_str = planned_dep[11:16]
                
                if cancelled:
                    status_str = "❌ FÄLLT AUS!"
                    css_class = "text-bad"
                elif delay_sec is not None:
                    delay_min = delay_sec // 60
                    if delay_min > 0:
                        status_str = f"+{delay_min} Min Verspätung"
                        css_class = "text-bad"
                    elif delay_min < 0:
                        status_str = f"{abs(delay_min)} Min früher"
                        css_class = "text-ok"
                    else:
                        status_str = "Pünktlich"
                        css_class = "text-ok"
                else:
                    status_str = "Pünktlich (Plan)"
                    css_class = "text-ok"
                
                plain_text += f"- {time_str} Uhr | {line_name} ({status_str})\n"
                
                # HTML Block für EINE Bahn
                html_text += f"""
                <div class='item'>
                    <span style='color: #fff; font-size: 15px;'>{time_str} Uhr</span> | 
                    <span class='badge'>{line_name}</span> 
                    <span class='{css_class}'>{status_str}</span>
                </div>
                """
                
        return plain_text + "\n", html_text
        
    except Exception as e:
        return f"Fehler Bahn: {e}\n\n", f"<div class='item text-bad'>API-Fehler: {str(e)}</div>"
