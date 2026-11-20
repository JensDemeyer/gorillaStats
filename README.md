# GorillaStats

Prive gymprogressietracker voor gebruik op een gsm, gehost op een Raspberry Pi
Zero 2 W en bereikbaar via Tailscale. De gsm-interface blijft het uitgangspunt
voor verdere ontwikkeling; de desktopbrowser dient vooral voor lokale tests.

## Bestaande functionaliteit

- Push/Pull/Legs-routines en eigen oefeningen.
- Sets, gewicht, herhalingen, notities, vorige sessie en PR-detectie.
- Rusttimer, dagoverzicht en progressiegrafieken.
- Cardio in etappes en lichaamsgewicht met BMI en doelgewicht, inclusief Fitdays CSV-import.
- XP, 25 rangen in vijf fases met een eigen evolutieroute, zeventien achievements en weekdoelen.

## Dashboard en evolutieroute

- Bovenaan staat een compacte levelkaart met het beeld van je huidige fase.
	Tik erop voor de **evolutieroute**: een kronkelpad door alle 25 levels met per fase
	een afbeelding (`static/stages/`). Behaalde levels zijn groen, je huidige level pulseert
	en toekomstige fases tonen een silhouet. Tik op een level of fase voor details.
- Daaronder: weekstreak, doelen, tegels met trainingsdagen per maand, gemiddelde per week,
	sets en cardio van deze week, een staafgrafiek van de laatste 12 weken
	(trainingsdagen, sets, volume of cardio) met een heatmap, en een lichaamskaart met BMI.
- Fase 3 en 4 gebruiken hetzelfde beeld (`alfa`); fase 4 krijgt een gouden gloed.
	Voeg je later een apart beeld voor fase 4 toe, pas dan `STAGES` in `static/js/journey.js` aan.
- Alle keuzelijsten openen als donkere jungle-lijst onderaan het scherm
	(`static/js/select.js`); de gewone `<select>` blijft onzichtbaar bestaan.

## Tijdens Je Training

- Kies bovenaan het schema (Push, Pull, Legs, ...) en daarna de oefening.
- Gewicht en reps staan al ingevuld: de laatst gelogde set van vandaag, anders
	dezelfde set van de vorige sessie. Met **−** en **+** pas je ze snel aan; tik op
	de staplengte (±2,5) om te wisselen tussen 0,5, 1,25, 2,5 en 5 kg. Tik je in een
	veld, dan wordt de waarde geselecteerd zodat je meteen kunt overtypen.
- Na elke set krijg je een motivatiekaart (meer gewicht, meer reps, PR, oefening
	klaar met knop naar de volgende) met de verdiende XP. De zinnen staan in
	`static/js/motivation.js`.
- Bij het openen van een oefening zie je een inzichtkaart op basis van je echte
	sessies (geschatte sets tellen niet mee), bijvoorbeeld hoeveel sessies je op hetzelfde gewicht zit.
- Gewicht en reps zijn optioneel: een set kan meteen worden opgeslagen.
- Met het potlood bij een set kun je gewicht, reps en notities later aanvullen.
	Dit kan tijdens de training of via het trainingslog met datumkeuze, ook op
	een volgende dag. Ontbrekende waarden tellen niet mee als nulmetingen of PR's.
- De rusttimer start alleen wanneer je zelf een tijd kiest.
- Swipe naar links voor de volgende oefening, naar rechts voor de vorige.
	De pijltjes doen hetzelfde. Aangepaste, nog niet opgeslagen invoer blijft tijdens deze
	browsersessie per oefening behouden.
- Via **Schema aanpassen** kun je Push, Pull, Legs en eigen schema's hernoemen,
	oefeningen aanpassen, toevoegen, verwijderen en herordenen. Oefeningen die
	je uit een schema verwijdert, behouden hun trainingshistoriek.

## Gewicht, BMI en doel

Op het tabblad **Gewicht** staat je BMI met een kleurenschaal, het gezonde
gewichtsbereik voor jouw lengte (standaard 190 cm) en hoeveel kilo je nog moet
afvallen (of aankomen) om bij BMI 24,9 (of 18,5) uit te komen. Je kunt je lengte en
een doelgewicht instellen; de voortgang loopt van het gewicht op het moment dat je
het doel instelde naar het doel. De grafiek toont het doel en de gezonde bovengrens,
en je kunt ook de berekende BMI per meting kiezen.

