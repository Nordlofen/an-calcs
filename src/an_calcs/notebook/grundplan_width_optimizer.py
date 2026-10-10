"""Choose discrete widths jointly, with an exact cap on reference groups."""

import time


def optimize(items, fixed_groups, maximum, step_mm, lower):
    """Return candidate indices, or the proven minimum group count if infeasible.

    Each item contains (width, utilization, reference-key) candidates. Width is
    the primary objective; U below the lower goal is a bounded tie-breaker.
    Unselected/locked footings supply fixed groups, including off-grid widths.
    """
    if not items:
        return ([], None) if len(fixed_groups) <= maximum else (None, len(fixed_groups))
    try:
        import numpy as np
        from scipy.optimize import Bounds, LinearConstraint, milp
        from scipy.sparse import coo_array
    except ImportError as exc:
        raise ValueError("Max referensgrupper kräver SciPy. Uppdatera an-calcs[notebook].") from exc

    groups = sorted(fixed_groups | {key for item in items for _, _, key in item})
    group_index = {key: index for index, key in enumerate(groups)}
    edges = [(i, j, group_index[key], width, u)
             for i, item in enumerate(items) for j, (width, u, key) in enumerate(item)]
    n, g, e = len(items), len(groups), len(edges)
    # Assignment variables first, then one binary activation per reference group.
    rows, cols, values = [], [], []
    lows, highs = [1.] * n, [1.] * n
    costs = np.zeros(e + g)
    for index, (i, _, group, width, u) in enumerate(edges):
        rows.extend([i, n + index, n + index])
        cols.extend([index, index, e + group]); values.extend([1., 1., -1.])
        # The sum of all soft penalties is < 1/2 of a single width step, so
        # minimizing total width always takes priority over the lower U goal.
        costs[index] = round(width * 1000 / step_mm) + max(0., lower - u) / (2 * (n + 1))
    lows.extend([-np.inf] * e); highs.extend([0.] * e)
    rows.extend([n + e] * g); cols.extend(range(e, e + g)); values.extend([1.] * g)
    lows.append(-np.inf); highs.append(float(maximum))
    matrix = coo_array((values, (np.asarray(rows, dtype=np.int32), np.asarray(cols, dtype=np.int32))),
                       shape=(n + e + 1, e + g)).tocsc()
    lower_bounds, upper_bounds = np.zeros(e + g), np.ones(e + g)
    for key in fixed_groups:
        lower_bounds[e + group_index[key]] = 1
    bounds = Bounds(lower_bounds, upper_bounds)
    deadline = time.monotonic() + 20

    def solve(objective, cap):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ValueError("Optimeringen tog för lång tid. Öka måttsteget eller välj färre sulor och förhandsvisa igen.")
        limits = np.array(highs); limits[-1] = cap
        result = milp(objective, integrality=np.ones(e + g), bounds=bounds,
                      constraints=LinearConstraint(matrix, lows, limits),
                      options={"time_limit": remaining, "mip_rel_gap": 0.})
        if result.status == 1:
            raise ValueError("Optimeringen tog för lång tid. Öka måttsteget eller välj färre sulor och förhandsvisa igen.")
        if result.status not in (0, 2):
            raise ValueError("Optimeringen kunde inte slutföras. Inga bredder har ändrats.")
        return result

    result = solve(costs, maximum)
    if result.status == 2:
        minimum_cost = np.zeros(e + g); minimum_cost[e:] = 1
        minimum = solve(minimum_cost, np.inf)
        if minimum.status != 0:
            raise ValueError("Ingen giltig kombination av bredder kunde hittas.")
        return None, int(round(minimum.fun))
    chosen, active = [None] * n, set(fixed_groups)
    for index, (i, j, group, _, _) in enumerate(edges):
        if result.x[index] > .5:
            if chosen[i] is not None:
                raise ValueError("Optimeringen gav en ogiltig tilldelning. Förhandsvisa igen.")
            chosen[i] = j; active.add(groups[group])
    if any(index is None for index in chosen) or len(active) > maximum:
        raise ValueError("Optimeringen gav en ogiltig tilldelning. Förhandsvisa igen.")
    return chosen, None
