# tesla_charging_control.py

import logging
import os
from logging.handlers import TimedRotatingFileHandler
from datetime import datetime, timedelta

# === Configurazione MQTT ===
MQTT_BROKER = "192.168.xxx.xxx"
MQTT_PORT = 1883

# === MQTT Topics da sottoscrivere ===

TOPIC_TESLA_STATE = "teslamate/cars/1/charging_state"
TOPIC_TESLA_SOC = "teslamate/cars/1/battery_level"
TOPIC_SHELLY_POWER = "shellies/shellyem-1/emeter/0/power"
TOPIC_TESLA_PLUGGED = "teslamate/cars/1/plugged_in"
TOPIC_TESLA_CURRENT_REQ = "teslamate/cars/1/charge_current_request"
TOPIC_TESLA_SOC_LIMIT = "teslamate/cars/1/charge_limit_soc"
TOPIC_RICARICA_AUTOMATICA = "mqtt/Tesla/Ricarica Automatica"

# === Setup Logging ===
LOG_DIR = "c:\\PYTHON\\TESLA\\logs"
LOG_FILE = os.path.join(LOG_DIR, "tesla_charging.log")

# Create log directory if it doesn't exist
os.makedirs(LOG_DIR, exist_ok=True)

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Create timed rotating handler (daily at midnight, keep 15 days)
handler = TimedRotatingFileHandler(
    LOG_FILE,
    when="midnight",
    interval=1,
    backupCount=15
)
handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

# Add console logging
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(message)s'))
logger.addHandler(console_handler)

# Function to clean old logs
def clean_old_logs():
    now = datetime.now()
    for filename in os.listdir(LOG_DIR):
        if filename.endswith(".log"):
            filepath = os.path.join(LOG_DIR, filename)
            file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
            if now - file_time > timedelta(days=15):
                try:
                    os.remove(filepath)
                    logging.info(f"Removed old log file: {filename}")
                except Exception as e:
                    logging.error(f"Error removing log file {filename}: {e}")
# === Output Home Assistant ===
HA_URL = "http://192.168.xxx.xxx:8123"
HA_TOKEN = "HOME_ASSIST_TOKEN"
HA_HEADERS = {
    "Authorization": f"Bearer {HA_TOKEN}",
    "Content-Type": "application/json"
}
HA_TESLA_AMPERE = "number.tesla_ble_498658_charging_amps"
HA_TESLA_SWITCH = "switch.tesla_ble_498658_charger_switch"
HA_TESLA_CHRG_LIMIT = "number.tesla_ble_498658_charging_limit"

# === Parametri di controllo ===
POTENZA_SICUREZZA_MAX = 3500
POTENZA_CARICA_MINIMA = 1500 #1500W per la ricarica notturna fino al 70%
AMP_MIN = 5
AMP_MAX = 32
VOLT = 230
WATT_TOLLERANZA = 5
MODIFICA_STEP = 1
DELAY_SECONDI = 10
CHARGE_LIMIT_SOC = 70 #Limite di carica mandatoria 70%
CHARGE_LIMIT_MAX = 100 #Limite massimo di ricarica impostabile 100%
# === Stati di ricarica ===
CHARGING_STATE_STOPPED = "stopped"
CHARGING_STATE_CHARGING = "charging"
CHARGING_STATE_COMPLETE = "complete"
# === Variabili di stato ===
stato_ricarica = ""
soc_attuale = 0.0
potenza_mqtt = 0.0
plugged_in = False
charge_current_request = 0.0
soc_limit = 0.0
ricarica_automatica = False
ultima_modifica = 0
corrente_attuale = AMP_MIN

# === Callback MQTT ===
def on_connect(client, userdata, flags, rc):
    print("MQTT connesso con codice:", rc)
    client.subscribe([
        (TOPIC_TESLA_STATE, 0),
        (TOPIC_SHELLY_POWER, 0),
        (TOPIC_TESLA_PLUGGED, 0),
        (TOPIC_TESLA_CURRENT_REQ, 0),
        (TOPIC_TESLA_SOC_LIMIT, 0),
        (TOPIC_TESLA_SOC, 0),
        (TOPIC_RICARICA_AUTOMATICA, 0),
    ])

# === Funzioni di controllo ===
def send_ha_command(entity_id, service, value=None):
    """Helper function for Home Assistant API calls"""
    service_type = service.split('/')[0]
    try:
        data = {"entity_id": entity_id}
        if value is not None:
            data["value"] = value
            
        requests.post(
            f"{HA_URL}/api/services/{service}",
            headers=HA_HEADERS,
            json=data
        )
        return True
    except Exception as e:
        print(f"[ERRORE] Comando {service_type} fallito per {entity_id}: {e}")
        return False

