def get_train_connections():
    try:
        # Einzigartiger User-Agent, damit die API uns nicht als Spam blockiert
        headers = {'User-Agent': 'untis-scraper-github-Gigar2453'}
        
        # IDs für Agathenburg und Stade abfragen
        url_a = "https://v6.db.transport.rest/locations?query=Agathenburg&results=1"
        req_a = urllib.request.Request(url_a, headers=headers)
        with urllib.request.urlopen(req_a) as response:
            id_a = json.loads(response.read().decode())[0]['id']
            
        url_b = "https://v6.db.transport.rest/locations?query=Stade&results=1"
        req_b = urllib.request.Request(url_b, headers=headers)
        with urllib.request.urlopen(req_b) as response:
            id_b = json.loads(response.read().decode())[0]['id']
            
        # Wir fragen 15 Verbindungen ab
        url_j = f"https://v6.db.transport.rest/journeys?from={id_a}&to={id_b}&results=15"
        req_j = urllib.request.Request(url_j, headers=headers)
        with urllib.request.urlopen(req_j) as response:
            journeys = json.loads(response.read().decode()).get('journeys', [])
            
        train_text = "🚆 ZUGVERBINDUNG (Agathenburg -> Stade):\n"
        
        s_bahnen = []
        for j in journeys:
            legs = j.get('legs', [])
            if not legs:
                continue
            leg = legs[0]
            line_name = leg.get('line', {}).get('name', 'Zug')
            planned_dep = leg.get('plannedDeparture')
            
            if not planned_dep:
                continue
                
            # Uhrzeit aus dem Datumsstempel herausschneiden (z.B. "06:40")
            time_str = planned_dep[11:16]
            
            # Wir ignorieren alle Züge, die vor 06:30 oder nach 07:40 abfahren
            if time_str < "06:30" or time_str > "07:40":
                continue
            
            if "RE" in line_name or "ME" in line_name or "Bus" in line_name:
                continue
            if "S" not in line_name: 
                continue
                
            s_bahnen.append(leg)
            
            # Wir wollen exakt die 3 S-Bahnen in diesem Zeitfenster haben
            if len(s_bahnen) == 3:
                break
        
        if not s_bahnen:
            return train_text + "-> Keine passenden S-Bahn Verbindungen zwischen 06:30 und 07:40 Uhr gefunden.\n\n"
            
        for leg in s_bahnen:
            line_name = leg.get('line', {}).get('name', 'S-Bahn')
            planned_dep = leg.get('plannedDeparture')
            delay_sec = leg.get('departureDelay')
            cancelled = leg.get('cancelled', False)
            
            if planned_dep:
                time_str = planned_dep[11:16]
                
                if cancelled:
                    status_str = " ❌ FÄLLT AUS!"
                elif delay_sec is not None:
                    delay_min = delay_sec // 60
                    if delay_min > 0:
                        status_str = f" (+{delay_min} Min Verspätung)"
                    elif delay_min < 0:
                        status_str = f" ({abs(delay_min)} Min früher)"
                    else:
                        status_str = " (Pünktlich)"
                else:
                    status_str = " (Pünktlich laut Plan)"
                
                train_text += f"- {time_str} Uhr | {line_name}{status_str}\n"
                
        return train_text + "\n"
        
    except Exception as e:
        return f"🚆 ZUGVERBINDUNG: Livedaten konnten nicht abgerufen werden ({e})\n\n"
