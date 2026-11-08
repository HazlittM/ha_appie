# HA Appie (Home Assistant) · [English below](#english)

Een Home Assistant-integratie voor **Albert Heijn** die veel meer doet dan bezorgmeldingen. Je bedient je boodschappen vanuit je dashboard:

- 🚚 **Bezorging:** status van je bezorging, je bezorgslot en een event voor meldingen (*"de bezorger komt eraan"*, *"bezorgd"*).
- 🛒 **Boodschappenlijst:** je AH-lijst als to-do in HA. Toevoegen, afvinken en verwijderen werkt twee kanten op, en tekst als `courgette` of `2 melk` wordt vanzelf het juiste AH-product.
- 🔁 **Vaste producten:** een weeklijstje van wat je steeds bestelt, met per product een aantal dat je kunt aanpassen en één knop om alles op de lijst te zetten.
- 🍝 **Recepten:** sla recepten op (typ ze in een formulier of plak ze), kies ze in een dropdown, stel het aantal personen in en zet het hele recept met één knop op je lijst. Hoeveelheden worden omgerekend naar verpakkingen, ingrediënten zoeken zelf het beste AH-product, en je kunt per ingrediënt een product vastzetten of een eigen vertaallijst gebruiken.
- 🔎 **Producten zoeken:** typ een zoekwoord en kies uit de resultaten, met verpakkingsgrootte, prijs, bonusmarkering en prijs per kg of liter.
- 🧾 **Overig:** winkelmand, inhoud van je bestelling, kassabonnen uit de winkel en je persoonlijke Bonus-aanbiedingen.

Alles is bedoeld om in een eigen dashboard te gebruiken (bijvoorbeeld in een pop-up), zodat je met een paar tikken boodschappen doet.

> ⚠️ **Onofficieel.** Albert Heijn heeft geen publieke API. Deze integratie gebruikt dezelfde API als de AH-app, alleen voor jouw eigen account (hij leest je bestellingen en schrijft alleen naar je boodschappenlijst). AH kan dit op elk moment wijzigen of blokkeren, en het gebruik kan tegen hun voorwaarden zijn. Gebruik op eigen risico. Niet verbonden met of goedgekeurd door Albert Heijn.

> ⚠️ **Nog niet getest:** de meldingen bij een bezorging (status `tijd_bekend`, `bezorgd`, `geannuleerd` en het event) zijn gebouwd maar nog niet met een echte bezorging geprobeerd. De rest (lijst, vaste producten, recepten, zoeken) is wel getest.

## Wat je krijgt

| Entiteit | Betekenis |
|---|---|
| `sensor.albert_heijn_bezorging_status` | `geen`, `gepland`, `tijd_bekend`, `bezorgd`, `geannuleerd`, `onbekend` voor de bezorging van vandaag of de eerstvolgende |
| `sensor.albert_heijn_bezorging_begin_bezorgslot` / `…_einde_bezorgslot` | het door jou geboekte bezorgslot (tijdstempels) |
| `event.albert_heijn_bezorging_bezorging` | vuurt af bij `tijd_bekend`, `bezorgd` en `geannuleerd` |

> De entiteits-ID's hierboven zijn de standaardnamen. Wijs je het apparaat aan een ruimte toe, dan kan Home Assistant er de ruimtenaam voor zetten (bijv. `sensor.meterkast_albert_heijn_bezorging_status`). Pas ze desgewenst aan in de entiteitsinstellingen.

### Vaste producten en slim toevoegen (vanaf 0.3)

- **Weeklijstje:** de integratie kijkt naar je afgeronde bezorgingen (de laatste 8) en maakt een lijst van producten die je in minstens de helft ervan bestelde (maximaal 30). Elk product krijgt een `number`-entiteit met het aantal dat je normaal bestelt (de mediaan). Pas het aantal aan, of zet het op 0 om het deze week over te slaan.
- **Eén knop:** `button.…_voeg_vaste_producten_toe_aan_boodschappenlijst` zet alle vaste producten met een aantal groter dan 0 op je AH-boodschappenlijst. Wat al op de lijst staat wordt overgeslagen, dus twee keer drukken verdubbelt niets. `…_standaardaantallen_herstellen` zet je aangepaste aantallen terug.
- **Slim toevoegen aan de to-do:** typ je `Courgette`, dan wordt het `AH Courgette`. De integratie kiest het product dat je waarschijnlijk bedoelt: eerst wat je eerder bestelde, dan een exacte naam, dan AH-eigen merk en de kortste naam. Past niets, dan blijft je tekst staan zoals getypt. Aantallen werken ook: `2 melk`, `melk 2x`.
- De tellingen staan in de HA-opslag (`.storage`); lijsten van bestelde producten gaan nooit mee naar de repo.

