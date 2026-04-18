import pandas as pd
import os

# --- SETTINGS ---
root_path = r'C:\Users\samba\Downloads' 
current_folder = os.path.dirname(os.path.abspath(__file__))

# 1. DATA INGESTION
sold_dfs = []
print("--- STAGE 1: INGESTION (RECURSIVE SEARCH) ---")
for root, dirs, files in os.walk(root_path):
    if 'raw' in root or 'crmls' in root:
        continue
    for file in files:
        if file.startswith('CRMLSSold') and file.endswith('.csv'):
            full_path = os.path.join(root, file)
            try:
                temp_df = pd.read_csv(full_path, low_memory=False)
                sold_dfs.append(temp_df)
                print(f"Loaded: {full_path} | Rows: {len(temp_df)}")
            except Exception as e:
                print(f"Error loading {file}: {e}")

if not sold_dfs:
    print("No Sold files found. Exiting.")
    exit()

df_sold = pd.concat(sold_dfs, ignore_index=True)
df_sold = df_sold.drop_duplicates()

# 2. PROPERTY TYPE FILTERING
df_sold = df_sold[df_sold['PropertyType'] == 'Residential']

# 3. MISSING VALUE REPORT
print("\n--- STAGE 3: MISSING VALUE REPORT (>90%) ---")
null_pct = (df_sold.isnull().sum() / len(df_sold)) * 100
high_missing = null_pct[null_pct > 90]
print(high_missing if not high_missing.empty else "None")

# 4. DYNAMIC COLUMN DETECTION
print("\n--- STAGE 4: NUMERIC DISTRIBUTION ---")
def find_col(possible_names, df):
    for name in possible_names:
        for col in df.columns:
            if col.strip().lower() == name.lower():
                return col
    return None

price_col = find_col(['Close Price', 'ClosePrice', 'SoldPrice', 'Sold Price'], df_sold)
area_col = find_col(['LivingArea', 'Living Area', 'SqFt', 'SquareFootage'], df_sold)
dom_col = find_col(['Days On Market', 'DaysOnMarket', 'DOM'], df_sold)

stats_cols = []
for col in [price_col, area_col, dom_col]:
    if col:
        stats_cols.append(col)
        if df_sold[col].dtype == 'object':
            df_sold[col] = df_sold[col].replace(r'[\$,]', '', regex=True).astype(float)

if stats_cols:
    print(df_sold[stats_cols].describe(percentiles=[.25, .5, .75, .9]))
else:
    print("Warning: Could not find columns for pricing, area, or DOM analysis.")

# 5. MORTGAGE RATE ENRICHMENT (FIXED FOR FRED HEADERS)
print("\n--- STAGE 5: FRED MORTGAGE MERGE ---")
try:
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=MORTGAGE30US"
    mortgage = pd.read_csv(url)
    mortgage.columns = [col.lower() for col in mortgage.columns]
    
    # Handle the FRED date header swap
    date_col_name = 'date' if 'date' in mortgage.columns else 'observation_date'
    
    mortgage[date_col_name] = pd.to_datetime(mortgage[date_col_name])
    mortgage.columns = ['date', 'rate_30yr_fixed']
    
    mortgage['year_month'] = mortgage['date'].dt.to_period('M')
    mortgage_monthly = mortgage.groupby('year_month')['rate_30yr_fixed'].mean().reset_index()
    
    sold_date_col = find_col(['CloseDate', 'Close Date', 'SoldDate', 'Sold Date'], df_sold)
    if sold_date_col:
        df_sold['year_month'] = pd.to_datetime(df_sold[sold_date_col]).dt.to_period('M')
        df_sold = df_sold.merge(mortgage_monthly, on='year_month', how='left')
        print(f"Merge Complete. Validation (Null Rates): {df_sold['rate_30yr_fixed'].isnull().sum()}")
    else:
        print("Error: Could not find a date column for the mortgage merge.")
except Exception as e:
    print(f"Mortgage Merge Failed: {e}")

# 6. EXPORT
output_path = os.path.join(current_folder, 'Master_Sold_Enriched.csv')
df_sold.to_csv(output_path, index=False)
print(f"\n--- SUCCESS: File saved to {output_path} ---")