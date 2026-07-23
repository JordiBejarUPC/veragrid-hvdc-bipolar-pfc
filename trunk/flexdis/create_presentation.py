"""
Create the FlexDis Cascading Events presentation using eRoots template.
"""
import sys
sys.path.insert(0, '/Users/Josep/Desktop/VeraGrid/src')

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
import json

TEMPLATE = '/Users/josep/Downloads/eRoots - Google Slides Presentation Template - v1 shorten.pptx'
OUTPUT = '/Users/Josep/Desktop/VeraGrid/trunk/flexdis/docs/FlexDis_Cascading_Events.pptx'

# Load results
with open('/Users/Josep/Desktop/VeraGrid/trunk/flexdis/docs/cascading_results.json') as f:
    results = json.load(f)

# Colors from template
DARK_TEAL = RGBColor(0x04, 0x38, 0x4F)
GREEN = RGBColor(0x41, 0xFE, 0x9F)
GRAY = RGBColor(0x91, 0x96, 0x9C)
DARK_GRAY = RGBColor(0x75, 0x75, 0x75)
BLACK = RGBColor(0x1A, 0x1A, 0x1A)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
RED = RGBColor(0xE0, 0x40, 0x40)
ORANGE = RGBColor(0xF0, 0xA0, 0x30)

prs = Presentation(TEMPLATE)
SW = prs.slide_width
SH = prs.slide_height

# Remove all existing slides
while len(prs.slides) > 0:
    rId = prs.slides._sldIdLst[0].rId
    prs.part.drop_rel(rId)
    prs.slides._sldIdLst.remove(prs.slides._sldIdLst[0])


def add_textbox(slide, left, top, width, height, text, font_size=18, color=BLACK,
                bold=False, alignment=PP_ALIGN.LEFT, font_name='Ubuntu Light'):
    """Add a text box to a slide."""
    txBox = slide.shapes.add_textbox(Emu(left), Emu(top), Emu(width), Emu(height))
    tf = txBox.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.text = text
    p.font.size = Pt(font_size)
    p.font.color.rgb = color
    p.font.bold = bold
    p.font.name = font_name
    p.alignment = alignment
    return tf


def add_paragraph(tf, text, font_size=18, color=BLACK, bold=False, font_name='Ubuntu Light',
                  space_before=Pt(6)):
    """Add a paragraph to an existing text frame."""
    p = tf.add_paragraph()
    p.text = text
    p.font.size = Pt(font_size)
    p.font.color.rgb = color
    p.font.bold = bold
    p.font.name = font_name
    p.space_before = space_before
    return p


# Margins and dimensions (in EMU, ~26.67x15 inch slides)
LEFT_MARGIN = Emu(int(SW * 0.06))
TOP_MARGIN = Emu(int(SH * 0.12))
CONTENT_W = Emu(int(SW * 0.88))
CONTENT_H = Emu(int(SH * 0.75))
HALF_W = Emu(int(SW * 0.42))
COL2_LEFT = Emu(int(SW * 0.52))

# ============================================================
# SLIDE 1: Title
# ============================================================
slide = prs.slides.add_slide(prs.slide_layouts[0])  # Intro title
# Clear placeholder text and set our content
for shape in slide.placeholders:
    idx = shape.placeholder_format.idx
    if idx == 0:  # Title
        shape.text_frame.paragraphs[0].text = "Cascading Disconnection of Converter-Interfaced DER"
        for run in shape.text_frame.paragraphs[0].runs:
            run.font.color.rgb = DARK_TEAL
    elif idx == 1:  # Subtitle
        shape.text_frame.paragraphs[0].text = "IEEE 33-bus Distribution Network — FlexDis Study"
        for run in shape.text_frame.paragraphs[0].runs:
            run.font.color.rgb = DARK_TEAL
    elif idx == 2:  # Date/author
        shape.text_frame.paragraphs[0].text = "March 2026"
        if len(shape.text_frame.paragraphs) > 1:
            shape.text_frame.paragraphs[1].text = "VeraGrid Simulation Platform"

