Planilhas esperadas (coloque aqui):

1) suppliers.xlsx
   Colunas:
   - id (texto)
   - name (texto)
   - logo (texto, opcional) -> caminho relativo dentro de app/static/images (ex: logos/fornecedorA.png)

2) products.xlsx
   Colunas:
   - id (texto)
   - supplier_id (texto) -> deve bater com suppliers.id
   - name (texto)
   - price (número)
   - promo_price (número, opcional)
   - image (texto, opcional) -> caminho relativo dentro de app/static/images (ex: produtos/prod1.jpg)

3) clients.xlsx (opcional para futuras features)
   Colunas sugeridas:
   - id, name, email, phone

Observação: não há import automático para clientes no momento. Foco atual: catálogo e carrinho.



