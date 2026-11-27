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


def _tolka_taltext(text, felmeddelande):
    try:
        return float(text.replace(",", "."))
    except ValueError:
        raise ValueError(felmeddelande) from None


def _tolka_l_1(l_1):
    felmeddelande = "l_1 måste vara ett positivt, ändligt tal eller strängen 'lang'."
    if isinstance(l_1, str):
        if l_1.strip().lower() == "lang":
            return "lang", 30.0
        l_1 = _tolka_taltext(l_1, felmeddelande)

    if not math.isfinite(l_1) or l_1 <= 0:
        raise ValueError(felmeddelande)

    return l_1, min(30.0, l_1 / 2.0)


def _hamta_k_c_90(upplagsfall, materialtyp, l, l_1, h):
    l_1_for_check = float("inf") if l_1 == "lang" else l_1

    if l_1_for_check < 2.0 * h:
        raise ValueError("För vald k_c,90-nivå krävs att l_1 >= 2h.")

    if upplagsfall == "understodd_barverksdel_dubbelsidig":
        if materialtyp == "konstruktionsvirke":
            return 1.25
        return 1.50

    if materialtyp == "konstruktionsvirke":
        return 1.50

    if l > 400.0:
        return 1.50

    return 1.75


def _tolka_px_direkt(px):
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
        raise ValueError(
            "Ogiltigt antal värden. Stödda format är: direktformat 11/12 värden, "
            "mittupplag 11/12/13 värden och andupplag 11/12/13 värden."
        )

    return {
        "b": b,
        "l": l,
        "a": a,
        "l_1": l_1,
        "h": h,
        "upplagsfall": upplagsfall,
        "materialtyp": materialtyp,
        "f_c_90_k": f_c_90_k,
        "k_mod": k_mod,
        "gamma_M": gamma_M,
        "tillat_hogre_tryck_eks": tillat_hogre_tryck_eks,
        "N_c_90_Ed": N_c_90_Ed,
        "upplagsplacering": None,
        "explicit_upplagsplacering": False,
    }


