# TransistorLoreCSV

Extracts all narrative text from [Transistor](https://store.steampowered.com/app/237930/Transistor/) and writes it to a single structured CSV — every trace bio, voiceline, scannable, news post, function description, and enemy entry, tagged by category, speaker, and earliest accessible location.

Built mostly with AI, for the purposes of the "AI Fluency" course hosted at https://anthropic.skilljar.com/ai-fluency-framework-foundations

## Prerequisites

- Python 3.10+
- Transistor installed via Steam
- [`vdf`](https://pypi.org/project/vdf/) (`pip install vdf`)

## Usage

```bash
python3 extract.py
```

Output: `transistor_lore.csv` (3 170 rows across 7 categories)

```
Wrote 3170 rows to transistor_lore.csv
  1893  voiceline
   731  scannable
   197  function_upgrade
   165  news_post
    64  trace_bio
    64  function_description
    56  enemy_lore
```

## CSV schema

| Column | Description |
|---|---|
| `id` | Source asset ID from `HelpText.en.xml` or subtitle CSV |
| `category` | `trace_bio` · `function_description` · `function_upgrade` · `voiceline` · `scannable` · `news_post` · `enemy_lore` |
| `function` | Internal weapon/function name (e.g. `Blink`, `Slam`) — populated for function rows only |
| `function_display` | In-game display name (e.g. `Jaunt()`, `Crash()`) |
| `speaker` | `The Transistor` · `Red` · `Asher` · `Royce` · `Sybil` · `Cloudbank Feed` |
| `area` | Human-readable area name (e.g. `The Canals`, `Bracket Towers`) |
| `earliest_level` | Earliest level key where this text is accessible (e.g. `Welcome01`, `Rooftops02`) |
| `flags` | Pipe-separated tags: `alt` (alternate line), `emote` (non-verbal), `procedural` (upgrade variant) |
| `trigger` | How the line fires: `interact` · `proximity` · `area` · `combat` · `level_load` · `enemy_death` · `card` · `menu` · `timed` |
| `scene_key` | `HelpTextId` of the scannable object that triggers this voiceline (when applicable) |
| `text` | Cleaned narrative text; multi-paragraph entries use real newlines |

Rows are sorted by `earliest_level` (game progression order), then by category, then by `id`.

## Example rows

**Trace bio** — the four bio fragments for Jaunt() / `Blink`:
```
id              category    function  function_display  speaker          area          earliest_level
Blink_Bio       trace_bio   Blink     Jaunt()           The Transistor   The Goldwalk  Welcome01
Blink_Bio_2     trace_bio   Blink     Jaunt()           The Transistor   The Goldwalk  Welcome01
Blink_Bio_3     trace_bio   Blink     Jaunt()           The Transistor   The Goldwalk  Welcome01
Blink_Bio_4     trace_bio   Blink     Jaunt()           The Transistor   The Goldwalk  Welcome01
```

**Function description** — what the Transistor says about an ability:
```
id    category              speaker          area          earliest_level  text
Blink function_description  The Transistor   The Goldwalk  Welcome01       Transport User to nearby location directly ahead.
```

**Voiceline** — scripted dialogue with trigger context:
```
id        category   speaker  area             earliest_level  trigger  text
Asher_2a  voiceline  Asher    Bracket Towers   Rooftops01      area     It's really you. Come all this way.
```

**Scannable** — world object text:
```
id             category   speaker          area          earliest_level  text
Story_00       scannable  The Transistor   The Goldwalk  Welcome01       Last night
```

**News post** — Cloudbank Feed headlines and articles:
```
id                          category   speaker          area          earliest_level
GoldwalkFoodOrder_Header1   news_post  Cloudbank Feed   The Goldwalk  Goldwalk01
```

## Level progression order

Rows respect the canonical in-game level sequence:

```
Welcome01 → Goldwalk01 → Goldwalk03 → Stage01 → Stage02 → Doors01 →
Canals01 → Elevators01 → Monster01 → Rooftops01–04 →
ReturnToStage01 → ReturnToGoldwalk01 → ReturnToWelcome01 →
Fairview01 → Showdown01 → Farewell01
```

Non-progression areas (`Flashback01`, `Glider01`, `Cycle01`) appear at the end.

## License

See [LICENSE](LICENSE).
