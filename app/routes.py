from __future__ import annotations

from dataclasses import dataclass
from math import ceil
from pathlib import Path, PurePosixPath
from typing import Dict, List, Optional
import os
import json

import pandas as pd
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, send_file
from io import BytesIO, StringIO
from werkzeug.utils import secure_filename


catalog_bp = Blueprint("catalog", __name__)


# --- Modelos simples para tipagem ---
@dataclass
class Supplier:
    id: str
    name: str
    logo_path: Optional[str] = None


@dataclass
class Product:
    id: str
    supplier_id: str
    name: str
    price: float
    promo_price: Optional[float]
    image_path: Optional[str]


@dataclass
class Client:
    id: str
    name: str
    email: str
    password: str  # DEMO: texto puro
    phone: Optional[str] = None
    address: Optional[str] = None
    state: Optional[str] = None
    city: Optional[str] = None
    cep: Optional[str] = None


DATA_DIR = Path("data")
IMAGES_DIR = Path("app/static/images")
ADMIN_FILE = DATA_DIR / "admin.json"


def _safe_float(value) -> Optional[float]:
    try:
        if pd.isna(value):
            return None
        return float(value)
    except Exception:
        return None


def _read_tabular(filename_no_ext: str) -> Optional[pd.DataFrame]:
    """Tenta ler .xlsx (openpyxl) e, em fallback, .csv UTF-8."""
    xlsx = DATA_DIR / f"{filename_no_ext}.xlsx"
    csv = DATA_DIR / f"{filename_no_ext}.csv"
    if xlsx.exists():
        try:
            return pd.read_excel(xlsx, engine="openpyxl")
        except Exception:
            pass
    if csv.exists():
        try:
            return pd.read_csv(csv)
        except Exception:
            pass
    return None


def load_suppliers() -> List[Supplier]:
    df = _read_tabular("suppliers")
    if df is None:
        return []
    # Colunas esperadas: id, name, logo (opcional)
    suppliers: List[Supplier] = []
    for _, row in df.iterrows():
        logo_rel = row.get("logo")
        if isinstance(logo_rel, str) and logo_rel:
            safe_logo_rel = str(logo_rel).replace("\\", "/")
            logo_path = (PurePosixPath("images") / safe_logo_rel).as_posix()
        else:
            logo_path = None
        suppliers.append(
            Supplier(
                id=str(row.get("id")),
                name=str(row.get("name")),
                logo_path=logo_path,
            )
        )
    return suppliers


def load_products() -> List[Product]:
    df = _read_tabular("products")
    if df is None:
        return []
    # Colunas esperadas: id, supplier_id, name, price, promo_price (opcional), image (opcional)
    products: List[Product] = []
    for _, row in df.iterrows():
        image_rel = row.get("image")
        if isinstance(image_rel, str) and image_rel:
            safe_image_rel = str(image_rel).replace("\\", "/")
            image_path = (PurePosixPath("images") / safe_image_rel).as_posix()
        else:
            image_path = None
        products.append(
            Product(
                id=str(row.get("id")),
                supplier_id=str(row.get("supplier_id")),
                name=str(row.get("name")),
                price=float(row.get("price") or 0.0),
                promo_price=_safe_float(row.get("promo_price")),
                image_path=image_path,
            )
        )
    return products


def load_clients() -> List[Client]:
    df = _read_tabular("clients")
    if df is None:
        return []
    clients: List[Client] = []
    for _, row in df.iterrows():
        clients.append(
            Client(
                id=str(row.get("id")),
                name=str(row.get("name")),
                email=str(row.get("email")),
                password=str(row.get("password")),
                phone=str(row.get("phone")) if row.get("phone") is not None else None,
                address=str(row.get("address")) if row.get("address") is not None else None,
                state=str(row.get("state")) if row.get("state") is not None else None,
                city=str(row.get("city")) if row.get("city") is not None else None,
                cep=str(row.get("cep")) if row.get("cep") is not None else None,
            )
        )
    return clients


def _get_cart() -> Dict[str, int]:
    cart: Dict[str, int] = session.get("cart", {})
    if not isinstance(cart, dict):
        cart = {}
    return cart


def _save_cart(cart: Dict[str, int]) -> None:
    session["cart"] = cart


