#!/usr/bin/env python3
"""
Transistor lore extractor
Parses HelpText.en.xml and produces transistor_lore.csv with all narrative
text, tagged by category, speaker, and earliest accessible location.
"""

import csv
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

GAME = Path("/home/deck/.local/share/Steam/steamapps/common/Transistor/Content")
OUT  = Path("/home/deck/nix/home/Proj/TransistorLoreCSV/transistor_lore.csv")

# ── Canonical level order (from ProgressData.txt LevelProgression) ─────────────
LEVEL_ORDER = [
    "Welcome01",
    "Goldwalk01", "Goldwalk03",
    "Stage01", "Stage02",
    "Doors01",
    "Canals01",
    "Elevators01",
    "Monster01",
    "Rooftops01", "Rooftops02", "Rooftops03", "Rooftops04",
    "ReturnToStage01",
    "ReturnToGoldwalk01",
    "ReturnToWelcome01",
    "Fairview01",
    "Showdown01",
    "Farewell01",
    # non-progression but canonical
    "Flashback01",
    "Glider01",
    "Cycle01",
]
LEVEL_SORT  = {lvl: i for i, lvl in enumerate(LEVEL_ORDER)}

LEVEL_AREA = {
    "Welcome01":          "The Goldwalk",
    "Goldwalk01":         "The Goldwalk",
    "Goldwalk03":         "The Goldwalk",
    "Stage01":            "The Empty Set",
    "Stage02":            "The Empty Set",
    "Doors01":            "The Waterfront",
    "Canals01":           "The Canals",
    "Elevators01":        "The Spine",
    "Monster01":          "Bracket Towers",
    "Rooftops01":         "Bracket Towers",
    "Rooftops02":         "Bracket Towers",
    "Rooftops03":         "Bracket Towers",
    "Rooftops04":         "Bracket Towers",
    "ReturnToStage01":    "The Empty Set (Return)",
    "ReturnToGoldwalk01": "The Goldwalk (Return)",
    "ReturnToWelcome01":  "The Goldwalk (Return)",
    "Fairview01":         "Fairview",
    "Showdown01":         "The Cradle",
    "Farewell01":         "Farewell",
    "Flashback01":        "Memoriam",
    "Glider01":           "(Transit)",
    "Cycle01":            "(Transit)",
}

# ── Weapon earliest-access (from PlayerProgressScripts.txt socket analysis) ────
# Welcome01 has 1 socket  → Level 2  (Hide, Jumper first offered)
# Goldwalk01 has 3 sockets → Levels 3–5 (Charm/Bomb at L3, Summon at L4)
# Goldwalk03 has 1 socket → Level 6  (Sidearm, Hook first offered)
# Stage01 has 1 socket    → Level 7  (from pool)
# Canals01 has 4 sockets  → Levels 8–11 (Tracker/Uppercut L8, Might/Orb L9, Heal L11)
WEAPON_LEVEL = {
    "Slam":        "Welcome01",
    "Snipe":       "Welcome01",
    "Clusterbomb": "Welcome01",   # Spark() — ClusterbombGP is the starter variant alias
    "Blink":       "Welcome01",
    "Hide":        "Welcome01",   # Level 2, first socket = still Welcome01
    "Jumper":      "Welcome01",   # Level 2, first socket = still Welcome01
    "Charm":       "Goldwalk01",  # Level 3
    "Bomb":        "Goldwalk01",  # Level 3
    "Summon":      "Goldwalk01",  # Level 4
    "Sidearm":     "Goldwalk03",  # Level 6
    "Hook":        "Goldwalk03",  # Level 6
    "Tracker":     "Canals01",    # Level 8
    "Uppercut":    "Canals01",    # Level 8
    "Might":       "Canals01",    # Level 9
    "Orb":         "Canals01",    # Level 9
    "Heal":        "Canals01",    # Level 11
}
# ClusterbombGP is the starting variant of Clusterbomb; treat upgrades as Clusterbomb
WEAPON_ALIASES = {"ClusterbombGP": "Clusterbomb"}

ALL_WEAPON_NAMES = set(WEAPON_LEVEL.keys()) | set(WEAPON_ALIASES.keys())

