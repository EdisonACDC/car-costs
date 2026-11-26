"""Constants for Car Costs."""

from __future__ import annotations

DOMAIN = "car_costs"
VERSION = "0.3.0b3"

STORAGE_VERSION = 1

# One snapshot per day, kept for five years.
HISTORY_MAX_DAYS = 5 * 366

# --- new car -------------------------------------------------------------
CONF_NAME = "name"
CONF_PURCHASE_PRICE = "purchase_price"
CONF_EXTRA_INVESTMENT = "extra_investment"
CONF_START_DATE = "start_date"
CONF_START_ODOMETER = "start_odometer"
CONF_ODOMETER_ENTITY = "odometer_entity"
CONF_SHOW_PANEL = "show_panel"
CONF_HOME_ENERGY_ENTITY = "home_energy_entity"
CONF_ELECTRICITY_PRICE = "electricity_price"
CONF_ELECTRICITY_PRICE_ENTITY = "electricity_price_entity"
CONF_AI_TASK_ENTITY = "ai_task_entity"
CONF_EV_CONSUMPTION = "ev_consumption"

# --- reference (old) car -------------------------------------------------
CONF_REF_NAME = "ref_name"
CONF_REF_FUEL = "ref_fuel"
CONF_REF_CONSUMPTION = "ref_consumption"
CONF_REF_FUEL_PRICE = "ref_fuel_price"
CONF_REF_FUEL_PRICE_ENTITY = "ref_fuel_price_entity"
CONF_OLD_CAR_SALE_PRICE = "old_car_sale_price"

# --- yearly fixed costs --------------------------------------------------
CONF_NEW_TAX = "new_tax"
CONF_NEW_INSURANCE = "new_insurance"
CONF_NEW_MAINTENANCE = "new_maintenance"
CONF_REF_TAX = "ref_tax"
CONF_REF_INSURANCE = "ref_insurance"
CONF_REF_MAINTENANCE = "ref_maintenance"

FUEL_TYPES = ["diesel", "petrol", "lpg", "cng"]

DEFAULTS = {
    CONF_NAME: "Skoda Kodiaq iV",
    CONF_PURCHASE_PRICE: 0.0,
    CONF_EXTRA_INVESTMENT: 0.0,
    CONF_START_ODOMETER: 0.0,
    CONF_ELECTRICITY_PRICE: 0.32,
    CONF_REF_NAME: "VW Passat B8",
    CONF_REF_FUEL: "diesel",
    CONF_REF_CONSUMPTION: 5.8,
    CONF_REF_FUEL_PRICE: 1.65,
    CONF_OLD_CAR_SALE_PRICE: 0.0,
    CONF_NEW_TAX: 0.0,
    CONF_NEW_INSURANCE: 0.0,
    CONF_NEW_MAINTENANCE: 0.0,
    CONF_REF_TAX: 0.0,
    CONF_REF_INSURANCE: 0.0,
    CONF_REF_MAINTENANCE: 0.0,
}

# --- log entries ---------------------------------------------------------
KIND_REFUEL = "refuel"
KIND_CHARGE = "charge"
LOCATION_HOME = "home"
LOCATION_PUBLIC = "public"
SOURCE_MANUAL = "manual"
SOURCE_RECEIPT = "receipt"

# --- services ------------------------------------------------------------
SERVICE_ADD_REFUEL = "add_refuel"
SERVICE_ADD_CHARGE = "add_charge"
SERVICE_DELETE_ENTRY = "delete_entry"
SERVICE_SCAN_RECEIPT = "scan_receipt"
SERVICE_UPDATE_ENTRY = "update_entry"

ATTR_CONFIG_ENTRY_ID = "config_entry_id"
ATTR_LITERS = "liters"
ATTR_KWH = "kwh"
ATTR_TOTAL_COST = "total_cost"
ATTR_ODOMETER = "odometer"
ATTR_DATE = "date"
ATTR_STATION = "station"
ATTR_NOTE = "note"
ATTR_LOCATION = "location"
ATTR_ENTRY_ID = "entry_id"
ATTR_IMAGE = "image"
ATTR_AUTO_ADD = "auto_add"

EVENT_UPDATED = f"{DOMAIN}_updated"
EVENT_RECEIPT_SCANNED = f"{DOMAIN}_receipt_scanned"

MEDIA_SUBDIR = "car_costs"
FRONTEND_URL = "/car_costs_static"
CARD_FILENAME = "car-costs-card.js"
PANEL_URL_PATH = "costi-auto"
PANEL_TITLE = "Costi Auto"
PANEL_ICON = "mdi:car-electric"
