import math


def _post(namn, latex, value, unit="", etikett=""):
    """
    Skapar en standardiserad datapost för presentations- och beräkningsdata.

    Parametrar:
        namn : str
            Internt namn på storheten.

        latex : str
            LaTeX-beteckning för storheten.

        value : float | int | str
            Värde som ska lagras.

        unit : str, optional
            Enhet som ren text, utan LaTeX-omslag.

        etikett : str, optional
            Kort förklarande text för storheten.

    Returvärde:
        dict
            Standardiserad datapost.
    """
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


def barformaga_trapelare(px):
    """
    Beräknar dimensionerande bärförmåga i tryck för träpelare enligt
    EN 1995-1-1, 6.3.2.

    Funktionen returnerar en standardiserad ``details``-dictionary där både
    numeriska värden och presentationsmetadata finns med. Tanken är att en
    generell presentationsklass, till exempel ``CalcBlock``, ska kunna använda
    returvärdet utan att känna till något om just träpelare.

    Parameterformat:
        px = [h, t, n, axel, beta, L, f_c_0_k, E_0_05, beta_c, gamma_M, k_mod]

    Parametrar:
        h : float
            Höjd på en enskild regel/planka [mm]

        t : float
            Tjocklek på en enskild regel/planka [mm]

        n : int | float
            Antal parallella reglar/plankor [-]

        axel : str
            Vald knäckningsaxel:
            - "styv" eller "y"
            - "vek" eller "z"

        beta : float
            Knäcklängdsfaktor [-]

        L : float
            Pelarlängd / knäcklängd [mm]

        f_c_0_k : float
            Karakteristisk tryckhållfasthet parallellt fiberriktningen [MPa]

        E_0_05 : float
            5-percentilvärde för elasticitetsmodul parallellt fiberriktningen [MPa]

        beta_c : float
            Imperfektionsfaktor för tryckknäckning [-]

        gamma_M : float
            Partialkoefficient för material [-]

        k_mod : float
            Modifieringsfaktor [-]

    Returvärde:
        dict
            Dictionary med nycklarna ``metodbeskrivning``, ``indata``,
            ``delresultat``, ``slutresultat`` och ``ekvationer``.
    """
    h, t, n, axel, beta, L, f_c_0_k, E_0_05, beta_c, gamma_M, k_mod = px

    if h <= 0:
        raise ValueError("h måste vara > 0.")
    if t <= 0:
        raise ValueError("t måste vara > 0.")
    if n <= 0:
        raise ValueError("n måste vara > 0.")
    if beta <= 0:
        raise ValueError("beta måste vara > 0.")
    if L <= 0:
        raise ValueError("L måste vara > 0.")
    if f_c_0_k <= 0:
        raise ValueError("f_c_0_k måste vara > 0.")
    if E_0_05 <= 0:
        raise ValueError("E_0_05 måste vara > 0.")
    if beta_c <= 0:
        raise ValueError("beta_c måste vara > 0.")
    if gamma_M <= 0:
        raise ValueError("gamma_M måste vara > 0.")
    if k_mod <= 0:
        raise ValueError("k_mod måste vara > 0.")

    axel_norm = str(axel).strip().lower()
    giltiga_axlar = {"styv", "y", "vek", "z"}
    if axel_norm not in giltiga_axlar:
        raise ValueError("axel måste vara 'styv', 'vek', 'y' eller 'z'.")

    I_y = n * t * h**3 / 12.0
    I_z = n * h * t**3 / 12.0
    A = n * h * t

    if axel_norm in {"styv", "y"}:
        vald_axel = "styv"
        I_vald = I_y
    else:
        vald_axel = "vek"
        I_vald = I_z

    i = math.sqrt(I_vald / A)
    L_cr = beta * L
    lambda_ = L_cr / i
    lambda_rel = (lambda_ / math.pi) * math.sqrt(f_c_0_k / E_0_05)
    k = 0.5 * (1.0 + beta_c * (lambda_rel - 0.3) + lambda_rel**2)
    rotuttryck = k**2 - lambda_rel**2

    if rotuttryck < 0:
        if rotuttryck > -1e-12:
            rotuttryck = 0.0
        else:
            raise ValueError("Uttrycket under rottecknet blev negativt.")

    k_c = 1.0 / (k + math.sqrt(rotuttryck))
    N_R_d = (k_mod / gamma_M) * f_c_0_k * A * k_c / 1000.0

    return {
        "metodbeskrivning": {
            "title": "Metodbeskrivning",
            "items": [
                {
                    "rubrik": "Beräkning",
                    "text": (
                        "Denna funktion avser beräkning av dimensionerande bärförmåga i "
                        "axiellt tryck för träpelare. Kontroll utförs med avseende på "
                        "tryckhållfasthet parallellt fiberriktningen samt reduktion för "
                        "instabilitet genom knäckning kring vald huvudaxel. Pelarens "
                        "relativa slankhet och reduktionsfaktor bestäms och används "
                        "därefter för att fastställa dimensionerande "
                        "normalkraftsbärförmåga."
                    ),
                },
                {
                    "rubrik": "Standard",
                    "text": (
                        "SS_EN_1995_1_1 - Eurokod 5: Dimensionering av "
                        "träkonstruktioner - Del 1-1: Allmänt - Gemensamma regler och "
                        "regler för byggnader"
                    ),
                },
                {
                    "rubrik": "Avsnitt",
                    "text": (
                        "6.3.2 - Pelare utsatta för enbart tryck eller för samtidigt "
                        "tryck och böjning"
                    ),
                },
                {
                    "rubrik": "Begränsning",
                    "text": (
                        "Funktionen är i sin nuvarande utformning avsedd för axiellt "
                        "tryckta träpelare. Någon explicit hänsyn till böjspänningar "
                        "eller samtidig verkan av tryck och böjning tas för närvarande "
                        "inte med i själva beräkningsgången. Den lasteffekt som "
                        "behandlas i funktionen utgörs därför enbart av tryckande "
                        "normalkraft."
                    ),
                },
            ],
        },
        "indata": {
            "title": "Indata",
            "items": [
                _post("h", "h", h, "mm", "tvärsnittshöjd"),
                _post("t", "t", t, "mm", "tjocklek"),
                _post("n", "n", n, "", "antal reglar"),
                _post("axel", r"\mathrm{axel}", vald_axel, "", "vald knäckningsaxel"),
                _post("beta", r"\beta", beta, "", "knäcklängdsfaktor"),
                _post("L", "L", L, "mm", "pelarlängd"),
                _post("f_c_0_k", r"f_{c,0,k}", f_c_0_k, "MPa", "karakteristisk tryckhållfasthet"),
                _post("E_0_05", r"E_{0.05}", E_0_05, "MPa", "5-percentil elasticitetsmodul"),
                _post("beta_c", r"\beta_c", beta_c, "", "imperfektionsfaktor"),
                _post("gamma_M", r"\gamma_M", gamma_M, "", "partialkoefficient"),
                _post("k_mod", r"k_{mod}", k_mod, "", "modifieringsfaktor"),
            ],
        },
        "delresultat": {
            "title": "Delresultat",
            "items": [
                _post("I_y", "I_y", I_y, "mm^4", "tröghetsmoment kring y-axeln"),
                _post("I_z", "I_z", I_z, "mm^4", "tröghetsmoment kring z-axeln"),
                _post("A", "A", A, "mm^2", "total tvärsnittsarea"),
                _post("I", "I", I_vald, "mm^4", "tröghetsmoment för vald axel"),
                _post("i", "i", i, "mm", "tröghetsradie"),
                _post("L_cr", r"L_{cr}", L_cr, "mm", "kritisk knäcklängd"),
                _post("lambda", r"\lambda", lambda_, "", "slankhet"),
                _post("lambda_rel", r"\lambda_{rel}", lambda_rel, "", "relativ slankhet"),
                _post("k", "k", k, "", "hjälpparameter för knäckning"),
                _post("k_c", "k_c", k_c, "", "reduktionsfaktor för knäckning"),
            ],
        },
        "slutresultat": {
            "title": "Slutresultat",
            "items": [
                _post("N_R_d", r"N_{R,d}", N_R_d, "kN", "dimensionerande bärförmåga i tryck"),
            ],
        },
        "ekvationer": {
            "title": "Ekvationer",
            "items": [
                _ekvation(r"I_y = \frac{n \, t \, h^3}{12}", "tröghetsmoment kring y-axeln"),
                _ekvation(r"I_z = \frac{n \, h \, t^3}{12}", "tröghetsmoment kring z-axeln"),
                _ekvation(r"A = n \, h \, t", "total tvärsnittsarea"),
                _ekvation(r"i = \sqrt{\frac{I}{A}}", "tröghetsradie"),
                _ekvation(r"L_{cr} = \beta \, L", "kritisk knäcklängd"),
                _ekvation(r"\lambda = \frac{L_{cr}}{i}", "slankhet"),
                _ekvation(r"\lambda_{rel} = \frac{\lambda}{\pi}\sqrt{\frac{f_{c,0,k}}{E_{0.05}}}", "relativ slankhet"),
                _ekvation(r"k = 0.5 \, \left(1 + \beta_c \, (\lambda_{rel} - 0.3) + \lambda_{rel}^2\right)", "hjälpparameter för knäckning"),
                _ekvation(r"k_c = \frac{1}{k + \sqrt{k^2 - \lambda_{rel}^2}}", "reduktionsfaktor för knäckning"),
                _ekvation(r"N_{R,d} = \frac{k_{mod}}{\gamma_M} \, f_{c,0,k} \, A \, k_c \, / \, 1000", "dimensionerande bärförmåga i tryck"),
            ],
        },
    }
