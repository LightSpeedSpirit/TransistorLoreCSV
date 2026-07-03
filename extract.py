#!/usr/bin/env python3
"""
Transistor lore extractor
Parses HelpText.en.xml and produces transistor_lore.csv with all narrative
text, tagged by category, speaker, and earliest accessible location.
"""

import csv
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

    weapon_display = load_weapon_display_names(root)

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
            "text":             text,
        })

    CAT_ORDER = {
        "trace_bio": 0, "function_description": 1, "function_upgrade": 2,
        "news_post": 3, "scannable": 4, "enemy_lore": 5, "unknown": 9,
    }
    rows.sort(key=lambda r: (
        r["sort_key"],
        CAT_ORDER.get(r["category"], 9),
        r["id"],
    ))

    fieldnames = [
        "id", "category", "function", "function_display",
        "speaker", "area", "earliest_level", "flags", "text",
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