def ricarica_fotovoltaico():
    global corrente_attuale, soc_limit, soc_attuale, stato_ricarica
    print(f"📊 Stato ➜ SOC: {soc_attuale}%, Limite: {soc_limit}%, Corrente: {corrente_attuale}A, Potenza: {potenza_mqtt}W, Stato: {stato_ricarica}")
    print("☀️ Modalità fotovoltaico attiva")
        
    if soc_limit != CHARGE_LIMIT_MAX:
        print(f"🔧 Limite di ricarica non impostato a {CHARGE_LIMIT_MAX}. Lo aggiorno...")
        if send_ha_command(HA_TESLA_CHRG_LIMIT, "number/set_value", CHARGE_LIMIT_MAX):
            soc_limit = CHARGE_LIMIT_MAX
            
    if stato_ricarica == CHARGING_STATE_STOPPED:
        print("🟢 Ricarica non attiva, invio comando di accensione...")
        if send_ha_command(HA_TESLA_SWITCH, "switch/turn_on"):
            # Aggiorniamo lo stato solo se il comando ha avuto successo
            stato_ricarica = CHARGING_STATE_CHARGING
        
    # Se stiamo assorbendo troppo dalla rete, riduciamo la corrente
    if potenza_mqtt > WATT_TOLLERANZA:
        if corrente_attuale > AMP_MIN:
            corrente_attuale = max(AMP_MIN, corrente_attuale - MODIFICA_STEP)
            print(f"⬇️ Riduzione corrente a {corrente_attuale}A (sopra tolleranza)")
            send_ha_command(HA_TESLA_AMPERE, "number/set_value", corrente_attuale)
        else:
            # Se siamo già al minimo e ancora assorbiamo troppo, fermiamo
            print("⚠️ Assorbimento eccessivo anche con corrente minima, arresto ricarica")
            arresta_ricarica("Assorbimento eccessivo in modalità fotovoltaico")
    # Se stiamo immettendo (potenza negativa) aumentiamo la corrente
    elif potenza_mqtt < -WATT_TOLLERANZA and corrente_attuale < AMP_MAX:
        # Calcoliamo quanto possiamo aumentare in base alla potenza disponibile
        potenza_disponibile = abs(potenza_mqtt) - WATT_TOLLERANZA
        step_possibili = int(potenza_disponibile / VOLT)
        step_da_applicare = min(MODIFICA_STEP, step_possibili)
        
        if step_da_applicare > 0:
            corrente_attuale = min(AMP_MAX, corrente_attuale + step_da_applicare)
            print(f"⬆️ Aumento corrente a {corrente_attuale}A (sovrapproduzione)")
            send_ha_command(HA_TESLA_AMPERE, "number/set_value", corrente_attuale)  

def arresta_ricarica(causa_arresto):
    global corrente_attuale, stato_ricarica
    #controllo stato prima del cambio
    #print(f"🔋 Arresto ricarica. Imposto corrente a {AMP_MIN}A.")
    if corrente_attuale != AMP_MIN:
        print("🛑 Imposto corrente minima a 0 A")
        if send_ha_command(HA_TESLA_AMPERE, "number/set_value", 0):    
            corrente_attuale = 0
    if stato_ricarica != CHARGING_STATE_STOPPED:
        print(f"🛑 Arresto la ricarica: {causa_arresto}" )
        if send_ha_command(HA_TESLA_SWITCH, "switch/turn_off"):
            stato_ricarica = CHARGING_STATE_STOPPED
    
def ricarica_prioritaria():
    global corrente_attuale, soc_limit, stato_ricarica, soc_attuale
    if soc_limit != CHARGE_LIMIT_SOC:
        if send_ha_command(HA_TESLA_CHRG_LIMIT, "number/set_value", CHARGE_LIMIT_SOC):
            soc_limit = CHARGE_LIMIT_SOC
            print(f"🔋 Limite carica impostato a {CHARGE_LIMIT_SOC}% .")
 
    if stato_ricarica == CHARGING_STATE_STOPPED:
        print("🟢 Ricarica non attiva in ricarica prioritaria, invio comando di accensione...")
        if send_ha_command(HA_TESLA_SWITCH, "switch/turn_on"):
            stato_ricarica = CHARGING_STATE_CHARGING
   
    print(f"⚙️ Modalità ricarica prioritaria: Bilancio={potenza_mqtt}W, Corrente={corrente_attuale}A")

    if potenza_mqtt > POTENZA_CARICA_MINIMA and corrente_attuale > AMP_MIN:
        corrente_attuale = max(AMP_MIN, corrente_attuale - MODIFICA_STEP)
        print(f"⬇️ Riduzione corrente a {corrente_attuale}A")
        send_ha_command(HA_TESLA_AMPERE, "number/set_value", corrente_attuale)  

    elif potenza_mqtt <= POTENZA_CARICA_MINIMA and corrente_attuale < AMP_MAX:
        potenza_nuova = potenza_mqtt + (VOLT * MODIFICA_STEP)
        print(f"Nuova potenza {potenza_nuova} - potenza_mqtt:{potenza_mqtt}")
        if potenza_nuova <= POTENZA_CARICA_MINIMA:
            corrente_attuale = min(AMP_MAX, corrente_attuale + MODIFICA_STEP)
            print(f"⬆️ Aumento corrente a {corrente_attuale}A")
            send_ha_command(HA_TESLA_AMPERE, "number/set_value", corrente_attuale)
    