# ============================================================
# SLIDE 2: Agenda
# ============================================================
slide = prs.slides.add_slide(prs.slide_layouts[3])  # Agenda
for shape in slide.placeholders:
    idx = shape.placeholder_format.idx
    if idx == 0:
        for p in shape.text_frame.paragraphs:
            if p.runs:
                p.runs[0].text = "Agenda"
    elif idx == 2:
        tf = shape.text_frame
        items = [
            ("01 Problem Statement", "Cascading disconnection of DER during faults"),
            ("02 Grid Setup", "IEEE 33-bus network with 4 VSC converters"),
            ("03 LVRT Grid Code Review", "European requirements for converter ride-through"),
            ("04 Short Circuit Analysis", "Fault simulation using sequences_vsc method"),
            ("05 Results & Comparison", "Three LVRT scenarios: 0.85, 0.50, 0.10 p.u."),
        ]
        tf.clear()
        for i, (title, desc) in enumerate(items):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            run = p.add_run()
            run.text = title
            run.font.size = Pt(28)
            run.font.bold = True
            run.font.color.rgb = GREEN
            run.font.name = 'Ubuntu Light'
            p2 = tf.add_paragraph()
            run2 = p2.add_run()
            run2.text = desc
            run2.font.size = Pt(18)
            run2.font.color.rgb = GRAY
            run2.font.name = 'Ubuntu Light'
            p2.space_after = Pt(16)

# ============================================================
# SLIDE 3: Section - Problem Statement
# ============================================================
slide = prs.slides.add_slide(prs.slide_layouts[4])  # Section header
for shape in slide.placeholders:
    idx = shape.placeholder_format.idx
    if idx == 0:
        tf = shape.text_frame
        tf.paragraphs[0].text = "Problem Statement"
        for r in tf.paragraphs[0].runs:
            r.font.color.rgb = DARK_TEAL
    elif idx == 2:
        tf = shape.text_frame
        tf.paragraphs[0].text = "01"
        for r in tf.paragraphs[0].runs:
            r.font.color.rgb = GREEN

# ============================================================
# SLIDE 4: Problem + Approach
# ============================================================
slide = prs.slides.add_slide(prs.slide_layouts[9])  # Title + body
for shape in slide.placeholders:
    idx = shape.placeholder_format.idx
    if idx == 0:
        shape.text_frame.paragraphs[0].text = "Cascading DER Disconnection"
        for r in shape.text_frame.paragraphs[0].runs:
            r.font.color.rgb = DARK_TEAL
    elif idx == 2:
        shape.text_frame.paragraphs[0].text = "Quantifying the impact of converter undervoltage protection settings"
        for r in shape.text_frame.paragraphs[0].runs:
            r.font.color.rgb = GRAY
    elif idx == 1:
        tf = shape.text_frame
        tf.clear()
        bullets = [
            ("The Problem", True, GREEN),
            ("During a fault, voltage drops propagate through the distribution network", False, BLACK),
            ("Converter-interfaced DER (wind, solar, batteries) have undervoltage protection", False, BLACK),
            ("When AC voltage drops below min_ac_voltage, the converter disconnects", False, BLACK),
            ("This reduces local generation, further depressing voltages — cascading effect", False, BLACK),
            ("", False, BLACK),
            ("The Question", True, GREEN),
            ("How does the LVRT threshold (min_ac_voltage) affect cascading severity?", False, BLACK),
            ("How many converters disconnect for a single fault at different locations?", False, BLACK),
            ("What is the total lost DER generation under different grid code requirements?", False, BLACK),
        ]
        for i, (text, bold, color) in enumerate(bullets):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            run = p.add_run()
            run.text = text
            run.font.size = Pt(22) if bold else Pt(18)
            run.font.bold = bold
            run.font.color.rgb = color
            run.font.name = 'Ubuntu Light'