# ── Compound lore prefixes (IDs that don't follow simple Level01_Xxx patterns) ──
# Maps prefix → (canonical level key, category)
# Sorted longest-first so we match the most specific prefix.
COMPOUND_LORE = {
    # Monster01
    "MonsterSymptomsList":           ("Monster01", "news_post"),
    "MonsterOutOfOrder":             ("Monster01", "scannable"),
    "GuideSpeakingText01":           ("Monster01", "scannable"),
    "GuideConversation01":           ("Monster01", "scannable"),
    # Fairview01
    "FairviewCamerataLab":           ("Fairview01", "scannable"),
    "FairviewTransistorOrigins":     ("Fairview01", "scannable"),
    "FairviewTransistorVictims":     ("Fairview01", "scannable"),
    "Fairview":                      ("Fairview01", "scannable"),   # catch-all for Fairview_*
    # Rooftops (treat all as Rooftops01 = earliest Rooftops area)
    "RooftopsAboutGrant":            ("Rooftops01", "scannable"),
    "RooftopsCamerataConfession":    ("Rooftops01", "scannable"),
    "RooftopsCamerataManifesto":     ("Rooftops01", "scannable"),
    "RooftopsFarewellFromAsher":     ("Rooftops01", "scannable"),
    "RooftopsMeetAsher":             ("Rooftops01", "scannable"),
    "RooftopsOverride1":             ("Rooftops01", "scannable"),
    "RooftopsOverride2":             ("Rooftops01", "scannable"),
    "RooftopsRogueProcess":          ("Rooftops01", "scannable"),
    "RooftopsTicker":                ("Rooftops01", "news_post"),
    "RooftopsWhyRed":                ("Rooftops01", "scannable"),
    # ReturnToGoldwalk01
    "ReturnToGoldwalkJansClosed":    ("ReturnToGoldwalk01", "scannable"),
    # ReturnToStage01
    "ReturnToStageObit":             ("ReturnToStage01", "news_post"),
    "ReturnToStageSignOff":          ("ReturnToStage01", "scannable"),
    # ReturnToWelcome01
    "ReturnToWelcomeAdminAccess":    ("ReturnToWelcome01", "scannable"),
    "ReturnToWelcomeBridgeToFairview": ("ReturnToWelcome01", "news_post"),
    "ReturnToWelcomeWeather":        ("ReturnToWelcome01", "news_post"),
    "ReturnToWelcomeTicker01":       ("ReturnToWelcome01", "news_post"),
    # Canals01
    "CanalsMissingTower":            ("Canals01", "news_post"),
    # Doors01
    "DoorsSportingEvent":            ("Doors01", "news_post"),
    # Elevators01
    "ElevatorsProcessSpreads":       ("Elevators01", "news_post"),
    "ElevatorsReloPoll":             ("Elevators01", "news_post"),
    # Stage01
    "StageTerminal":                 ("Stage01", "scannable"),
    "StageHeadliner":                ("Stage01", "news_post"),
    "StageIncident":                 ("Stage01", "news_post"),
    # Flashback01
    "FlashbackBridgeToFairview":     ("Flashback01", "news_post"),
    # Stage02
    "SybilDead01":                   ("Stage02", "scannable"),
    # Welcome01 (intro / global OVC)
    "Story":                         ("Welcome01", "scannable"),     # game intro text
    "LaunchText":                    ("Welcome01", "scannable"),
    "CamerataTerminal":              ("Rooftops01", "scannable"),
    # TestTerminal = climate poll terminal at the Empty Set
    "TestTerminalByline":            ("Stage01", "news_post"),
    "TestTerminal":                  ("Stage01", "scannable"),
    # GoldwalkFoodOrder / CanalsSkyColor / MonsterAttackStory already handled
    # but catch any missed variants here too
    "GoldwalkFoodOrder":             ("Goldwalk01", "news_post"),
    "CanalsSkyColor":                ("Canals01", "news_post"),
    "MonsterAttackStory":            ("Monster01", "news_post"),
    "Goldwalk03Offline":             ("Goldwalk03", "news_post"),
}
# Build sorted list (longest prefix first for greedy matching)
COMPOUND_LORE_SORTED = sorted(COMPOUND_LORE.keys(), key=lambda k: -len(k))

# TickerText01–07 approximate level mapping based on content chronology
TICKER_LEVEL_MAP = {
    "01": "Welcome01",
    "02": "Goldwalk01",
    "03": "Stage01",
    "04": "Canals01",
    "05": "Elevators01",
    "06": "Rooftops01",
    "07": "ReturnToGoldwalk01",
}

# ── Level ID prefix matching (standard Level01_Xxx IDs) ───────────────────────
# Sorted longest-first so Goldwalk03 beats Goldwalk, ReturnToGoldwalk01 beats Goldwalk
SIMPLE_LEVEL_PREFIXES = sorted([
    "ReturnToGoldwalk01", "ReturnToWelcome01", "ReturnToStage01", "ReturnToCycle01",
    "Goldwalk01", "Goldwalk03",
    "Rooftops01", "Rooftops02", "Rooftops03", "Rooftops04",
    "Flashback01", "Fairview01", "Farewell01", "Showdown01",
    "Elevators01", "Monster01", "Canals01", "Doors01",
    "Stage01", "Stage02",
    "Welcome01",
    "Glider01", "Cycle01",
    "Boat01",
    "Goldwalk",    # catch remaining Goldwalk_* without number
], key=lambda k: -len(k))

SANDBOX_PATTERN = re.compile(r"^Sandbox", re.I)

