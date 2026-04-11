import pandas as pd
import os

# --- SETTINGS ---
root_path = r'C:\Users\samba\Downloads' 
current_folder = os.path.dirname(os.path.abspath(__file__))

# 1. DATA INGESTION
listing_dfs = []
print("--- STAGE 1: INGESTION (RECURSIVE SEARCH) ---")
for root, dirs, files in os.walk(root_path):
    if 'raw' in root or 'crmls' in root:
        continue
        
    for file in files:
        if file.startswith('CRMLSListing') and file.endswith('.csv'):
            full_path = os.path.join(root, file)
            try:
                temp_df = pd.read_csv(full_path, low_memory=False)
                listing_dfs.append(temp_df)
                print(f"Loaded: {full_path} | Rows: {len(temp_df)}")
            except Exception as e:
                print(f"Error loading {file}: {e}")

if not listing_dfs:
    print("No Listing files found. Exiting.")
    exit()

df_listing = pd.concat(listing_dfs, ignore_index=True)
df_listing = df_listing.drop_duplicates()

# 2. PROPERTY TYPE FILTERING
df_listing = df_listing[df_listing['PropertyType'] == 'Residential']

# 3. MISSING VALUE REPORT
print("\n--- STAGE 3: MISSING VALUE REPORT (>90%) ---")
null_pct = (df_listing.isnull().sum() / len(df_listing)) * 100
high_missing = null_pct[null_pct > 90]
print(high_missing if not high_missing.empty else "None")

# 4. MORTGAGE RATE ENRICHMENT
print("\n--- STAGE 4: FRED MORTGAGE MERGE ---")
try:
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=MORTGAGE30US"
    mortgage = pd.read_csv(url)
    mortgage.columns = [col.lower() for col in mortgage.columns]
    mortgage['date'] = pd.to_datetime(mortgage['date'])
    mortgage.columns = ['date', 'rate_30yr_fixed']
    
    mortgage['year_month'] = mortgage['date'].dt.to_period('M')
    mortgage_monthly = mortgage.groupby('year_month')['rate_30yr_fixed'].mean().reset_index()
    
    date_col = 'ListingContractDate' if 'ListingContractDate' in df_listing.columns else 'Listing Contract Date'
    df_listing['year_month'] = pd.to_datetime(df_listing[date_col]).dt.to_period('M')
    
    df_listing = df_listing.merge(mortgage_monthly, on='year_month', how='left')
    print(f"Merge Complete. Validation (Null Rates): {df_listing['rate_30yr_fixed'].isnull().sum()}")
except Exception as e:
    print(f"Mortgage Merge Failed: {e}")

# 5. EXPORT
output_path = os.path.join(current_folder, 'Master_Listing_Enriched.csv')
df_listing.to_csv(output_path, index=False)
print(f"\n--- SUCCESS: File saved to {output_path} ---")