### Producten zoeken (vanaf 0.4)
Typ een zoekwoord in **Zoek product**; **Zoekresultaat** toont dan de 20 beste AH-producten met verpakkingsgrootte, prijs (bonus gemarkeerd) en prijs per kg of liter. Kies er één, stel **Zoek aantal** in en druk op **Zoekresultaat toevoegen**. Staat het product al op de lijst, dan wordt het aantal opgeteld.

### Recepten (vanaf 0.4)
Sla een recept op en zet het met één knop op je AH-boodschappenlijst, omgerekend naar het aantal personen.
- Opslaan: actie `ha_appie.save_recipe` (Ontwikkelaarstools → Acties) met `name`, `persons` (voor hoeveel personen de hoeveelheden gelden) en `ingredients` (één per regel, bv. `400 g rundergehakt`; een recept van internet plakken mag).
- Bediening (dropdown): kies het recept in de keuzelijst **Recept**; daaronder staan **Recept personen** (aanpassen herberekent alles), **Recept ingrediënten** (een lijst waarin je regels toevoegt, aanpast of verwijdert) en de knop **Recept op boodschappenlijst**. Opnieuw opslaan met dezelfde naam vervangt de ingrediënten en houdt het gekozen aantal personen.
- Elk ingrediënt wordt het AH-product dat je waarschijnlijk bedoelt (eerder gekochte producten gaan voor); het aantal verpakkingen wordt omhoog afgerond op de verpakkingsgrootte (`600 g` met 500 g-verpakkingen = 2). Lepels, blikjes en ingrediënten zonder hoeveelheid worden 1 verpakking; niet gevonden = tekst op de lijst.
- Productkeuze: zie **Beste overeenkomst** hieronder. Verkleinwoorden en meervouden worden herkend ("cherrytomaatjes" = "cherrytomaten"). Past er niets, dan komt het als tekst op de lijst. Wil je zelf kiezen: zoek het product (Product zoeken), kies het ingrediënt bij **Recept ingrediënt kiezen** en druk op **Zoekresultaat vastzetten bij ingrediënt**. Een 📌 laat zien dat de keuze vaststaat; met **Ingrediënt weer automatisch kiezen** haal je het weg.
- Nieuw recept invullen in het dashboard: vul **Nieuw recept naam**, **Nieuw recept personen** en **Nieuw recept ingrediënten** in (met `;` tussen de regels, bijvoorbeeld `500 gr gehakt; 2 uien; 1 zak rijst`) en druk op **Nieuw recept opslaan**. Het recept wordt meteen geselecteerd en het formulier wordt leeg gemaakt. Meer ingrediënten voeg je daarna toe in de lijst **Recept ingrediënten**.
- Beste overeenkomst: bij recepten kiest hij het product dat het meest op je ingrediënt lijkt ("lays paprika chips" wordt "Lay's Paprika"). Minstens 60% van je woorden moet in de naam staan, die woorden moeten bij elkaar staan en er mag niets achter komen ("Rode bieten met ui" is dus geen "rode ui", "Pasta Pestosaus" geen "pasta").
- Typefouten en eigen vertalingen: kleine spelfouten worden vanzelf opgevangen ("cremé fraise" = "crème fraîche"). Lukt een woord toch niet, zet dan in de lijst **Vertaallijst** een regel als `cremé fraise = creme fraiche` (links wat je typt, rechts wat AH kent). Dat geldt voor recepten én voor slim toevoegen in de to-do. De lijst is persoonlijk en staat alleen in je eigen HA-opslag.
- Er staat al iets van hetzelfde product op de lijst? Dan wordt het opgeteld. Twee keer drukken verdubbelt dus.
- Ook beschikbaar: `ha_appie.add_recipe_to_list` (met optioneel `persons`) en `ha_appie.delete_recipe`.

