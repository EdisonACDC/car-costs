# Car Costs – Costi Auto per Home Assistant

Quanto ti costa davvero la nuova auto (benzina + corrente) e quanto avresti speso con la vecchia per gli stessi km? Car Costs lo calcola ogni giorno e ti dice quando l'acquisto si ripaga.

## Cosa fa
- **km** letti dal contachilometri (es. integrazione **MySkoda**) o dai rifornimenti
- **Corrente di casa** dal sensore kWh della presa/wallbox (`total_increasing`), al prezzo di casa
- **Rifornimenti e ricariche** a mano dalla card o con i servizi
- **Foto dello scontrino** → letto con **AI Task** (OpenAI, Gemini, Anthropic, Ollama con modello vision…), controlli e salvi
- **Confronto**: per ogni km la vecchia auto consuma `consumo × prezzo carburante` (fisso o sensore Tankerkönig)
- **Costi fissi** annuali (bollo, assicurazione, manutenzione) di entrambe, ripartiti per giorno
- **Ammortamento**: investimento = prezzo + spese extra − vendita vecchia auto; % recuperata e data di pareggio prevista

## Installazione
1. HACS → Repository personalizzati → `https://github.com/EdisonACDC/car-costs` (Integrazione)
2. Installa e riavvia Home Assistant
3. Impostazioni → Dispositivi e servizi → Aggiungi → **Car Costs**
4. Dashboard → Aggiungi card → `custom:car-costs-card` (la card si carica da sola, niente risorse da aggiungere)

```yaml
type: custom:car-costs-card
# config_entry_id: ...   # solo se segui più auto
# limit: 15
```

## Web app per il telefono (0.3)
Apri `https://<tuo-home-assistant>/car-costs` (va bene anche l'indirizzo Nabu Casa), accedi con il tuo utente di Home Assistant e aggiungila alla schermata Home:
- **iPhone**: Safari → Condividi → *Aggiungi alla schermata Home*
- **Android**: Chrome → ⋮ → *Installa app*

Stile "vetro", tema chiaro/scuro automatico, italiano/tedesco/inglese. Quattro schermate più il pulsante ＋:
- **Panoramica**: anello di ammortamento, risparmio, data di pareggio, confronto a parità di km, riquadri, ultimi movimenti
- **Registro**: voci per mese, filtri, ricerca distributore, dettagli con foto dello scontrino, modifica ed elimina
- **＋**: 📷 scontrino (foto → AI Task → modulo già compilato), ⛽ rifornimento, 🔌 ricarica
- **Grafici**: spesa al mese, risparmio cumulato, €/100 km, benzina/corrente (3 mesi / 12 mesi / tutto)
- **Impostazioni**: auto seguita, prezzi, lingua, esci

Funziona anche solo in LAN (niente servizi esterni), l'ultimo riepilogo resta disponibile offline. Con più auto: `/car-costs?entry=<config_entry_id>`.

## Servizi
| Servizio | Campi |
|---|---|
| `car_costs.add_refuel` | `liters`, `total_cost`, `odometer`, `date`, `station`, `note` |
| `car_costs.add_charge` | `kwh`, `total_cost` (vuoto a casa = prezzo di casa), `location` home/public |
| `car_costs.scan_receipt` | `image` (media o percorso file), `auto_add` |
| `car_costs.update_entry` | `entry_id` + i campi da cambiare |
| `car_costs.delete_entry` | `entry_id` (cancella anche la foto) |

Evento `car_costs_receipt_scanned` dopo ogni scontrino (utile per una notifica).

## Note
- Se hai il sensore della presa, le ricariche di casa sono già contate: a mano inserisci solo quelle fuori casa.
- La benzina della nuova auto è contata quando fai il pieno, il confronto con la vecchia per km: nelle prime settimane i numeri oscillano.
- Le foto degli scontrini restano in `/media/car_costs` e si cancellano con la voce.
- Opzione *consumo elettrico* (kWh/100 km): se impostata, la app stima la quota di km in elettrico.
- Ogni notte viene salvato uno snapshot dei totali (max 5 anni): servono ai grafici.
