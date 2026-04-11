import pandas as pd
import os

# 1. Define where to search
# Note: If you moved your files to avoid duplicates, update this path (e.g., to Downloads\Idxexchange)
root_path = r'C:\Users\samba\Downloads' 

sold_dfs = []
print("--- STARTING FILE INGESTION (SOLD TRANSACTIONS) ---")

# 2. Search through all folders and subfolders
for root, dirs, files in os.walk(root_path):
    for file in files:
        # 3. STRICT FILTER: Only grab files matching the exact Sold naming convention
        if file.startswith('CRMLSSold') and file.endswith('.csv'):
            full_path = os.path.join(root, file)
            
            try:
                # low_memory=False prevents the mixed data type warning
                temp_df = pd.read_csv(full_path, low_memory=False)
                sold_dfs.append(temp_df)
                
                # VALIDATION LAYER 1: Row count for each individual file
                print(f"Success - Loaded {file}: {len(temp_df)} rows")
            except Exception as e:
                print(f"Error reading {file}: {e}")

# 4. Combine, Validate, Clean, and Export
if sold_dfs:
    # Merge them all together
    df_sold = pd.concat(sold_dfs, ignore_index=True)
    
    # VALIDATION LAYER 2: Row count after concatenation
    print("\n" + "="*40)
    print("--- CONCATENATION COMPLETE ---")
    print(f"Total rows combined (Pre-Filter): {len(df_sold)}")
    print("="*40)

    # VALIDATION LAYER 3: Frequency table before filtering
    print("\n--- PROPERTY TYPES (BEFORE FILTER) ---")
    if 'PropertyType' in df_sold.columns:
        print(df_sold['PropertyType'].value_counts(dropna=False))
    else:
        print("WARNING: 'PropertyType' column not found!")

    # FILTER: Keep only 'Residential'
    if 'PropertyType' in df_sold.columns:
        df_sold = df_sold[df_sold['PropertyType'] == 'Residential']

    # VALIDATION LAYER 4: Row count after filtering
    print("\n" + "="*40)
    print("--- FILTERING COMPLETE ---")
    print(f"Total rows (Post-Residential Filter): {len(df_sold)}")
    print("="*40)

    # VALIDATION LAYER 5: Frequency table after filtering
    print("\n--- PROPERTY TYPES (AFTER FILTER) ---")
    if 'PropertyType' in df_sold.columns:
        print(df_sold['PropertyType'].value_counts(dropna=False))
    
    # --- CLEANING & FEATURES ---
    # Fix the Close Price column (remove $, commas, convert to float)
    if 'Close Price' in df_sold.columns:
        df_sold['Close Price'] = df_sold['Close Price'].replace(r'[\$,]', '', regex=True).astype(float)

    # Add Price per Square Foot
    if 'LivingArea' in df_sold.columns and 'Close Price' in df_sold.columns:
        df_sold['Price_SqFt'] = df_sold['Close Price'] / df_sold['LivingArea']

    # Export to the final CSV
    df_sold.to_csv('Master_Sold_Analysis.csv', index=False)
    print("\n--- COMPLETE: Master_Sold_Analysis.csv is ready for Tableau! ---")
else:
    print("\nNo Sold files were found in your Downloads.")