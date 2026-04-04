import pandas as pd
import os

# 1. Define where to search (Your Downloads folder)
root_path = r'C:\Users\samba\Downloads' 

sold_dfs = []
print("Scanning Downloads for Sold transactions...")

# 2. Search through all folders and subfolders
for root, dirs, files in os.walk(root_path):
    for file in files:
        # 3. STRICT FILTER: Only grab files matching the exact Sold naming convention
        if file.startswith('CRMLSSold') and file.endswith('.csv'):
            full_path = os.path.join(root, file)
            
            try:
                temp_df = pd.read_csv(full_path)
                sold_dfs.append(temp_df)
                print(f"Success - Loaded: {file}")
            except Exception as e:
                print(f"Error reading {file}: {e}")

# 4. Combine, Clean, and Export
if sold_dfs:
    # Merge them all together
    df_sold = pd.concat(sold_dfs, ignore_index=True)
    
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