## Cardio in etappes

Voeg per cardiosessie meerdere etappes toe, bijvoorbeeld 15 minuten op 5,5 km/u met
15% helling gevolgd door 5 minuten op 5 km/u zonder helling. De kcal worden live berekend
met je gewicht op die datum (de laatste weging op of voor de datum):

- **Loopband:** de ACSM-vergelijkingen. Wandelen (< 7 km/u): VO2 = 0,1·v + 1,8·v·helling + 3,5.
	Hardlopen (≥ 7 km/u): VO2 = 0,2·v + 0,9·v·helling + 3,5, met v in m/min en VO2 in
	ml/kg/min. Daarna kcal = VO2 · gewicht · minuten · 5 / 1000.
- **Fietsen:** MET-waarde uit de snelheid (Compendium of Physical Activities).
- **Overige types:** MET-waarde uit het gekozen niveau (licht, matig, zwaar).

Het resultaat is een schatting van het totale verbruik (inclusief rust). Lengte speelt
geen rol in deze formules; die gebruik je voor BMI en doelen. Je kunt het getal altijd
zelf aanpassen. Oude cardiologs zonder etappes blijven gewoon bestaan.

De bestaande database wordt bij het starten automatisch en transactioneel
bijgewerkt. Nieuw zijn een tabel `settings` (lengte, doelgewicht) en een kolom
`segments_json` bij cardio. Bestaande logs blijven behouden.

De backend gebruikt FastAPI en SQLite zonder ORM. De frontend bestaat uit een
HTML-bestand met CSS en JavaScript (`static/css`, `static/js`), zonder buildstap.

## Fitdays CSV

De knop **CSV importeren** opent de bestandskiezer en uploadt het gekozen
bestand direct. De import ondersteunt puntkomma's, komma's en tabs als
scheidingsteken, decimale komma's, Fitdays-datums zoals `17:36 Jan.27,2025`
en eenheden zoals `kg`, `%` en `kcal`. `- -` blijft een ontbrekende waarde.
Fouten en overgeslagen rijen worden bij de knop getoond.

Alle numerieke meetkolommen blijven bewaard en zijn via **Meetwaarde** als
grafiek te kiezen. Een ontbrekende meting wordt niet als nul getekend.
Er blijft een meting per datum: bij meerdere rijen op dezelfde dag wordt de
laatste CSV-rij gebruikt. Dezelfde dag opnieuw importeren werkt de meting bij,
zonder een dubbele meetdag. Deze import gebruikt alleen de Python-standaardbibliotheek.

## Een Training Achteraf Registreren

Kies in het trainingslog **Training toevoegen**, selecteer de trainingsdatum
en vink de oefeningen aan die je hebt gedaan. Je kunt op schema filteren of
een oefening zoeken, ook een oefening die inmiddels uit je schema is verwijderd.
Het aantal sets, gewicht en de optionele reps blijven aanpasbaar.

Het voorgestelde gewicht is per oefening het gemiddelde van de laatste drie
eerdere sessiegemiddelden, strikt voor de gekozen datum. Elke sessie telt even
zwaar mee, ongeacht het aantal sets. Zijn er maar een of twee sessies met
bekende gewichten, dan worden die gebruikt; zonder historie blijft het gewicht
leeg. Reps worden niet verzonnen.

Automatische gewichten worden als **geschat** opgeslagen. Ze tellen mee voor je
trainingsactiviteit, maar leveren geen PR op en worden niet opnieuw gebruikt
om volgende schattingen te berekenen. Een handmatig ingevoerd gewicht is niet
automatisch een schatting. Via het potlood kun je eerdere sets corrigeren,
inclusief datum, oefening en de aanduiding geschat.

## Beloningen

Beloningen worden uit bestaande logs berekend, ook voor historische data. Er zijn
geen extra tabellen, achtergrondtaken of dependencies nodig.

- Een actieve dag is minimaal 3 sets of 10 minuten cardio, maximaal eenmaal per dag.
- Een doelweek telt 3 actieve dagen. Rustdagen breken de weekstreak niet.
	De huidige week mag nog bezig zijn; een gemiste volledige week breekt de streak.
- Per dag: 10 XP per set voor de eerste 12 sets, 40 XP bij 3 sets,
	30 XP bij 10 minuten cardio en 10 XP voor een weging.
