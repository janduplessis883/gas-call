from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from supabase import Client, create_client


APP_TITLE = "Gas at Call"
PRODUCT_IDS = ["5kg", "9kg", "14kg", "19kg", "48kg"]
PDF_DIR = Path("generated_pdfs")
VAT_RATE = Decimal("0.15")


st.set_page_config(page_title=APP_TITLE, layout="wide")


def money(value: Any) -> str:
    return f"R {float(value or 0):,.2f}"


def to_float(value: Any) -> float:
    return float(value or 0)


def vat_amount(base_amount: float | Decimal) -> float:
    return float(Decimal(str(base_amount)) * VAT_RATE)


def including_vat(base_amount: float | Decimal) -> float:
    base = Decimal(str(base_amount or 0))
    return float(base + (base * VAT_RATE))


def build_line_item(product_id: str, quantity: int, gas_base: float, container_base: float) -> dict[str, Any]:
    gas_total = Decimal(str(quantity)) * Decimal(str(gas_base or 0))
    container_total = Decimal(str(quantity)) * Decimal(str(container_base or 0))
    subtotal = gas_total + container_total
    vat = subtotal * VAT_RATE
    total = subtotal + vat
    unit_base = Decimal(str(gas_base or 0)) + Decimal(str(container_base or 0))
    return {
        "product_id": product_id,
        "quantity": quantity,
        "gas_amount_ex_vat": float(gas_base or 0),
        "container_amount_ex_vat": float(container_base or 0),
        "gas_total_ex_vat": float(gas_total),
        "container_total_ex_vat": float(container_total),
        "vat_amount": float(vat),
        "unit_price": float(unit_base + (unit_base * VAT_RATE)),
        "line_total": float(total),
    }


def document_totals(items: list[dict[str, Any]]) -> dict[str, float]:
    gas_total = sum(to_float(item.get("gas_total_ex_vat")) for item in items)
    container_total = sum(to_float(item.get("container_total_ex_vat")) for item in items)
    vat_total = sum(to_float(item.get("vat_amount")) for item in items)
    total = sum(to_float(item.get("line_total")) for item in items)
    return {
        "gas_total_ex_vat": gas_total,
        "container_total_ex_vat": container_total,
        "vat_amount": vat_total,
        "subtotal": gas_total + container_total,
        "total": total,
    }


def product_default(product: dict[str, Any], key: str) -> float:
    return to_float(product.get(key, 0))


@st.cache_resource
def get_supabase() -> Client:
    config = st.secrets.get("connections", {}).get("supabase", {})
    url = config.get("SUPABASE_URL") or st.secrets.get("SUPABASE_URL")
    key = config.get("SUPABASE_KEY") or st.secrets.get("SUPABASE_KEY")
    if not url or not key:
        st.error("Supabase URL and key are missing from .streamlit/secrets.toml.")
        st.stop()
    return create_client(url, key)


db = get_supabase()


def stop_with_database_setup_error(action: str, error: Exception) -> None:
    st.error(f"Supabase blocked the app while trying to {action}.")
    st.info(
        "Run supabase_rls_policies.sql in the Supabase SQL editor, then refresh this app. "
        "That file opens the app tables to the PIN-protected Streamlit app and inserts the five standard products."
    )
    with st.expander("Technical details"):
        st.code(str(error))
    st.stop()


def run_query(table: str, order: str | None = None, desc: bool = False) -> list[dict[str, Any]]:
    query = db.table(table).select("*")
    if order:
        query = query.order(order, desc=desc)
    return query.execute().data or []


def insert_row(table: str, payload: dict[str, Any]) -> dict[str, Any]:
    try:
        return db.table(table).insert(payload).execute().data[0]
    except Exception as error:
        stop_with_database_setup_error(f"save a row in {table}", error)


def update_row(table: str, row_id: str, payload: dict[str, Any]) -> None:
    try:
        db.table(table).update(payload).eq("id", row_id).execute()
    except Exception as error:
        stop_with_database_setup_error(f"update a row in {table}", error)


def get_products() -> list[dict[str, Any]]:
    try:
        products = db.table("products").select("*").order("sort_order").execute().data or []
    except Exception as error:
        stop_with_database_setup_error("read products", error)

    if not products:
        st.error("The products table is empty.")
        st.info("Run supabase_rls_policies.sql in Supabase to insert the five standard products.")
        st.stop()
    return products


