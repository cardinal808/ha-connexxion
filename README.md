# Connexxion Groepsvervoer voor Home Assistant

[![Open in de Marketplace](https://img.shields.io/badge/Home%20Assistant-Marketplace-41BDF5.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=cardinal808&repository=ha-connexxion&category=integration)
[![Validate](https://github.com/cardinal808/ha-connexxion/actions/workflows/validate.yml/badge.svg)](https://github.com/cardinal808/ha-connexxion/actions/workflows/validate.yml)

Custom integration voor het ouderportaal van **Connexxion Groepsvervoer** (leerlingen- en BSO-vervoer). Je ziet de geplande ritten, live ophaal- en aankomsttijden, de chauffeur en tijdens de rit de positie van het voertuig op de kaart. Instellen gaat via de gebruikersinterface.

*English: Home Assistant integration for the Dutch Connexxion Groepsvervoer (Transdev) parent portal: planned rides, live pickup/arrival times and the vehicle's position during a ride. Install it from Settings → Marketplace.*

> ⚠️ Onofficieel. Niet gelieerd aan Connexxion of Transdev. De integratie gebruikt dezelfde API als het ouderportaal; als die verandert, kan de integratie stoppen met werken.

## Installatie

### Via de Marketplace (Home Assistant 2026.11 en nieuwer, aanbevolen)

**[Open deze integratie in je Marketplace](https://my.home-assistant.io/redirect/marketplace_repository/?owner=cardinal808&repository=ha-connexxion&category=integration)**

Klik op de link hierboven, of:

1. Ga naar **Instellingen → Marketplace** en zoek *Connexxion Groepsvervoer*.
2. Staat hij er (nog) niet tussen? Voeg via het menu (⋮) de repository `https://github.com/cardinal808/ha-connexxion` toe als **Integratie**.
3. Installeer en herstart Home Assistant via de melding die de Marketplace geeft.

### Via HACS (Home Assistant ouder dan 2026.11)

Voeg in HACS `https://github.com/cardinal808/ha-connexxion` toe als aangepaste repository van het type **Integratie**, download en herstart.

## Instellen

**Instellingen → Apparaten en diensten → Integratie toevoegen → Connexxion Groepsvervoer**, en log in met het e-mailadres en wachtwoord van het ouderportaal.

Zijn er meerdere kinderen aan je account gekoppeld, dan kies je er één. Voeg de integratie daarna nog een keer toe voor elk volgend kind.

Werkt het inloggen later niet meer, dan vraagt Home Assistant vanzelf om opnieuw in te loggen.

## Entiteiten

Per kind maakt de integratie een apparaat *Connexxion &lt;voornaam&gt;* met:

| Entiteit (Engels / Nederlands HA) | Inhoud |
|---|---|
| `sensor.connexxion_<naam>_pickup` / `_ophalen` | Ophaaltijd van de huidige of volgende rit. Tijdens de rit de live verwachte tijd |
| `sensor.connexxion_<naam>_arrival` / `_aankomst` | Aankomsttijd van de huidige of volgende rit, ook live |
| `sensor.connexxion_<naam>_rides` / `_ritten` | Aantal geplande ritten, met de lijst in het attribuut `rides` |
| `calendar.connexxion_<naam>_schedule` / `_planning` | Alle geplande ritten als afspraken |
| `device_tracker.connexxion_<naam>_vehicle` / `_voertuig` | Positie van het voertuig, alleen tijdens de rit |
| `binary_sensor.connexxion_<naam>_ride_window` / `_rit_venster` | Aan vanaf 45 min vóór ophalen tot 15 min na aankomst |

De ritsensoren hebben de attributen `date`, `day`, `pickup_time` en `arrival_time` (gepland), `expected_pickup_time` en `expected_arrival_time` (live), `origin`, `destination`, `direction` (`to_home` / `from_home`), `status`, `driver`, `license_plate` en `vehicle_updated`.

Geannuleerde ritten worden overgeslagen. Een rit blijft "huidig" tot 15 minuten na aankomst; daarna schuiven de sensoren door naar de volgende.

## Hoe vaak wordt er ververst?

- **Rond een rit** (45 min vóór ophalen tot 15 min na aankomst): elke 5 minuten, inclusief live tijden, chauffeur en positie.
- **Elke ochtend om 06:30**: één keer.
- **Daarbuiten**: hooguit eens per 3 uur.

## Dashboard

[`dashboard/connexxion_cards.yaml`](dashboard/connexxion_cards.yaml) bevat twee voorbeeldkaarten: de planning als kalenderkaart, en een kaart met het voertuig die alleen tijdens de rit zichtbaar is.

## Overstappen van de YAML-versie

Gebruikte je eerder het script en package uit [cardinal808/Connexxion_groepsvervoer](https://github.com/cardinal808/Connexxion_groepsvervoer)? Verwijder dan `packages/connexxion.yaml`, de map `/config/connexxion/` (met `connexxion.py` en `.token.json`) en de `connexxion_*`-regels uit `secrets.yaml`, en voeg deze integratie toe. De entiteiten en attribuutnamen zijn anders (bijv. `driver` in plaats van `chauffeur`), dus pas je kaarten en automatiseringen aan.

## Problemen

- **"Inloggen mislukt"**: controleer of je met dezelfde gegevens kunt inloggen op het ouderportaal.
- **"Geen reiziger gekoppeld"**: aan je account hangt nog geen kind. Dat regel je bij Connexxion of je gemeente.
- **Debuglogs**: zet in de integratie *Debuglogboek inschakelen* aan.
- Bij een issue helpt een download van de **diagnostiek** (menu van de integratie). Wachtwoord, namen, adressen en kenteken worden daaruit weggelaten.

## Ontwikkelen

```bash
pip install -r requirements_test.txt
pytest
```

## Licentie

[MIT](LICENSE)