def _get_current_user() -> Optional[Client]:
    user_email = session.get("user_email")
    if not user_email:
        return None
    # Se for admin (definido em admin.json), retorna um usuário sintético
    admin = load_admin()
    if user_email == admin.get("email"):
        return Client(
            id="admin",
            name="Administrador",
            email=admin.get("email"),
            password=admin.get("password", ""),
        )
    return next((c for c in load_clients() if c.email == user_email), None)


def _ensure_admin_file() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not ADMIN_FILE.exists():
        ADMIN_FILE.write_text(json.dumps({
            "email": "swinck@gmail.com",
            "password": "123456",
        }, ensure_ascii=False), encoding="utf-8")


def load_admin() -> Dict[str, str]:
    _ensure_admin_file()
    try:
        return json.loads(ADMIN_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"email": "swinck@gmail.com", "password": "123456"}


def save_admin(email: str, password: Optional[str] = None) -> None:
    data = load_admin()
    if email:
        data["email"] = email
    if password:
        data["password"] = password
    ADMIN_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _is_admin_email(email: str) -> bool:
    admin = load_admin()
    return email and email == admin.get("email")


def _require_admin() -> Optional[str]:
    user = _get_current_user()
    if not user or not _is_admin_email(user.email):
        return "Acesso restrito ao administrador."
    return None


def _save_clients_dataframe(df: pd.DataFrame) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    wanted_cols = ["id", "name", "email", "password", "phone", "address", "state", "city", "cep"]
    for col in wanted_cols:
        if col not in df.columns:
            df[col] = None
    df = df[wanted_cols]
    df.to_excel(DATA_DIR / "clients.xlsx", index=False)
    df.to_csv(DATA_DIR / "clients.csv", index=False)


def _save_suppliers_dataframe(df: pd.DataFrame) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    wanted_cols = ["id", "name", "logo"]
    for col in wanted_cols:
        if col not in df.columns:
            df[col] = None
    df = df[wanted_cols]
    df.to_excel(DATA_DIR / "suppliers.xlsx", index=False)
    df.to_csv(DATA_DIR / "suppliers.csv", index=False)


def _save_products_dataframe(df: pd.DataFrame) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    wanted_cols = ["id", "supplier_id", "name", "price", "promo_price", "image"]
    for col in wanted_cols:
        if col not in df.columns:
            df[col] = None
    df = df[wanted_cols]
    df.to_excel(DATA_DIR / "products.xlsx", index=False)
    df.to_csv(DATA_DIR / "products.csv", index=False)


@catalog_bp.route("/")
def index():
    suppliers = load_suppliers()
    user = _get_current_user()
    return render_template("index.html", suppliers=suppliers, user=user)


@catalog_bp.route("/supplier/<supplier_id>")
def supplier_catalog(supplier_id: str):
    page_size = 9
    page = max(int(request.args.get("page", 1)), 1)

    products = [p for p in load_products() if p.supplier_id == supplier_id]
    total = len(products)
    total_pages = max(ceil(total / page_size), 1)
    if page > total_pages:
        page = total_pages

    start = (page - 1) * page_size
    end = start + page_size
    page_products = products[start:end]

    # Para título/nome do fornecedor
    supplier = next((s for s in load_suppliers() if s.id == supplier_id), None)

    user = _get_current_user()
    return render_template(
        "supplier.html",
        supplier=supplier,
        products=page_products,
        page=page,
        total_pages=total_pages,
        supplier_id=supplier_id,
        user=user,
    )


@catalog_bp.post("/cart/add/<product_id>")
def cart_add(product_id: str):
    cart = _get_cart()
    qty = int(request.form.get("qty", 1))
    cart[product_id] = cart.get(product_id, 0) + max(qty, 1)
    _save_cart(cart)
    flash("Produto adicionado ao carrinho.")
    referer = request.headers.get("Referer") or url_for("catalog.index")
    return redirect(referer)


@catalog_bp.post("/cart/remove/<product_id>")
def cart_remove(product_id: str):
    cart = _get_cart()
    if product_id in cart:
        cart.pop(product_id)
        _save_cart(cart)
        flash("Produto removido do carrinho.")
    referer = request.headers.get("Referer") or url_for("catalog.view_cart")
    return redirect(referer)