# ── Pure UI prefix patterns (exclude entirely) ─────────────────────────────────
# Any ID whose first segment matches these → UI
UI_START_PATTERNS = (
    "Focus_Info", "Focus_Limiter", "Focus_Meta", "Focus_Upgrade",
    "Hint_",
    "Title_",           # soundtrack track names shown in UI
    "Sandbox",          # extra modes
    "Info",             # inspect-screen UI
    "Terminal",         # generic OVC terminal UI labels
    "TerminalInfo",
    "CardBuyScreen", "HandScreen", "HandScreenSlot",
    "EnemyUpgradeScreen",
    "DamageEstimate",
    "InGameCredits",
    "InGameUI",
    "InspectScreen",
    "Mechanics",
    "Limiter_",
    "Egg_",
    "Meta_",
    "Socket_",
    "Slot",
    "MiscSettingsScreen",
    "SettingsScreen",
    "KeyMappingScreen",
    "GameEndScreen",
    "GameStartScreen",
    "GameExit",
    "GameDesc",
    "PauseMenu",
    "RestartConfirm",
    "ExitConfirm",
    "ProfileScreen",
    "Installer",
    "Error",
    "Save",
    "Storage",
    "Resolution",
    "Confirm",
    "Achievements",
    "Ach",
    "LoremIpsum",
    "StatusEffect",
    "Overkill",
    "LifeLost",
    "EnemyLevelUp",
    "EnemyUpgrade",
    "BoomboxInstructions",
    "FaceDownCard",
    "ControlScheme",
    "ResChange",
    "SignedInAs",
    "SignIn",
    "ProfileChange",
    "NoStorage",
    "promptFor",
    "forceCancel",
    "forceDisconnected",
    "SaveError",
    "SaveFile",
    "WarningSave",
    "Reselect",
    "Downloading",
    "WaitingForDownload",
    "DownloadContent",
    "MissingGamepad",
    "CertTesting",
    "TestStat",
    "TestLead",
    "TestManagers",
    "SoftwareTest",
    "SrLeads",
    "QA",
    "SupergiantGames",
    "Supergiant",
    "Special Thanks",
    "Acknowledgements",
    "Additional Credits",
    "AdditionalVoices",
    "VoiceActors",
    "LoremIpsum",
    "StartNewGame",
    "RestartConfirm",
    "ReturnToMainMenu",
    "EnterFinalMapSequence",
    "Shell_",
    "RevertResolution",
    "Reselect",
    "Fullscreen",
    "Vsync",
    "Localization",
    "SHARE",
    "START",
    "BACK",
    "OPTIONS",
    "Press START",
    "Prepare Yourself",
    "How to Play",
    "CycleLeft",
    "CycleRight",
    "Waypoint",
    "FightTime",
    "Objective",
    "Complete",
    "Completed",
    "CompletionTime",
    "Ready",
    "MapPresence",
    "WelcomePresence",
    "DoorsPresence",
    "CanalsPresence",
    "ElevatorsPresence",
    "RooftopsPresence",
    "FairviewPresence",
    "ShowdownPresence",
    "FlashbackPresence",
    "StagePresence",
    "MonsterPresence",
    "ReturnToPresence",
    "InactivePresence",
    "TravelPresence",
    "MenuPresence",
    "CombatPresence",
    "ProfileAlt",
    "ProfileDesc",
    "ProfileEmpty",
    "ProfileError",
    "ProfileSelect",
    "FriendAlt",
    "Trophies",
    "Friends",
    "Royce",
    "RoyceOverloads",
    "Locked",
    "Not ",
    "Empty ",
    "Loading",
    "DrawPreqreq",
    "Draw",
    "Card ",
    "Cards Left",
    "Toggle",
    "Stop",
    "Move",
    "Select",
    "Focus ",
    "Use ",
    "Open",
    "Undo",
    "Attack",
    "MoveUp",
    "MoveDown",
    "MoveLeft",
    "MoveRight",
    "Menu ",
    "Profile ",
    "Add",
    "Off",
    "On",
    "Ok",
    "Yes",
    "No ",
    "Next",
    "Confirm",
    "Cancel",
    "Back",
    "Exit",
    "Resume",
    "Restore",
    "Upgrade ",
    "BasePower",
    "WeaponType",
    "PlayerUpgradeType",
    "PlayerDopplewalk",
    "PlayerPartner",
    "PlayerPet",
    "PlayerExecute",
    "PetExecute",
    "DarkPlayer",
    "Idol",
    "BombExplode",
    "BombUnit",
    "HauntExplode",
    "Haunt ",
    "CombatOver",
    "Combo",
    "CharmMight",
    "CurseDamage",
    "HideBomb",
    "SlamStun",
    "BaseEgg",
    "VirusLock",
    "VirusPlant",
    "Thing",
    "Trace01",
    "Scanner ",
    "Linger",
    "InfoInstructionText",
    "MusicUnlockPrefix",
    "SoundtrackAvailable",
    "SpecialEgg",
    "BaysignMotorcycle",
    "BaysignTelescope",
    "BaysignTerminal",
    "GuideHitText",
    "GuideSpeak",
    "Beach",
    "HealthBar",
    "StaminaBar",
    "Heart01",
    "InteractInstructions",
    "InteractShield",
    "Invincible",
    "MetaUpgrade",
    "ModifiedDamage",
    "Purchase",
    "Settings",
    "Sign Out",
    "Boombox",
    "Card",
    "DAMAGE TAKEN",
    "DISTANCE",
    "EST.",
    "HATCH",
    "Display",
    "Gamepad",
    "GoldwalkPresence",
    "Graphics",
    "GuaranteedCrit",
    "Haunt",
    "Guide_",
    "Scanner",
    "EggUpgrader",
    "TickerText",   # handled separately below by number
    "Level ",
    "Info ",
    "Music and Audio",
    "Sound and Music",
    "Map Beautification",
    "DesignAndProduction",
    "GameplayEngineering",
    "SystemsEngineering",
    "Design and Writing",
    "Design ",
    "Engineering",
    "Animation",
    "Art ",
    "TechArt",
    "2DArt",
    "3DArt",
    "QA",
    "featuring",
    "or",
    "speciale",
    "specialo",
    "Amir", "Andrew", "Camilo", "Chris", "Darren",
    "Gavin", "Greg", "Jen", "Josh", "Logan",
    "Michael", "Morgan",
    "GameEndScreen",
    "TestTerminalABTest",
    "TestTerminalResult",
    "TestTerminalVote",
    "TestTerminalVoteConfirm",
    "TestTerminalVoteResult",
    "TestTerminalVoteShowResults",
    "Mechanics",
    "BeachPresence",
    "ArchonAttack",   # Kill() special mode — no bio, skip
    "RooftopsTicker01", "RooftopsTicker02", "RooftopsTicker03",
    "RooftopsTicker04", "RooftopsTicker05", "RooftopsTicker06",
    "RooftopsTicker07",
    "CombatPresence",
    "MapPresence",
    "FocusScreen",
    "StagePresence",
    "BeachPresence",
    "GliderPresence",
    "BoatPresence",
    "CyclePresence",
    "DoorsPresence",
    "ShowdownPresence",
    "FarewellPresence",
    "ReturnToStagePresence",
    "MonsterPresence",
    "BoomboxOff",
    "BoomboxOn",
)

