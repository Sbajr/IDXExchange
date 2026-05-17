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

# 5. MORTGAGE RATE ENRICHMENT 
print("\n--- STAGE 5: FRED MORTGAGE MERGE ---")
try:
    url = "https://fred.stlouisfed.org/graph/fredgraph.csv?id=MORTGAGE30US"
    mortgage = pd.read_csv(url)
    mortgage.columns = [col.lower() for col in mortgage.columns]
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
except Exception as e:
    print(f"Mortgage Merge Failed: {e}")

# 6. WEEKS 4-5 DATA CLEANING & LOGIC CHECKS
print("\n--- STAGE 6: DATA CLEANING & LOGIC CHECKS ---")
for d_col in ['CloseDate', 'PurchaseContractDate', 'ListingContractDate']:
    actual_col = find_col([d_col, d_col.replace(' ', '')], df_sold)
    if actual_col:
        df_sold[actual_col] = pd.to_datetime(df_sold[actual_col], errors='coerce')

df_sold['invalid_phys_attr_flag'] = False
if price_col: df_sold.loc[df_sold[price_col] <= 0, 'invalid_phys_attr_flag'] = True
if area_col: df_sold.loc[df_sold[area_col] <= 0, 'invalid_phys_attr_flag'] = True
if dom_col: df_sold.loc[df_sold[dom_col] < 0, 'invalid_phys_attr_flag'] = True

list_c = find_col(['ListingContractDate', 'Listing Contract Date'], df_sold)
close_c = find_col(['CloseDate', 'Close Date'], df_sold)
df_sold['negative_timeline_flag'] = False
if list_c and close_c:
    df_sold['negative_timeline_flag'] = df_sold[list_c] > df_sold[close_c]

lat_c, lon_c = find_col(['Latitude'], df_sold), find_col(['Longitude'], df_sold)
df_sold['geo_error_flag'] = False
if lat_c and lon_c:
    df_sold[lat_c] = pd.to_numeric(df_sold[lat_c], errors='coerce')
    df_sold[lon_c] = pd.to_numeric(df_sold[lon_c], errors='coerce')
    df_sold['geo_error_flag'] = (df_sold[lon_c] > 0) | (df_sold[lat_c] == 0)

print(f"Flags - Invalid Phys: {df_sold['invalid_phys_attr_flag'].sum()} | Geo: {df_sold['geo_error_flag'].sum()}")

# 7. WEEK 6 FEATURE ENGINEERING & METRICS
print("\n--- STAGE 7: FEATURE ENGINEERING & METRICS ---")
orig_list_c = find_col(['OriginalListPrice', 'Original List Price'], df_sold)
purch_c = find_col(['PurchaseContractDate', 'Purchase Contract Date'], df_sold)

if orig_list_c:
    if df_sold[orig_list_c].dtype == 'object':
        df_sold[orig_list_c] = pd.to_numeric(df_sold[orig_list_c].replace(r'[\$,]', '', regex=True), errors='coerce')

if price_col and orig_list_c:
    df_sold['Close_to_Original_Ratio'] = df_sold[price_col] / df_sold[orig_list_c]
if price_col and area_col:
    df_sold['Price_Per_SqFt'] = df_sold[price_col] / df_sold[area_col]

if purch_c and list_c:
    df_sold['Listing_to_Contract_Days'] = (df_sold[purch_c] - df_sold[list_c]).dt.days
if close_c and purch_c:
    df_sold['Contract_to_Close_Days'] = (df_sold[close_c] - df_sold[purch_c]).dt.days

if close_c:
    df_sold['Year'] = df_sold[close_c].dt.year
    df_sold['Month'] = df_sold[close_c].dt.month
    df_sold['YrMo'] = df_sold[close_c].dt.to_period('M').astype(str)

# 8. WEEK 6 SEGMENT ANALYSIS
county_c = find_col(['CountyOrParish', 'County'], df_sold)
if county_c and price_col:
    print(f"\n--- STAGE 8: SEGMENT ANALYSIS BY {county_c} ---")
    summary_cols = {price_col: 'median'}
    if 'Price_Per_SqFt' in df_sold.columns: summary_cols['Price_Per_SqFt'] = 'mean'
    if 'Close_to_Original_Ratio' in df_sold.columns: summary_cols['Close_to_Original_Ratio'] = 'mean'
    if dom_col: summary_cols[dom_col] = 'median'
    
    segment_summary = df_sold.groupby(county_c).agg(summary_cols).reset_index()
    print(segment_summary.head())

# 9. WEEK 7 OUTLIER DETECTION (IQR METHOD)
print("\n--- STAGE 9: OUTLIER DETECTION (IQR) ---")
df_sold['is_outlier'] = False
initial_rows = len(df_sold)
median_before = df_sold[price_col].median() if price_col else None

for col in [price_col, area_col, dom_col]:
    if col and col in df_sold.columns:
        Q1 = df_sold[col].quantile(0.25)
        Q3 = df_sold[col].quantile(0.75)
        IQR = Q3 - Q1
        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR
        
        # Flag if outside bounds (ignore NaN)
        outlier_mask = (df_sold[col].notna()) & ((df_sold[col] < lower_bound) | (df_sold[col] > upper_bound))
        df_sold.loc[outlier_mask, 'is_outlier'] = True

df_sold_clean = df_sold[~df_sold['is_outlier']].copy()
final_rows = len(df_sold_clean)
median_after = df_sold_clean[price_col].median() if price_col else None

print(f"Original Rows: {initial_rows} | Filtered Rows: {final_rows} | Outliers Removed: {initial_rows - final_rows}")
print(f"Median {price_col} Before: {median_before} | After: {median_after}")

# 10. EXPORT
output_flagged = os.path.join(current_folder, 'Master_Sold_Flagged.csv')
output_filtered = os.path.join(current_folder, 'Master_Sold_Filtered.csv')

df_sold.to_csv(output_flagged, index=False)
df_sold_clean.to_csv(output_filtered, index=False)
print(f"\n--- SUCCESS: Saved Flagged Dataset to {output_flagged} ---")
print(f"--- SUCCESS: Saved Clean Filtered Dataset to {output_filtered} ---")