def on_message(client, userdata, msg):
    global potenza_mqtt, plugged_in, charge_current_request, soc_limit, soc_attuale, ricarica_automatica, corrente_attuale, stato_ricarica
    
    topic = msg.topic
    payload = msg.payload.decode()

    try:
        if topic == TOPIC_SHELLY_POWER:
            potenza_mqtt = float(payload)
        elif topic == TOPIC_TESLA_PLUGGED:
            plugged_in = payload.lower() == "true"
        elif topic == TOPIC_TESLA_CURRENT_REQ:
            charge_current_request = float(payload)
        elif topic == TOPIC_TESLA_SOC_LIMIT:
            soc_limit = float(payload)
        elif topic == TOPIC_TESLA_SOC:
            soc_attuale = float(payload)
        elif topic == TOPIC_TESLA_STATE:
            stato_ricarica = payload.lower()
        elif topic == TOPIC_RICARICA_AUTOMATICA:
            ricarica_automatica = payload.lower() == "true"

        print(f"[MQTT] Stato aggiornato: W={potenza_mqtt}, Plug={plugged_in}, AReq={charge_current_request}, SOC={soc_limit}, SOC_NOW={soc_attuale}, Auto={ricarica_automatica}, on/off={stato_ricarica}")

        if topic == TOPIC_SHELLY_POWER and potenza_mqtt > POTENZA_SICUREZZA_MAX and stato_ricarica == CHARGING_STATE_CHARGING:
            print("🚨 Potenza oltre soglia di sicurezza! Corrente forzata a 5A e spegnimento")
            corrente_attuale = AMP_MIN
            send_ha_command(HA_TESLA_AMPERE, "number/set_value", AMP_MIN) 
            arresta_ricarica("🚨 PERICOLO!!! Potenza oltre soglia di sicurezza 🚨 🚨 🚨 ")
    except ValueError:
        print(f"[ERRORE] Payload non valido per {topic}: {payload}")

# === Avvio del client MQTT ===
client = mqtt.Client()
client.on_connect = on_connect
client.on_message = on_message
client.connect(MQTT_BROKER, MQTT_PORT, 60)

try:
    logging.info(f"MQTT connesso con codice: {rc}")
    # Call clean_old_logs at startup
    clean_old_logs()
    client.loop_start()
    while True:
        # Controllo di sicurezza
        if potenza_mqtt >= POTENZA_SICUREZZA_MAX: 
            print(f"PERICOLO!!! Potenza oltre soglia di sicurezza 🚨 🚨 🚨 W attuali: {potenza_mqtt}")
            arresta_ricarica("PERICOLO!!! Potenza oltre soglia di sicurezza")
            time.sleep(DELAY_SECONDI*12)
            continue
            
        # Controlli preliminari
        if not ricarica_automatica:
            print("⚙️ Ricarica automatica disattivata. Nessuna regolazione eseguita.")
            arresta_ricarica("Disattivazione manuale")
            time.sleep(DELAY_SECONDI)
            continue
            
        if not plugged_in:
            print("🔌 Cavo scollegato. Nessuna regolazione necessaria.")
            arresta_ricarica("Cavo scollegato")
            time.sleep(DELAY_SECONDI)
            continue
            
        if soc_attuale >= 100 and stato_ricarica == CHARGING_STATE_CHARGING:
            arresta_ricarica("Carica completa 100%")
            time.sleep(DELAY_SECONDI)
            continue
            
        # Logica di ricarica
        charge_power = charge_current_request * VOLT
        surplus_fotovoltaico = potenza_mqtt - charge_power < -1500
        
        if soc_attuale < CHARGE_LIMIT_SOC:
            # Priorità alla ricarica fino al limite minimo
            ricarica_prioritaria()
        elif soc_attuale < CHARGE_LIMIT_MAX and surplus_fotovoltaico:
            # Sopra il limite minimo ma sotto il massimo e c'è surplus fotovoltaico
            ricarica_fotovoltaico()
        else:
            # Nessuna condizione soddisfatta, fermiamo la ricarica
            arresta_ricarica("Carica non necessaria")
        time.sleep(DELAY_SECONDI)
except KeyboardInterrupt:
    print("Interrotto da tastiera.")
    client.loop_stop()
    client.disconnect()