@catalog_bp.get("/cart")
def view_cart():
    cart = _get_cart()
    products = {p.id: p for p in load_products()}

    # Monta itens do carrinho com totais
    items = []
    total_value = 0.0
    for pid, qty in cart.items():
        product = products.get(pid)
        if not product:
            continue
        price = product.promo_price if product.promo_price is not None else product.price
        line_total = price * qty
        total_value += line_total
        items.append({
            "product": product,
            "qty": qty,
            "price": price,
            "line_total": line_total,
        })

    # Cupom e frete
    coupon_code = session.get("coupon_code")
    coupon_discounts = {"DESCONTO10": 0.10, "DESCONTO5": 0.05}
    discount_rate = coupon_discounts.get(coupon_code, 0.0)
    discount_value = round(total_value * discount_rate, 2)
    shipping_value = float(session.get("shipping_value", 0.0) or 0.0)
    grand_total = max(total_value - discount_value + shipping_value, 0.0)

    user = _get_current_user()
    return render_template(
        "cart.html",
        items=items,
        total_value=total_value,
        discount_rate=discount_rate,
        discount_value=discount_value,
        coupon_code=coupon_code,
        shipping_value=shipping_value,
        grand_total=grand_total,
        user=user,
    )


# --- Autenticação simples ---
@catalog_bp.get("/login")
def login_page():
    if _get_current_user():
        return redirect(url_for("catalog.index"))
    return render_template("login.html")


@catalog_bp.post("/login")
def login_submit():
    email = request.form.get("email", "").strip()
    password = request.form.get("password", "")
    # Primeiro confere admin
    admin = load_admin()
    if email == admin.get("email") and password == admin.get("password"):
        session["user_email"] = email
        flash("Bem-vindo(a), Administrador(a)!")
    else:
        client = next((c for c in load_clients() if c.email == email and c.password == password), None)
        if not client:
            flash("Credenciais inválidas.")
            return redirect(url_for("catalog.login_page"))
        session["user_email"] = client.email
        flash(f"Bem-vindo(a), {client.name}!")
    next_url = request.args.get("next")
    return redirect(next_url or url_for("catalog.index"))


@catalog_bp.get("/logout")
def logout():
    session.pop("user_email", None)
    flash("Sessão encerrada.")
    return redirect(url_for("catalog.index"))


# --- Exportações ---
@catalog_bp.get("/cart/export/xlsx")
def export_cart_xlsx():
    cart = _get_cart()
    if not cart:
        flash("Carrinho vazio.")
        return redirect(url_for("catalog.view_cart"))

    products = {p.id: p for p in load_products()}
    rows = []
    total = 0.0
    for pid, qty in cart.items():
        p = products.get(pid)
        if not p:
            continue
        price = p.promo_price if p.promo_price is not None else p.price
        line_total = price * qty
        total += line_total
        rows.append({
            "Produto": p.name,
            "Preço": price,
            "Quantidade": qty,
            "Total": line_total,
        })
    df = pd.DataFrame(rows)

    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Carrinho")
    output.seek(0)
    return send_file(output, as_attachment=True, download_name="carrinho.xlsx", mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")


@catalog_bp.get("/cart/export/pdf")
def export_cart_pdf():
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
    except Exception:
        flash("Dependência de PDF ausente. Instale 'reportlab'.")
        return redirect(url_for("catalog.view_cart"))

    cart = _get_cart()
    if not cart:
        flash("Carrinho vazio.")
        return redirect(url_for("catalog.view_cart"))

    products = {p.id: p for p in load_products()}
    items = []
    total = 0.0
    for pid, qty in cart.items():
        p = products.get(pid)
        if not p:
            continue
        price = p.promo_price if p.promo_price is not None else p.price
        line_total = price * qty
        total += line_total
        items.append((p.name, qty, price, line_total))

    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    y = height - 40
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, y, "Carrinho de Compras")
    y -= 30
    c.setFont("Helvetica", 10)
    c.drawString(40, y, "Produto")
    c.drawString(260, y, "Qtd")
    c.drawString(320, y, "Preço")
    c.drawString(400, y, "Total")
    y -= 20
    for name, qty, price, line_total in items:
        if y < 60:
            c.showPage()
            y = height - 40
        c.drawString(40, y, str(name))
        c.drawRightString(300, y, str(qty))
        c.drawRightString(380, y, f"R$ {price:.2f}")
        c.drawRightString(500, y, f"R$ {line_total:.2f}")
        y -= 18
    y -= 10
    c.setFont("Helvetica-Bold", 11)
    c.drawRightString(500, y, f"Total: R$ {total:.2f}")
    c.showPage()
    c.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name="carrinho.pdf", mimetype="application/pdf")