# ── Subtitle file → level mapping ────────────────────────────────────────────
# Keys are subtitle CSV stems (filename without .csv).
# Values are (earliest_level, area_label).
# Speaker for all level-narration files is "The Transistor" (the Voice).
# Files omitted here are either skip targets or handled per-character.
SUBTITLE_LEVEL_MAP = {
    "Welcome01":        ("Welcome01",          "The Goldwalk"),
    "Goldwalk":         ("Goldwalk01",         "The Goldwalk"),
    "Stage":            ("Stage01",            "The Empty Set"),
    "Doors":            ("Doors01",            "The Waterfront"),
    "Canals":           ("Canals01",           "The Canals"),
    "Elevators":        ("Elevators01",        "The Spine"),
    "Monster":          ("Monster01",          "Bracket Towers"),
    "Rooftops":         ("Rooftops01",         "Bracket Towers"),
    "ReturnToStage":    ("ReturnToStage01",    "The Empty Set (Return)"),
    "ReturnToGoldwalk": ("ReturnToGoldwalk01", "The Goldwalk (Return)"),
    "ReturnToWelcome":  ("ReturnToWelcome01",  "The Goldwalk (Return)"),
    "Fairview":         ("Fairview01",         "Fairview"),
    "Farewell":         ("Farewell01",         "Farewell"),
    "Flashback":        ("Flashback01",        "Memoriam"),
    "Glider":           ("Glider01",           "(Transit)"),
    "Cycle01":          ("Cycle01",            "(Transit)"),
    "ReturnToCycle":    ("Cycle01",            "(Transit)"),
    # Boat cutscene plays just before Doors01 and is triggered in DoorsAudioScripts
    "Boat":             ("Doors01",            "The Waterfront"),
}

# Character subtitle files: stem → (speaker_name, fixed_level)
# Royce and Asher are omitted here — their levels vary by scene (see per-character functions).
SUBTITLE_CHARACTER_MAP = {
    "Sybil": ("Sybil", "Stage02"),
}

# Files to exclude from subtitle extraction entirely
SUBTITLE_SKIP = {"Miscellaneous", "Sandbox"}

# Root trigger type → human-readable label
TRIGGER_LABELS = {
    # Direct player interaction
    "OnUsed":            "interact",
    "OnControlPressed":  "interact",
    # Proximity (player walks near object)
    "OnPlayerDistance":     "proximity",
    "OnPlayerDistanceAny":  "proximity",
    # Named event (fired by terminals, cutscene scripts, world scripts)
    "OnTriggerFired":    "area",
    "OnFlagTrue":        "flag",
    "OnFlagFalse":       "flag",
    # Level / world lifecycle
    "OnLoad":            "level_load",
    "OnWorldLoad":       "level_load",
    "OnAnyLoad":         "level_load",
    # Enemy / object lifecycle
    "OnDestroy":         "enemy_death",
    "OnDestroyAny":      "enemy_death",
    "OnSpawn":           "enemy_spawn",
    # Combat events
    "OnHit":             "combat",
    "OnDamaged":         "combat",
    "OnWeaponFired":     "combat",
    "OnPlayerLifeLost":  "combat",
    "OnPlayerRevive":    "combat",
    "OnRecoveryBegin":   "combat",
    "OnFocusExecute":    "combat",
    "OnFocusRecovered":  "combat",
    "OnPerfectChargeShot":                    "combat",
    "OnProjectilePassedThroughStealthed":     "combat",
    # Card / function system
    "OnCardPlayed":      "card",
    "OnCardDrawn":       "card",
    "OnCardBought":      "card",
    # Menu / UI
    "OnMenuOpened":      "menu",
    "OnMenuClosed":      "menu",
    # Timed
    "OnTimer":           "timed",
}


def royce_level(sub_id: str) -> str:
    """Map a Royce (or RoyceLive) subtitle ID to its earliest level.

    Scene ranges derived from *AudioScripts.txt analysis:
      scenes 2–5  → ReturnToWelcome01  (truce calls + Fairview intro)
      scenes 6–32 → Fairview01         (Fairview monologues)
      scenes 33+  → Showdown01         (boss fight + aftermath)
    """
    m = re.match(r"^Royce(?:Live)?_(\d+)", sub_id)
    if not m:
        return "ReturnToWelcome01"
    scene = int(m.group(1))
    if scene <= 5:
        return "ReturnToWelcome01"
    if scene <= 32:
        return "Fairview01"
    return "Showdown01"


def asher_level(sub_id: str) -> str:
    """Map an Asher subtitle ID to its earliest level.

    Terminal placement derived from RooftopsAudioScripts.txt:
      scene 2      → Rooftops01  (intro terminal 40064, MeetAsherTerminalVO)
      scenes 4–5   → Rooftops01  (optional terminals 1–2: Manifesto, Confession)
      scenes 6–7   → Rooftops02  (optional terminals 3–4: Rogue Process, Why Red)
      scene 8      → Rooftops03  (optional terminal 5: About Grant)
      scenes 10–11 → Rooftops04  (farewell terminal, FarewellFromAsherMoreData)
    """
    m = re.match(r"^Asher_(\d+)", sub_id)
    if not m:
        return "Rooftops01"
    scene = int(m.group(1))
    if scene <= 5:
        return "Rooftops01"
    if scene <= 7:
        return "Rooftops02"
    if scene <= 9:
        return "Rooftops03"
    return "Rooftops04"