### Meer dan bezorging (vanaf 0.2)

| Entiteit | Betekenis |
|---|---|
| `todo.…_boodschappenlijst` | je AH-boodschappenlijst als to-do: lezen, toevoegen en afvinken. Afvinken **verwijdert** het item, want AH kent geen "afgevinkt" |
| `sensor.…_winkelmand` | aantal producten in je online winkelmand (attribuut `items`) |
| `sensor.…_producten_in_bestelling` | aantal producten in de huidige of eerstvolgende bestelling (attribuut `products`) |
| `sensor.…_laatste_kassabon`, `…_bedrag_laatste_kassabon`, `…_uitgegeven_in_winkel_deze_maand` | kassabonnen van aankopen in de winkel met je Bonuskaart (laatste 50) |
| `sensor.…_persoonlijke_bonus`, `…_bonus_op_eerder_gekocht` | aantal aanbiedingen deze bonusweek (attribuut `offers`, `period_start`, `period_end`) |

Deze gegevens worden elke 30 minuten ververst. De lijsten (`items`, `products`, `offers`) worden niet in de Home Assistant-database bewaard.

**Privacy:** deze entiteiten tonen je boodschappen en bonnen aan iedereen die je Home Assistant kan zien. Adres, telefoonnummer en geboortedatum worden bewust **niet** gelezen.

De status-sensor heeft ook de attributen `upcoming` (data van geplande bezorgingen), `order_id`, `ah_status` (ruwe AH-status) en `eta_estimated`.

**Beperking in versie 0.1:** de exacte aankomsttijd uit de AH-melding ("tussen 10:20 en 10:50") is nog niet gevonden in de API. Dit geeft je wel het bezorgslot, het moment dat AH een aankomsttijd *heeft* (`tijd_bekend`) en het moment van bezorgen. Het attribuut `eta_estimated` laat zien wat AH op dat veld teruggeeft; zie je daar ooit een waarde, open dan graag een issue.

## Installeren

**HACS:** HACS → ⋮ → *Aangepaste repository's* → voeg deze repo toe (categorie *Integratie*) → installeer → herstart Home Assistant.
**Handmatig:** kopieer `custom_components/ha_appie` naar je `custom_components`-map en herstart.

Daarna: *Instellingen → Apparaten & diensten → Integratie toevoegen → HA Appie*.

## Inloggen (eenmalig)

AH laat alleen inloggen via de app-omleiding, dus dit gaat met een code:

1. Open de link uit het configuratiescherm in een browser **op een computer**, met de ontwikkelaarstools open (F12 → *Netwerk*, *Logboek behouden* aan).
2. Log in bij AH. Daarna probeert de browser `appie://login-exit?code=…` te openen; dat lukt niet, maar de aanvraag staat in het Netwerk-tabblad.
3. Plak de hele URL (of alleen de waarde na `code=`) in het scherm. De code is kort geldig en werkt één keer.

Je wachtwoord komt nooit in Home Assistant. Alleen de tokens worden bewaard (in `.storage`, zoals bij elke integratie). Er worden geen adressen of boodschappen gelezen.

## Voorbeeld-automations

```yaml
automation:
  - alias: HA Appie - aankomsttijd bekend
    triggers:
      - trigger: state
        entity_id: sensor.albert_heijn_bezorging_status
        to: tijd_bekend
    actions:
      - action: notify.mobile_app_JOUW_TELEFOON
        data:
          title: Albert Heijn
          message: >-
            De bezorger komt eraan. Slot:
            {{ as_local(states('sensor.albert_heijn_bezorging_begin_bezorgslot') | as_datetime).strftime('%H:%M') }}
            - {{ as_local(states('sensor.albert_heijn_bezorging_einde_bezorgslot') | as_datetime).strftime('%H:%M') }}

  - alias: HA Appie - bezorgd
    triggers:
      - trigger: state
        entity_id: sensor.albert_heijn_bezorging_status
        to: bezorgd
    actions:
      - action: notify.mobile_app_JOUW_TELEFOON
        data: {title: Albert Heijn, message: Je boodschappen zijn bezorgd.}
```

## Problemen

