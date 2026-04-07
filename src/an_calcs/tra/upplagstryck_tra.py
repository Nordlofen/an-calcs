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


def _tolka_l_1(l_1):
    if isinstance(l_1, str):
        if l_1.strip().lower() != "lang":
            raise ValueError("l_1 måste vara ett positivt tal eller strängen 'lang'.")
        return "lang", 30.0

    if l_1 <= 0:
        raise ValueError("l_1 måste vara ett positivt tal eller strängen 'lang'.")

    return l_1, min(30.0, l_1 / 2.0)


def _hamta_k_c_90(upplagsfall, materialtyp, l, l_1, h):
    if upplagsfall == "understodd_barverksdel_dubbelsidig":
        if l_1 == "lang":
            l_1_for_check = float("inf")
        else:
            l_1_for_check = l_1

        if l_1_for_check < 2.0 * h:
            raise ValueError(
                "För 'understodd_barverksdel_dubbelsidig' krävs att l_1 >= 2h."
            )

        if materialtyp == "konstruktionsvirke":
            return 1.25
        return 1.50

    if l > 2.0 * h:
        raise ValueError("För 'barverksdel_pa_upplag_enkelsidig' krävs att l <= 2h.")

    if materialtyp == "konstruktionsvirke":
        return 1.50

    if l > 400.0:
        raise ValueError(
            "För limträ och 'barverksdel_pa_upplag_enkelsidig' krävs att l <= 400 mm."
        )

    return 1.75