def load_vo_triggers() -> dict:
    """Parse all *AudioScripts.txt files and return a dict mapping VO IDs to
    their root trigger label (from TRIGGER_LABELS).  Chains of OnSoundComplete
    are traced back to the originating event type."""
    scripts_dir = GAME / "Scripts"
    trigger_map: dict = {}   # vo_id → (trigger_type, trigger_source)

    for path in sorted(scripts_dir.glob("*AudioScripts.txt")):
        with path.open() as f:
            content = f.read()

        current_type   = None
        current_source = ""
        brace_depth    = 0

        for line in content.split("\n"):
            stripped = line.strip()
            if stripped.startswith("--"):
                continue

            m = re.match(
                r"^(On\w+)\b\s*(.*?)(?:\s*;.*)?$",
                stripped,
            )
            if m:
                current_type   = m.group(1)
                current_source = m.group(2).strip()
                brace_depth    = 0

            brace_depth += stripped.count("{") - stripped.count("}")

            # Match PlaySpeech()/PlaySpeechOnce() direct calls
            # and speech-variable assignments (speech = "/VO/...")
            for pm in re.finditer(
                r'(?:PlaySpeech(?:Once)?\(\{\s*Name\s*=\s*|'
                r'\bspeech\w*\s*=\s*)'
                r'"/?VO/([^"]+)"',
                stripped,
            ):
                if current_type:
                    vo_id = pm.group(1)
                    if vo_id not in trigger_map:
                        trigger_map[vo_id] = (current_type, current_source)

    def get_root(vo_id: str, depth: int = 0) -> str:
        if depth > 20:
            return "unknown"
        info = trigger_map.get(vo_id)
        if not info:
            return ""
        ttype, tsource = info
        if ttype == "OnSoundComplete":
            src = re.sub(r"^/?VO/", "", tsource)
            return get_root(src, depth + 1)
        return TRIGGER_LABELS.get(ttype, ttype)

    return {vo_id: get_root(vo_id) for vo_id in trigger_map}


def load_scan_scene_keys() -> tuple[dict, set]:
    """Return (vo_to_scan, scan_hids_with_vos).

    vo_to_scan       : voiceline_id -> HelpTextId of the scannable that triggers it
                       (only OnUsed events — direct player examination)
    scan_hids_with_vos: set of HelpTextIds that have at least one linked voiceline
    """
    maps_dir    = GAME / "Maps"
    scripts_dir = GAME / "Scripts"

    # Build object_id (str) -> HelpTextId from all thing_text files
    obj_to_hid: dict = {}
    for path in sorted(maps_dir.glob("*.thing_text")):
        data = json.loads(path.read_text())
        for obj in data:
            hid = obj.get("HelpTextId") or ""
            oid = obj.get("Id")
            if hid and oid is not None:
                obj_to_hid[str(oid)] = hid

    # Parse AudioScripts: OnUsed(object_id) -> voiceline_id
    vo_to_scan: dict = {}
    for path in sorted(scripts_dir.glob("*AudioScripts.txt")):
        content      = path.read_text()
        current_type = None
        current_src  = ""
        for line in content.split("\n"):
            stripped = line.strip()
            if stripped.startswith("--"):
                continue
            m = re.match(r"^(On\w+)\b\s*(.*?)(?:\s*;.*)?$", stripped)
            if m:
                current_type = m.group(1)
                current_src  = m.group(2).strip()
            if current_type != "OnUsed":
                continue
            for sid in re.findall(r"\b(\d+)\b", current_src):
                hid = obj_to_hid.get(sid)
                if not hid:
                    continue
                for pm in re.finditer(
                    r'(?:PlaySpeech(?:Once)?\(\{\s*Name\s*=\s*|'
                    r'\bspeech\w*\s*=\s*)'
                    r'"/?VO/([^"]+)"',
                    stripped,
                ):
                    vo_id = pm.group(1)
                    if vo_id not in vo_to_scan:
                        vo_to_scan[vo_id] = hid

    scan_hids_with_vos = set(vo_to_scan.values())
    return vo_to_scan, scan_hids_with_vos


