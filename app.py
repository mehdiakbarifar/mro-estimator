import pandas as pd
import os
from collections import defaultdict

DATA_DIR = "data"

def load_csv(name):
    path = os.path.join(DATA_DIR, name)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Missing file: {path}")
    return pd.read_csv(path)

# === Load Data ===
engine_models_df = load_csv("EngineModels.csv")
assemblies_df = load_csv("Assemblies.csv")
parts_df = load_csv("Parts.csv")
procedures_df = load_csv("Procedures.csv")
multipliers_df = load_csv("CostMultipliers.csv")

# === Helper Functions ===
def prompt_choice(options, label_extractor=lambda x: str(x), prompt="Select: ", multi=False):
    for i, opt in enumerate(options, start=1):
        print(f"{i}. {label_extractor(opt)}")
    while True:
        choice = input(prompt).strip()
        if multi:
            try:
                indices = [int(c.strip()) for c in choice.split(",") if c.strip()]
                if all(1 <= idx <= len(options) for idx in indices):
                    return [options[idx - 1] for idx in indices]
            except ValueError:
                pass
        else:
            try:
                idx = int(choice)
                if 1 <= idx <= len(options):
                    return options[idx - 1]
            except ValueError:
                pass
        print("Invalid selection. Try again.")

def get_multiplier(part_number, procedure_code):
    row = multipliers_df[
        (multipliers_df["PartNumber"] == part_number) &
        (multipliers_df["ProcedureCode"] == procedure_code)
    ]
    return float(row["Multiplier"].values[0]) if not row.empty else 1.0

def calculate_cost(part_number, procedure_code, quantity):
    proc_row = procedures_df[procedures_df["ProcedureCode"] == procedure_code]
    if proc_row.empty:
        raise ValueError(f"Procedure {procedure_code} not found.")
    base_cost = float(proc_row["BaseCostUSD"].values[0])
    multiplier = get_multiplier(part_number, procedure_code)
    total = base_cost * multiplier * quantity
    return base_cost, multiplier, total

# === CLI Flow ===
print("\n=== Akbarifar MRO Cost Estimator ===\n")

# Step 1: Select Engine Model
engine_models = list(engine_models_df["EngineModel"])
selected_engine = prompt_choice(engine_models, prompt="Select Engine Model: ")

# Step 2: Select Assembly
engine_assemblies = assemblies_df[assemblies_df["EngineModel"] == selected_engine]
if engine_assemblies.empty:
    raise SystemExit(f"No assemblies found for {selected_engine}")

assemblies = list(engine_assemblies["AssemblyCode"].unique())
selected_assembly = prompt_choice(assemblies, prompt="Select Assembly: ")

# Step 3: Select Multiple Parts
assembly_parts = parts_df[
    (parts_df["EngineModel"] == selected_engine) &
    (parts_df["AssemblyCode"] == selected_assembly)
]
if assembly_parts.empty:
    raise SystemExit(f"No parts found for {selected_engine} - {selected_assembly}")

selected_parts = prompt_choice(
    list(assembly_parts.index),
    label_extractor=lambda idx: f"{assembly_parts.loc[idx, 'PartNumber']} - {assembly_parts.loc[idx, 'Description']}",
    prompt="Select Parts (comma-separated): ",
    multi=True
)

# Step 4: For each part, get quantity & procedures
quote_items = []
for idx in selected_parts:
    part_row = assembly_parts.loc[idx]
    print(f"\n--- {part_row.PartNumber} - {part_row.Description} ---")
    series_qty = None if pd.isna(part_row.SeriesQty) else int(part_row.SeriesQty)
    if series_qty:
        print(f"Series Quantity: {series_qty}")
        use_series = input("Use full series? (y/n): ").strip().lower() == "y"
        quantity = series_qty if use_series else int(input("Enter quantity: "))
    else:
        quantity = int(input("Enter quantity: "))

    # Show all available procedures
    selected_procs = prompt_choice(
        list(procedures_df.index),
        label_extractor=lambda pidx: f"{procedures_df.loc[pidx, 'ProcedureCode']} - {procedures_df.loc[pidx, 'ProcedureName']}",
        prompt="Select Procedures (comma-separated): ",
        multi=True
    )

    for pidx in selected_procs:
        proc_code = procedures_df.loc[pidx, "ProcedureCode"]
        base_cost, multiplier, total = calculate_cost(part_row.PartNumber, proc_code, quantity)
        quote_items.append({
            "PartNumber": part_row.PartNumber,
            "Description": part_row.Description,
            "ProcedureCode": proc_code,
            "Quantity": quantity,
            "BaseCost": base_cost,
            "Multiplier": multiplier,
            "Total": total
        })

# Step 5: Show Breakdown with per-part totals
print("\n=== COST BREAKDOWN (USD) ===")
grand_total = 0
part_totals = defaultdict(float)

for item in quote_items:
    print(f"{item['PartNumber']} - {item['Description']} | {item['ProcedureCode']} | "
          f"Qty: {item['Quantity']} | Base: ${item['BaseCost']:.2f} | Mult: {item['Multiplier']} | "
          f"Total: ${item['Total']:.2f}")
    part_totals[item['PartNumber']] += item['Total']
    grand_total += item["Total"]

print("\n--- SUBTOTALS PER PART ---")
for part_num, subtotal in part_totals.items():
    desc = next(i['Description'] for i in quote_items if i['PartNumber'] == part_num)
    print(f"{part_num} - {desc}: ${subtotal:.2f}")

print(f"\nGRAND TOTAL: ${grand_total:.2f}")