- Elke 500 XP is een level, van Baby Gorillatje tot Ultra Alfa Gorilla op
	level 25 (12.000 XP). Daarna blijft je totale XP oplopen, maar je rang is maximaal.
- **Jouw evolutie** toont alle 25 rangen met hun beschrijvingen in een scrollbare
	tijdlijn. De fasekeuze springt naar een fase; de doelknop brengt je terug naar
	je huidige level. Toekomstige rangen blijven zichtbaar met de benodigde XP.
- De vijf fases zijn De Wieg van het Regenwoud (1-5), De Puber Apen (6-10),
	De Zilverruggelings (11-15), Opperbeesten (16-20) en Primal Mythologie (21-25).
- Elke fase heeft een achievement bij het bereiken van het laatste level:
	5, 10, 15, 20 en 25. Deze fasebadges geven geen extra XP, zodat er geen
	zelfversterkende levelbeloningen ontstaan. De twaalf bestaande achievements
	behouden hun bonus-XP. Bestaande logs en XP worden automatisch meegenomen.
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

## Eenmalige import van `dates.json` (Pi)

`dates.json` bevat gymbezoeken (club, datum `DD-MM-YYYY`, tijd). `import_dates.py`
bewaart club en starttijd per dag in de nieuwe tabel `workout_sessions` en vult
dagen zonder logs op met geschatte sessies. Alleen de Python-standaardbibliotheek
is nodig. Het script gebruikt jouw eigen echte (niet-geschatte) logs als referentie.

- Dagen die al logs hebben blijven onaangeroerd.
- De routine volgt Push → Pull → Legs na de vorige gelogde dag, en vermijdt
	dezelfde routine als de eerstvolgende echte dag.
- Per routine komen enkel oefeningen die in minstens de helft van je echte
	sessies zitten, met je gebruikelijke aantal sets.
- Gewicht wordt tussen je echte sessies geïnterpoleerd en op jouw gebruikelijke
	gewichtsstap afgerond. Voor je eerste echte sessie ligt het hooguit één stap per
	14 dagen (max. 10%) lager; erna blijft het op je laatste gemiddelde. Reps zijn
	het gemiddelde van de drie dichtstbijzijnde echte sessies.
- Alles wordt als **geschat** opgeslagen met notitie `import:dates.json | club tijd`:
	het telt voor XP, streak en kalender, maar geeft geen PR's en dient nooit als
	referentie. Opnieuw uitvoeren is veilig; alleen nieuwe datums worden ingevuld.

Op de Pi (pas de servicenaam aan, zoek hem met `systemctl list-units | grep -i gorilla`):

```sh
# lokaal: committen en pushen (gym.db staat in .gitignore en blijft op de Pi onaangeroerd)
cd <map-van-de-repo>
sudo systemctl stop <service>
git pull
venv/bin/python import_dates.py --verbose     # dry-run: toont wat er zou gebeuren
venv/bin/python import_dates.py --apply       # schrijft, met backup gym.db.pre-import-<tijd>
sudo systemctl start <service>
```

Terugdraaien kan met `venv/bin/python import_dates.py --rollback --apply`
(verwijdert alleen geïmporteerde sets en sessies), of door de backup terug te zetten.
Tests: `.\venv\Scripts\python.exe -m unittest test_import_dates -v`.

## Installeren op Android (PWA)

De app is een installeerbare PWA: na installatie opent hij fullscreen vanaf het
startscherm, zonder adresbalk. Chart.js en de lettertypes staan lokaal in
`static/vendor/`, de app-shell wordt door de service worker (`static/sw.js`)
gecachet. API-aanroepen gaan altijd rechtstreeks naar de Pi en worden nooit
gecachet. `index.html`, `static/js` en `static/css` worden eerst van de Pi gehaald, dus
een `git pull` volstaat. Wijzig je de vendor-bestanden, iconen of fase-afbeeldingen,
verhoog dan `CACHE` in `sw.js`.

Chrome installeert alleen via HTTPS (of `localhost`), dus het Tailscale-IP over
`http` volstaat niet. Tailscale kan dit gratis regelen:

1. Zet in de Tailscale admin console **MagicDNS** en **HTTPS Certificates** aan.
2. Laat uvicorn op de Pi enkel lokaal luisteren (`--host 127.0.0.1 --port 8000`,
	pas dit aan in de systemd-service en herstart die).