# --- Cupom e frete ---
@catalog_bp.post("/cart/coupon")
def apply_coupon():
    code = (request.form.get("coupon", "").strip() or "").upper()
    allowed = {"DESCONTO10", "DESCONTO5"}
    if code in allowed:
        session["coupon_code"] = code
        flash("Cupom aplicado.")
    else:
        session.pop("coupon_code", None)
        flash("Cupom inválido removido.")
    return redirect(url_for("catalog.view_cart"))


@catalog_bp.post("/cart/shipping")
def set_shipping():
    try:
        value = float(request.form.get("shipping", 0) or 0)
        if value < 0:
            value = 0.0
    except Exception:
        value = 0.0
    session["shipping_value"] = value
    flash("Frete atualizado.")
    return redirect(url_for("catalog.view_cart"))


# --- Checkout protegido ---
@catalog_bp.get("/checkout")
def checkout_page():
    user = _get_current_user()
    if not user:
        return redirect(url_for("catalog.login_page", next=url_for("catalog.checkout_page")))
    return render_template("checkout.html", user=user)


@catalog_bp.post("/checkout")
def checkout_submit():
    user = _get_current_user()
    if not user:
        return redirect(url_for("catalog.login_page", next=url_for("catalog.checkout_page")))
    # Aqui faria criação de pedido. Demo: apenas limpa carrinho
    session.pop("cart", None)
    flash("Pedido finalizado! Obrigado pela compra.")
    return redirect(url_for("catalog.index"))


# --- Export CSV (ERP) ---
@catalog_bp.get("/cart/export/csv")
def export_cart_csv():
    import csv

    cart = _get_cart()
    if not cart:
        flash("Carrinho vazio.")
        return redirect(url_for("catalog.view_cart"))

    products = {p.id: p for p in load_products()}
    text_buffer = StringIO()
    writer = csv.writer(text_buffer, delimiter=";")
    writer.writerow(["SKU", "Nome", "Quantidade", "PrecoUnitario", "TotalLinha"]) 
    for pid, qty in cart.items():
        p = products.get(pid)
        if not p:
            continue
        price = p.promo_price if p.promo_price is not None else p.price
        line_total = price * qty
        price_str = f"{price:.2f}".replace(".", ",")
        total_str = f"{line_total:.2f}".replace(".", ",")
        writer.writerow([p.id, p.name, qty, price_str, total_str])
    data = text_buffer.getvalue()
    # Prepara bytes com BOM UTF-8
    data_bytes = ("\ufeff" + data).encode("utf-8")
    return send_file(BytesIO(data_bytes), as_attachment=True, download_name="carrinho.csv", mimetype="text/csv; charset=utf-8")


# --- Importação de clientes ---
@catalog_bp.get("/admin/clients/import")
def clients_import_page():
    msg = _require_admin()
    if msg:
        flash(msg)
        return redirect(url_for("catalog.index"))
    user = _get_current_user()
    return render_template("import_clients.html", user=user)


@catalog_bp.post("/admin/clients/import")
def clients_import_submit():
    msg = _require_admin()
    if msg:
        flash(msg)
        return redirect(url_for("catalog.index"))
    file = request.files.get("file")
    if not file or file.filename == "":
        flash("Selecione um arquivo .xlsx ou .csv")
        return redirect(url_for("catalog.clients_import_page"))
    filename = secure_filename(file.filename)
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    try:
        if ext == "xlsx":
            df = pd.read_excel(file, engine="openpyxl")
        elif ext == "csv":
            df = pd.read_csv(file)
        else:
            flash("Formato não suportado. Use .xlsx ou .csv")
            return redirect(url_for("catalog.clients_import_page"))
        _save_clients_dataframe(df)
        flash("Clientes importados com sucesso.")
    except Exception as e:
        flash(f"Falha ao importar: {e}")
    return redirect(url_for("catalog.clients_import_page"))


# --- Importação de fornecedores ---
@catalog_bp.get("/admin/suppliers/import")
def suppliers_import_page():
    msg = _require_admin()
    if msg:
        flash(msg)
        return redirect(url_for("catalog.index"))
    user = _get_current_user()
    return render_template("import_data.html", user=user, entity="fornecedores", accept=".xlsx,.csv", help_cols=["id","name","logo"]) 


