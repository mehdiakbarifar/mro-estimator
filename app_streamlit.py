import streamlit as st
import pandas as pd
import os
from collections import defaultdict
from fpdf import FPDF
from io import BytesIO

DATA_DIR = "data"

def load_csv(name):
    path = os.path.join(DATA_DIR, name)
    if not os.path.exists(path):
        st.error(f"Missing file: {path}")
        st.stop()
    return pd.read_csv(path)

# Load data
engine_models_df = load_csv("EngineModels.csv")
assemblies_df = load_csv("Assemblies.csv")
parts_df = load_csv("Parts.csv")
procedures_df = load_csv("Procedures.csv")
multipliers_df = load_csv("CostMultipliers.csv")

def get_multiplier(part_number, procedure_code):
    row = multipliers_df[
        (multipliers_df["PartNumber"] == part_number) &
        (multipliers_df["ProcedureCode"] == procedure_code)
    ]
    return float(row["Multiplier"].values[0]) if not row.empty else 1.0

def calculate_cost(part_number, procedure_code, quantity):
    proc_row = procedures_df[procedures_df["ProcedureCode"] == procedure_code]
    base_cost = float(proc_row["BaseCostUSD"].values[0])
    multiplier = get_multiplier(part_number, procedure_code)
    return base_cost, multiplier, base_cost * multiplier * quantity

# Helper to wrap text in a table cell
def wrap_text_cell(pdf, text, width, height):
    x = pdf.get_x()
    y = pdf.get_y()
    pdf.multi_cell(width, height, text, border=1)
    pdf.set_xy(x + width, y)

def generate_pdf(quote_items, part_totals, grand_total):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "Akbarifar MRO - Cost Estimate", ln=True, align="C")
    pdf.ln(5)

    pdf.set_font("Arial", '', 12)
    pdf.cell(0, 10, "Detailed Breakdown:", ln=True)
    pdf.set_font("Arial", '', 9)

    # Table header
    pdf.cell(30, 8, "Part No", border=1)
    pdf.cell(50, 8, "Description", border=1)
    pdf.cell(25, 8, "Procedure", border=1)
    pdf.cell(15, 8, "Qty", border=1, align="R")
    pdf.cell(20, 8, "Base", border=1, align="R")
    pdf.cell(20, 8, "Mult", border=1, align="R")
    pdf.cell(25, 8, "Total", border=1, align="R")
    pdf.ln()

    # Table rows
    for item in quote_items:
        pdf.cell(30, 8, item['PartNumber'], border=1)
        wrap_text_cell(pdf, item['Description'], 50, 8)
        pdf.cell(25, 8, item['ProcedureCode'], border=1)
        pdf.cell(15, 8, str(item['Quantity']), border=1, align="R")
        pdf.cell(20, 8, f"{item['BaseCost']:.2f}", border=1, align="R")
        pdf.cell(20, 8, f"{item['Multiplier']:.2f}", border=1, align="R")
        pdf.cell(25, 8, f"{item['Total']:.2f}", border=1, align="R")
        pdf.ln()

    pdf.ln(5)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, "Subtotals per Part:", ln=True)
    pdf.set_font("Arial", '', 10)
    for part_num, subtotal in part_totals.items():
        pdf.cell(0, 8, f"{part_num}: ${subtotal:.2f}", ln=True)

    pdf.ln(5)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, f"Grand Total: ${grand_total:.2f}", ln=True)

    # Return as BytesIO for Streamlit
    pdf_bytes = pdf.output(dest='S').encode('latin-1')
    return BytesIO(pdf_bytes)

# Streamlit UI
st.set_page_config(page_title="Akbarifar MRO Estimator", layout="wide")
st.title("Akbarifar MRO Cost Estimator")

# Step 1: Engine Model
engine_model = st.selectbox("Select Engine Model", engine_models_df["EngineModel"])

# Step 2: Assembly
assembly_options = assemblies_df[assemblies_df["EngineModel"] == engine_model]["AssemblyCode"].unique()
assembly = st.selectbox("Select Assembly", assembly_options)

# Step 3: Parts
part_options = parts_df[
    (parts_df["EngineModel"] == engine_model) &
    (parts_df["AssemblyCode"] == assembly)
]
selected_parts = st.multiselect(
    "Select Parts",
    options=part_options["PartNumber"],
    format_func=lambda pn: f"{pn} - {part_options.loc[part_options['PartNumber'] == pn, 'Description'].values[0]}"
)

quote_items = []
if selected_parts:
    st.subheader("Part Details & Procedures")
    for pn in selected_parts:
        part_row = part_options[part_options["PartNumber"] == pn].iloc[0]
        series_qty = None if pd.isna(part_row.SeriesQty) else int(part_row.SeriesQty)
        
        col1, col2 = st.columns([1, 2])
        with col1:
            use_series = st.checkbox(f"Use full series for {pn} ({series_qty if series_qty else 'N/A'})", value=True if series_qty else False)
            qty = series_qty if (use_series and series_qty) else st.number_input(f"Quantity for {pn}", min_value=1, value=1, key=f"qty_{pn}")
        with col2:
            selected_procs = st.multiselect(
                f"Select Procedures for {pn}",
                options=procedures_df["ProcedureCode"],
                format_func=lambda pc: f"{pc} - {procedures_df.loc[procedures_df['ProcedureCode'] == pc, 'ProcedureName'].values[0]}",
                key=f"proc_{pn}"
            )
        
        for proc in selected_procs:
            base_cost, multiplier, total = calculate_cost(pn, proc, qty)
            quote_items.append({
                "PartNumber": pn,
                "Description": part_row.Description,
                "ProcedureCode": proc,
                "Quantity": qty,
                "BaseCost": base_cost,
                "Multiplier": multiplier,
                "Total": total
            })

# Step 4: Show results + PDF download
if quote_items:
    st.subheader("Cost Breakdown")
    df = pd.DataFrame(quote_items)
    st.dataframe(df, use_container_width=True)

    st.markdown("### Subtotals per Part")
    part_totals = defaultdict(float)
    for item in quote_items:
        part_totals[item['PartNumber']] += item['Total']
    for part_num, subtotal in part_totals.items():
        desc = next(i['Description'] for i in quote_items if i['PartNumber'] == part_num)
        st.write(f"**{part_num} - {desc}:** ${subtotal:.2f}")

    grand_total = df['Total'].sum()
    st.markdown(f"## Grand Total: ${grand_total:.2f}")

    # PDF download button
    pdf_file = generate_pdf(quote_items, part_totals, grand_total)
    st.download_button(
        label="📄 Download PDF Quote",
        data=pdf_file,
        file_name="MRO_Cost_Estimate.pdf",
        mime="application/pdf"
    )