def get_clients() -> list[dict[str, Any]]:
    return db.table("clients").select("*").order("name").execute().data or []


def get_stock_movements() -> list[dict[str, Any]]:
    return db.table("stock_movements").select("*").order("movement_date", desc=True).execute().data or []


def stock_by_product() -> dict[str, int]:
    stock = {product_id: 0 for product_id in PRODUCT_IDS}
    for movement in get_stock_movements():
        stock[movement["product_id"]] = stock.get(movement["product_id"], 0) + int(movement["quantity"])
    return stock


def invoice_balance(invoice_id: str) -> float:
    invoice = db.table("invoices").select("total").eq("id", invoice_id).single().execute().data
    payments = db.table("payments").select("amount").eq("invoice_id", invoice_id).execute().data or []
    paid = sum(to_float(payment["amount"]) for payment in payments)
    return to_float(invoice["total"]) - paid


def refresh_invoice_status(invoice_id: str) -> None:
    balance = invoice_balance(invoice_id)
    invoice = db.table("invoices").select("total").eq("id", invoice_id).single().execute().data
    total = to_float(invoice["total"])
    if balance <= 0:
        status = "paid"
    elif balance < total:
        status = "partial"
    else:
        status = "unpaid"
    update_row("invoices", invoice_id, {"status": status})


def next_document_number(prefix: str, table: str, column: str) -> str:
    existing = db.table(table).select(column).order("created_at", desc=True).limit(1).execute().data or []
    if not existing:
        return f"{prefix}-0001"
    last = existing[0][column]
    try:
        number = int(str(last).split("-")[-1]) + 1
    except ValueError:
        number = len(existing) + 1
    return f"{prefix}-{number:04d}"


def generate_pdf(
    doc_type: str,
    number: str,
    client: dict[str, Any],
    doc_date: date,
    items: list[dict[str, Any]],
    total: float,
    reason: str = "",
) -> Path:
    PDF_DIR.mkdir(exist_ok=True)
    filename = PDF_DIR / f"{number}.pdf"
    styles = getSampleStyleSheet()
    story = [
        Paragraph(f"<b>{APP_TITLE}</b>", styles["Title"]),
        Paragraph(doc_type, styles["Heading2"]),
        Paragraph(f"<b>Number:</b> {number}", styles["Normal"]),
        Paragraph(f"<b>Date:</b> {doc_date.isoformat()}", styles["Normal"]),
        Spacer(1, 8 * mm),
        Paragraph(f"<b>Client:</b> {client['name']}", styles["Normal"]),
        Paragraph(client.get("address", ""), styles["Normal"]),
        Paragraph(client.get("contact_number", ""), styles["Normal"]),
        Paragraph(client.get("email", ""), styles["Normal"]),
        Spacer(1, 8 * mm),
    ]
    if reason:
        story.extend([Paragraph(f"<b>Reason:</b> {reason}", styles["Normal"]), Spacer(1, 6 * mm)])

    table_rows = [["Cylinder size", "Qty", "Gas/unit ex VAT", "Cylinder/unit ex VAT", "VAT", "Line total"]]
    for item in items:
        table_rows.append(
            [
                item["product_id"],
                str(item["quantity"]),
                money(item.get("gas_amount_ex_vat", 0)),
                money(item.get("container_amount_ex_vat", 0)),
                money(item.get("vat_amount", 0)),
                money(item["line_total"]),
            ]
        )
    table_rows.append(["", "", "", "", "Total", money(total)])

    table = Table(table_rows, colWidths=[35 * mm, 18 * mm, 32 * mm, 38 * mm, 25 * mm, 32 * mm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0c1722")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#d7ded8")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                ("FONTNAME", (4, -1), (-1, -1), "Helvetica-Bold"),
            ]
        )
    )
    story.append(table)

    doc = SimpleDocTemplate(str(filename), pagesize=A4, rightMargin=18 * mm, leftMargin=18 * mm)
    doc.build(story)
    return filename


def require_login() -> None:
    expected_pin = str(st.secrets.get("app", {}).get("MANAGER_PIN", ""))
    if not expected_pin:
        st.error("Manager PIN is missing from .streamlit/secrets.toml.")
        st.stop()
    if st.session_state.get("authenticated"):
        return
    st.title(APP_TITLE)
    st.caption("Depot, deliveries, clients, invoices and cylinder tracking.")
    with st.form("login"):
        pin = st.text_input("Manager PIN", type="password")
        submitted = st.form_submit_button("Unlock")
    if submitted:
        if pin == expected_pin:
            st.session_state.authenticated = True
            st.rerun()
        st.error("Incorrect PIN.")
    st.stop()


