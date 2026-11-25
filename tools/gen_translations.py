"""Generate strings.json and translations/*.json for Car Costs."""

import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "custom_components" / "car_costs"

T = {
    "en": {
        "steps": {
            "user": ("Your new car", "Purchase data. The investment to pay back is purchase price + extra costs − what you get for the old car."),
            "energy": ("Electricity and receipts", "Optional: the energy sensor of the plug/wallbox you charge with at home, and the AI Task entity that reads receipt photos."),
            "reference": ("Car to compare with", "The old car: for every km you drive, Car Costs calculates what it would have cost in fuel."),
            "fixed": ("Yearly fixed costs", "Tax, insurance and maintenance per year, for both cars. Leave 0 if you do not want to compare them."),
        },
        "fields": {
            "name": "Name of the new car", "purchase_price": "Purchase price", "extra_investment": "Extra costs (wallbox, registration…)",
            "start_date": "Start date (delivery)", "start_odometer": "Odometer at delivery (0 = first reading of the sensor)",
            "odometer_entity": "Odometer sensor (e.g. MySkoda)", "electricity_price": "Electricity price at home",
            "electricity_price_entity": "Electricity price sensor (optional, overrides the price)",
            "home_energy_entity": "Home charging energy sensor (kWh)", "ai_task_entity": "AI Task for receipt photos",
            "ev_consumption": "Electric consumption (kWh/100 km) – for the estimate of electric km, optional",
            "ref_name": "Name of the old car", "ref_fuel": "Fuel", "ref_consumption": "Real consumption",
            "ref_fuel_price": "Fuel price", "ref_fuel_price_entity": "Fuel price sensor (e.g. Tankerkönig, optional)",
            "old_car_sale_price": "Sale price of the old car",
            "new_tax": "New car: road tax / year", "new_insurance": "New car: insurance / year", "new_maintenance": "New car: maintenance / year",
            "ref_tax": "Old car: road tax / year", "ref_insurance": "Old car: insurance / year", "ref_maintenance": "Old car: maintenance / year",
        },
        "fuel": {"diesel": "Diesel", "petrol": "Petrol", "lpg": "LPG", "cng": "CNG"},
        "location": {"home": "Home", "public": "Public / receipt"},
        "sensors": {
            "km_driven": "Km driven", "fuel_liters": "Fuel litres", "electricity_kwh": "Electricity kWh",
            "fuel_cost": "Fuel cost", "electricity_cost": "Electricity cost", "energy_cost": "Energy cost",
            "reference_cost": "Old car fuel cost (same km)", "energy_savings": "Energy savings",
            "fixed_cost_savings": "Fixed cost savings", "total_savings": "Total savings",
            "savings_per_month": "Savings per month", "investment": "Investment",
            "cost_per_100km": "Cost per 100 km", "reference_cost_per_100km": "Old car cost per 100 km",
            "avg_fuel_consumption": "Average fuel consumption", "amortization": "Paid back",
            "break_even_date": "Break-even date",
        },
        "services": {
            "add_refuel": ("Add refuel", "Log a refuel of the new car."),
            "add_charge": ("Add charge", "Log a charge. Without a cost, home charges use the home electricity price."),
            "delete_entry": ("Delete entry", "Delete an entry from the log (and its receipt photo)."),
            "update_entry": ("Edit entry", "Change the fields of an entry in the log."),
            "scan_receipt": ("Scan receipt", "Read a fuel or charging receipt from a photo with AI Task."),
        },
        "sfields": {
            "config_entry_id": ("Car", "Needed only if you track more than one car."),
            "liters": ("Litres", "Litres of fuel."), "kwh": ("kWh", "Energy charged."),
            "total_cost": ("Total cost", "Amount paid in euro."), "odometer": ("Odometer", "Km on the odometer (optional)."),
            "date": ("Date", "Date of the refuel/charge (default today)."), "station": ("Station", "Station or operator."),
            "note": ("Note", "Free text."), "location": ("Location", "Where you charged."),
            "entry_id": ("Entry ID", "ID of the log entry."), "image": ("Photo", "Photo of the receipt."),
            "auto_add": ("Add automatically", "Add the entry if the receipt was read completely."),
        },
        "errors": {
            "entry_not_found": "Car Costs: car not found.",
            "entry_required": "Car Costs: more than one car is set up, choose which one.",
            "log_entry_not_found": "Car Costs: log entry not found.",
        },
    },
    "it": {
        "steps": {
            "user": ("La nuova auto", "Dati d'acquisto. L'investimento da recuperare è prezzo + spese extra − quanto ricavi dalla vecchia auto."),
            "energy": ("Corrente e scontrini", "Facoltativi: il sensore di energia della presa/wallbox con cui ricarichi a casa e l'entità AI Task che legge le foto degli scontrini."),
            "reference": ("Auto di confronto", "La vecchia auto: per ogni km che fai, Costi Auto calcola quanto avresti speso di carburante con lei."),
            "fixed": ("Costi fissi annuali", "Bollo, assicurazione e manutenzione all'anno per entrambe le auto. Lascia 0 se non vuoi confrontarli."),
        },
        "fields": {
            "name": "Nome della nuova auto", "purchase_price": "Prezzo d'acquisto", "extra_investment": "Spese extra (wallbox, immatricolazione…)",
            "start_date": "Data di inizio (consegna)", "start_odometer": "Km alla consegna (0 = prima lettura del sensore)",
            "odometer_entity": "Sensore contachilometri (es. MySkoda)", "electricity_price": "Prezzo corrente di casa",
            "electricity_price_entity": "Sensore prezzo corrente (facoltativo, sostituisce il prezzo)",
            "home_energy_entity": "Sensore energia ricarica a casa (kWh)", "ai_task_entity": "AI Task per le foto degli scontrini",
            "ev_consumption": "Consumo elettrico (kWh/100 km) – per stimare i km in elettrico, facoltativo",
            "ref_name": "Nome della vecchia auto", "ref_fuel": "Carburante", "ref_consumption": "Consumo reale",
            "ref_fuel_price": "Prezzo carburante", "ref_fuel_price_entity": "Sensore prezzo carburante (es. Tankerkönig, facoltativo)",
            "old_car_sale_price": "Prezzo di vendita della vecchia auto",
            "new_tax": "Nuova auto: bollo / anno", "new_insurance": "Nuova auto: assicurazione / anno", "new_maintenance": "Nuova auto: manutenzione / anno",
            "ref_tax": "Vecchia auto: bollo / anno", "ref_insurance": "Vecchia auto: assicurazione / anno", "ref_maintenance": "Vecchia auto: manutenzione / anno",
        },
        "fuel": {"diesel": "Diesel", "petrol": "Benzina", "lpg": "GPL", "cng": "Metano"},
        "location": {"home": "Casa", "public": "Colonnina / scontrino"},
        "sensors": {
            "km_driven": "Km percorsi", "fuel_liters": "Litri benzina", "electricity_kwh": "kWh corrente",
            "fuel_cost": "Spesa benzina", "electricity_cost": "Spesa corrente", "energy_cost": "Spesa energia",
            "reference_cost": "Spesa vecchia auto (stessi km)", "energy_savings": "Risparmio carburante",
            "fixed_cost_savings": "Risparmio costi fissi", "total_savings": "Risparmio totale",
            "savings_per_month": "Risparmio al mese", "investment": "Investimento",
            "cost_per_100km": "Costo per 100 km", "reference_cost_per_100km": "Costo vecchia auto per 100 km",
            "avg_fuel_consumption": "Consumo medio benzina", "amortization": "Ammortizzato",
            "break_even_date": "Data di pareggio",
        },
        "services": {
            "add_refuel": ("Aggiungi rifornimento", "Registra un rifornimento della nuova auto."),
            "add_charge": ("Aggiungi ricarica", "Registra una ricarica. Senza costo, a casa usa il prezzo della corrente di casa."),
            "delete_entry": ("Elimina voce", "Elimina una voce dal registro (e la foto dello scontrino)."),
            "update_entry": ("Modifica voce", "Cambia i campi di una voce del registro."),
            "scan_receipt": ("Leggi scontrino", "Legge uno scontrino di carburante o ricarica da una foto con AI Task."),
        },
        "sfields": {
            "config_entry_id": ("Auto", "Serve solo se segui più di un'auto."),
            "liters": ("Litri", "Litri di carburante."), "kwh": ("kWh", "Energia caricata."),
            "total_cost": ("Costo totale", "Importo pagato in euro."), "odometer": ("Km", "Km del contachilometri (facoltativo)."),
            "date": ("Data", "Data del rifornimento/ricarica (predefinito oggi)."), "station": ("Distributore", "Distributore o gestore."),
            "note": ("Nota", "Testo libero."), "location": ("Luogo", "Dove hai ricaricato."),
            "entry_id": ("ID voce", "ID della voce del registro."), "image": ("Foto", "Foto dello scontrino."),
            "auto_add": ("Aggiungi in automatico", "Aggiunge la voce se lo scontrino è stato letto completamente."),
        },
        "errors": {
            "entry_not_found": "Costi Auto: auto non trovata.",
            "entry_required": "Costi Auto: ci sono più auto, scegli quale.",
            "log_entry_not_found": "Costi Auto: voce del registro non trovata.",
        },
    },
    "de": {
        "steps": {
            "user": ("Dein neues Auto", "Kaufdaten. Die Investition ist Kaufpreis + Nebenkosten − Verkaufserlös des alten Autos."),
            "energy": ("Strom und Belege", "Optional: der Energiesensor der Steckdose/Wallbox zum Laden zu Hause und die AI-Task-Entität, die Belegfotos liest."),
            "reference": ("Vergleichsauto", "Das alte Auto: für jeden gefahrenen km berechnet Car Costs, was es an Kraftstoff gekostet hätte."),
            "fixed": ("Jährliche Fixkosten", "Kfz-Steuer, Versicherung und Wartung pro Jahr für beide Autos. 0 lassen, wenn nicht verglichen werden soll."),
        },
        "fields": {
            "name": "Name des neuen Autos", "purchase_price": "Kaufpreis", "extra_investment": "Nebenkosten (Wallbox, Zulassung…)",
            "start_date": "Startdatum (Übergabe)", "start_odometer": "Km-Stand bei Übergabe (0 = erster Sensorwert)",
            "odometer_entity": "Kilometerstand-Sensor (z. B. MySkoda)", "electricity_price": "Strompreis zu Hause",
            "electricity_price_entity": "Strompreis-Sensor (optional, ersetzt den Preis)",
            "home_energy_entity": "Energiesensor Laden zu Hause (kWh)", "ai_task_entity": "AI Task für Belegfotos",
            "ev_consumption": "Stromverbrauch (kWh/100 km) – für die Schätzung der elektrischen km, optional",
            "ref_name": "Name des alten Autos", "ref_fuel": "Kraftstoff", "ref_consumption": "Realer Verbrauch",
            "ref_fuel_price": "Kraftstoffpreis", "ref_fuel_price_entity": "Kraftstoffpreis-Sensor (z. B. Tankerkönig, optional)",
            "old_car_sale_price": "Verkaufspreis des alten Autos",
            "new_tax": "Neues Auto: Kfz-Steuer / Jahr", "new_insurance": "Neues Auto: Versicherung / Jahr", "new_maintenance": "Neues Auto: Wartung / Jahr",
            "ref_tax": "Altes Auto: Kfz-Steuer / Jahr", "ref_insurance": "Altes Auto: Versicherung / Jahr", "ref_maintenance": "Altes Auto: Wartung / Jahr",
        },
        "fuel": {"diesel": "Diesel", "petrol": "Benzin", "lpg": "Autogas", "cng": "Erdgas"},
        "location": {"home": "Zu Hause", "public": "Öffentlich / Beleg"},
        "sensors": {
            "km_driven": "Gefahrene km", "fuel_liters": "Liter Kraftstoff", "electricity_kwh": "Strom kWh",
            "fuel_cost": "Kraftstoffkosten", "electricity_cost": "Stromkosten", "energy_cost": "Energiekosten",
            "reference_cost": "Kosten altes Auto (gleiche km)", "energy_savings": "Ersparnis Energie",
            "fixed_cost_savings": "Ersparnis Fixkosten", "total_savings": "Ersparnis gesamt",
            "savings_per_month": "Ersparnis pro Monat", "investment": "Investition",
            "cost_per_100km": "Kosten pro 100 km", "reference_cost_per_100km": "Altes Auto pro 100 km",
            "avg_fuel_consumption": "Durchschnittsverbrauch", "amortization": "Amortisiert",
            "break_even_date": "Break-even-Datum",
        },
        "services": {
            "add_refuel": ("Tankvorgang hinzufügen", "Einen Tankvorgang des neuen Autos erfassen."),
            "add_charge": ("Ladevorgang hinzufügen", "Einen Ladevorgang erfassen. Ohne Kosten wird zu Hause der Strompreis verwendet."),
            "delete_entry": ("Eintrag löschen", "Einen Eintrag aus dem Protokoll löschen (samt Belegfoto)."),
            "update_entry": ("Eintrag bearbeiten", "Felder eines Eintrags im Protokoll ändern."),
            "scan_receipt": ("Beleg scannen", "Einen Tank- oder Ladebeleg per Foto mit AI Task lesen."),
        },
        "sfields": {
            "config_entry_id": ("Auto", "Nur nötig, wenn mehrere Autos erfasst werden."),
            "liters": ("Liter", "Liter Kraftstoff."), "kwh": ("kWh", "Geladene Energie."),
            "total_cost": ("Gesamtkosten", "Bezahlter Betrag in Euro."), "odometer": ("Km-Stand", "Kilometerstand (optional)."),
            "date": ("Datum", "Datum (Standard heute)."), "station": ("Tankstelle", "Tankstelle oder Anbieter."),
            "note": ("Notiz", "Freitext."), "location": ("Ort", "Wo geladen wurde."),
            "entry_id": ("Eintrags-ID", "ID des Eintrags."), "image": ("Foto", "Foto des Belegs."),
            "auto_add": ("Automatisch hinzufügen", "Eintrag hinzufügen, wenn der Beleg vollständig gelesen wurde."),
        },
        "errors": {
            "entry_not_found": "Car Costs: Auto nicht gefunden.",
            "entry_required": "Car Costs: mehrere Autos eingerichtet, bitte eines wählen.",
            "log_entry_not_found": "Car Costs: Eintrag nicht gefunden.",
        },
    },
}