# ── Non-verbal emotes ─────────────────────────────────────────────────────────
# These have no subtitle text.  Columns: (id, speaker, earliest_level, trigger, text)
_EMOTE_DATA = [
    # ── Intro / universal ───────────────────────────────────────────────
    ("Muse_Emote_SwordPull",      "Red", "Welcome01",        "interact", "(grunt pulling the Transistor from the body)"),
    ("Muse_Emote_Inhale",         "Red", "Welcome01",        "interact", "(sharp inhale — breath before pulling the Transistor)"),
    ("Muse_Emote_Intrigued",      "Red", "Welcome01",        "interact", "(intrigued murmur — on examining any object)"),
    ("Muse_Emote_SurprisedBad",   "Red", "Welcome01",        "proximity","(startled gasp)"),
    ("Muse_Emote_Approval",       "Red", "Welcome01",        "area",     "(approving murmur)"),
    ("Muse_Emote_Disapproval",    "Red", "Welcome01",        "area",     "(disapproving murmur)"),
    ("Muse_Emote_Frustrated",     "Red", "Welcome01",        "proximity","(frustrated sound)"),
    # ── Combat / gameplay emotes (any level, earliest = Welcome01) ──────
    ("Muse_Emote_Humming01",      "Red", "Welcome01",        "combat",   "(humming — calm)"),
    ("Muse_Emote_Humming02",      "Red", "Welcome01",        "combat",   "(humming — faster variant)"),
    ("Muse_Emote_BattleCry",      "Red", "Welcome01",        "combat",   "(battle cry — entering combat)"),
    ("Muse_Emote_Concentrating",  "Red", "Welcome01",        "combat",   "(concentrating sound — in Focus mode)"),
    ("Muse_Emote_Charge_Quick",   "Red", "Welcome01",        "combat",   "(quick charge grunt)"),
    ("Muse_Emote_Charge_Slow",    "Red", "Welcome01",        "combat",   "(slow charge grunt)"),
    ("Muse_Emote_AngryBreathing", "Red", "Welcome01",        "combat",   "(angry breathing)"),
    ("Muse_Emote_AngryBreathing2","Red", "Welcome01",        "combat",   "(angry breathing — variant)"),
    ("Muse_Emote_Relief",         "Red", "Welcome01",        "combat",   "(exhale of relief)"),
    ("Muse_Emote_VictoryCry",     "Red", "Welcome01",        "combat",   "(victory cry)"),
    ("Muse_Emote_Breathless",     "Red", "Welcome01",        "combat",   "(breathless — after sustained combat)"),
    ("Muse_Emote_Exhausted",      "Red", "Welcome01",        "combat",   "(exhausted sound)"),
    ("Muse_Emote_FinalBreath",    "Red", "Welcome01",        "combat",   "(final breath — on death)"),
    ("Muse_Emote_Melancholy",     "Red", "Welcome01",        "combat",   "(melancholy vocalization — on revival after death)"),
    # ── Memoriam (Flashback01) ───────────────────────────────────────────
    ("Muse_Emote_Sigh",           "Red", "Flashback01",      "interact", "(sigh — interacting with the Transistor in Memoriam)"),
    # ── Rooftops03 washroom still scene ─────────────────────────────────
    ("Muse_Emote_SadSigh",        "Red", "Rooftops03",       "area",     "(sad sigh — at the washroom sink)"),
    ("Muse_Emote_Satisfaction",   "Red", "Rooftops03",       "area",     "(satisfied exhale — exiting the washroom)"),
    ("Muse_Emote_Agreement",      "Red", "Rooftops03",       "area",     "(murmur of agreement — after the Transistor's \"Good? Good.\")"),
    # ── Farewell / Country ending ────────────────────────────────────────
    ("Muse_Emote_JoyousLaugh",    "Red", "Farewell01",       "area",     "(joyous laugh — entering the Country)"),
    # ── Transistor narrator combat emote ────────────────────────────────
    ("Transistor_Emote_Frustrated","The Transistor","Welcome01","combat", "(frustrated grunt — when Red loses power slots in combat)"),
]


def load_emotes() -> list:
    """Return rows for non-verbal emotes (no subtitle text)."""
    rows = []
    for sub_id, speaker, level, trigger, text in _EMOTE_DATA:
        area     = LEVEL_AREA.get(level, level)
        sort_key = LEVEL_SORT.get(level, 999)
        rows.append({
            "sort_key":         sort_key,
            "id":               sub_id,
            "category":         "voiceline",
            "function":         "",
            "function_display": "",
            "speaker":          speaker,
            "area":             area,
            "earliest_level":   level,
            "flags":            "emote",
            "trigger":          trigger,
            "scene_key":        "",
            "text":             text,
        })
    return rows


