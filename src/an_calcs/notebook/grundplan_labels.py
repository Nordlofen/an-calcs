"""Display notation shared by the notebook schema and PDF labels.

Stored calculation keys stay compatible: b maps to x, l to y, and a
moment about y acts in x (and vice versa). No values or signs change here.
"""

DISPLAY_LABELS = {
    "b": "Sulmått i x-led", "l": "Sulmått i y-led",
    "e_b_plac": "Placeringsexcentricitet i x-led",
    "e_l_plac": "Placeringsexcentricitet i y-led",
    "F_vy": "Vertikallast", "F_vy_bruk": "Vertikallast, långtid",
    "F_hb": "Horisontallast i x-led", "F_hl": "Horisontallast i y-led",
    "M_insp_b": "Moment kring x-axeln", "M_insp_l": "Moment kring y-axeln",
    "M_insp_b_bruk": "Moment kring x-axeln",
    "M_insp_l_bruk": "Moment kring y-axeln",
    "gamma_m": "Partialkoefficient", "gamma_m0": "Partialkoefficient",
    "f_d_brott": "Bärförmåga i brott", "f_d_bruk": "Bärförmåga i bruk",
}

# Structured text permits real italic/subscript elements without parsing HTML.
# It also works offline in the exported result view.
DISPLAY_SYMBOLS = {
    "b": {"base": "b", "subscript": "x"},
    "l": {"base": "b", "subscript": "y"},
    "t": {"base": "t"}, "d": {"base": "d"},
    "e_b_plac": {"base": "e", "subscript": "x,plac"},
    "e_l_plac": {"base": "e", "subscript": "y,plac"},
    "F_vy": {"base": "V"}, "F_vy_bruk": {"base": "V"},
    "F_hb": {"base": "H", "subscript": "x"},
    "F_hl": {"base": "H", "subscript": "y"},
    "M_insp_b": {"base": "M", "subscript": "x"},
    "M_insp_l": {"base": "M", "subscript": "y"},
    "M_insp_b_bruk": {"base": "M", "subscript": "x"},
    "M_insp_l_bruk": {"base": "M", "subscript": "y"},
    "c_prime": {"base": "c", "suffix": "′"},
    "c_uk": {"base": "c", "subscript": "uk"},
    "gamma": {"base": "γ"}, "gamma_prime": {"base": "γ", "suffix": "′"},
    "phi_k": {"base": "φ", "subscript": "k"},
    "delta_h": {"prefix": "Δ", "base": "h"},
    "beta": {"base": "β"}, "alpha": {"base": "α"}, "eta": {"base": "η"},
    "gamma_m": {"base": "γ", "subscript": "m"},
    "gamma_m0": {"base": "γ", "subscript": "m,0"},
    "gamma_Rd": {"base": "γ", "subscript": "Rd"},
    "f_d_brott": {"base": "f", "subscript": "d,brott"},
    "f_d_bruk": {"base": "f", "subscript": "d,bruk"},
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