# ============================================================
# SLIDE 5: Grid Setup
# ============================================================
slide = prs.slides.add_slide(prs.slide_layouts[9])  # Title + body
for shape in slide.placeholders:
    idx = shape.placeholder_format.idx
    if idx == 0:
        shape.text_frame.paragraphs[0].text = "IEEE 33-Bus Distribution Network"
        for r in shape.text_frame.paragraphs[0].runs:
            r.font.color.rgb = DARK_TEAL
    elif idx == 2:
        shape.text_frame.paragraphs[0].text = "Grid setup with 4 VSC converters at end-of-feeder buses"
        for r in shape.text_frame.paragraphs[0].runs:
            r.font.color.rgb = GRAY
    elif idx == 1:
        tf = shape.text_frame
        tf.clear()
        lines = [
            ("Network Characteristics", True, GREEN),
            ("33 AC buses, 12.66 kV radial distribution network", False, BLACK),
            ("32 loads (total ~3.72 MW), 37 lines (incl. 5 tie switches)", False, BLACK),
            ("Single slack generator at Bus 1 (substation)", False, BLACK),
            ("", False, BLACK),
            ("VSC Converter Placement (DER Emulation)", True, GREEN),
            ("VSC Bus 18  —  0.20 MW  —  Wind turbine (end of main feeder)", False, BLACK),
            ("VSC Bus 22  —  0.15 MW  —  Battery storage (branch from Bus 2)", False, BLACK),
            ("VSC Bus 25  —  0.30 MW  —  Solar/Wind (branch from Bus 3)", False, BLACK),
            ("VSC Bus 33  —  0.15 MW  —  Battery storage (branch from Bus 6)", False, BLACK),
            ("", False, BLACK),
            ("Total DER: 0.80 MW (~21% of total load)", True, DARK_TEAL),
            ("", False, BLACK),
            ("Healthy-state voltage range: [0.928, 1.000] p.u.", False, BLACK),
            ("Power flow: Newton-Raphson, converged in 3 iterations", False, BLACK),
        ]
        for i, (text, bold, color) in enumerate(lines):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            run = p.add_run()
            run.text = text
            run.font.size = Pt(20) if bold else Pt(17)
            run.font.bold = bold
            run.font.color.rgb = color
            run.font.name = 'Ubuntu Light'

# ============================================================
# SLIDE 6: LVRT Grid Codes
# ============================================================
slide = prs.slides.add_slide(prs.slide_layouts[9])  # Title + body
for shape in slide.placeholders:
    idx = shape.placeholder_format.idx
    if idx == 0:
        shape.text_frame.paragraphs[0].text = "LVRT Requirements — European Grid Codes"
        for r in shape.text_frame.paragraphs[0].runs:
            r.font.color.rgb = DARK_TEAL
    elif idx == 2:
        shape.text_frame.paragraphs[0].text = "Review of undervoltage disconnection thresholds for distribution-connected DER"
        for r in shape.text_frame.paragraphs[0].runs:
            r.font.color.rgb = GRAY
    elif idx == 1:
        tf = shape.text_frame
        tf.clear()
        lines = [
            ("EU Regulation 2016/631 (NC RfG)", True, GREEN),
            ("Framework for generator connection requirements (Type A–D)", False, BLACK),
            ("LVRT mandatory for Type B+ (>0.8 MW); parameters set by national TSOs/DSOs", False, BLACK),
            ("", False, BLACK),
            ("EN 50549-1:2019 (LV Distribution)", True, GREEN),
            ("Continuous operating range: 0.80–1.00 p.u.", False, BLACK),
            ("Below 0.80 p.u.: time-limited operation, DER must resume 90% power within 1s", False, BLACK),
            ("", False, BLACK),
            ("VDE-AR-N 4105/4110 (Germany, LV/MV)", True, GREEN),
            ("LV: ride through ≥150 ms; MV: ride through ≥250 ms", False, BLACK),
            ("Modern codes require near-zero voltage ride-through for 140–250 ms", False, BLACK),
            ("", False, BLACK),
            ("IEEE 1547-2018 (US, for comparison)", True, GREEN),
            ("Cat I: trip below 0.50 p.u. after 160 ms", False, BLACK),
            ("Cat III: ride through down to 0.30 p.u. for extended periods", False, BLACK),
        ]
        for i, (text, bold, color) in enumerate(lines):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            run = p.add_run()
            run.text = text
            run.font.size = Pt(20) if bold else Pt(17)
            run.font.bold = bold
            run.font.color.rgb = color
            run.font.name = 'Ubuntu Light'