3. Publiceer hem binnen je tailnet (geen Funnel, de app heeft geen authenticatie):
	`sudo tailscale serve --bg --https=443 http://127.0.0.1:8000`.
	Controleer de syntax met `tailscale serve --help`, die verschilt per versie.
4. Open `https://<pi-naam>.<tailnet>.ts.net` in Chrome op je gsm en kies
	**App installeren**.

Zodat je Tailscale nooit meer handmatig hoeft aan te zetten: Android
Instellingen > Netwerk > VPN > Tailscale (tandwiel) > **Altijd-aan VPN**.
Sluit Tailscale ook uit van batterijoptimalisatie.

## Android-app (APK)

De map `android/` bevat een kleine native app (Kotlin, geen extra frameworks) die
alleen de WebView rond de Pi-app vormt. Bij het openen zet ze Tailscale aan met de
intent `com.tailscale.ipn.CONNECT_VPN`: eerst via de `AutomationActivity` (nieuwere
Tailscale-versies), anders via de `IPNReceiver`-broadcast (oudere versies). Daarna wacht
ze tot de Pi bereikbaar is (tot 30 seconden, de start wordt hooguit twee keer herhaald) en
laadt de app. Tijdens het opstarten toont de app een jungle-scherm met je logo en drie
stappen (Tailscale, je Pi, app laden) met live status, een voortgangsbalk en een teller.
Lukt het niet, dan staat de mislukte stap in het rood met **Opnieuw proberen** en
**Tailscale openen**. Sluit je de app met
de terugknop, dan zet ze Tailscale weer uit, behalve als er al een VPN actief was
voor je de app opende. Bestanden kiezen (CSV, afbeeldingen) werkt zoals in de browser.
HTTPS is voor de app niet nodig; `http://<tailscale-ip>:8000` volstaat omdat het
verkeer toch door de Tailscale-tunnel loopt.

De app-code komt altijd van de Pi: na `git pull` op de Pi heb je geen nieuwe APK nodig.
Een nieuwe APK is alleen nodig als de app zelf verandert (adres, icoon, naam, code in `android/`).

Eenmalig instellen en bouwen op de pc (Android Studio is geïnstalleerd):

1. Kopieer `android/gorillastats.properties.example` naar `android/gorillastats.properties`
	en vul bij `url` het Tailscale-IP van de Pi in (te zien in de Tailscale-app of met
	`tailscale ip -4` op de Pi). Uvicorn moet op dat IP luisteren, zoals bij **Raspberry Pi**.
2. Open de map `android/` in Android Studio en laat Gradle synchroniseren, of bouw in PowerShell:
	```powershell
	cd android
	.\gradlew.bat assembleRelease
	```
3. De APK staat in `android\app\build\outputs\apk\release\app-release.apk`.
	Zet hem op je gsm (kabel, `adb install -r app-release.apk` of via een bestandsoverdracht)
	en sta installeren uit onbekende bronnen toe voor die app.
4. Open Tailscale op je gsm één keer en laat de VPN-toestemming goed: daarna kan GorillaStats
	de VPN zonder tussenkomst starten.

Bewaar `%USERPROFILE%\.android\debug.keystore`: de APK wordt ermee ondertekend en
alleen met dezelfde sleutel kun je later bijwerken zonder de app te verwijderen.
Een ander gsm-adres of Tailscale-IP vraagt enkel een nieuwe build. Zet `disconnectOnExit=false`
in `gorillastats.properties` als Tailscale na het sluiten aan moet blijven.

Op OnePlus kan agressief batterijbeheer de VPN-start of de app afsluiten; zet GorillaStats
en Tailscale bij de batterij-instellingen op **Onbeperkt** als dat gebeurt.

## Data en afhankelijkheden

De database `gym.db` wordt bij de eerste start in de projectmap aangemaakt,
met de standaardroutines. Die is uitgesloten van Git. De locatie is onafhankelijk
van de werkmap van het serverproces.
Lokale ontwikkeling gebruikt een eigen database, niet die op de Pi.

Maak voor een eenvoudige bestandsbackup eerst de server stil en kopieer daarna
`gym.db`. Kopieer een actieve SQLite-database niet los van
de WAL-bestanden.

Chart.js en de lettertypes worden lokaal geserveerd; de interface heeft geen
externe verbindingen meer nodig.