def _tolka_px_med_upplagsplacering(px):
    upplagsplacering = str(px[2]).strip().lower()

    if upplagsplacering == "mittupplag":
        if len(px) == 11:
            (
                b,
                l,
                _,
                l_1,
                h,
                upplagsfall,
                materialtyp,
                f_c_90_k,
                k_mod,
                gamma_M,
                tillat_hogre_tryck_eks,
            ) = px
            a = None
            N_c_90_Ed = None
        elif len(px) == 12:
            if isinstance(px[-1], bool):
                (
                    b,
                    l,
                    _,
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
            else:
                (
                    b,
                    l,
                    _,
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
                a = None
        elif len(px) == 13:
            (
                b,
                l,
                _,
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
            raise ValueError(
                "För 'mittupplag' accepteras 11 värden utan last, 12 värden med "
                "last eller 12/13 värden med redundant a-plats som ignoreras."
            )
    else:
        if len(px) == 11:
            (
                b,
                l,
                _,
                l_1,
                h,
                upplagsfall,
                materialtyp,
                f_c_90_k,
                k_mod,
                gamma_M,
                tillat_hogre_tryck_eks,
            ) = px
            a = 0.0
            N_c_90_Ed = None
        elif len(px) == 12:
            if isinstance(px[-1], bool):
                (
                    b,
                    l,
                    _,
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
                if a is None:
                    a = 0.0
            else:
                (
                    b,
                    l,
                    _,
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
                a = 0.0
        elif len(px) == 13:
            (
                b,
                l,
                _,
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
            if a is None:
                a = 0.0
        else:
            raise ValueError(
                "För 'andupplag' accepteras 11 värden utan a, 12 värden med last "
                "utan a eller 12/13 värden med explicit a."
            )

    return {
        "b": b,
        "l": l,
        "a": a,
        "l_1": l_1,
        "h": h,
        "upplagsfall": upplagsfall,
        "materialtyp": materialtyp,
        "f_c_90_k": f_c_90_k,
        "k_mod": k_mod,
        "gamma_M": gamma_M,
        "tillat_hogre_tryck_eks": tillat_hogre_tryck_eks,
        "N_c_90_Ed": N_c_90_Ed,
        "upplagsplacering": upplagsplacering,
        "explicit_upplagsplacering": True,
    }


def _tolka_px(px):
    if not isinstance(px, (list, tuple)):
        raise TypeError("px måste vara en lista eller tuple.")

    if len(px) < 3:
        raise ValueError(
            "Ogiltigt antal värden. Stödda format är: direktformat 11/12 värden, "
            "mittupplag 11/12/13 värden och andupplag 11/12/13 värden."
        )

    tredje = px[2]
    if isinstance(tredje, str):
        tredje_norm = tredje.strip().lower()
        if tredje_norm in {"mittupplag", "andupplag"}:
            return _tolka_px_med_upplagsplacering(px)
        raise ValueError(
            "Om tredje parametern är text måste den vara 'mittupplag' eller 'andupplag'."
        )

    return _tolka_px_direkt(px)


def upplagstryck_tra(px):
    """
    Beräknar dimensionerande bärförmåga för upplagstryck vinkelrätt
    fiberriktningen enligt EN 1995-1-1, 6.1.5.

    Kan användas med ``an_print.Panel(upplagstryck_tra)``. Panelen använder
    ordningen i exemplet nedan.

    Exempel på px:
        px = [
            b,
            l,
            upplagsplacering,
            a,
            l_1,
            h,
            upplagsfall,
            materialtyp,
            f_c_90_k,
            k_mod,
            gamma_M,
            tillat_hogre_tryck_eks,
            F_c_90_Ed
        ]

    Parameternycklar:
        b
            Kontaktbredd [mm].

        l
            Fysisk upplagslängd [mm].

        upplagsplacering
            ``"mittupplag"`` eller ``"andupplag"``.
            I direktformat används inte denna parameter alls.

        a
            Avstånd till ändträkant [mm].
            - används för ``"andupplag"``
            - ignoreras för ``"mittupplag"``
            - får vara ``None`` eller utelämnas för ``"andupplag"``, vilket
              då behandlas som ``a = 0``.

        l_1
            Tillgänglig längd inåt i lastspridningsriktningen [mm] eller
            strängen ``"lang"``. Längden kan även anges som text med
            decimalpunkt eller decimalkomma.

        h
            Bärverksdelens höjd [mm].

        upplagsfall
            ``"understodd_barverksdel_dubbelsidig"``
            eller ``"barverksdel_pa_upplag_enkelsidig"``.

        materialtyp
            ``"konstruktionsvirke"`` eller ``"limtra"``.

        f_c_90_k
            Karakteristisk tryckhållfasthet vinkelrätt fiberriktningen [MPa].

        k_mod
            Modifieringsfaktor [-].

        gamma_M
            Partialkoefficient [-].

        tillat_hogre_tryck_eks
            ``True`` eller ``False``.
            Om ``True`` används effektivt ``k_mod = 1`` och ``gamma_M = 1``.

        F_c_90_Ed
            Valfri dimensionerande kontaktkraft vinkelrätt mot fiberriktningen [kN].
            Kan anges som tal eller text med decimalpunkt eller decimalkomma.
            Tom text motsvarar ``None``.

    Kortare varianter som också accepteras:
        - direktformat utan ``upplagsplacering`` där tredje värdet tolkas som ``a``
        - ``"mittupplag"`` utan ``a``
        - ``"andupplag"`` utan ``a`` vilket då tolkas som ``a = 0``
        - samtliga ovanstående både med och utan ``F_c_90_Ed``

    Kopiera till notebook:
        details = upplagstryck_tra([
            90,                                  # b [mm]
            45,                                  # l [mm]
            "mittupplag",                        # upplagsplacering
            None,                                # a [mm], ignoreras för mittupplag
            25,                                  # l_1 [mm]
            10,                                  # h [mm]
            "understodd_barverksdel_dubbelsidig",# upplagsfall
            "konstruktionsvirke",                # materialtyp
            2.5,                                 # f_c_90_k [MPa]
            0.8,                                 # k_mod [-]
            1.3,                                 # gamma_M [-]
            True,                                # tillat_hogre_tryck_eks
            10.0,                                # F_c_90_Ed [kN]
        ])
    """
    data = _tolka_px(px)

    b = data["b"]
    l = data["l"]
    a = data["a"]
    l_1 = data["l_1"]
    h = data["h"]
    upplagsfall = str(data["upplagsfall"]).strip().lower()
    materialtyp = str(data["materialtyp"]).strip().lower()
    f_c_90_k = data["f_c_90_k"]
    k_mod = data["k_mod"]
    gamma_M = data["gamma_M"]
    tillat_hogre_tryck_eks = data["tillat_hogre_tryck_eks"]
    F_c_90_Ed = data["N_c_90_Ed"]
    upplagsplacering = data["upplagsplacering"]
    explicit_upplagsplacering = data["explicit_upplagsplacering"]

    if not math.isfinite(b) or b <= 0:
        raise ValueError("b måste vara > 0.")
    if not math.isfinite(l) or l <= 0:
        raise ValueError("l måste vara > 0.")
    if not math.isfinite(h) or h <= 0:
        raise ValueError("h måste vara > 0.")
    if not math.isfinite(f_c_90_k) or f_c_90_k <= 0:
        raise ValueError("f_c_90_k måste vara > 0.")
    if not math.isfinite(k_mod) or k_mod <= 0:
        raise ValueError("k_mod måste vara > 0.")
    if not math.isfinite(gamma_M) or gamma_M <= 0:
        raise ValueError("gamma_M måste vara > 0.")
    lastfel = "F_c_90_Ed måste vara ett positivt, ändligt tal om det anges."
    if isinstance(F_c_90_Ed, str):
        F_c_90_Ed = _tolka_taltext(F_c_90_Ed, lastfel) if F_c_90_Ed.strip() else None
    if F_c_90_Ed is not None and (not math.isfinite(F_c_90_Ed) or F_c_90_Ed <= 0):
        raise ValueError(lastfel)

    if upplagsplacering != "mittupplag":
        if not math.isfinite(a) or a < 0:
            raise ValueError("a måste vara >= 0.")

    if upplagsfall not in {
        "understodd_barverksdel_dubbelsidig",
        "barverksdel_pa_upplag_enkelsidig",
    }:
        raise ValueError(
            "upplagsfall måste vara "
            "'understodd_barverksdel_dubbelsidig' eller "
            "'barverksdel_pa_upplag_enkelsidig'."
        )

    if materialtyp not in {"konstruktionsvirke", "limtra"}:
        raise ValueError("materialtyp måste vara 'konstruktionsvirke' eller 'limtra'.")

    l_1_post_value, x_in = _tolka_l_1(l_1)

    if explicit_upplagsplacering and upplagsplacering == "mittupplag":
        x_end = None
        l_ef = l + 2.0 * x_in
    else:
        x_end = min(30.0, a)
        l_ef = l + x_in + x_end

    A_ef = b * l_ef

    k_mod_eff = 1.0 if tillat_hogre_tryck_eks else k_mod
    gamma_M_eff = 1.0 if tillat_hogre_tryck_eks else gamma_M
    f_c_90_d = (k_mod_eff / gamma_M_eff) * f_c_90_k
    k_c_90 = _hamta_k_c_90(upplagsfall, materialtyp, l, l_1_post_value, h)
    F_c_90_Rd = k_c_90 * f_c_90_d * A_ef / 1000.0

    delresultat_items = [
        _post("x_in", r"x_{in}", x_in, "mm", "effektivt tillägg inåt i bärverksdelen"),
        _post("l_ef", r"l_{ef}", l_ef, "mm", "effektiv upplagslängd"),
        _post("A_ef", r"A_{ef}", A_ef, "mm^2", "effektiv kontaktyta"),
        _post("k_c_90", r"k_{c,90}", k_c_90, "", "faktor för tryck vinkelrätt fiberriktningen"),
        _post("f_c_90_d", r"f_{c,90,d}", f_c_90_d, "MPa", "dimensionerande tryckhållfasthet"),
    ]

    if x_end is not None:
        delresultat_items.insert(
            0,
            _post("x_end", r"x_{end}", x_end, "mm", "effektivt tillägg mot ändträkant"),
        )

    # Behåll postnamnen för redovisningskod som läser details.
    slutresultat_items = [
        _post("N_c_90_Rd", r"F_{c,90,Rd}", F_c_90_Rd, "kN", "dimensionerande bärförmåga för upplagstryck"),
    ]

    if F_c_90_Ed is not None:
        sigma_c_90_d = F_c_90_Ed * 1000.0 / A_ef
        eta = 100.0 * F_c_90_Ed / F_c_90_Rd
        eta_text = f"{eta:.3f} %"
        kontroll_ok = F_c_90_Ed <= F_c_90_Rd

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
                _post("N_c_90_Ed", r"F_{c,90,Ed}", F_c_90_Ed, "kN", "dimensionerande kontaktkraft"),
                _post("eta", r"\mu", eta_text, "", "utnyttjandegrad"),
                _post("kontroll_ok", r"\mathrm{OK}", kontroll_ok, "", "uppfyller bärförmågekravet"),
            ]
        )

    indata_items = [
        _post("b", "b", b, "mm", "kontaktbredd"),
        _post("l", "l", l, "mm", "fysisk upplagslängd"),
    ]

    if explicit_upplagsplacering:
        indata_items.append(
            _post("upplagsplacering", "upplagsplacering", upplagsplacering, "-", "vald upplagsplacering")
        )

    if not (explicit_upplagsplacering and upplagsplacering == "mittupplag"):
        indata_items.append(_post("a", "a", a, "mm", "avstånd till ändträkant"))

    indata_items.extend(
        [
            _post("l_1", r"l_1", l_1_post_value, "mm" if l_1_post_value != "lang" else "-", "tillgänglig längd inåt"),
            _post("h", "h", h, "mm", "bärverksdelens höjd"),
            _post("upplagsfall", "upplagsfall", upplagsfall, "-", "valt normfall"),
            _post("materialtyp", "materialtyp", materialtyp, "-", "materialtyp"),
            _post("f_c_90_k", r"f_{c,90,k}", f_c_90_k, "MPa", "karakteristisk tryckhållfasthet"),
            _post("k_mod", r"k_{mod}", k_mod_eff, "-", "modifieringsfaktor"),
            _post("gamma_M", r"\gamma_M", gamma_M_eff, "-", "partialkoefficient"),
            _post("tillat_hogre_tryck_eks", "EKS", bool(tillat_hogre_tryck_eks), "-", "tillåt högre tryck enligt EKS"),
        ]
    )

    if F_c_90_Ed is not None:
        indata_items.append(
            _post("N_c_90_Ed", r"F_{c,90,Ed}", F_c_90_Ed, "kN", "dimensionerande kontaktkraft")
        )

    ekvationer = [
        _ekvation(r"x_{in} = 30", "effektivt tillägg inåt när l1 är 'lang'"),
        _ekvation(r"x_{in} = \min(30, l_1 / 2)", "effektivt tillägg inåt när l1 anges numeriskt"),
    ]

    ar_mittupplag = explicit_upplagsplacering and upplagsplacering == "mittupplag"

    if ar_mittupplag:
        ekvationer.append(_ekvation(r"l_{ef} = l + 2 \, x_{in}", "effektiv upplagslängd för mittupplag"))
    else:
        ekvationer.append(_ekvation(r"x_{end} = \min(30, a)", "effektivt tillägg mot ändträkant"))

    ekvationer.extend(
        [
            _ekvation(r"l_1 \geq 2h", "förutsättning för val av kc,90"),
            _ekvation(
                r"k_{c,90} = \begin{cases} 1.25 & \text{för konstruktionsvirke} \\ 1.50 & \text{för limträ} \end{cases}",
                "värde för kc,90 vid dubbelsidigt understödd bärverksdel",
            ),
            _ekvation(
                r"k_{c,90} = \begin{cases} 1.50 & \text{för konstruktionsvirke} \\ 1.75 & \text{för limträ om } l \leq 400 \,\mathrm{mm} \\ 1.50 & \text{för limträ om } l > 400 \,\mathrm{mm} \end{cases}",
                "värde för kc,90 vid enkelsidigt upplag",
            ),
        ]
    )

    if not ar_mittupplag:
        ekvationer.append(_ekvation(r"l_{ef} = l + x_{end} + x_{in}", "effektiv upplagslängd för ändupplag"))

    ekvationer.append(_ekvation(r"A_{ef} = b \, l_{ef}", "effektiv kontaktyta"))

    ekvationer.extend(
        [
            _ekvation(r"f_{c,90,d} = \frac{k_{mod}}{\gamma_M} \, f_{c,90,k}", "dimensionerande tryckhållfasthet"),
            _ekvation(r"\sigma_{c,90,d} = \frac{F_{c,90,Ed} \, 1000}{A_{ef}}", "dimensionerande tryckspänning"),
            _ekvation(r"F_{c,90,Rd} = k_{c,90} \, f_{c,90,d} \, A_{ef} \, / \, 1000", "dimensionerande bärförmåga för upplagstryck"),
        ]
    )

    return {
        "metodbeskrivning": {
            "title": "Metodbeskrivning",
            "items": [
                {
                    "rubrik": "Beräkning",
                    "text": (
                        "Denna funktion avser beräkning av upplagstryck vinkelrätt "
                        "fiberriktningen för koncentrerad last i trä. Funktionen "
                        "stödjer både tidigare grundformat och ett explicit val mellan "
                        "'mittupplag' och 'andupplag'. Vid mittupplag beräknas "
                        "effektiv kontaktyta med dubbelt bidrag från x_in, medan "
                        "ändupplag använder x_in och x_end."
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
                        "Om l_1 anges som 'lang' antas lastspridningen vara "
                        "tillräckligt stor för att x_in ska få sättas till 30 mm. "
                        "För mittupplag kan ett redundant a-värde skickas med men "
                        "det ignoreras i beräkningen och visas inte i indata. För "
                        "andupplag får a utelämnas eller sättas till None; båda "
                        "fallen behandlas då som a = 0. "
                        "LVL/Kerto behandlas som limträ i denna funktion."
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
            "items": ekvationer,
        },
    }


_EKS_FAKTOR = {"field": "tillat_hogre_tryck_eks", "equals": True, "value": 1.0}

upplagstryck_tra.panel_schema = {
    "title": "Upplagstryck i trä",
    "px": [
        "b", "l", "upplagsplacering", "a", "l_1", "h", "upplagsfall", "materialtyp",
        "f_c_90_k", "k_mod", "gamma_M", "tillat_hogre_tryck_eks", "N_c_90_Ed",
    ],
    "fields": [
        {"name": "b", "type": "float", "label": "Kontaktbredd", "symbol": "<i>b</i>", "unit": "mm", "default": 90.0},
        {"name": "l", "type": "float", "label": "Fysisk upplagslängd", "symbol": "<i>l</i>", "unit": "mm", "default": 45.0},
        {
            "name": "upplagsplacering", "type": "choice", "label": "Upplagsplacering", "symbol": "",
            "default": "mittupplag",
            "options": [
                {"label": "Mittupplag", "value": "mittupplag"},
                {"label": "Ändupplag", "value": "andupplag"},
            ],
        },
        {
            "name": "a", "type": "float", "label": "Avstånd till ändträkant", "symbol": "<i>a</i>", "unit": "mm",
            "default": 0.0, "visible_if": {"field": "upplagsplacering", "equals": "andupplag"},
        },
        {
            "name": "l_1", "type": "text", "label": "Tillgänglig längd inåt", "symbol": "<i>l</i><sub>1</sub>",
            "unit": "mm", "default": "440",
            "help": "Ange ett tal. Skriv lang om längden är tillräcklig för fullt tillägg (30 mm) och minst 2h.",
        },
        {"name": "h", "type": "float", "label": "Bärverksdelens höjd", "symbol": "<i>h</i>", "unit": "mm", "default": 220.0},
        {
            "name": "upplagsfall", "type": "choice", "label": "Upplagsfall", "symbol": "",
            "default": "understodd_barverksdel_dubbelsidig", "span": 2,
            "options": [
                {"label": "Helt understödd eller dubbelsidigt belastad", "value": "understodd_barverksdel_dubbelsidig"},
                {"label": "Enkelsidigt belastad på upplag", "value": "barverksdel_pa_upplag_enkelsidig"},
            ],
        },
        {
            "name": "materialtyp", "type": "choice", "label": "Materialtyp", "symbol": "", "default": "konstruktionsvirke",
            "options": [
                {"label": "Konstruktionsvirke", "value": "konstruktionsvirke"},
                {"label": "Limträ", "value": "limtra"},
            ],
        },
        {
            "name": "f_c_90_k", "type": "float", "label": "Karakteristisk tryckhållfasthet",
            "symbol": "<i>f</i><sub>c,90,k</sub>", "unit": "MPa", "default": 2.5,
        },
        {
            "name": "k_mod", "type": "float", "label": "Modifieringsfaktor", "symbol": "<i>k</i><sub>mod</sub>",
            "default": 0.8, "fixed_if": _EKS_FAKTOR,
        },
        {
            "name": "gamma_M", "type": "float", "label": "Partialkoefficient", "symbol": "γ<sub>M</sub>",
            "default": 1.3, "fixed_if": _EKS_FAKTOR,
        },
        {
            "name": "tillat_hogre_tryck_eks", "type": "bool", "label": "Tillåt högre tryck enligt EKS", "symbol": "",
            "default": False, "span": 2,
        },
        {
            "name": "N_c_90_Ed", "type": "text", "label": "Dimensionerande kontaktkraft",
            "symbol": "<i>F</i><sub>c,90,Ed</sub>", "unit": "kN", "default": "",
            "help": "Lämna tomt för att bara beräkna bärförmågan.",
        },
    ],
    "sections": [
        {
            "title": "Indata", "collapsible": True, "collapsed": False, "columns": 1,
            "sections": [
                {"title": "Geometri", "fields": ["upplagsplacering", "a", "b", "l", "h", "l_1"], "columns": 2},
                {"title": "Material", "fields": ["materialtyp", "f_c_90_k"], "columns": 2},
                {"title": "Last", "fields": ["N_c_90_Ed"], "columns": 1},
            ],
        },
        {
            "title": "Beräkningsinställningar", "collapsible": True, "collapsed": True, "columns": 2,
            "fields": ["upplagsfall", "tillat_hogre_tryck_eks", "k_mod", "gamma_M"],
        },
    ],
}