# ============================================================
# SLIDE 7: Three Scenarios
# ============================================================
slide = prs.slides.add_slide(prs.slide_layouts[9])
for shape in slide.placeholders:
    idx = shape.placeholder_format.idx
    if idx == 0:
        shape.text_frame.paragraphs[0].text = "Study Scenarios"
        for r in shape.text_frame.paragraphs[0].runs:
            r.font.color.rgb = DARK_TEAL
    elif idx == 2:
        shape.text_frame.paragraphs[0].text = "Three min_ac_voltage thresholds representing different LVRT capabilities"
        for r in shape.text_frame.paragraphs[0].runs:
            r.font.color.rgb = GRAY
    elif idx == 1:
        tf = shape.text_frame
        tf.clear()
        scenarios = [
            ("Scenario A — No LVRT: 0.85 p.u.", RED,
             "Legacy/basic inverters without LVRT (pre-2018, Type A small DER)\n"
             "Trips as soon as voltage leaves normal operating range\n"
             "Worst case for cascading"),
            ("Scenario B — Moderate LVRT: 0.50 p.u.", ORANGE,
             "IEEE 1547 Category I threshold, older European codes\n"
             "Can sustain moderate voltage dips\n"
             "Common in many distribution-connected DER worldwide"),
            ("Scenario C — Stringent LVRT: 0.10 p.u.", GREEN,
             "Modern EU-compliant (VDE 4110/4120, RfG Type B+)\n"
             "Rides through deep faults (near-zero voltage for 140-250 ms)\n"
             "Best case — only nearest converters disconnect"),
        ]
        for i, (title, color, desc) in enumerate(scenarios):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            run = p.add_run()
            run.text = title
            run.font.size = Pt(24)
            run.font.bold = True
            run.font.color.rgb = color
            run.font.name = 'Ubuntu Light'
            p.space_before = Pt(20) if i > 0 else Pt(0)
            for line in desc.split('\n'):
                p2 = tf.add_paragraph()
                run2 = p2.add_run()
                run2.text = "    " + line
                run2.font.size = Pt(17)
                run2.font.color.rgb = BLACK
                run2.font.name = 'Ubuntu Light'

# ============================================================
# SLIDE 8: SC Method
# ============================================================
slide = prs.slides.add_slide(prs.slide_layouts[9])
for shape in slide.placeholders:
    idx = shape.placeholder_format.idx
    if idx == 0:
        shape.text_frame.paragraphs[0].text = "Short Circuit Methodology"
        for r in shape.text_frame.paragraphs[0].runs:
            r.font.color.rgb = DARK_TEAL
    elif idx == 2:
        shape.text_frame.paragraphs[0].text = "sequences_vsc: Full AC/DC power flow during fault conditions"
        for r in shape.text_frame.paragraphs[0].runs:
            r.font.color.rgb = GRAY
    elif idx == 1:
        tf = shape.text_frame
        tf.clear()
        lines = [
            ("Method: sequences_vsc", True, GREEN),
            ("Full AC/DC Newton-Raphson power flow during fault", False, BLACK),
            ("Generators modeled as Norton equivalents behind subtransient impedance", False, BLACK),
            ("VSC controls switch to Fault mode during short circuit", False, BLACK),
            ("min_ac_voltage disconnection enforced by the solver", False, BLACK),
            ("", False, BLACK),
            ("Fault Configuration", True, GREEN),
            ("Type: LLLG (3-phase bolted fault), Zf = 1e-6 + j1e-6 ohms", False, BLACK),
            ("Applied individually at each of the 33 AC buses", False, BLACK),
            ("Pre-fault state from converged Newton-Raphson power flow", False, BLACK),
            ("", False, BLACK),
            ("What We Measure", True, GREEN),
            ("Voltage at each VSC AC bus during fault", False, BLACK),
            ("Number of VSCs disconnected (V_ac < min_ac_voltage)", False, BLACK),
            ("Total lost DER generation (MW) per fault location", False, BLACK),
            ("VSC power output from solver (Pfp, St, loading)", False, BLACK),
        ]
        for i, (text, bold, color) in enumerate(lines):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            run = p.add_run()
            run.text = text
            run.font.size = Pt(20) if bold else Pt(17)
            run.font.bold = bold
            run.font.color.rgb = color
            run.font.name = 'Ubuntu Light'

