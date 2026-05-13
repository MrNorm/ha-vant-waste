# Havant Borough Waste Collection — Home Assistant integration

A custom Home Assistant integration that surfaces your bin collection
schedule from [waste.havant.gov.uk](https://waste.havant.gov.uk) as sensors.

Despite the repo name, this is a **custom integration** (HACS-installable),
not a Supervisor add-on. Works on Home Assistant Container, Core, OS and
Supervised installations.

## What you get

One service-style device with these entities (names will match your
account's actual bins):

| Entity | State | Notes |
| --- | --- | --- |
| `sensor.havant_waste_collection_next_collection` | Date of the next collection across all bins | Attributes include `type`, `status`, `days_until`, `is_today`, plus a list of the next 10 upcoming collections |
| `sensor.havant_waste_collection_next_residual_240l` | Date of next residual collection | Per-type sensor, one for each bin your account has |
| `sensor.havant_waste_collection_next_recycling_240l` | Date of next recycling | |
| `sensor.havant_waste_collection_next_garden_240l` | Date of next garden waste | Only created if your account has it |
| `sensor.havant_waste_collection_next_food_caddy_23l` | Date of next food caddy | |

Each sensor exposes the council's `status` value (e.g. `Not Started`,
`Closed-Complete`), so you can build automations like "if the next
collection is today and not yet completed, send me a reminder."

## Credentials & security

- Credentials are entered through Home Assistant's **config flow** UI.
- They are stored in HA's encrypted `.storage`, **not in this repository
  or in any YAML file**.
- The integration polls every 6 hours over HTTPS. No data leaves your HA
  instance other than the login request itself.

## Installation

### Via HACS (recommended)

1. HACS → Integrations → ⋮ → *Custom repositories*.
2. Add this repo's URL, category *Integration*.
3. Install **Havant Borough Waste Collection**.
4. Restart Home Assistant.
5. Settings → Devices & Services → *Add Integration* → search **Havant**.
6. Enter the email and password you use at [waste.havant.gov.uk](https://waste.havant.gov.uk).

### Manually

1. Copy `custom_components/havant_waste/` into your HA `config/custom_components/` directory.
2. Restart HA, then add the integration from the UI as above.

## Example automation

```yaml
automation:
  - alias: "Bin day reminder"
    triggers:
      - trigger: time
        at: "19:00:00"
    conditions:
      - condition: template
        value_template: "{{ state_attr('sensor.havant_waste_collection_next_collection', 'days_until') == 1 }}"
    actions:
      - action: notify.mobile_app
        data:
          title: "Bins out tomorrow"
          message: >
            {{ state_attr('sensor.havant_waste_collection_next_collection', 'type') }}
            ({{ states('sensor.havant_waste_collection_next_collection') }})
```

## Development

A live recon and end-to-end smoke test is included under `scripts/`.
Create a `.env` file (already gitignored) with:

```
HAVANT_USERNAME=you@example.com
HAVANT_PASSWORD=your-password
```

Then:

```
python3 scripts/recon.py            # raw event JSON + waste-type discovery
python3 scripts/smoke_integration.py  # exercises the API client end-to-end
```

The `scripts/` directory is intentionally outside `custom_components/` so
it does not ship with the integration.

## Caveats

- The schedule data is scraped from a JavaScript blob on the landing
  page. If the council ever changes their page template the regex in
  `api.py` may need updating — the `scripts/recon.py` probe will tell
  you what changed.
- "BIN NOT OUT" advisory events from the council are filtered out;
  only real collection jobs become sensor state.
- Not affiliated with or endorsed by Havant Borough Council.
