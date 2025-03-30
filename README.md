# TeslaBLE_Regulator
Regolazione automatica della ricarica della Tesla tramite BLE di una ESP32

### Regole per il Controllo Intelligente della Ricarica Tesla via Energia Solare

---

🌟 **Obiettivo**

Utilizzare dinamicamente la sovrapproduzione solare per alimentare la ricarica Tesla tramite BLE con ESP32 collegata ad Home Assistant, massimizzando l'autoconsumo e regolando la corrente di ricarica.

Obiettivi specifici:

- Evitare prelievi superiori a 250 W dalla rete durante la ricarica sopra il limite di riserva (`CHARGE_LIMIT_SOC`, default al 70%).
- Prevenire superamenti dei 3500 W per evitare interventi degli interruttori magnetotermici.

---

#### 🛁 **Input via MQTT**

##### 🟠 **Shelly EM (produzione/consumo)**

- **Topic:** `shellies/shellyem-C45BBEE1F292/emeter/0/energy`
  - **Descrizione:** misura la potenza attiva sulla rete elettrica
  - **Formato:** Watt (positivo = consumo, negativo = sovrapproduzione)

##### 🗾 **TeslaMate (stato Tesla)**

- **Topic:** `teslamate/cars/1/plugged_in`
  - **Descrizione:** stato collegamento wallbox
  - **Formato:** booleano

- **Topic:** `teslamate/cars/1/charge_current_request`
  - **Descrizione:** corrente richiesta Tesla
  - **Formato:** Ampere

- **Topic:** `teslamate/cars/1/charge_limit_soc`
  - **Descrizione:** limite massimo di ricarica
  - **Formato:** %

- **Topic:** `teslamate/cars/1/battery_level`
  - **Descrizione:** livello attuale della batteria
  - **Formato:** %

- **Topic:** `mqtt/Tesla/Ricarica Automatica`
  - **Descrizione:** ricarica automatica abilitata/disabilitata
  - **Formato:** booleano

---

#### 🔋 **Output: Controllo Home Assistant**

- **HA\_Tesla\_Ampere:** `number.tesla_ble_498658_charging_amps` → corrente ricarica
- **HA\_Tesla\_ChrgSwitch:** `switch.tesla_ble_498658_charger_switch` → on/off ricarica
- **HA\_Tesla\_ChrgLimit:** `number.tesla_ble_498658_charging_limit` → limite % ricarica

---

### ⚖️ **Parametri di Controllo**

| Parametro               | Valore | Descrizione                              |
| ----------------------- | ------ | ---------------------------------------- |
| `POTENZA_SICUREZZA_MAX` | 3500   | Limite massimo potenza per sicurezza (W) |
| `AMP_MIN`               | 5      | Corrente minima impostabile (A)          |
| `AMP_MAX`               | 32     | Corrente massima impostabile (A)         |
| `VOLT`                  | 230    | Tensione nominale (V)                    |
| `WATT_TOLLERANZA`       | 250    | Consumo massimo accettato dalla rete (W) |
| `MODIFICA_STEP`         | 1      | Step incremento/decremento corrente (A)  |
| `DELAY_SECONDI`         | 15     | Attesa minima tra regolazioni (s)        |
| `CHARGE_LIMIT_SOC`      | 70     | Soglia minima % riserva energetica       |
| `POTENZA_CARICA_MINIMA` | 1800   | Potenza massima emergenza sotto SOC (W)  |

---

### ♻️ **Logica di Regolazione Dinamica**

#### 🔻 \*\*Ricarica sotto la soglia di sicurezza (CHARGE\_LIMIT\_SOC)

• Quando il livello di carica è inferiore alla soglia CHARGE\_LIMIT\_SOC, l'obiettivo è garantire il raggiungimento minimo della riserva energetica.&#x20;

• In questa fase, la ricarica può essere effettuata anche in assenza di sovrapproduzione, ma senza superare un limite di potenza stabilito.&#x20;

• Il parametro di riferimento sarà:&#x20;

POTENZA\_CARICA\_MINIMA → massimo valore ammesso in Watt per ricarica di emergenza

| **Potenza Totale**                                    | **Azione**                                         |
| ----------------------------------------------------- | -------------------------------------------------- |
| ≤ `POTENZA_CARICA_MINIMA`                             | Mantenere/aumentare corrente di 1 A (entro limite) |
| > `POTENZA_CARICA_MINIMA` e ≤ `POTENZA_SICUREZZA_MAX` | Ridurre corrente di 1 A                            |
| > `POTENZA_SICUREZZA_MAX`                             | Arrestare immediatamente la ricarica               |

#### ☀️ Ricarica sopra la soglia di sicurezza (SOC)\*\*



| **Bilancio Energetico**                      | **Azione**                            |
| -------------------------------------------- | ------------------------------------- |
| Sovrapproduzione > 250 W (bilancio < -250 W) | Aumentare corrente di ricarica di 1 A |
| Consumo da rete > 250 W (bilancio > +250 W)  | Diminuire corrente di ricarica di 1 A |
| Bilancio tra -250 W e +250 W                 | Mantenere corrente invariata          |
| Potenza Totale > `POTENZA_SICUREZZA_MAX`     | Arrestare immediatamente la ricarica  |

Il bilancio è calcolato come:

```
bilancio = potenza_mqtt + (corrente_attuale * 230)
```

---

### ⛔️ **Limiti di Sicurezza**

- Corrente sempre tra 5 A e 32 A
- Nessuna modifica se il valore è invariato
- Attesa minima di 15 secondi tra modifiche

---

### 🧠 **Estensioni Future**

- Arresto ricarica sotto 5 A disponibili
- Gestione `switch.tesla_ble_498658_charger_switch`
- Logging continuo dati
- Predizione dinamica produzione solare

