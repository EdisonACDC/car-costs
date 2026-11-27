<p align="center"><picture><source media="(prefers-color-scheme: dark)" srcset="docs/images/dark_logo.png"><img src="docs/images/logo.png" alt="Car Costs" width="420"></picture></p>

<p align="center">
  <a href="https://github.com/EdisonACDC/car-costs/releases"><img alt="Download" src="https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2FEdisonACDC%2Fcar-costs%2Fbadges%2Fdownloads.json&cacheSeconds=3600&label=Download"></a>
  <a href="https://analytics.home-assistant.io/custom_integrations.json"><img alt="Installazioni attive" src="https://img.shields.io/endpoint?url=https%3A%2F%2Fraw.githubusercontent.com%2FEdisonACDC%2Fcar-costs%2Fbadges%2Finstalls.json&cacheSeconds=3600&label=Installazioni%20attive"></a>
  <br>
  <sub>I download comprendono anche gli aggiornamenti; le installazioni attive vengono da Home Assistant Analytics (solo chi ha attivato le statistiche).</sub>
</p>

<p align="center">
  <a href="README.md">English</a> · <b>Italiano</b> · <a href="README.de.md">Deutsch</a>
</p>

<p align="center">
  Quanto ti costa davvero la nuova auto (benzina + corrente) e quanto avresti speso con la vecchia per
  gli stessi km? Car Costs lo calcola ogni giorno e ti dice quando l'acquisto si ripaga.
</p>

<p align="center">
  <a href="https://github.com/EdisonACDC/car-costs/releases/latest"><img src="https://img.shields.io/github/v/release/EdisonACDC/car-costs" alt="Release"></a>
  <a href="https://hacs.xyz/"><img src="https://img.shields.io/badge/HACS-Custom-41BDF5.svg" alt="HACS custom"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/EdisonACDC/car-costs" alt="Licenza"></a>
  <a href="https://ko-fi.com/edisonacdc"><img src="https://img.shields.io/badge/Ko--fi-Support%20on%20Ko--fi-FF5E5B?logo=kofi&logoColor=white" alt="Sostienimi su Ko-fi"></a>
</p>

<p align="center">
  <a href="https://my.home-assistant.io/redirect/hacs_repository/?owner=EdisonACDC&repository=car-costs&category=integration"><img src="https://my.home-assistant.io/badges/hacs_repository.svg" alt="Apri Home Assistant e l'integrazione Car Costs in HACS"></a>
</p>

<p align="center">
  <img src="docs/images/demo.gif" width="300" alt="Car Costs: foto dello scontrino, modulo compilato, salvato, panoramica aggiornata">
</p>

<p align="center">
  <img src="docs/images/screenshots.png" alt="Schermate di Car Costs, chiaro e scuro: panoramica, registro, grafici, modulo scontrino, tablet">
</p>

## Cosa fa

- **Costi Auto nel menu laterale** di Home Assistant: un'app in stile "vetro" che si adatta a telefono,
  tablet e PC, con il tema chiaro o scuro di Home Assistant. Nessun secondo login, nessun add-on.
