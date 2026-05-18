import math


def _post(namn, latex, value, unit="", etikett=""):
    """Skapar en standardiserad datapost."""
    return {
        "namn": namn,
        "latex": latex,
        "value": value,
        "unit": unit,
        "etikett": etikett,
    }


def _ekvation(latex, etikett):
    """Skapar en standardiserad ekvationspost."""
    return {"latex": latex, "etikett": etikett}


TERRANGDATA = {
    "0": {"z_0": 0.003, "z_min": 1.0},
    "I": {"z_0": 0.01, "z_min": 1.0},
    "II": {"z_0": 0.05, "z_min": 2.0},
    "III": {"z_0": 0.30, "z_min": 5.0},
    "IV": {"z_0": 1.00, "z_min": 10.0},
}

K_P = 3.0
C_0 = 1.0
Z_REF = 0.05
RHO = 1.25


def _normalisera_terrangtyp(value):
    if isinstance(value, int) and value == 0:
        return "0"

    terrangtyp = str(value).strip().upper()
    if terrangtyp not in TERRANGDATA:
        raise ValueError("terrangtyp måste vara 0, '0', 'I', 'II', 'III' eller 'IV'.")
    return terrangtyp


def _tolka_px(px):
    if not isinstance(px, (list, tuple)):
        raise ValueError("px för vindhastighetstryck måste vara en lista eller tuple.")
    if len(px) != 3:
        raise ValueError("px för vindhastighetstryck måste innehålla exakt 3 värden.")

    terrangtyp, z, v_b = px
    terrangtyp = _normalisera_terrangtyp(terrangtyp)
    z = float(z)
    v_b = float(v_b)

    if z <= 0:
        raise ValueError("z måste vara > 0.")
    if v_b <= 0:
        raise ValueError("v_b måste vara > 0.")

    return terrangtyp, z, v_b


def vindhastighetstryck(px):
    """
    Beräknar karakteristiskt vindhastighetstryck q_pk(z).

    Exempel på px:
        px = [
            "II",  # terrangtyp: 0, I, II, III eller IV
            10.0,  # z, byggnadshöjd [m]
            24.0,  # v_b, referensvindhastighet [m/s]
        ]
    """
    terrangtyp, z, v_b = _tolka_px(px)

    z_0 = TERRANGDATA[terrangtyp]["z_0"]
    z_min = TERRANGDATA[terrangtyp]["z_min"]
    z_eff = max(z, z_min)
    log_z = math.log(z_eff / z_0)

    k_r = 0.19 * (z_0 / Z_REF) ** 0.07
    I_v = 1.0 / (C_0 * log_z)
    q_b = 0.5 * RHO * v_b**2 / 1000.0
    q_pk = (1.0 + 2.0 * K_P * I_v) * (k_r * log_z * C_0) ** 2 * q_b

    return {
        "metodbeskrivning": {
            "title": "Metodbeskrivning",
            "items": [
                {
                    "rubrik": "Beräkning",
                    "text": (
                        "Beräknar karakteristiskt vindhastighetstryck "
                        "utifrån terrängtyp, byggnadshöjd och referensvindhastighet. "
                        "Terrängtypen används för att bestämma råhetslängd och minsta höjd."
                    ),
                },
                {
                    "rubrik": "Standard",
                    "text": "BFS 2024:6, 38-39 §§. Formel för karakteristiskt hastighetstryck redovisas på sida 26.",
                },
                {
                    "rubrik": "Antaganden",
                    "text": (
                        "Topografifaktorn sätts till 1,0. Grundhastighetstrycket "
                        "beräknas med standardantagen luftdensitet 1,25 kg/m3."
                    ),
                },
            ],
        },
        "indata": {
            "title": "Indata",
            "items": [
                _post("terrangtyp", "terrängtyp", terrangtyp, "-", "terrängtyp"),
                _post("z", "z", z, "m", "byggnadshöjd"),
                _post("v_b", r"v_b", v_b, "m/s", "referensvindhastighet"),
            ],
        },
        "delresultat": {
            "title": "Delresultat",
            "items": [
                _post("z_0", r"z_0", z_0, "m", "råhetslängd"),
                _post("z_min", r"z_{min}", z_min, "m", "minsta höjd för terrängtyp"),
                _post("z_eff", r"z_{eff}", z_eff, "m", "beräkningshöjd"),
                _post("z_ref", r"z_{ref}", Z_REF, "m", "referensråhetslängd"),
                _post("k_p", r"k_p", K_P, "-", "toppfaktor"),
                _post("c_0", r"c_0(z)", C_0, "-", "topografifaktor"),
                _post("rho", r"\rho", RHO, "kg/m^3", "luftdensitet"),
                _post("k_r", r"k_r", k_r, "-", "terrängfaktor"),
                _post("I_v", r"I_v(z)", I_v, "-", "turbulensintensitet"),
                _post("q_b", r"q_b", q_b, "kN/m^2", "grundhastighetstryck"),
            ],
        },
        "slutresultat": {
            "title": "Slutresultat",
            "items": [
                _post("q_pk", r"q_{pk}(z)", q_pk, "kN/m^2", "karakteristiskt hastighetstryck"),
            ],
        },
        "ekvationer": {
            "title": "Ekvationer",
            "items": [
                _ekvation(r"z_{eff} = \max(z, z_{min})", "beräkningshöjd"),
                _ekvation(r"k_r = 0.19 \left(\frac{z_0}{z_{ref}}\right)^{0.07}", "terrängfaktor"),
                _ekvation(r"I_v(z) = \frac{1}{c_0(z)\ln(z_{eff}/z_0)}", "turbulensintensitet"),
                _ekvation(r"q_b = \frac{1}{2}\rho v_b^2", "grundhastighetstryck"),
                _ekvation(
                    r"q_{pk}(z) = [1 + 2 k_p I_v(z)] [k_r \ln(z_{eff}/z_0)c_0(z)]^2 q_b",
                    "karakteristiskt hastighetstryck",
                ),
            ],
        },
    }


vindhastighetstryck.panel_schema = {
    "title": "Vindhastighetstryck",
    "px": ["terrangtyp", "z", "v_b"],
    "fields": [
        {
            "name": "terrangtyp",
            "type": "choice",
            "label": "Terrängtyp",
            "default": "II",
            "options": [
                {"label": "0", "value": "0"},
                {"label": "I", "value": "I"},
                {"label": "II", "value": "II"},
                {"label": "III", "value": "III"},
                {"label": "IV", "value": "IV"},
            ],
        },
        {"name": "z", "type": "float", "label": "Byggnadshöjd", "unit": "m", "default": 10.0},
        {"name": "v_b", "type": "float", "label": "Referensvindhastighet", "unit": "m/s", "default": 24.0},
    ],
}