# ============================================================
# SLIDE 9: Results - Cross-scenario comparison
# ============================================================
slide = prs.slides.add_slide(prs.slide_layouts[4])  # Section header
for shape in slide.placeholders:
    idx = shape.placeholder_format.idx
    if idx == 0:
        tf = shape.text_frame
        tf.paragraphs[0].text = "Results"
        for r in tf.paragraphs[0].runs:
            r.font.color.rgb = DARK_TEAL
    elif idx == 2:
        tf = shape.text_frame
        tf.paragraphs[0].text = "04"
        for r in tf.paragraphs[0].runs:
            r.font.color.rgb = GREEN

# ============================================================
# SLIDE 10: Key Metrics Table
# ============================================================
slide = prs.slides.add_slide(prs.slide_layouts[9])
for shape in slide.placeholders:
    idx = shape.placeholder_format.idx
    if idx == 0:
        shape.text_frame.paragraphs[0].text = "Cross-Scenario Comparison"
        for r in shape.text_frame.paragraphs[0].runs:
            r.font.color.rgb = DARK_TEAL
    elif idx == 2:
        shape.text_frame.paragraphs[0].text = "Impact of LVRT threshold on cascading disconnection severity"
        for r in shape.text_frame.paragraphs[0].runs:
            r.font.color.rgb = GRAY
    elif idx == 1:
        tf = shape.text_frame
        tf.clear()

        # Summary metrics
        header = f"{'Scenario':<40s} {'Faults w/ disc.':>18s} {'Max disc.':>12s} {'Avg disc.':>12s} {'Max lost':>12s}"
        p = tf.paragraphs[0]
        run = p.add_run()
        run.text = header
        run.font.size = Pt(18)
        run.font.bold = True
        run.font.color.rgb = DARK_TEAL
        run.font.name = 'Ubuntu Light'

        sep = "─" * 95
        p2 = tf.add_paragraph()
        r2 = p2.add_run()
        r2.text = sep
        r2.font.size = Pt(14)
        r2.font.color.rgb = GRAY

        scenario_data = [
            ("A — No LVRT (0.85 p.u.)", "32/33 (97%)", "4/4", "2.39", "0.800 MW (100%)", RED),
            ("B — Moderate LVRT (0.50 p.u.)", "32/33 (97%)", "4/4", "1.61", "0.800 MW (100%)", ORANGE),
            ("C — Stringent LVRT (0.10 p.u.)", "32/33 (97%)", "4/4", "1.36", "0.800 MW (100%)", GREEN),
        ]

        for label, faults, maxd, avgd, maxl, color in scenario_data:
            row = f"{label:<40s} {faults:>18s} {maxd:>12s} {avgd:>12s} {maxl:>12s}"
            p3 = tf.add_paragraph()
            run3 = p3.add_run()
            run3.text = row
            run3.font.size = Pt(18)
            run3.font.color.rgb = BLACK
            run3.font.name = 'Ubuntu Light'
            p3.space_before = Pt(12)

        # Key insight
        p4 = tf.add_paragraph()
        p4.space_before = Pt(30)
        r4 = p4.add_run()
        r4.text = "Key Finding: "
        r4.font.size = Pt(22)
        r4.font.bold = True
        r4.font.color.rgb = GREEN
        r4.font.name = 'Ubuntu Light'

        p5 = tf.add_paragraph()
        r5 = p5.add_run()
        r5.text = "Average VSC disconnections drop from 2.39 to 1.36 (43% reduction) with stringent LVRT"
        r5.font.size = Pt(22)
        r5.font.bold = True
        r5.font.color.rgb = DARK_TEAL
        r5.font.name = 'Ubuntu Light'