- **Km** letti dal contachilometri (per esempio l'integrazione **MySkoda**) o dai rifornimenti.
- **Corrente di casa** dal sensore kWh della presa o della wallbox, al prezzo di casa.
- **Rifornimenti e ricariche** a mano, con i servizi, oppure da una **foto dello scontrino**: un'AI lo
  legge, controlli il modulo già compilato e salvi. La foto resta con la voce.
- **Confronto**: per ogni km la vecchia auto consumerebbe `consumo × prezzo carburante` (fisso o da sensore).
- **Costi fissi** annuali (bollo, assicurazione, manutenzione) di entrambe, ripartiti per giorno.
- **Ammortamento**: investimento = prezzo + spese extra − vendita della vecchia auto; % recuperata e data di pareggio prevista.
- **Grafici**: spesa al mese, risparmio cumulato, €/100 km, benzina e corrente.
- **Quota di km in elettrico** (stima), se indichi il consumo elettrico.
- **Web app per il telefono** (installabile, funziona offline con l'ultimo riepilogo) e la card Lovelace `car-costs-card`.
- Italiano, tedesco e inglese, dalla lingua di Home Assistant.

## Installazione

1. **Installa l'integrazione.** In HACS apri **⋮ → Repository personalizzati**, aggiungi
   `https://github.com/EdisonACDC/car-costs` come **Integrazione**, installa **Car Costs** e riavvia
   Home Assistant.
2. **Aggiungila.** Vai in **Impostazioni → Dispositivi e servizi → Aggiungi integrazione → Car Costs** e
   segui i quattro passi.
3. **Apri "Costi Auto"** dal menu laterale. Il pannello compare da solo.

> **Occhio al nome nel Marketplace.** Se compaiono altri progetti chiamati "Car Costs", scegli quello di
> tipo **Integrazione**, di **EdisonACDC**.

## Configurazione

Il setup ha quattro passi brevi; tutto si può cambiare dopo da **Impostazioni → Dispositivi e servizi → Car Costs → Configura**.

1. **Auto**: nome, prezzo d'acquisto, spese extra (wallbox, immatricolazione…), data di consegna, km alla
   consegna, sensore dei km (facoltativo) e se **mostrare "Costi Auto" nel menu laterale**.
2. **Corrente e scontrini**: prezzo di casa (o un sensore del prezzo), il sensore kWh della presa o della
   wallbox, il consumo elettrico (kWh/100 km, facoltativo) e l'entità **AI Task** che legge gli scontrini.
3. **Auto con cui confrontare**: la vecchia auto, il suo carburante, consumo, prezzo del carburante (o un sensore) e prezzo di vendita.
4. **Costi annuali**: bollo, assicurazione e manutenzione di entrambe.

Con più auto aggiungi l'integrazione una volta per auto; il pannello e l'app offrono il selettore dell'auto.

## AI per gli scontrini

Fotografa lo scontrino con **＋ → 📷 Scontrino**: la foto va all'entità **AI Task** che hai scelto, che
restituisce data, distributore, litri o kWh e totale. Vedi il modulo già compilato, con i campi
mancanti in rosso, e premi **Salva**.

- **Gratis**: Google Gemini, con una chiave gratuita da [Google AI Studio](https://aistudio.google.com/apikey),
  aggiunta con l'integrazione *Google Generative AI* di Home Assistant.
- Anche **OpenAI**, **Anthropic** oppure **Ollama** con un modello vision.
- **Cosa si manda**: solo la foto dello scontrino e l'istruzione di leggerlo. Nient'altro della tua casa.
  La foto resta in `/media/car_costs` e si cancella con la voce; le foto che non finiscono in nessuna
  voce si cancellano dopo 24 ore.
- Senza AI l'app ti chiede di compilare il modulo a mano.

## App sul telefono

Il telefono **non** ha bisogno di un account di Home Assistant e non vede mai il login di Home Assistant. Chiede l'accesso e tu confermi, come la conferma del genitore in Family Hub:

1. In **Costi Auto → Impostazioni → App sul telefono** c'è un **QR code** con l'indirizzo dell'app (nessun segreto dentro). Inquadralo col telefono.
2. **iPhone:** in Safari tocca Condividi → *Aggiungi alla schermata Home*, poi apri l'icona. **Android / PC:** l'app può chiedere subito (e propone *Installa app*).
3. L'app mostra **Richiedi l'accesso** con il nome del telefono. Premilo: il telefono mostra "Conferma sul telefono di Home Assistant – codice **4821**".
4. Home Assistant manda una **notifica** con *Accetta* / *Rifiuta* (ai telefoni scelti in *Notifica le richieste a*), una notifica persistente, e mostra la richiesta nel pannello (**Richieste in attesa**) con lo stesso codice. Controlla che il codice sia quello del telefono, poi accetta. Dalla notifica: *Vedere e aggiungere*, tutte le auto. Dal pannello scegli permessi (*Solo vedere*, *Vedere e aggiungere*, *Vedere, aggiungere e modificare*) e auto.
5. Il telefono riceve il suo token (256 bit, in Home Assistant solo come hash SHA-256, rinnovato ogni 30 giorni) e apre l'app. L'icona non chiede più nessun link.

- Una richiesta dura 10 minuti. Al massimo 3 in attesa insieme e 5 all'ora per indirizzo; oltre c'è `429`. Prima dell'accettazione non esce nessun dato (auto, importi, nomi) e il token si consegna una volta sola.
- I **telefoni collegati** sono nell'elenco del pannello (nome, ultimo accesso, permessi). Puoi rinominarne uno, cambiare permessi e auto, scollegarlo (smette subito) o collegare un *nuovo telefono* al suo posto. Ci sono anche gli ultimi eventi.
- *Altri modi* (per chi non ha l'app Companion): un link con un codice monouso (24 ore, dopo il `#` dell'indirizzo), mostrato come QR, e *Incolla il link* sul telefono.
- Il telefono riceve solo le auto e le azioni che gli hai dato, da `/api/car_costs/app/…`. Non riceve mai entità, configurazione o altro di Home Assistant. Le richieste sono limitate per telefono e per indirizzo.
- Automazioni: l'evento `car_costs_phone_request` (`request_id`, `name`, `status`) parte quando una richiesta viene fatta e decisa.
- Senza un indirizzo esterno (Nabu Casa o URL esterno di Home Assistant) il pannello avvisa che l'app funziona solo in casa. L'ultimo riepilogo resta disponibile offline.

## Servizi

| Servizio | Campi |
|---|---|
| `car_costs.add_refuel` | `liters`, `total_cost`, `odometer`, `date`, `station`, `note` |
| `car_costs.add_charge` | `kwh`, `total_cost` (vuoto a casa = prezzo di casa), `location` home/public |
| `car_costs.scan_receipt` | `image` (media o percorso file), `auto_add` |
| `car_costs.update_entry` | `entry_id` + i campi da cambiare |
| `car_costs.delete_entry` | `entry_id` (cancella anche la foto) |

L'evento `car_costs_receipt_scanned` parte dopo ogni scontrino (utile per una notifica).

## Card

La card Lovelace viene caricata dall'integrazione, non c'è nessuna risorsa da aggiungere:

```yaml
type: custom:car-costs-card
# config_entry_id: ...   # solo se segui più auto
# limit: 15
```

## FAQ

**Serve la wallbox o una presa smart?** No. Senza, inserisci a mano le ricariche di casa. Con un sensore
kWh sono contate da sole, quindi a mano inserisci solo quelle fuori casa.

**Serve MySkoda?** No. Va bene qualsiasi sensore con i km; senza, i km vengono dai rifornimenti.

**Serve l'AI?** No, serve solo a leggere le foto degli scontrini. Tutto si può inserire a mano.

**Serve un add-on?** No. Non serve nemmeno il Supervisor.

**Dove sono i miei dati?** Nell'archivio di Home Assistant (un file per auto) e, per le foto, in
`/media/car_costs`. Nulla esce da casa tua, tranne la foto dello scontrino che mandi all'AI scelta.

**E lo storico?** Ogni notte si salva uno snapshot dei totali (fino a 5 anni): servono ai grafici.

**Funziona in altre lingue?** Italiano, tedesco e inglese, dalla lingua di Home Assistant.

## Stato e limiti

- Provato con i test automatici (pytest su un Home Assistant di prova) e, per pannello e app, in un browser
  contro un Home Assistant **simulato**. Da verificare su un'installazione vera: il pannello dentro il
  frontend di Home Assistant (pulsante menu, tema, lingua), la fotocamera e l'AI che legge scontrini
  veri da telefono, e come si comportano i numeri dopo qualche settimana.
- Nelle prime settimane i numeri oscillano: la benzina della nuova auto è contata quando fai il pieno, il
  costo della vecchia per km percorso.
- Auto, distributori e importi negli screenshot sono inventati.

## Sostienimi

Se Car Costs ti è utile, puoi offrirmi un caffè ☕ [ko-fi.com/edisonacdc](https://ko-fi.com/edisonacdc)

E metti una ⭐ al repo: aiuta altri a trovarlo.

## Sviluppo

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements_test.txt
pytest
ruff check . && ruff format --check .
mypy
```

App e pannello in un browser, contro un Home Assistant simulato (Node.js):

```bash
cd tools/e2e
npm install && npx playwright install chromium
node run.mjs          # controlli e screenshot
node make_docs.mjs    # immagini del README
```

## Licenza

MIT, vedi [LICENSE](LICENSE). Modifiche: [CHANGELOG.md](CHANGELOG.md).
