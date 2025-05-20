from flask import Flask, render_template, request
from datetime import datetime

app = Flask(__name__)

# ——— FILTRO PARA FORMATEAR COMO MONEDA ———
@app.template_filter()
def currency(value):
    try:
        v = float(value)
    except (TypeError, ValueError):
        return value
    return "$" + f"{v:,.2f}"
# ————————————————————————————————————————

SMLMV_2025 = 1_423_500  # Correcto
  # NUEVO: Salario mínimo mensual legal vigente 2025

def dias360(start, end):
    d1, m1, y1 = start.day, start.month, start.year
    d2, m2, y2 = end.day,   end.month,   end.year
    d1 = min(d1, 30)
    if d2 == 31 and d1 in (30, 31):
        d2 = 30
    else:
        d2 = min(d2, 30)
    return 360*(y2 - y1) + 30*(m2 - m1) + (d2 - d1)

def split_periods_by_year(start, end):
    periods = []
    current = start
    while current.year < end.year:
        periods.append((current, datetime(current.year, 12, 31)))
        current = datetime(current.year + 1, 1, 1)
    periods.append((current, end))
    return periods

@app.route('/', methods=['GET', 'POST'])
def index():
    result = None
    if request.method == 'POST':
        fecha_ingreso = datetime.strptime(request.form['fecha_ingreso'], '%Y-%m-%d')
        fecha_retiro  = datetime.strptime(request.form['fecha_retiro'],  '%Y-%m-%d')
        salario       = float(request.form.get('salario', 0) or 0)
        variables     = float(request.form.get('variables', 0) or 0)
        vac_tomadas   = float(request.form.get('vac_tomadas', 0) or 0)
        dias_manual   = request.form.get('dias_manual')  # NUEVO
        sin_justa     = 'sin_justa_causa' in request.form  # NUEVO

        SI = salario + variables

        aplicar       = 'applyDeducciones' in request.form
        salud_pct     = float(request.form.get('salud_pct',   0) or 0)
        pension_pct   = float(request.form.get('pension_pct', 0) or 0)
        retfuente_pct = float(request.form.get('retencion_pct', 0) or 0)
        ded_pct       = (salud_pct + pension_pct + retfuente_pct) if aplicar else 0

        datos_por_ano = {}
        for sub_start, sub_end in split_periods_by_year(fecha_ingreso, fecha_retiro):
            ano  = sub_start.year
            dias = dias360(sub_start, sub_end)
            ces = SI * dias / 360
            inte = ces * 0.12 * dias / 360
            pri = SI * dias / 360
            vac = SI * dias / 720

            if ano not in datos_por_ano:
                datos_por_ano[ano] = {'ces': 0.0, 'int': 0.0, 'pri': 0.0, 'vac': 0.0}
            datos_por_ano[ano]['ces'] += ces
            datos_por_ano[ano]['int'] += inte
            datos_por_ano[ano]['pri'] += pri
            datos_por_ano[ano]['vac'] += vac

        total_ces       = sum(d['ces'] for d in datos_por_ano.values())
        total_int       = sum(d['int'] for d in datos_por_ano.values())
        total_pri       = sum(d['pri'] for d in datos_por_ano.values())
        total_vac_bruto = sum(d['vac'] for d in datos_por_ano.values())

        valor_por_dia  = SI / 30
        vac_descuento  = vac_tomadas * valor_por_dia
        total_vac_neto = max(total_vac_bruto - vac_descuento, 0)

        total_bruto = total_ces + total_int + total_pri + total_vac_neto
        total_neto  = total_bruto * (1 - ded_pct/100) if aplicar else total_bruto

        # NUEVO: cálculo de indemnización por despido sin justa causa
        indemnizacion = 0
        if sin_justa:
            if dias_manual:
                dias_trabajados = int(dias_manual)
            else:
                dias_trabajados = dias360(fecha_ingreso, fecha_retiro)

            anios = dias_trabajados // 360
            fraccion = (dias_trabajados % 360) / 360

            if salario < 10 * SMLMV_2025:
                indemnizacion = salario  # 30 días
                if anios > 1:
                    indemnizacion += salario * 20 / 30 * (anios - 1 + fraccion)
            else:
                indemnizacion = salario * 20 / 30  # 20 días
                if anios > 1:
                    indemnizacion += salario * 15 / 30 * (anios - 1 + fraccion)

        result = {
            'SI':               SI,
            'subperiodos':      split_periods_by_year(fecha_ingreso, fecha_retiro),
            'datos_por_ano':    datos_por_ano,
            'total_ces':        total_ces,
            'total_int':        total_int,
            'total_pri':        total_pri,
            'total_vac_bruto':  total_vac_bruto,
            'vac_tomadas':      vac_tomadas,
            'vac_descuento':    vac_descuento,
            'total_vac_neto':   total_vac_neto,
            'total_bruto':      total_bruto,
            'aplicar':          aplicar,
            'salud':            salud_pct,
            'pension':          pension_pct,
            'ret_fuente':       retfuente_pct,
            'ded_pct':          ded_pct,
            'total_neto':       total_neto,
            'indemnizacion':    indemnizacion,  # NUEVO
            'sin_justa':        sin_justa,      # NUEVO
            'dias_usados':      dias_manual if dias_manual else None  # NUEVO
        }

    return render_template('index.html', result=result)

if __name__ == '__main__':
    app.run(debug=True)