def client_lookup(clients: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {client["name"]: client for client in clients}


def show_client_details(client: dict[str, Any]) -> None:
    col1, col2, col3 = st.columns(3)
    col1.info(client.get("address") or "No address captured")
    col2.info(client.get("contact_number") or "No contact number")
    col3.info(client.get("email") or "No email")


def dashboard_page() -> None:
    products = get_products()
    stock = stock_by_product()
    invoices = run_query("invoices", "invoice_date", True)
    payments = run_query("payments", "payment_date", True)
    total_invoiced = sum(to_float(invoice["total"]) for invoice in invoices if invoice["status"] != "void")
    total_paid = sum(to_float(payment["amount"]) for payment in payments)

    st.header("Dashboard")
    c1, c2, c3 = st.columns(3)
    c1.metric("Stock in depot", f"{sum(stock.values())} cylinders")
    c2.metric("Outstanding balance", money(total_invoiced - total_paid))
    c3.metric("Active clients", len(get_clients()))

    st.subheader("Stock on hand")
    stock_rows = [
        {
            "Product": product["id"],
            "In stock": stock.get(product["id"], 0),
            "Gas cost ex VAT": money(product_default(product, "gas_purchase_cost_ex_vat")),
            "Cylinder cost ex VAT": money(product_default(product, "container_purchase_cost_ex_vat")),
            "Gas sale ex VAT": money(product_default(product, "gas_sale_price_ex_vat")),
            "Cylinder sale ex VAT": money(product_default(product, "container_sale_price_ex_vat")),
            "Sale incl VAT": money(
                including_vat(
                    product_default(product, "gas_sale_price_ex_vat")
                    + product_default(product, "container_sale_price_ex_vat")
                )
            ),
        }
        for product in products
    ]
    st.dataframe(pd.DataFrame(stock_rows), use_container_width=True, hide_index=True)

    st.subheader("Recent invoices")
    if invoices:
        rows = []
        for invoice in invoices[:10]:
            rows.append(
                {
                    "Invoice": invoice["invoice_number"],
                    "Date": invoice["invoice_date"],
                    "Gas ex VAT": money(invoice.get("gas_total_ex_vat", 0)),
                    "Cylinder ex VAT": money(invoice.get("container_total_ex_vat", 0)),
                    "VAT": money(invoice.get("vat_amount", 0)),
                    "Total": money(invoice["total"]),
                    "Status": invoice["status"],
                    "Balance": money(invoice_balance(invoice["id"])),
                }
            )
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("No invoices yet.")


def clients_page() -> None:
    st.header("Clients")
    clients = get_clients()
    with st.expander("Add a new client", expanded=not clients):
        with st.form("client_form", clear_on_submit=True):
            name = st.text_input("Client name")
            address = st.text_area("Address")
            contact = st.text_input("Contact number")
            email = st.text_input("Email address")
            notes = st.text_area("Notes")
            if st.form_submit_button("Save client"):
                if not name.strip():
                    st.error("Client name is required.")
                else:
                    insert_row(
                        "clients",
                        {
                            "name": name.strip(),
                            "address": address.strip(),
                            "contact_number": contact.strip(),
                            "email": email.strip(),
                            "notes": notes.strip(),
                        },
                    )
                    st.success("Client saved.")
                    st.rerun()

    if not clients:
        st.info("No clients captured yet.")
        return

    selected_name = st.selectbox("Edit client", [client["name"] for client in clients])
    selected = client_lookup(clients)[selected_name]
    with st.form("edit_client"):
        name = st.text_input("Client name", selected["name"])
        address = st.text_area("Address", selected.get("address", ""))
        contact = st.text_input("Contact number", selected.get("contact_number", ""))
        email = st.text_input("Email address", selected.get("email", ""))
        notes = st.text_area("Notes", selected.get("notes", ""))
        if st.form_submit_button("Update client"):
            update_row(
                "clients",
                selected["id"],
                {
                    "name": name.strip(),
                    "address": address.strip(),
                    "contact_number": contact.strip(),
                    "email": email.strip(),
                    "notes": notes.strip(),
                },
            )
            st.success("Client updated.")
            st.rerun()


def stock_page() -> None:
    st.header("Stock")
    products = get_products()
    stock = stock_by_product()

    st.subheader("Capture depot delivery")
    with st.form("purchase_form", clear_on_submit=True):
        purchase_date = st.date_input("Date delivered", value=date.today())
        quantities: dict[str, int] = {}
        for product in products:
            col1, col2, col3, col4, col5, col6 = st.columns([0.85, 0.9, 1, 1, 1, 1])
            col1.markdown(f"**{product['id']}**")
            quantities[product["id"]] = col2.number_input(f"{product['id']} bottles", min_value=0, step=1)
            qty = quantities[product["id"]]
            gas_cost = product_default(product, "gas_purchase_cost_ex_vat")
            container_cost = product_default(product, "container_purchase_cost_ex_vat")
            gas_total = gas_cost * qty
            container_total = container_cost * qty
            col3.metric("Gas cost", money(gas_cost))
            col4.metric("Cylinder cost", money(container_cost))
            col5.metric("VAT", money(vat_amount(gas_total + container_total)))
            col6.metric("Line total", money(including_vat(gas_total + container_total)))
        notes = st.text_input("Delivery notes")
        if st.form_submit_button("Add to stock"):
            added = 0
            for product in products:
                qty = int(quantities[product["id"]])
                if qty:
                    line = build_line_item(
                        product["id"],
                        qty,
                        product_default(product, "gas_purchase_cost_ex_vat"),
                        product_default(product, "container_purchase_cost_ex_vat"),
                    )
                    insert_row(
                        "stock_movements",
                        {
                            "product_id": product["id"],
                            "movement_type": "purchase",
                            "quantity": qty,
                            "unit_price": line["unit_price"],
                            "gas_amount_ex_vat": line["gas_amount_ex_vat"],
                            "container_amount_ex_vat": line["container_amount_ex_vat"],
                            "gas_total_ex_vat": line["gas_total_ex_vat"],
                            "container_total_ex_vat": line["container_total_ex_vat"],
                            "vat_amount": line["vat_amount"],
                            "line_total": line["line_total"],
                            "movement_date": purchase_date.isoformat(),
                            "notes": notes,
                        },
                    )
                    added += qty
            st.success(f"Added {added} cylinders to depot stock.")
            st.rerun()

    st.subheader("Stock on hand")
    st.dataframe(
        pd.DataFrame([{"Product": product["id"], "In stock": stock.get(product["id"], 0)} for product in products]),
        use_container_width=True,
        hide_index=True,
    )

    st.subheader("Stock movement history")
    movements = get_stock_movements()
    if movements:
        movement_rows = [
            {
                "Date": movement["movement_date"],
                "Product": movement["product_id"],
                "Type": movement["movement_type"],
                "Qty": movement["quantity"],
                "Gas/unit ex VAT": money(movement.get("gas_amount_ex_vat", 0)),
                "Cylinder/unit ex VAT": money(movement.get("container_amount_ex_vat", 0)),
                "Gas total ex VAT": money(movement.get("gas_total_ex_vat", 0)),
                "Cylinder total ex VAT": money(movement.get("container_total_ex_vat", 0)),
                "VAT": money(movement.get("vat_amount", 0)),
                "Total incl VAT": money(movement.get("line_total", 0)),
                "Notes": movement.get("notes", ""),
            }
            for movement in movements
        ]
        st.dataframe(pd.DataFrame(movement_rows), use_container_width=True, hide_index=True)
    else:
        st.info("No stock movements yet.")


def sales_page() -> None:
    st.header("New sale and invoice")
    clients = get_clients()
    products = get_products()
    stock = stock_by_product()
    if not clients:
        st.warning("Add a client before creating an invoice.")
        return

    selected_name = st.selectbox("Client", [client["name"] for client in clients])
    client = client_lookup(clients)[selected_name]
    show_client_details(client)

    with st.form("sale_form"):
        invoice_date = st.date_input("Invoice date", value=date.today())
        item_inputs = []
        for product in products:
            st.markdown(f"**{product['id']}**")
            col1, col2, col3, col4, col5, col6 = st.columns([0.9, 1, 1, 1, 1, 0.9])
            qty = col1.number_input(
                f"{product['id']} quantity",
                min_value=0,
                max_value=max(0, stock.get(product["id"], 0)),
                step=1,
                key=f"sale_qty_{product['id']}",
            )
            gas_price = col2.number_input(
                f"{product['id']} gas ex VAT",
                min_value=0.0,
                value=product_default(product, "gas_sale_price_ex_vat"),
                step=10.0,
                key=f"sale_gas_price_{product['id']}",
            )
            container_price = col3.number_input(
                f"{product['id']} cylinder ex VAT",
                min_value=0.0,
                value=product_default(product, "container_sale_price_ex_vat"),
                step=10.0,
                key=f"sale_container_price_{product['id']}",
            )
            line_preview = build_line_item(product["id"], int(qty), gas_price, container_price)
            col4.metric("VAT", money(line_preview["vat_amount"]))
            col5.metric("Line total", money(line_preview["line_total"]))
            col6.metric("Available", stock.get(product["id"], 0))
            if qty:
                item_inputs.append(line_preview)
        totals = document_totals(item_inputs)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Gas total ex VAT", money(totals["gas_total_ex_vat"]))
        c2.metric("Cylinder total ex VAT", money(totals["container_total_ex_vat"]))
        c3.metric("VAT", money(totals["vat_amount"]))
        c4.metric("Invoice total", money(totals["total"]))
        submitted = st.form_submit_button("Create invoice PDF")

    if submitted:
        if not item_inputs:
            st.error("Add at least one cylinder to the invoice.")
            return
        invoice_number = next_document_number("INV", "invoices", "invoice_number")
        invoice = insert_row(
            "invoices",
            {
                "invoice_number": invoice_number,
                "client_id": client["id"],
                "invoice_date": invoice_date.isoformat(),
                "gas_total_ex_vat": totals["gas_total_ex_vat"],
                "container_total_ex_vat": totals["container_total_ex_vat"],
                "vat_amount": totals["vat_amount"],
                "subtotal": totals["subtotal"],
                "total": totals["total"],
                "status": "unpaid",
            },
        )
        for item in item_inputs:
            insert_row("invoice_items", {"invoice_id": invoice["id"], **item})
            insert_row(
                "stock_movements",
                {
                    "product_id": item["product_id"],
                    "movement_type": "sale",
                    "quantity": -int(item["quantity"]),
                    "unit_price": item["unit_price"],
                    "gas_amount_ex_vat": item["gas_amount_ex_vat"],
                    "container_amount_ex_vat": item["container_amount_ex_vat"],
                    "gas_total_ex_vat": item["gas_total_ex_vat"],
                    "container_total_ex_vat": item["container_total_ex_vat"],
                    "vat_amount": item["vat_amount"],
                    "line_total": item["line_total"],
                    "movement_date": invoice_date.isoformat(),
                    "client_id": client["id"],
                    "invoice_id": invoice["id"],
                    "notes": invoice_number,
                },
            )
        pdf_path = generate_pdf("Tax Invoice", invoice_number, client, invoice_date, item_inputs, totals["total"])
        update_row("invoices", invoice["id"], {"pdf_filename": str(pdf_path)})
        st.success(f"Invoice {invoice_number} created.")
        with open(pdf_path, "rb") as pdf:
            st.download_button("Download invoice PDF", pdf, file_name=pdf_path.name, mime="application/pdf")


def payments_page() -> None:
    st.header("Payments")
    invoices = db.table("invoices").select("*, clients(name)").neq("status", "paid").order("invoice_date", desc=True).execute().data or []
    if not invoices:
        st.info("No unpaid invoices.")
        return

    labels = [
        f"{invoice['invoice_number']} - {invoice['clients']['name']} - balance {money(invoice_balance(invoice['id']))}"
        for invoice in invoices
    ]
    selected_label = st.selectbox("Invoice", labels)
    invoice = invoices[labels.index(selected_label)]
    balance = invoice_balance(invoice["id"])
    st.metric("Outstanding balance", money(balance))

    with st.form("payment_form", clear_on_submit=True):
        payment_date = st.date_input("Payment date", value=date.today())
        amount = st.number_input("Amount received", min_value=0.0, max_value=max(balance, 0.0), value=max(balance, 0.0), step=10.0)
        method = st.selectbox("Payment method", ["Cash", "EFT", "Card", "Other"])
        reference = st.text_input("Reference")
        notes = st.text_input("Notes")
        if st.form_submit_button("Capture payment"):
            insert_row(
                "payments",
                {
                    "invoice_id": invoice["id"],
                    "client_id": invoice["client_id"],
                    "payment_date": payment_date.isoformat(),
                    "amount": amount,
                    "method": method,
                    "reference": reference,
                    "notes": notes,
                },
            )
            refresh_invoice_status(invoice["id"])
            st.success("Payment captured.")
            st.rerun()

    st.subheader("Payment history")
    payments = run_query("payments", "payment_date", True)
    if payments:
        st.dataframe(pd.DataFrame(payments), use_container_width=True, hide_index=True)


def credits_page() -> None:
    st.header("Credit notes")
    clients = get_clients()
    products = get_products()
    if not clients:
        st.warning("Add a client before creating a credit note.")
        return

    selected_name = st.selectbox("Client", [client["name"] for client in clients])
    client = client_lookup(clients)[selected_name]
    show_client_details(client)

    with st.form("credit_form"):
        credit_date = st.date_input("Credit date", value=date.today())
        reason = st.text_input("Reason")
        item_inputs = []
        for product in products:
            st.markdown(f"**{product['id']}**")
            col1, col2, col3, col4, col5 = st.columns([1, 1, 1, 1, 1])
            qty = col1.number_input(f"{product['id']} returned qty", min_value=0, step=1, key=f"credit_qty_{product['id']}")
            gas_price = col2.number_input(
                f"{product['id']} gas ex VAT",
                min_value=0.0,
                value=product_default(product, "gas_sale_price_ex_vat"),
                step=10.0,
                key=f"credit_gas_price_{product['id']}",
            )
            container_price = col3.number_input(
                f"{product['id']} cylinder ex VAT",
                min_value=0.0,
                value=product_default(product, "container_sale_price_ex_vat"),
                step=10.0,
                key=f"credit_container_price_{product['id']}",
            )
            line_preview = build_line_item(product["id"], int(qty), gas_price, container_price)
            col4.metric("VAT", money(line_preview["vat_amount"]))
            col5.metric("Line total", money(line_preview["line_total"]))
            if qty:
                item_inputs.append(line_preview)
        totals = document_totals(item_inputs)
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Gas total ex VAT", money(totals["gas_total_ex_vat"]))
        c2.metric("Cylinder total ex VAT", money(totals["container_total_ex_vat"]))
        c3.metric("VAT", money(totals["vat_amount"]))
        c4.metric("Credit total", money(totals["total"]))
        submitted = st.form_submit_button("Create credit note PDF")

    if submitted:
        if not item_inputs:
            st.error("Add at least one returned cylinder.")
            return
        credit_number = next_document_number("CRN", "credit_notes", "credit_number")
        credit = insert_row(
            "credit_notes",
            {
                "credit_number": credit_number,
                "client_id": client["id"],
                "credit_date": credit_date.isoformat(),
                "gas_total_ex_vat": totals["gas_total_ex_vat"],
                "container_total_ex_vat": totals["container_total_ex_vat"],
                "vat_amount": totals["vat_amount"],
                "amount": totals["total"],
                "reason": reason,
            },
        )
        for item in item_inputs:
            insert_row("credit_note_items", {"credit_note_id": credit["id"], **item})
            insert_row(
                "stock_movements",
                {
                    "product_id": item["product_id"],
                    "movement_type": "credit_note",
                    "quantity": int(item["quantity"]),
                    "unit_price": item["unit_price"],
                    "gas_amount_ex_vat": item["gas_amount_ex_vat"],
                    "container_amount_ex_vat": item["container_amount_ex_vat"],
                    "gas_total_ex_vat": item["gas_total_ex_vat"],
                    "container_total_ex_vat": item["container_total_ex_vat"],
                    "vat_amount": item["vat_amount"],
                    "line_total": item["line_total"],
                    "movement_date": credit_date.isoformat(),
                    "client_id": client["id"],
                    "credit_note_id": credit["id"],
                    "notes": credit_number,
                },
            )
        pdf_path = generate_pdf("Credit Note", credit_number, client, credit_date, item_inputs, totals["total"], reason)
        update_row("credit_notes", credit["id"], {"pdf_filename": str(pdf_path)})
        st.success(f"Credit note {credit_number} created.")
        with open(pdf_path, "rb") as pdf:
            st.download_button("Download credit note PDF", pdf, file_name=pdf_path.name, mime="application/pdf")


def cylinders_page() -> None:
    st.header("Outstanding cylinders")
    movements = db.table("stock_movements").select("*, clients(name)").in_("movement_type", ["sale", "credit_note"]).execute().data or []
    outstanding: dict[tuple[str, str], int] = {}
    for movement in movements:
        if not movement.get("client_id"):
            continue
        client_name = movement.get("clients", {}).get("name", "Unknown client")
        key = (client_name, movement["product_id"])
        outstanding[key] = outstanding.get(key, 0) - int(movement["quantity"])

    rows = [
        {"Client": client_name, "Product": product_id, "Outstanding": qty}
        for (client_name, product_id), qty in sorted(outstanding.items())
        if qty > 0
    ]
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.info("No cylinders are currently outstanding with clients.")


def settings_page() -> None:
    st.header("Prices")
    st.caption("Set the gas and cylinder amounts for each cylinder size. Enter prices excluding VAT; VAT is calculated automatically at 15%.")
    products = get_products()
    for product in products:
        with st.form(f"price_{product['id']}"):
            st.subheader(f"{product['id']} cylinder")

            st.markdown("**Stock cost used when adding new bottles**")
            cost1, cost2, cost3, cost4 = st.columns([1, 1, 1, 1])
            gas_cost = cost1.number_input(
                "Gas cost ex VAT",
                min_value=0.0,
                value=product_default(product, "gas_purchase_cost_ex_vat"),
                step=10.0,
                key=f"default_gas_cost_{product['id']}",
            )
            container_cost = cost2.number_input(
                "Cylinder cost ex VAT",
                min_value=0.0,
                value=product_default(product, "container_purchase_cost_ex_vat"),
                step=10.0,
                key=f"default_container_cost_{product['id']}",
            )
            cost3.metric("VAT on cost", money(vat_amount(gas_cost + container_cost)))
            cost4.metric("Cost incl VAT", money(including_vat(gas_cost + container_cost)))

            st.markdown("**Selling price used on invoices**")
            sale1, sale2, sale3, sale4 = st.columns([1, 1, 1, 1])
            gas_price = sale1.number_input(
                "Gas price ex VAT",
                min_value=0.0,
                value=product_default(product, "gas_sale_price_ex_vat"),
                step=10.0,
                key=f"default_gas_price_{product['id']}",
            )
            container_price = sale2.number_input(
                "Cylinder price ex VAT",
                min_value=0.0,
                value=product_default(product, "container_sale_price_ex_vat"),
                step=10.0,
                key=f"default_container_price_{product['id']}",
            )
            sale3.metric("VAT on sale", money(vat_amount(gas_price + container_price)))
            sale4.metric("Sale incl VAT", money(including_vat(gas_price + container_price)))

            if st.form_submit_button(f"Save {product['id']} price"):
                update_row(
                    "products",
                    product["id"],
                    {
                        "gas_purchase_cost_ex_vat": gas_cost,
                        "container_purchase_cost_ex_vat": container_cost,
                        "gas_sale_price_ex_vat": gas_price,
                        "container_sale_price_ex_vat": container_price,
                        "default_price": including_vat(gas_price + container_price),
                    },
                )
                st.success(f"{product['id']} price updated.")
                st.rerun()

    st.subheader("PDF archive")
    st.caption("Generated invoice and credit-note PDFs are saved locally in the app folder.")
    if PDF_DIR.exists():
        st.write(str(PDF_DIR.resolve()))
    else:
        st.info("No PDFs generated yet.")


def main() -> None:
    require_login()
    st.sidebar.title(APP_TITLE)
    page = st.sidebar.radio(
        "Menu",
        [
            "Dashboard",
            "Clients",
            "Stock",
            "Sales & invoices",
            "Payments",
            "Credit notes",
            "Outstanding cylinders",
            "Prices & settings",
        ],
    )
    if st.sidebar.button("Lock app"):
        st.session_state.authenticated = False
        st.rerun()

    if page == "Dashboard":
        dashboard_page()
    elif page == "Clients":
        clients_page()
    elif page == "Stock":
        stock_page()
    elif page == "Sales & invoices":
        sales_page()
    elif page == "Payments":
        payments_page()
    elif page == "Credit notes":
        credits_page()
    elif page == "Outstanding cylinders":
        cylinders_page()
    else:
        settings_page()


if __name__ == "__main__":
    main()
