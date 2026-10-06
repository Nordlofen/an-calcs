"""Display notation shared by the notebook schema and PDF labels.

Stored calculation keys stay compatible: b maps to x, l to y, and a
moment about y acts in x (and vice versa). No values or signs change here.
"""

DISPLAY_LABELS = {
    "b": "Sulmått i x-led, bₓ", "l": "Sulmått i y-led, bᵧ",
    "e_b_plac": "Placeringsexcentricitet x, eₓ",
    "e_l_plac": "Placeringsexcentricitet y, eᵧ",
    "F_vy": "Vertikallast, V", "F_vy_bruk": "Vertikallast, V (långtid)",
    "F_hb": "Horisontallast i x-led, Hₓ", "F_hl": "Horisontallast i y-led, Hᵧ",
    "M_insp_b": "Moment kring x-axeln, Mₓ", "M_insp_l": "Moment kring y-axeln, Mᵧ",
    "M_insp_b_bruk": "Moment kring x-axeln, Mₓ (långtid)",
    "M_insp_l_bruk": "Moment kring y-axeln, Mᵧ (långtid)",
}

LOAD_GROUPS = [
    {"label": "Brott", "fields": [
        {"name": "F_vy", "symbol": "V", "unit": "kN"},
        {"name": "F_hb", "symbol": "Hₓ", "unit": "kN"},
        {"name": "F_hl", "symbol": "Hᵧ", "unit": "kN"},
        {"name": "M_insp_b", "symbol": "Mₓ", "unit": "kNm"},
        {"name": "M_insp_l", "symbol": "Mᵧ", "unit": "kNm"},
    ]},
    {"label": "Bruk", "fields": [
        {"name": "F_vy_bruk", "symbol": "V", "unit": "kN"},
        {"name": "M_insp_b_bruk", "symbol": "Mₓ", "unit": "kNm"},
        {"name": "M_insp_l_bruk", "symbol": "Mᵧ", "unit": "kNm"},
    ]},
]