FIELDS_BY_STEP = {
    "user": ["name", "purchase_price", "extra_investment", "start_date", "start_odometer", "odometer_entity"],
    "energy": ["electricity_price", "electricity_price_entity", "home_energy_entity", "ev_consumption", "ai_task_entity"],
    "reference": ["ref_name", "ref_fuel", "ref_consumption", "ref_fuel_price", "ref_fuel_price_entity", "old_car_sale_price"],
    "fixed": ["new_tax", "new_insurance", "new_maintenance", "ref_tax", "ref_insurance", "ref_maintenance"],
}
SERVICE_FIELDS = {
    "add_refuel": ["config_entry_id", "liters", "total_cost", "odometer", "date", "station", "note", "image"],
    "add_charge": ["config_entry_id", "kwh", "total_cost", "location", "odometer", "date", "station", "note", "image"],
    "delete_entry": ["config_entry_id", "entry_id"],
    "update_entry": ["config_entry_id", "entry_id", "liters", "kwh", "total_cost", "location", "odometer", "date", "station", "note", "image"],
    "scan_receipt": ["config_entry_id", "image", "auto_add"],
}


def build(t: dict) -> dict:
    def step(sid: str, flow_sid: str) -> dict:
        title, desc = t["steps"][sid]
        return {"title": title, "description": desc, "data": {f: t["fields"][f] for f in FIELDS_BY_STEP[sid]}}

    config_steps = {s: step(s, s) for s in FIELDS_BY_STEP}
    options_steps = {("init" if s == "user" else s): step(s, s) for s in FIELDS_BY_STEP}
    return {
        "config": {"step": config_steps},
        "options": {"step": options_steps},
        "selector": {
            "fuel": {"options": t["fuel"]},
            "location": {"options": t["location"]},
        },
        "entity": {"sensor": {k: {"name": v} for k, v in t["sensors"].items()}},
        "services": {
            sid: {
                "name": t["services"][sid][0],
                "description": t["services"][sid][1],
                "fields": {f: {"name": t["sfields"][f][0], "description": t["sfields"][f][1]} for f in fields},
            }
            for sid, fields in SERVICE_FIELDS.items()
        },
        "exceptions": {k: {"message": v} for k, v in t["errors"].items()},
    }


(OUT / "translations").mkdir(exist_ok=True)
for lang, t in T.items():
    (OUT / "translations" / f"{lang}.json").write_text(json.dumps(build(t), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
(OUT / "strings.json").write_text(json.dumps(build(T["en"]), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("ok")
