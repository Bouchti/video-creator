"""Vocabulary of the pressurised-water reactor kit (cutaway/blender/assemblies/pwr.py builds and animates it)."""

KIT = {
    "assembly": "pwr",
    "subject": ("a pressurised-water reactor (PWR) nuclear power plant: reactor vessel with fuel assemblies and "
                "control rods, a primary coolant loop with steam generator, pump and pressuriser inside a "
                "containment building, then a steam turbine, generator, condenser and cooling tower"),
    "topics": ["how a nuclear reactor works", "nuclear power plant", "nuclear reactor", "pressurized water reactor",
               "nuclear energy", "how nuclear power works", "fission reactor"],
    "mechanisms": {
        "fission": {"explains": "uranium atoms split in the fuel rods and release heat; the water glows blue",
                    "cut": "vessel", "cameras": ["core_close", "vessel_section"],
                    "anchors": ["fuel_rods", "reactor_core", "reactor_vessel"]},
        "control_rods": {"explains": "control rods slide into the core to absorb neutrons and slow the reaction",
                         "cut": "vessel", "cameras": ["vessel_section", "rods_close"],
                         "anchors": ["control_rods", "rod_drives", "reactor_core"]},
        "primary_loop": {"explains": "water under huge pressure carries the heat away without boiling",
                         "cut": "containment", "cameras": ["loop_wide", "vessel_section", "pump_close"],
                         "anchors": ["hot_leg", "cold_leg", "coolant_pump", "pressurizer", "reactor_vessel"]},
        "steam_generator": {"explains": "the hot water heats thousands of tubes; separate water outside them "
                                       "boils into steam",
                            "cut": "steam_generator", "cameras": ["sg_section", "sg_close", "loop_wide"],
                            "anchors": ["steam_generator", "sg_tubes", "steam_line"]},
        "turbine": {"explains": "steam spins the turbine blades, the shaft turns the generator, electricity flows",
                    "cut": "turbine", "cameras": ["turbine_section", "turbine_close", "plant_wide"],
                    "anchors": ["turbine_blades", "turbine_shaft", "generator", "steam_line"]},
        "cooling": {"explains": "the condenser turns steam back to water; the cooling tower dumps the leftover "
                               "heat as water vapour",
                    "cut": "turbine", "cameras": ["plant_wide", "tower_close", "turbine_section"],
                    "anchors": ["condenser", "cooling_tower", "vapour_plume"]},
    },
    "anchors": {
        "reactor_vessel": "the steel reactor pressure vessel", "reactor_core": "the core: fuel assemblies",
        "fuel_rods": "fuel rods in an assembly", "control_rods": "control rod cluster (moves up and down)",
        "rod_drives": "control rod drive mechanisms on the vessel head", "hot_leg": "hot leg pipe (to the "
        "steam generator)", "cold_leg": "cold leg pipe (back to the reactor)", "coolant_pump": "reactor coolant "
        "pump", "pressurizer": "pressuriser", "steam_generator": "steam generator", "sg_tubes": "steam generator "
        "U-tubes", "steam_line": "main steam line", "turbine_blades": "turbine blades", "turbine_shaft":
        "turbine shaft", "generator": "electric generator", "condenser": "condenser", "cooling_tower":
        "cooling tower", "vapour_plume": "water vapour plume", "containment": "containment building",
    },
    "exterior_anchors": ["containment", "cooling_tower", "vapour_plume", "steam_line"],
    "cuts": {
        "containment": "the containment dome and walls sliced open: vessel, loop, steam generator, pump, pressuriser",
        "vessel": "the reactor vessel sliced in half: core, fuel assemblies, control rods, flowing water",
        "steam_generator": "the steam generator sliced in half: tube bundle, boiling water, steam",
        "turbine": "the turbine casing cut open: blade stages on the shaft, generator, condenser below",
        "quarter": "a quarter of the containment removed: outside and inside in one 3/4 view",
    },
    "cameras": {
        "plant_wide": ("closed or turbine", "the whole plant: containment, turbine hall, cooling tower"),
        "plant_low": ("closed", "low dramatic angle on the containment dome and cooling tower"),
        "tower_close": ("closed or turbine", "the cooling tower and its vapour plume"),
        "loop_wide": ("containment or quarter", "inside containment: vessel, steam generator, pump, pressuriser"),
        "quarter_hero": ("quarter", "3/4 view into the open containment"),
        "vessel_section": ("vessel or containment", "the cut reactor vessel, head to bottom"),
        "core_close": ("vessel", "close on the fuel assemblies and the blue glow"),
        "rods_close": ("vessel", "close on the control rods entering the core"),
        "pump_close": ("containment or quarter", "close on the reactor coolant pump and cold leg"),
        "sg_section": ("steam_generator", "the cut steam generator, tube bundle and steam dome"),
        "sg_close": ("steam_generator", "close on the U-tubes and boiling water"),
        "turbine_section": ("turbine", "the open turbine: blade stages and shaft"),
        "turbine_close": ("turbine", "close on spinning turbine blades"),
    },
    "events": {
        "rods_in": "control rods slide down into the core (power falls)",
        "rods_out": "control rods lift out of the core (power rises)",
        "power_up": "the core glow brightens",
        "steam_burst": "a burst of steam leaves the steam generator",
        "pump_start": "the coolant pump spins up",
    },
    "drive": "flow",                       # a flow phase drives turbine, pumps and coolant; events are timed states
    "units": [1],
    "event_sfx": {"rods_in": "clunk", "rods_out": "clunk", "steam_burst": "hiss", "power_up": "riser"},
    "bed": ["power plant hum", "turbine hum", "machinery hum", "industrial hum"],
    "research_scope": "true for a typical modern pressurised-water reactor power plant (1,000-1,400 MW class)",
    "loop_hint": "open and close on the same closed plant_wide view",
}