- *"Code afgewezen"*: de code is verlopen of al gebruikt. Log opnieuw in en plak meteen.
- Als AH de API wijzigt, ziet Home Assistant een fout of een lege status. Alle AH-specifieke code staat in `api.py` en `model.py`.
- Verversing: elke minuut op een bezorgdag, anders elke 15 minuten.

## Ontwikkelen

`python3 tests/test_model.py` draait de tests van de statuslogica (geen Home Assistant nodig).

---

## English

A Home Assistant integration for **Albert Heijn** that does far more than delivery notifications. Run your grocery shopping from your dashboard:

- 🚚 **Delivery:** delivery status, your time slot and an event for notifications ("arrival time known", "delivered").
- 🛒 **Shopping list:** your AH list as a to-do in HA. Add, tick off and remove; text like `courgette` or `2 melk` automatically becomes the right AH product.
- 🔁 **Regular products:** a weekly list of what you keep ordering, an adjustable quantity per product and one button to put everything on the list.
- 🍝 **Recipes:** store recipes (type them in a form or paste them), pick one from a dropdown, set the number of persons and put the whole recipe on your list with one button. Amounts are converted to pack counts, each ingredient finds the best AH product by itself, and you can pin a product per ingredient or keep a personal translation list.
- 🔎 **Product search:** type a keyword and pick a result, with pack size, price, bonus marker and price per kg or litre.
- 🧾 **Also:** basket, order contents, in-store receipts and your personal Bonus offers.

Everything is meant to be used from your own dashboard (for example in a pop-up), so shopping takes a few taps.

> ⚠️ **Unofficial.** AH has no public API. This uses the same API as the AH app, for your own account only (it reads your orders and only writes to your shopping list). It can break or be blocked at any time and may be against AH's terms. Use at your own risk. Not affiliated with Albert Heijn.

> ⚠️ **Not yet tested:** delivery notifications (statuses `tijd_bekend`, `bezorgd`, `geannuleerd` and the event) are built but have not yet been tried with a real delivery. The rest (list, regular products, recipes, search) has been tested.

**Entities (0.3 adds a weekly list of regular products with adjustable quantities, one button to add them to the shopping list, and smart matching of typed items ("courgette" becomes "AH Courgette"); 0.2 adds shopping list as a to-do, basket, order contents, in-store receipts and Bonus offers):** a status sensor (`geen`, `gepland`, `tijd_bekend`, `bezorgd`, `geannuleerd`, `onbekend`), delivery slot start/end timestamps, and an event entity firing on `tijd_bekend` (AH has an arrival estimate), `bezorgd` (delivered) and `geannuleerd` (cancelled).

**Limitation in 0.1:** the exact arrival window from the AH push notification is not yet exposed. The `eta_estimated` attribute shows the raw field for diagnosis.

**Install:** add this repository to HACS as a custom *Integration* repository (or copy `custom_components/ha_appie`), restart, then add the integration. **Log in:** open the link shown in the setup dialog on a desktop with the browser dev tools Network tab open, log in, and copy the `code` from the `appie://login-exit?code=…` redirect into the dialog (single use, short-lived). Your password never reaches Home Assistant; only tokens are stored. See the automation examples above.

### Product search (0.4+)
Type in **Zoek product**; **Zoekresultaat** lists the 20 best AH products with pack size. Pick one, set **Zoek aantal** and press **Zoekresultaat toevoegen** (added to any quantity already on the list).

### Recipes (0.4+)
Store a recipe and put it on your AH shopping list with one press, scaled to the number of persons.
- Save with the action `ha_appie.save_recipe` (`name`, `persons` = the persons the amounts are for, `ingredients` one per line, pasting a web recipe works).
- Controls: pick a recipe in the **Recept** dropdown; **Recept personen** rescales, **Recept ingrediënten** is an editable list (add, rename, delete lines), and **Recept op boodschappenlijst** is the button. Saving again under the same name replaces the ingredients and keeps the chosen persons.
- Ingredients become the AH product you probably mean (previous purchases first), packs rounded up to the pack size; spoons/cans/no amount = 1 pack; not found = text. Amounts already on the list are added to, so pressing twice doubles.
- Also: `ha_appie.add_recipe_to_list` (optional `persons`), `ha_appie.delete_recipe`.