# ============================================================
# SLIDE 11: Distribution shift
# ============================================================
slide = prs.slides.add_slide(prs.slide_layouts[9])
for shape in slide.placeholders:
    idx = shape.placeholder_format.idx
    if idx == 0:
        shape.text_frame.paragraphs[0].text = "Disconnection Distribution"
        for r in shape.text_frame.paragraphs[0].runs:
            r.font.color.rgb = DARK_TEAL
    elif idx == 2:
        shape.text_frame.paragraphs[0].text = "How many VSCs disconnect per fault event across scenarios"
        for r in shape.text_frame.paragraphs[0].runs:
            r.font.color.rgb = GRAY
    elif idx == 1:
        tf = shape.text_frame
        tf.clear()

        header = f"{'# VSCs disconnected':<25s} {'Scenario A (0.85)':>20s} {'Scenario B (0.50)':>20s} {'Scenario C (0.10)':>20s}"
        p = tf.paragraphs[0]
        r = p.add_run()
        r.text = header
        r.font.size = Pt(19)
        r.font.bold = True
        r.font.color.rgb = DARK_TEAL
        r.font.name = 'Ubuntu Light'

        dist_data = [
            ("0 (no cascade)", "1", "1", "1"),
            ("1 (local impact)", "3", "17", "23"),
            ("2 (moderate cascade)", "14", "10", "6"),
            ("3 (severe cascade)", "12", "4", "2"),
            ("4 (total blackout)", "3", "1", "1"),
        ]

        for label, a, b, c in dist_data:
            row = f"{label:<25s} {a:>20s} {b:>20s} {c:>20s}"
            p2 = tf.add_paragraph()
            r2 = p2.add_run()
            r2.text = row
            r2.font.size = Pt(19)
            r2.font.color.rgb = BLACK
            r2.font.name = 'Ubuntu Light'
            p2.space_before = Pt(10)

        # Interpretation
        p3 = tf.add_paragraph()
        p3.space_before = Pt(30)
        r3 = p3.add_run()
        r3.text = "Interpretation"
        r3.font.size = Pt(22)
        r3.font.bold = True
        r3.font.color.rgb = GREEN
        r3.font.name = 'Ubuntu Light'

        interp = [
            "Scenario A: Most faults cause 2-3 VSC cascading disconnections",
            "Scenario C: 70% of faults only affect 1 VSC (localized impact)",
            "The distribution shifts from multi-converter cascading to single-converter trips",
        ]
        for text in interp:
            p4 = tf.add_paragraph()
            r4 = p4.add_run()
            r4.text = "  " + text
            r4.font.size = Pt(17)
            r4.font.color.rgb = BLACK
            r4.font.name = 'Ubuntu Light'