@catalog_bp.post("/admin/suppliers/import")
def suppliers_import_submit():
    msg = _require_admin()
    if msg:
        flash(msg)
        return redirect(url_for("catalog.index"))
    file = request.files.get("file")
    if not file or file.filename == "":
        flash("Selecione um arquivo .xlsx ou .csv")
        return redirect(url_for("catalog.suppliers_import_page"))
    filename = secure_filename(file.filename)
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    try:
        if ext == "xlsx":
            df = pd.read_excel(file, engine="openpyxl")
        elif ext == "csv":
            df = pd.read_csv(file)
        else:
            flash("Formato não suportado. Use .xlsx ou .csv")
            return redirect(url_for("catalog.suppliers_import_page"))
        _save_suppliers_dataframe(df)
        flash("Fornecedores importados com sucesso.")
    except Exception as e:
        flash(f"Falha ao importar: {e}")
    return redirect(url_for("catalog.suppliers_import_page"))


# --- Importação de produtos ---
@catalog_bp.get("/admin/products/import")
def products_import_page():
    msg = _require_admin()
    if msg:
        flash(msg)
        return redirect(url_for("catalog.index"))
    user = _get_current_user()
    return render_template("import_data.html", user=user, entity="produtos", accept=".xlsx,.csv", help_cols=["id","supplier_id","name","price","promo_price","image"]) 


@catalog_bp.post("/admin/products/import")
def products_import_submit():
    msg = _require_admin()
    if msg:
        flash(msg)
        return redirect(url_for("catalog.index"))
    file = request.files.get("file")
    if not file or file.filename == "":
        flash("Selecione um arquivo .xlsx ou .csv")
        return redirect(url_for("catalog.products_import_page"))
    filename = secure_filename(file.filename)
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    try:
        if ext == "xlsx":
            df = pd.read_excel(file, engine="openpyxl")
        elif ext == "csv":
            df = pd.read_csv(file)
        else:
            flash("Formato não suportado. Use .xlsx ou .csv")
            return redirect(url_for("catalog.products_import_page"))
        _save_products_dataframe(df)
        flash("Produtos importados com sucesso.")
    except Exception as e:
        flash(f"Falha ao importar: {e}")
    return redirect(url_for("catalog.products_import_page"))


# --- Minha Conta ---
@catalog_bp.get("/account")
def account_page():
    user = _get_current_user()
    if not user:
        return redirect(url_for("catalog.login_page", next=url_for("catalog.account_page")))
    return render_template("account.html", user=user)


@catalog_bp.post("/account")
def account_submit():
    user = _get_current_user()
    if not user:
        return redirect(url_for("catalog.login_page", next=url_for("catalog.account_page")))

    # Se for admin, atualiza dados no admin.json
    if _is_admin_email(user.email):
        new_name = request.form.get("name", user.name).strip()
        new_email = request.form.get("email", user.email).strip()
        pw = request.form.get("password", "").strip()
        pw2 = request.form.get("password_confirm", "").strip()
        new_password = None
        if pw:
            if pw != pw2:
                flash("As senhas não conferem.")
                return redirect(url_for("catalog.account_page"))
            new_password = pw
        save_admin(email=new_email or None, password=new_password)
        if new_email and new_email != user.email:
            session["user_email"] = new_email
        flash("Dados do administrador atualizados.")
        return redirect(url_for("catalog.account_page"))

    df = _read_tabular("clients")
    if df is None:
        flash("Base de clientes ausente.")
        return redirect(url_for("catalog.account_page"))

    mask = df["email"].astype(str) == str(user.email)
    if mask.any():
        idx = df[mask].index[0]
        df.loc[idx, "name"] = request.form.get("name", user.name)
        new_email = request.form.get("email", user.email).strip()
        pw = request.form.get("password", "").strip()
        pw2 = request.form.get("password_confirm", "").strip()
        new_password = None
        if pw:
            if pw != pw2:
                flash("As senhas não conferem.")
                return redirect(url_for("catalog.account_page"))
            new_password = pw
        if new_email:
            df.loc[idx, "email"] = new_email
        if new_password:
            df.loc[idx, "password"] = new_password
        df.loc[idx, "phone"] = request.form.get("phone", user.phone or "")
        df.loc[idx, "address"] = request.form.get("address", user.address or "")
        df.loc[idx, "state"] = request.form.get("state", user.state or "")
        df.loc[idx, "city"] = request.form.get("city", user.city or "")
        df.loc[idx, "cep"] = request.form.get("cep", user.cep or "")
        _save_clients_dataframe(df)
        if new_email and new_email != user.email:
            session["user_email"] = new_email
        flash("Dados atualizados.")
    else:
        flash("Cliente não encontrado para atualizar.")
    return redirect(url_for("catalog.account_page"))


