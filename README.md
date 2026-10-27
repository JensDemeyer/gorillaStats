# GorillaStats

Prive gymprogressietracker voor gebruik op een gsm, gehost op een Raspberry Pi
Zero 2 W en bereikbaar via Tailscale. De gsm-interface blijft het uitgangspunt
voor verdere ontwikkeling; de desktopbrowser dient vooral voor lokale tests.

## Bestaande functionaliteit

- Push/Pull/Legs-routines en eigen oefeningen.
- Sets, gewicht, herhalingen, notities, vorige sessie en PR-detectie.
- Rusttimer, dagoverzicht en progressiegrafieken.
- Cardioregistratie en lichaamsgewicht, inclusief Fitdays CSV-import.
- Afbeeldingen en GIF's uploaden per oefening.
- XP, levels, twaalf achievements, weekdoelen en een activiteitenkalender.

## Tijdens Je Training

- Gewicht en reps zijn optioneel: een set kan meteen worden opgeslagen.
- Met het potlood bij een set kun je gewicht, reps en notities later aanvullen.
	Dit kan tijdens de training of via het trainingslog met datumkeuze, ook op
	een volgende dag. Ontbrekende waarden tellen niet mee als nulmetingen of PR's.
- De rusttimer start alleen wanneer je zelf een tijd kiest.
- Swipe naar links voor de volgende oefening, naar rechts voor de vorige.
	De pijltjes doen hetzelfde. Nog niet opgeslagen invoer blijft tijdens deze
	browsersessie per oefening behouden.
- De vorige sessie staat bij de oefening; bij elke nieuwe set zie je de
	overeenkomstige set van de vorige keer. Tik op een vorige set om die over te nemen.
- Via **Schema aanpassen** kun je Push, Pull, Legs en eigen schema's hernoemen,
	oefeningen aanpassen, toevoegen, verwijderen en herordenen. Oefeningen die
	je uit een schema verwijdert, behouden hun trainingshistoriek.

De bestaande database wordt bij het starten automatisch en transactioneel
bijgewerkt voor optionele setgegevens. Bestaande logs blijven behouden.

De backend gebruikt FastAPI en SQLite zonder ORM. De frontend bestaat uit een
HTML-bestand met CSS en JavaScript, zonder buildstap.

## Beloningen

Beloningen worden uit bestaande logs berekend, ook voor historische data. Er zijn
geen extra tabellen, achtergrondtaken of dependencies nodig.

- Een actieve dag is minimaal 3 sets of 10 minuten cardio, maximaal eenmaal per dag.
- Een doelweek telt 3 actieve dagen. Rustdagen breken de weekstreak niet.
	De huidige week mag nog bezig zijn; een gemiste volledige week breekt de streak.
- Per dag: 10 XP per set voor de eerste 12 sets, 40 XP bij 3 sets,
	30 XP bij 10 minuten cardio en 10 XP voor een weging.
- Elke 500 XP is een level. Achievements geven eenmalige bonus-XP.
- Zwaarder trainen, meer afvallen en extra sets boven de daglimiet geven geen
	extra XP. Verwijderde logs worden ook uit de beloningen verwijderd.
- Geluid staat standaard uit en kan met de luidsprekerknop aan. De voorkeur
	blijft op het apparaat bewaard. Minder beweging volgt de apparaatinstelling.

Gerichte tests zonder extra testdependencies:

```powershell
.\venv\Scripts\python.exe -m unittest test_rewards test_workout -v
```

## Lokaal starten (Windows PowerShell)

Voer dit uit vanuit de projectmap. Python 3.13 is lokaal getest.

```powershell
uv venv venv
.\venv\Scripts\python.exe -m ensurepip --upgrade
.\venv\Scripts\python.exe -m pip install -r requirements.txt
.\venv\Scripts\python.exe -m uvicorn main:app --reload --reload-exclude venv --host 127.0.0.1 --port 8000
```

Zonder `uv` kun je de omgeving aanmaken met `python -m venv venv`.
Bij volgende starts volstaat het laatste commando. Is poort 8000 bezet, gebruik
dan bijvoorbeeld `--port 8001`.

- App: http://127.0.0.1:8000
- API-documentatie: http://127.0.0.1:8000/docs

Test de interface met gsm-emulatie op bijvoorbeeld 360 x 800 en 390 x 844 pixels.
Voor testen op een echte gsm kun je bewust `--host 0.0.0.0` gebruiken en verbinden
via het Tailscale-IP van de ontwikkelcomputer. Daarvoor moeten Tailscale en de
firewall die verbinding toelaten. `127.0.0.1` op de gsm verwijst naar de gsm zelf.

## Raspberry Pi

```sh
python3 -m venv venv
venv/bin/python -m pip install -r requirements.txt
venv/bin/python -m uvicorn main:app --host <tailscale-ip-van-de-pi> --port 8000 --workers 1
```

Vervang de placeholder door het echte Tailscale-IP. Gebruik op de Pi geen
`--reload` en houd het bij een worker om het geheugenverbruik te beperken.
De app heeft geen eigen authenticatie: publiceer hem niet rechtstreeks op het
internet en beperk toegang tot vertrouwde apparaten via Tailscale.

## Data en afhankelijkheden

De database `gym.db` wordt bij de eerste start in de projectmap aangemaakt,
met de standaardroutines. Uploads staan in `static/media/`. Beide zijn uitgesloten
van Git. De locaties zijn onafhankelijk van de werkmap van het serverproces.
Lokale ontwikkeling gebruikt een eigen database, niet die op de Pi.

Maak voor een eenvoudige bestandsbackup eerst de server stil en kopieer daarna
`gym.db` en `static/media/`. Kopieer een actieve SQLite-database niet los van
de WAL-bestanden.

Chart.js en Google Fonts worden momenteel extern geladen. Een werkende
Tailscale-verbinding betekent dus niet dat de interface volledig offline werkt.