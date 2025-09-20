from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import pandas as pd


DATA_DIR = Path("data")
IMG_DIR = Path("app/static/images")


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (IMG_DIR / "logos").mkdir(parents=True, exist_ok=True)
    (IMG_DIR / "produtos").mkdir(parents=True, exist_ok=True)


def create_placeholder(path: Path, text: str, size=(600, 400), bg=(230, 230, 230)) -> None:
    img = Image.new("RGB", size, bg)
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.load_default()
    except Exception:
        font = None
    tw, th = draw.textbbox((0, 0), text, font=font)[2:]
    x = (size[0] - tw) // 2
    y = (size[1] - th) // 2
    draw.text((x, y), text, fill=(40, 40, 40), font=font)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)


def seed():
    ensure_dirs()

    # Fornecedores
    suppliers = [
        {"id": "forn1", "name": "Fornecedor A", "logo": "logos/fornA.png"},
        {"id": "forn2", "name": "Fornecedor B", "logo": "logos/fornB.png"},
    ]
    for s in suppliers:
        create_placeholder(IMG_DIR / s["logo"], s["name"], size=(400, 200))
    pd.DataFrame(suppliers).to_excel(DATA_DIR / "suppliers.xlsx", index=False)

    # 12 produtos para forn1 e 6 para forn2
    products = []
    for i in range(1, 13):
        pid = f"A{i}"
        img_rel = f"produtos/{pid}.jpg"
        create_placeholder(IMG_DIR / img_rel, f"{pid}")
        products.append({
            "id": pid,
            "supplier_id": "forn1",
            "name": f"Produto {pid}",
            "price": 10.0 + i,
            "promo_price": 9.5 + i if i % 3 == 0 else None,
            "image": img_rel,
        })
    for i in range(1, 7):
        pid = f"B{i}"
        img_rel = f"produtos/{pid}.jpg"
        create_placeholder(IMG_DIR / img_rel, f"{pid}")
        products.append({
            "id": pid,
            "supplier_id": "forn2",
            "name": f"Produto {pid}",
            "price": 20.0 + i,
            "promo_price": None,
            "image": img_rel,
        })

    dfp = pd.DataFrame(products)
    dfp.to_excel(DATA_DIR / "products.xlsx", index=False)
    # Também grava CSVs como fallback
    dfp.to_csv(DATA_DIR / "products.csv", index=False)
    pd.DataFrame(suppliers).to_csv(DATA_DIR / "suppliers.csv", index=False)

    # Clientes de exemplo
    clients = [
        {"id": "c1", "name": "Cliente Demo", "email": "demo@teste.com", "password": "123456"},
    ]
    pdc = pd.DataFrame(clients)
    pdc.to_excel(DATA_DIR / "clients.xlsx", index=False)
    pdc.to_csv(DATA_DIR / "clients.csv", index=False)

    print("Dados de exemplo gerados em 'data/' e imagens em 'app/static/images/'.")


if __name__ == "__main__":
    seed()


