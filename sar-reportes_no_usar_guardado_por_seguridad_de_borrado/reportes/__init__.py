from . import inventario, ventas_clientes, consulta_cuentas, reg_ctas

CATALOGO = {
    inventario.ID:        inventario,
    ventas_clientes.ID:   ventas_clientes,
    consulta_cuentas.ID:  consulta_cuentas,
    reg_ctas.ID:          reg_ctas,
}
