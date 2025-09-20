# Catálogo da Distribuidora (Flask)

## Passo a passo no Cursor (Windows)

1) Ativar o ambiente virtual
```
.\.venv\Scripts\Activate.ps1
```
Se ainda não existir, crie antes:
```
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2) Instalar dependências (primeira vez)
```
pip install --upgrade pip
pip install flask pandas openpyxl pillow flask-session
```

3) Gerar dados e imagens de exemplo (opcional, recomendado)
```
python seed_data.py
```
Isso cria planilhas em `data/` e imagens em `app/static/images/`.

4) Rodar o servidor
```
python run.py
```
Acesse: `http://127.0.0.1:5000/`

## Estrutura essencial
```
app/
  __init__.py
  routes.py
  templates/
    base.html
    index.html
    supplier.html
    cart.html
  static/
    css/styles.css
    images/
      logos/
      produtos/
 data/
  suppliers.xlsx
  products.xlsx
seed_data.py
run.py
```

## Formato das planilhas (resumo)
- suppliers: colunas `id`, `name`, `logo` (ex.: `logos/fornA.png`)
- products: colunas `id`, `supplier_id`, `name`, `price`, `promo_price` (opcional), `image` (ex.: `produtos/p1.jpg`)

Observações:
- Leitura prioriza XLSX (openpyxl) e faz fallback para CSV.
- Carrinho usa sessão no servidor (Flask-Session).
- Paginação: 9 produtos por página.

