# Changelog

Nieuwste bovenaan. Bij elke nieuwe versie: regel toevoegen, `version` in `manifest.json` ophogen en de README bijwerken zodat die alleen beschrijft wat er nú in zit.
Newest first. For every release: add an entry, bump `version` in `manifest.json` and update the README so it only describes what is in the integration now.

## 0.5.0
- Kassabon in detail: regels met productfoto's, kortingen en betaling van de laatste bon, eerdere bonnen, bespaard deze maand, uitgaven per maand; bon als PDF (bekijken of opslaan in een map).
- Bezorging: verwachte aankomst (track & trace), *wijzigen tot*, minimumbedrag, factuur als PDF; optioneel vrije bezorgmomenten voor een zelf ingevuld adres.
- Persoonlijke Bonus met prijzen en activatiestatus (`bonuspage/v1/personal`, valt terug op de oude bron).
- Favoriete winkel met openingstijden en *Laatste kans*; favorietenlijsten; bonuskaart als barcode (opt-in).
- Acties: productinformatie en barcode opzoeken, producten zoeken en toevoegen, Allerhande-recepten zoeken, bekijken en overnemen, PDF's opslaan, aan favorieten toevoegen.
- Opties: elk nieuw onderdeel is uit te zetten. Optionele AH-verzoeken die falen maken alleen die entiteit onbeschikbaar (debuglog), nooit de setup of een nieuwe login.
- Tokenvernieuwing kan niet meer twee keer tegelijk lopen (refresh-tokens zijn eenmalig).
- Ingebouwde dashboardkaart `custom:ha-appie-card` in AH-stijl met visuele editor (NL/EN, licht/donker, mobiel), zelf geregistreerd als Lovelace-resource.
- Integratie-icoon (`brand/`).
- README: 2FA-workaround en ander account koppelen zonder `_2`.

## Onbeperkt / unreleased (documentatie)
- README: bezorgmeldingen getest met een echte bezorging; voorbeeld-automation meldt `tijd_bekend` pas om 07:30 en met neutrale tekst. De exacte aankomsttijd is niet via de API beschikbaar.

## 0.4.0
- Recepten: opslaan (formulier of actie), kiezen in een dropdown, aantal personen, op de AH-lijst met verpakkingen naar boven afgerond, ingrediënten bewerken, product vastzetten per ingrediënt, vertaallijst.
- Producten zoeken met prijs, bonus en prijs per kg/liter.
- Productkeuze op beste overeenkomst, tolerant voor typefouten.
- Hernoemd naar HA Appie (domein `ha_appie`).

## 0.3.0
- Weeklijstje met vaste producten (aantal per product, één knop) en slim toevoegen aan de to-do.

## 0.2.0
- Boodschappenlijst als to-do, winkelmand, bestelinhoud, kassabonnen en Bonus-aanbiedingen.

## 0.1.0
- Bezorgstatus, bezorgslot en event.