def load_subtitles(vo_triggers: dict, vo_to_scan: dict) -> list:
    """Parse all story voiceline CSVs from Subtitles/en/ and return rows."""
    subtitle_dir = GAME / "Subtitles/en"
    rows = []
    seen_ids: set = set()   # Asher.csv duplicates the whole file; deduplicate by ID

    for csv_path in sorted(subtitle_dir.glob("*.csv")):
        stem = csv_path.stem
        if stem in SUBTITLE_SKIP:
            continue

        # Determine speaker and level source
        if stem == "Asher":
            speaker     = "Asher"
            fixed_level = None
            is_royce    = False
            is_asher    = True
        elif stem in SUBTITLE_CHARACTER_MAP:
            speaker, fixed_level = SUBTITLE_CHARACTER_MAP[stem]
            is_royce = False
            is_asher = False
        elif stem == "Royce":
            speaker     = "Royce"
            fixed_level = None
            is_royce    = True
            is_asher    = False
        elif stem in SUBTITLE_LEVEL_MAP:
            fixed_level, _ = SUBTITLE_LEVEL_MAP[stem]
            speaker  = "The Transistor"
            is_royce = False
            is_asher = False
        else:
            continue  # unrecognised file — skip

        with csv_path.open(encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                sub_id = row.get("ID", "").strip()
                line   = row.get("Line", "").strip()
                if not sub_id or not line:
                    continue
                if sub_id in seen_ids:
                    continue
                seen_ids.add(sub_id)

                if is_asher:
                    level = asher_level(sub_id)
                elif is_royce:
                    level = royce_level(sub_id)
                else:
                    level = fixed_level

                area     = LEVEL_AREA.get(level, level or "")
                sort_key = LEVEL_SORT.get(level, 999)
                trigger   = vo_triggers.get(sub_id, "")
                scene_key = vo_to_scan.get(sub_id, "")

                flags = []
                if "ALT" in sub_id:
                    flags.append("alt")

                rows.append({
                    "sort_key":         sort_key,
                    "id":               sub_id,
                    "category":         "voiceline",
                    "function":         "",
                    "function_display": "",
                    "speaker":          speaker,
                    "area":             area,
                    "earliest_level":   level,
                    "flags":            "|".join(flags),
                    "trigger":          trigger,
                    "scene_key":        scene_key,
                    "text":             line,
                })

    return rows


# ── Text cleaning ──────────────────────────────────────────────────────────────
_FORMAT_RE = re.compile(r'\\Format \w+')
_COLOR_RE  = re.compile(r'\\Color \w+')

def clean_text(raw: str) -> str:
    if not raw:
        return ""
    text = raw.replace(r"\n", "\n")
    text = _FORMAT_RE.sub("", text)
    text = _COLOR_RE.sub("", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    lines = [ln.strip() for ln in text.split("\n")]
    out, prev_blank = [], False
    for ln in lines:
        blank = ln == ""
        if blank and prev_blank:
            continue
        out.append(ln)
        prev_blank = blank
    return "\n".join(out).strip()

# ── Main classification ────────────────────────────────────────────────────────

def load_weapon_display_names(root) -> dict:
    names = {}
    for elem in root.findall(".//Text"):
        eid = elem.get("Id", "")
        if eid.endswith("_Generic"):
            weapon = eid[: -len("_Generic")]
            display = elem.get("DisplayName") or elem.get("Description") or ""
            display = clean_text(display).split("\n")[0].strip()
            if display:
                names[weapon] = display
    # Add alias
    names["ClusterbombGP"] = names.get("Clusterbomb", "Spark()")
    return names


def is_ui(eid: str) -> bool:
    for pat in UI_START_PATTERNS:
        if eid.startswith(pat):
            return True
    # Single-character IDs are keyboard key labels
    if len(eid) <= 2 and eid.upper() == eid:
        return True
    # Keyboard key names
    if re.match(r"^(Left|Right)(Alt|Control|Shift|Shoulder|Stick|Trigger)", eid):
        return True
    if re.match(r"^(DPad|NumPad|F\d|Oem|Mouse|Wheel|XButton|PageUp|PageDown|Home|End|Insert|Delete|Tab|Space|BackSpace|CapsLock|Escape|Enter|Decimal|Add|Subtract|Multiply|Divide|PrintScreen)", eid):
        return True
    if re.match(r"^D\d$", eid):   # D0-D9 numrow
        return True
    if eid in {"2x", "4x", "A", "B", "C", "D", "E", "F", "G", "H", "I", "J",
               "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V",
               "W", "X", "Y", "Z", "BACK", "START", "OPTIONS", "SHARE",
               "2DArt", "3DArt",
               "Jump", "Up", "Down", "Left", "Right", "Top",
               "Focus", "Menu",
               "Level", "Profile", "Settings", "No",
               "Egg", "Empty", "Vulnerable", "Gamepad",
               "Use", "Using", "UsePlanned",
               "UnuseableInstructions", "UseInstructions", "UseInstructionsTouch",
               "Visual FX", "_PlayerPartner", "_PlayerUnit",
               "Upgrade_Capacity", "Not_Enough_Supply", "No_Continue_without_device",
               "Menu_PressAnyButton", "Menu_PressAnyKey",
               "Focus_Disrupted",
               "Additional Credits", "AdditionalVoices", "Acknowledgements",
               "Special Thanks", "VoiceActors",
               "Design", "Engineering", "Animation", "Art", "QA",
               "featuring", "or", "speciale", "specialo",
               "Music and Audio", "Sound and Music", "Map Beautification",
               "How to Play", "Prepare Yourself", "Press START",
               "Design and Writing", "DesignAndProduction",
               "GameplayEngineering", "SystemsEngineering",
               "Supergiant", "Supergiant Games",
               "Games", "Models and Weapons",
               "AchSetDetails", "AchSetName",
               "SrLeads", "SoftwareTestEngineers", "CertTesting", "QA",
               "TechArt",
               }:
        return True
    return False


def classify_ticker(eid: str):
    """Return (level, category) for TickerText IDs."""
    m = re.match(r"^TickerText(\d+)", eid)
    if m:
        num = m.group(1).zfill(2)
        lvl = TICKER_LEVEL_MAP.get(num, "Welcome01")
        return lvl, "news_post"
    return "Welcome01", "news_post"


def classify(eid: str, weapon_display: dict):
    """
    Returns (category, function_internal, function_display, earliest_level, flags).
    """
    flags = []

    # ── 1. Hard UI exclusion ─────────────────────────────────────────────────
    if is_ui(eid):
        return "ui", "", "", "", []

    # ── 2. TickerText handled specially ─────────────────────────────────────
    if eid.startswith("TickerText"):
        lvl, cat = classify_ticker(eid)
        return cat, "", "", lvl, []

    # ── 3. Weapon / function text ─────────────────────────────────────────────
    # Resolve alias (ClusterbombGP → Clusterbomb)
    canonical_weapon = None
    for wname in list(WEAPON_LEVEL.keys()) + list(WEAPON_ALIASES.keys()):
        if eid == wname or eid.startswith(wname + "_"):
            canonical_weapon = WEAPON_ALIASES.get(wname, wname)
            break

    if canonical_weapon and canonical_weapon in WEAPON_LEVEL:
        lvl = WEAPON_LEVEL[canonical_weapon]
        display = weapon_display.get(canonical_weapon, canonical_weapon)
        suffix = eid[len(canonical_weapon):].lstrip("_") if "_" in eid or eid != canonical_weapon else ""
        # Alias suffix
        if not suffix and canonical_weapon != eid:
            alias_len = len([k for k in WEAPON_ALIASES if eid.startswith(k)][0]) if any(eid.startswith(k) for k in WEAPON_ALIASES) else 0
            suffix = eid[alias_len:].lstrip("_")

        if suffix in ("Bio", "Bio_2", "Bio_3", "Bio_4"):
            return "trace_bio", canonical_weapon, display, lvl, flags
        if suffix in ("Generic", "Generic_Upgrade", "Passive", "") or eid == canonical_weapon:
            return "function_description", canonical_weapon, display, lvl, flags
        # Everything else is upgrade descriptions
        flags.append("procedural")
        return "function_upgrade", canonical_weapon, display, lvl, flags

    # ── 4. Compound lore prefixes ─────────────────────────────────────────────
    for pfx in COMPOUND_LORE_SORTED:
        if eid == pfx or eid.startswith(pfx + "_") or eid.startswith(pfx):
            lvl, cat = COMPOUND_LORE[pfx]
            # Avoid false matches: e.g. "Fairview01_Location01" should match
            # simple level prefix, not compound "Fairview"
            # Skip if simple level prefix matches first (handled below)
            for splvl in SIMPLE_LEVEL_PREFIXES:
                if eid.startswith(splvl + "_") or eid == splvl:
                    lvl = splvl if splvl in LEVEL_SORT else lvl
                    cat = "scannable"
                    return cat, "", "", lvl, flags
            return cat, "", "", lvl, flags

    # ── 5. Simple Level01_Xxx prefixes ───────────────────────────────────────
    for splvl in SIMPLE_LEVEL_PREFIXES:
        if eid.startswith(splvl + "_") or eid == splvl:
            # Skip sandboxes
            if SANDBOX_PATTERN.match(splvl):
                return "ui", "", "", "", []
            lvl = splvl if splvl in LEVEL_SORT else splvl
            return "scannable", "", "", lvl, flags

    # ── 6. Enemy lore ─────────────────────────────────────────────────────────
    enemy_names = (
        "Flusher", "Popper", "Speeder", "Guide", "Haunter",
        "Zoner", "Demolisher", "Priest", "Shielder", "Lobber",
        "Berserker", "Summoner", "Suppressor", "MonsterTail",
        "BerserkerWeapon", "FlusherFriendly",
        "SuppressorSmall", "SuppressorTutorialEgg",
    )
    for ep in enemy_names:
        if eid == ep or eid.startswith(ep + "_") or eid.startswith(ep + "Level"):
            return "enemy_lore", "", "", "", flags

    return "unknown", "", "", "", flags


def main():
    helptext_path = GAME / "Game/Text/HelpText.en.xml"
    tree = ET.parse(helptext_path)
    root = tree.getroot()

    weapon_display                 = load_weapon_display_names(root)
    vo_to_scan, scan_hids_with_vos = load_scan_scene_keys()

    rows = []
    for elem in root.findall(".//Text"):
        eid         = elem.get("Id", "")
        raw_display = elem.get("DisplayName") or ""
        raw_desc    = elem.get("Description") or ""

        raw_text = raw_desc if raw_desc.strip() else raw_display.strip()
        text = clean_text(raw_text)

        if not text:
            continue

        category, func_int, func_disp, earliest_lvl, flags = classify(eid, weapon_display)

        if category == "ui":
            continue

        # Derive area name
        area = LEVEL_AREA.get(earliest_lvl, earliest_lvl or "")

        # Sort key
        sort_key = LEVEL_SORT.get(earliest_lvl, 999)

        # Speaker
        if category == "trace_bio":
            speaker = "The Transistor"
        elif category in ("function_description", "function_upgrade"):
            speaker = "The Transistor"
        elif category == "scannable":
            speaker = "The Transistor"
        elif category == "news_post":
            speaker = "Cloudbank Feed"
        elif category == "enemy_lore":
            speaker = "The Transistor"
        else:
            speaker = ""

        rows.append({
            "sort_key":         sort_key,
            "id":               eid,
            "category":         category,
            "function":         func_int,
            "function_display": func_disp,
            "speaker":          speaker,
            "area":             area,
            "earliest_level":   earliest_lvl,
            "flags":            "|".join(flags),
            "trigger":          "",
            "scene_key":        eid if eid in scan_hids_with_vos else "",
            "text":             text,
        })

    vo_triggers = load_vo_triggers()
    rows += load_subtitles(vo_triggers, vo_to_scan)
    rows += load_emotes()

    CAT_ORDER = {
        "trace_bio": 0, "function_description": 1, "function_upgrade": 2,
        "voiceline": 3, "news_post": 4, "scannable": 5, "enemy_lore": 6, "unknown": 9,
    }
    rows.sort(key=lambda r: (
        r["sort_key"],
        CAT_ORDER.get(r["category"], 9),
        r["id"],
    ))

    fieldnames = [
        "id", "category", "function", "function_display",
        "speaker", "area", "earliest_level", "flags", "trigger", "scene_key", "text",
    ]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    total = len(rows)
    by_cat = {}
    for r in rows:
        by_cat[r["category"]] = by_cat.get(r["category"], 0) + 1

    print(f"Wrote {total} rows to {OUT}")
    for cat, n in sorted(by_cat.items(), key=lambda x: -x[1]):
        print(f"  {n:4d}  {cat}")


if __name__ == "__main__":
    main()