def upplagstryck_tra(px):
    """
    Beräknar dimensionerande bärförmåga för upplagstryck vinkelrätt
    fiberriktningen enligt EN 1995-1-1, 6.1.5.

    Parameterformat:
        px = [
            b, l, a, l_1, h, upplagsfall, materialtyp,
            f_c_90_k, k_mod, gamma_M, tillat_hogre_tryck_eks
        ]
        eller
        px = [
            b, l, a, l_1, h, upplagsfall, materialtyp,
            f_c_90_k, k_mod, gamma_M, tillat_hogre_tryck_eks, N_c_90_Ed
        ]

    Parametrar:
        b : float
            Kontaktbredd [mm]

        l : float
            Fysisk kontaktlängd [mm]

        a : float
            Avstånd till ändträkant [mm]. Värdet 0 representerar ändupplag.

        l_1 : float | str
            Tillgänglig längd inåt i lastspridningsriktningen [mm] eller "lang".

        h : float
            Bärverksdelens höjd [mm]

        upplagsfall : str
            "understodd_barverksdel_dubbelsidig" eller
            "barverksdel_pa_upplag_enkelsidig"

        materialtyp : str
            "konstruktionsvirke" eller "limtra"

        f_c_90_k : float
            Karakteristisk tryckhållfasthet vinkelrätt fiberriktningen [MPa]

        k_mod : float
            Modifieringsfaktor [-]

        gamma_M : float
            Partialkoefficient [-]

        tillat_hogre_tryck_eks : bool
            Om True används svensk EKS-tillämpning med k_mod = 1,0 och gamma_M = 1,0.

        N_c_90_Ed : float | None
            Dimensionerande tryckkraft [kN]

    Returvärde:
        dict
            Dictionary med nycklarna ``metodbeskrivning``, ``indata``,
            ``delresultat``, ``slutresultat`` och ``ekvationer``.
    """
    if len(px) == 11:
        (
            b,
            l,
            a,
            l_1,
            h,
            upplagsfall,
            materialtyp,
            f_c_90_k,
            k_mod,
            gamma_M,
            tillat_hogre_tryck_eks,
        ) = px
        N_c_90_Ed = None
    elif len(px) == 12:
        (
            b,
            l,
            a,
            l_1,
            h,
            upplagsfall,
            materialtyp,
            f_c_90_k,
            k_mod,
            gamma_M,
            tillat_hogre_tryck_eks,
            N_c_90_Ed,
        ) = px
    else:
        raise ValueError("px måste innehålla 11 eller 12 värden.")

    if b <= 0:
        raise ValueError("b måste vara > 0.")
    if l <= 0:
        raise ValueError("l måste vara > 0.")
    if a < 0:
        raise ValueError("a måste vara >= 0.")
    if h <= 0:
        raise ValueError("h måste vara > 0.")
    if f_c_90_k <= 0:
        raise ValueError("f_c_90_k måste vara > 0.")
    if k_mod <= 0:
        raise ValueError("k_mod måste vara > 0.")
    if gamma_M <= 0:
        raise ValueError("gamma_M måste vara > 0.")
    if N_c_90_Ed is not None and N_c_90_Ed <= 0:
        raise ValueError("N_c_90_Ed måste vara > 0 om det anges.")

    upplagsfall = str(upplagsfall).strip().lower()
    if upplagsfall not in {
        "understodd_barverksdel_dubbelsidig",
        "barverksdel_pa_upplag_enkelsidig",
    }:
        raise ValueError(
            "upplagsfall måste vara "
            "'understodd_barverksdel_dubbelsidig' eller "
            "'barverksdel_pa_upplag_enkelsidig'."
        )

    materialtyp = str(materialtyp).strip().lower()
    if materialtyp not in {"konstruktionsvirke", "limtra"}:
        raise ValueError("materialtyp måste vara 'konstruktionsvirke' eller 'limtra'.")

    l_1_post_value, x_in = _tolka_l_1(l_1)
    x_end = min(30.0, a)
    A_ef = b * (l + x_end + x_in)

    k_mod_eff = 1.0 if tillat_hogre_tryck_eks else k_mod
    gamma_M_eff = 1.0 if tillat_hogre_tryck_eks else gamma_M
    f_c_90_d = (k_mod_eff / gamma_M_eff) * f_c_90_k
    k_c_90 = _hamta_k_c_90(upplagsfall, materialtyp, l, l_1_post_value, h)
    N_c_90_Rd = k_c_90 * f_c_90_d * A_ef / 1000.0

    delresultat_items = [
        _post("x_end", r"x_{end}", x_end, "mm", "effektivt tillägg mot ändträkant"),
        _post("x_in", r"x_{in}", x_in, "mm", "effektivt tillägg inåt i bärverksdelen"),
        _post("A_ef", r"A_{ef}", A_ef, "mm^2", "effektiv kontaktyta"),
        _post("k_c_90", r"k_{c,90}", k_c_90, "", "faktor för tryck vinkelrätt fiberriktningen"),
        _post("f_c_90_d", r"f_{c,90,d}", f_c_90_d, "MPa", "dimensionerande tryckhållfasthet"),
    ]

    slutresultat_items = [
        _post("N_c_90_Rd", r"N_{c,90,Rd}", N_c_90_Rd, "kN", "dimensionerande bärförmåga"),
    ]

    if N_c_90_Ed is not None:
        sigma_c_90_d = N_c_90_Ed * 1000.0 / A_ef
        eta = N_c_90_Ed / N_c_90_Rd
        kontroll_ok = N_c_90_Ed <= N_c_90_Rd

        delresultat_items.append(
            _post(
                "sigma_c_90_d",
                r"\sigma_{c,90,d}",
                sigma_c_90_d,
                "MPa",
                "dimensionerande tryckspänning",
            )
        )
        slutresultat_items.extend(
            [
                _post("N_c_90_Ed", r"N_{c,90,Ed}", N_c_90_Ed, "kN", "dimensionerande tryckkraft"),
                _post("eta", r"\eta", eta, "", "utnyttjandegrad"),
                _post("kontroll_ok", r"\mathrm{OK}", kontroll_ok, "", "uppfyller bärförmågekravet"),
            ]
        )

    indata_items = [
        _post("b", "b", b, "mm", "kontaktbredd"),
        _post("l", "l", l, "mm", "fysisk kontaktlängd"),
        _post("a", "a", a, "mm", "avstånd till ändträkant"),
        _post("l_1", r"l_1", l_1_post_value, "mm" if l_1_post_value != "lang" else "-", "tillgänglig längd inåt"),
        _post("h", "h", h, "mm", "bärverksdelens höjd"),
        _post("upplagsfall", "upplagsfall", upplagsfall, "-", "valt normfall"),
        _post("materialtyp", "materialtyp", materialtyp, "-", "materialtyp"),
        _post("f_c_90_k", r"f_{c,90,k}", f_c_90_k, "MPa", "karakteristisk tryckhållfasthet"),
        _post("k_mod", r"k_{mod}", k_mod_eff, "-", "modifieringsfaktor"),
        _post("gamma_M", r"\gamma_M", gamma_M_eff, "-", "partialkoefficient"),
        _post("tillat_hogre_tryck_eks", "EKS", bool(tillat_hogre_tryck_eks), "-", "tillåt högre tryck enligt EKS"),
    ]

    if N_c_90_Ed is not None:
        indata_items.append(
            _post("N_c_90_Ed", r"N_{c,90,Ed}", N_c_90_Ed, "kN", "dimensionerande tryckkraft")
        )

    return {
        "metodbeskrivning": {
            "title": "Metodbeskrivning",
            "items": [
                {
                    "rubrik": "Beräkning",
                    "text": (
                        "Denna funktion avser beräkning av upplagstryck vinkelrätt "
                        "fiberriktningen för koncentrerad last i trä. Effektiv "
                        "kontaktyta bestäms med randtillägg mot ändträkant samt med "
                        "lastspridning inåt i bärverksdelen. Därefter bestäms "
                        "dimensionerande hållfasthet, korrekt värde på k_c,90 och "
                        "slutligen dimensionerande bärförmåga."
                    ),
                },
                {
                    "rubrik": "Standard",
                    "text": (
                        "SS_EN_1995_1_1 - Eurokod 5: Dimensionering av "
                        "träkonstruktioner - Del 1-1: Allmänt - Gemensamma regler "
                        "och regler för byggnader"
                    ),
                },
                {
                    "rubrik": "Avsnitt",
                    "text": "6.1.5 - Tryck vinkelrätt fiberriktningen",
                },
                {
                    "rubrik": "Begränsning",
                    "text": (
                        "Ändupplag modelleras genom att sätta a = 0 mm. Om l_1 anges "
                        "som 'lang' antas lastspridningen vara tillräckligt stor för "
                        "att x_in ska få sättas till 30 mm. LVL/Kerto behandlas som "
                        "limträ i denna funktion."
                    ),
                },
            ],
        },
        "indata": {
            "title": "Indata",
            "items": indata_items,
        },
        "delresultat": {
            "title": "Delresultat",
            "items": delresultat_items,
        },
        "slutresultat": {
            "title": "Slutresultat",
            "items": slutresultat_items,
        },
        "ekvationer": {
            "title": "Ekvationer",
            "items": [
                _ekvation(r"x_{end} = \min(30, a)", "effektivt tillägg mot ändträkant"),
                _ekvation(r"x_{in} = 30", "effektivt tillägg inåt när l1 är 'lang'"),
                _ekvation(r"x_{in} = \min(30, l_1 / 2)", "effektivt tillägg inåt när l1 anges numeriskt"),
                _ekvation(r"A_{ef} = b \, (l + x_{end} + x_{in})", "effektiv kontaktyta"),
                _ekvation(r"f_{c,90,d} = \frac{k_{mod}}{\gamma_M} \, f_{c,90,k}", "dimensionerande tryckhållfasthet"),
                _ekvation(r"\sigma_{c,90,d} = \frac{N_{c,90,Ed} \, 1000}{A_{ef}}", "dimensionerande tryckspänning"),
                _ekvation(r"N_{c,90,Rd} = k_{c,90} \, f_{c,90,d} \, A_{ef} \, / \, 1000", "dimensionerande bärförmåga"),
            ],
        },
    }
