"""
Script de prueba para validar la nueva fórmula de precios para 3+ cotizaciones
"""

def test_formula_3_mas_cotizaciones():
    """Prueba la nueva fórmula con diferentes escenarios"""

    # Configuración de ejemplo (valores reales de la BD)
    CONFIG = {
        'descuento_competencia': 200,
        'precio_domicilio': 5000,
        'costo_operario_domicilio': 3333,
        'ganancia_min_escaso': 1500,
        'redondeo_superior': 100
    }

    # Escenarios de prueba
    escenarios = [
        {
            'nombre': 'Escenario 1: Brecha >= descuento (margen suficiente)',
            'cotizaciones': [10000, 12000, 15000, 18000],
            'descripcion': 'Brecha2/3 = 3000 >= descuento_competencia (200)'
        },
        {
            'nombre': 'Escenario 2: Brecha >= descuento (margen insuficiente)',
            'cotizaciones': [10000, 11000, 11500, 12000],
            'descripcion': 'Brecha2/3 = 500 >= descuento_competencia (200), pero diferencia para cálculo < ganancia_min'
        },
        {
            'nombre': 'Escenario 3: Brecha < descuento (caso crítico)',
            'cotizaciones': [13050, 13158, 13200],
            'descripcion': 'Brecha2/3 = 42 < descuento_competencia (200) - Caso Naproxeno LA SANTE'
        },
        {
            'nombre': 'Escenario 4: Precios muy cercanos (brecha < descuento)',
            'cotizaciones': [5000, 5100, 5150, 5200],
            'descripcion': 'Brecha2/3 = 50 < descuento_competencia (200)'
        },
        {
            'nombre': 'Escenario 5: Precios muy dispersos',
            'cotizaciones': [5000, 10000, 15000, 20000],
            'descripcion': 'Brecha2/3 = 5000 >> descuento_competencia (200)'
        }
    ]

    import math

    print("="*80)
    print("PRUEBA DE NUEVA FORMULA - 3 O MAS COTIZACIONES")
    print("="*80)
    print(f"\nCONFIGURACION:")
    print(f"   - Descuento Competencia: ${CONFIG['descuento_competencia']:,}")
    print(f"   - Precio Domicilio: ${CONFIG['precio_domicilio']:,}")
    print(f"   - Costo Operario Domicilio: ${CONFIG['costo_operario_domicilio']:,}")
    print(f"   - Ganancia Minima Escaso: ${CONFIG['ganancia_min_escaso']:,}")
    print(f"   - Redondeo Superior: ${CONFIG['redondeo_superior']}")
    print()

    for esc in escenarios:
        print("\n" + "-"*80)
        print(f">> {esc['nombre']}")
        print(f"   {esc['descripcion']}")
        print(f"   Cotizaciones: {[f'${c:,}' for c in esc['cotizaciones']]}")
        print()

        # Ordenar cotizaciones (simulando ORDER BY precio ASC)
        precios_cot = sorted(esc['cotizaciones'])

        # Extraer cotización 2 y 3
        cotizacion_2 = precios_cot[1]
        cotizacion_3 = precios_cot[2]

        print(f"   Cotización #2: ${cotizacion_2:,}")
        print(f"   Cotización #3: ${cotizacion_3:,}")
        print()

        # Calcular brecha entre cotizacion 2 y 3
        brecha2_3 = cotizacion_3 - cotizacion_2
        print(f"   [0] BRECHA 2/3 = {cotizacion_3:,} - {cotizacion_2:,} = ${brecha2_3:,}")
        print()

        # VALIDACIÓN TEMPRANA: si brecha pequeña, precio directo
        if brecha2_3 < CONFIG['descuento_competencia']:
            precio_nuevo = cotizacion_2 + (brecha2_3 / 2)
            print(f"   [!] Brecha ({brecha2_3:,}) < Descuento ({CONFIG['descuento_competencia']:,})")
            print(f"      -> VALIDACION TEMPRANA: Posicionarse a mitad de camino")
            print(f"      -> PRECIO FINAL = {cotizacion_2:,} + ({brecha2_3:,} / 2)")
            print(f"      -> PRECIO FINAL = ${precio_nuevo:,.2f}")
            print(f"      -> [Saltar calculos de PRECIO_PARA_CALCULO y DIFERENCIA]")
        else:
            # Brecha suficiente, aplicar fórmula completa
            print(f"   [OK] Brecha ({brecha2_3:,}) >= Descuento ({CONFIG['descuento_competencia']:,})")
            print(f"      -> Aplicar formula completa")
            print()

            # Variable 1: PRECIO PARA CALCULO
            PRECIO_PARA_CALCULO = cotizacion_3 - CONFIG['descuento_competencia']
            print(f"   [1] PRECIO PARA CALCULO = {cotizacion_3:,} - {CONFIG['descuento_competencia']:,}")
            print(f"      = ${PRECIO_PARA_CALCULO:,}")
            print()

            # Variable 2: DIFERENCIA PARA CALCULO
            DIFERENCIA_PARA_CALCULO = (PRECIO_PARA_CALCULO
                                       - cotizacion_2
                                       + CONFIG['precio_domicilio']
                                       - CONFIG['costo_operario_domicilio'])
            print(f"   [2] DIFERENCIA PARA CALCULO = {PRECIO_PARA_CALCULO:,} - {cotizacion_2:,} + {CONFIG['precio_domicilio']:,} - {CONFIG['costo_operario_domicilio']:,}")
            print(f"      = ${DIFERENCIA_PARA_CALCULO:,}")
            print()

            # Logica de decision
            if DIFERENCIA_PARA_CALCULO > CONFIG['ganancia_min_escaso']:
                print(f"   [OK] Diferencia ({DIFERENCIA_PARA_CALCULO:,}) > Ganancia Min ({CONFIG['ganancia_min_escaso']:,})")
                print(f"      -> Margen suficiente")
                precio_nuevo = PRECIO_PARA_CALCULO
                print(f"      -> PRECIO FINAL = PRECIO PARA CALCULO = ${precio_nuevo:,}")
            else:
                print(f"   [!]  Diferencia ({DIFERENCIA_PARA_CALCULO:,}) <= Ganancia Min ({CONFIG['ganancia_min_escaso']:,})")
                print(f"      -> Margen insuficiente, ajustando...")
                DIFERENCIA_FINAL = CONFIG['ganancia_min_escaso'] - DIFERENCIA_PARA_CALCULO
                print(f"      -> DIFERENCIA FINAL = {CONFIG['ganancia_min_escaso']:,} - {DIFERENCIA_PARA_CALCULO:,} = ${DIFERENCIA_FINAL:,}")
                precio_nuevo = PRECIO_PARA_CALCULO + DIFERENCIA_FINAL
                print(f"      -> PRECIO FINAL = {PRECIO_PARA_CALCULO:,} + {DIFERENCIA_FINAL:,} = ${precio_nuevo:,}")

        print()

        # Aplicar redondeo
        if CONFIG['redondeo_superior'] > 0:
            precio_antes_redondeo = precio_nuevo
            precio_nuevo = math.ceil(precio_nuevo / CONFIG['redondeo_superior']) * CONFIG['redondeo_superior']
            if precio_antes_redondeo != precio_nuevo:
                print(f"   [R] Redondeo aplicado: ${precio_antes_redondeo:,} -> ${precio_nuevo:,}")

        precio_nuevo = round(precio_nuevo)
        print()
        print(f"   [*] PRECIO FINAL (despues de redondeo): ${precio_nuevo:,}")
        print(f"   [+] Margen sobre Cot#2: ${(precio_nuevo - cotizacion_2):,}")
        print(f"   [+] Margen sobre Cot#3: ${(precio_nuevo - cotizacion_3):,}")

    print("\n" + "="*80)
    print("[OK] PRUEBA COMPLETADA")
    print("="*80)

if __name__ == '__main__':
    test_formula_3_mas_cotizaciones()
