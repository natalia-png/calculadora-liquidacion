from flask import Flask, render_template, request
from datetime import datetime

app = Flask(__name__)


# ——— FILTRO PARA MONEDA ———
@app.template_filter()
def currency(value):
    """
    Convierte un número en un string tipo $1,234,567.89
    """
    try:
        v = float(value)
    except (TypeError, ValueError):
        return value
    return "$" + f"{v:,.2f}"

def dias360(start, end):
    """
    Convención 30/360 (método EE. UU.):
    - Si el día de inicio es 31, se reduce a 30.
    - Si el día final es 31 y el día inicial es 30 o 31, se reduce a 30.
    """
    d1, m1, y1 = start.day, start.month, start.year
    d2, m2, y2 = end.day,   end.month,   end.year
    d1 = min(d1, 30)
    if d2 == 31 and d1 in (30, 31):
        d2 = 30
    else:
        d2 = min(d2, 30)
    return 360*(y2 - y1) + 30*(m2 - m1) + (d2 - d1)

def split_periods_by_year(start, end):
    """
    Divide el rango start–end en subrangos que no excedan un año civil.
    Ej: 2020-03-15 → 2025-05-18 produce:
      [
        (2020-03-15, 2020-12-31),
        (2021-01-01, 2021-12-31),
        ...,
        (2025-01-01, 2025-05-18)
      ]
    """
    periods = []
    current = start
    # mientras estemos en años anteriores al de end
    while current.year < end.year:
        periods.append((current, datetime(current.year, 12, 31)))
        current = datetime(current.year + 1, 1, 1)
    periods.append((current, end))
    return periods

@app.route('/', methods=['GET', 'POST'])
def index():
    result = None
    if request.method == 'POST':
        # --- 1. Parseo de inputs básicos ---
        fecha_ingreso = datetime.strptime(request.form['fecha_ingreso'], '%Y-%m-%d')
        fecha_retiro  = datetime.strptime(request.form['fecha_retiro'],  '%Y-%m-%d')
        salario       = float(request.form.get('salario', 0) or 0)
        variables     = float(request.form.get('variables', 0) or 0)
        vac_tomadas   = float(request.form.get('vac_tomadas', 0) or 0)

        # Salario integrado
        SI = salario + variables

        # --- 2. Deducciones desglosadas ---
        aplicar = 'applyDeducciones' in request.form
        salud_pct   = float(request.form.get('salud_pct',   0) or 0)
        pension_pct = float(request.form.get('pension_pct', 0) or 0)
        rf_pct      = float(request.form.get('retencion_pct', 0) or 0)
        ded_pct     = (salud_pct + pension_pct + rf_pct) if aplicar else 0

        # --- 3. Cálculo por subperiodos de año ---
        tot_ces, tot_int, tot_pri = 0.0, 0.0, 0.0
        vac_bruto = 0.0

        for sub_start, sub_end in split_periods_by_year(fecha_ingreso, fecha_retiro):
            d = dias360(sub_start, sub_end)
            ces = SI * d / 360
            tot_ces   += ces
            tot_int   += ces * 0.12 * d / 360
            tot_pri   += SI * d / 360
            vac_bruto += SI * d / 720

        # --- 4. Vacaciones netas tras días ya tomados ---
        valor_por_dia = SI / 30
        vac_descuento = vac_tomadas * valor_por_dia
        total_vac = max(vac_bruto - vac_descuento, 0)

        # --- 5. Totales bruto y neto ---
        total_bruto = tot_ces + tot_int + tot_pri + total_vac
        total_neto  = total_bruto * (1 - ded_pct/100) if aplicar else total_bruto

        # --- 6. Preparar resultado para la plantilla ---
        result = {
            'SI':             SI,
            'subperiodos':    split_periods_by_year(fecha_ingreso, fecha_retiro),
            'cesantias':      tot_ces,
            'intereses':      tot_int,
            'prima':          tot_pri,
            'vac_bruto':      vac_bruto,
            'vac_tomadas':    vac_tomadas,
            'vacaciones':     total_vac,
            'total_bruto':    total_bruto,
            'aplicar':        aplicar,
            'salud':          salud_pct,
            'pension':        pension_pct,
            'ret_fuente':     rf_pct,
            'ded_pct':        ded_pct,
            'total_neto':     total_neto
        }

    return render_template('index.html', result=result)

if __name__ == '__main__':
    app.run(debug=True)