# ============================================================
# SLIDE 12: Per-VSC Vulnerability
# ============================================================
slide = prs.slides.add_slide(prs.slide_layouts[9])
for shape in slide.placeholders:
    idx = shape.placeholder_format.idx
    if idx == 0:
        shape.text_frame.paragraphs[0].text = "VSC Vulnerability Analysis"
        for r in shape.text_frame.paragraphs[0].runs:
            r.font.color.rgb = DARK_TEAL
    elif idx == 2:
        shape.text_frame.paragraphs[0].text = "Which converters are most affected by network faults"
        for r in shape.text_frame.paragraphs[0].runs:
            r.font.color.rgb = GRAY
    elif idx == 1:
        tf = shape.text_frame
        tf.clear()
        lines = [
            ("Most Vulnerable: VSC Bus 18 (Wind, 0.20 MW)", True, RED),
            ("Disconnects in 31/33 fault locations across all scenarios", False, BLACK),
            ("Located at end of longest feeder (Bus 1 → ... → Bus 18)", False, BLACK),
            ("Electrically far from substation — deepest voltage dips", False, BLACK),
            ("", False, BLACK),
            ("Moderately Vulnerable: VSC Bus 33 & Bus 25", True, ORANGE),
            ("VSC Bus 33: disconnects in 24-29 faults depending on scenario", False, BLACK),
            ("VSC Bus 25: disconnects in 12-17 faults depending on scenario", False, BLACK),
            ("Both at end-of-feeder but on shorter branches", False, BLACK),
            ("", False, BLACK),
            ("Most Resilient: VSC Bus 22 (Battery, 0.15 MW)", True, GREEN),
            ("Only disconnects for 3-4 faults (Bus 19-22 branch + Bus 1-2)", False, BLACK),
            ("Short branch from Bus 2 — electrically close to substation", False, BLACK),
            ("Voltage remains above threshold for most fault locations", False, BLACK),
            ("", False, BLACK),
            ("Bus 1 (substation): the only bus where no VSC disconnects", True, DARK_TEAL),
        ]
        for i, (text, bold, color) in enumerate(lines):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            run = p.add_run()
            run.text = text
            run.font.size = Pt(20) if bold else Pt(17)
            run.font.bold = bold
            run.font.color.rgb = color
            run.font.name = 'Ubuntu Light'

# ============================================================
# SLIDE 13: Conclusions
# ============================================================
slide = prs.slides.add_slide(prs.slide_layouts[9])
for shape in slide.placeholders:
    idx = shape.placeholder_format.idx
    if idx == 0:
        shape.text_frame.paragraphs[0].text = "Conclusions & Policy Implications"
        for r in shape.text_frame.paragraphs[0].runs:
            r.font.color.rgb = DARK_TEAL
    elif idx == 2:
        shape.text_frame.paragraphs[0].text = ""
    elif idx == 1:
        tf = shape.text_frame
        tf.clear()
        lines = [
            ("Cascading Amplifier Effect", True, GREEN),
            ("Higher thresholds (0.85 p.u.) cause even moderate dips to trigger cascading", False, BLACK),
            ("disconnection — a positive feedback loop that amplifies the fault impact", False, BLACK),
            ("", False, BLACK),
            ("Stringent LVRT Reduces Cascading by 43%", True, GREEN),
            ("Average VSCs disconnected per fault: 2.39 (no LVRT) → 1.36 (stringent LVRT)", False, BLACK),
            ("Multi-converter cascading events drop from 29/33 to 9/33 faults", False, BLACK),
            ("", False, BLACK),
            ("Network Topology Matters", True, GREEN),
            ("End-of-feeder converters (Bus 18) are most vulnerable to cascading", False, BLACK),
            ("Short-branch converters (Bus 22) are naturally resilient", False, BLACK),
            ("Converter placement strategy should consider electrical distance from substation", False, BLACK),
            ("", False, BLACK),
            ("Policy Implication", True, DARK_TEAL),
            ("Mandating stringent LVRT (modern grid codes EN 50549, VDE 4110) is essential", False, BLACK),
            ("for limiting cascading DER loss in distribution networks with high DER penetration", False, BLACK),
        ]
        for i, (text, bold, color) in enumerate(lines):
            p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
            run = p.add_run()
            run.text = text
            run.font.size = Pt(22) if bold else Pt(18)
            run.font.bold = bold
            run.font.color.rgb = color
            run.font.name = 'Ubuntu Light'

# ============================================================
# SAVE
# ============================================================
prs.save(OUTPUT)
print(f"Presentation saved to {OUTPUT}")
print(f"Total slides: {len(prs.slides)}")
