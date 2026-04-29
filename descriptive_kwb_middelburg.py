import pandas as pd
import numpy as np

df_kwb2025 = pd.read_excel(r'C:\Users\20212599\OneDrive - TU Eindhoven\Documents\Studie\2025-2026\1BM130 Design of AI-driven business operation\Shared group folder\Data files\CBS\kwb2025.xlsx')


#Only check those from Middelburg (just a random city I chose) - it is with the (Z.) because I think there are multiple Middelburgs?
df_Middelburg = df_kwb2025[df_kwb2025["gm_naam"] == "Middelburg (Z.)"]
print(df_Middelburg.head())

#This part below does not work because the data for the income is missing
#g_ink_pi_Middelburg = np.mean(df_Middelburg["g_ink_pi"])
#print("The average income in Middelburg per resident is: ", g_ink_pi_Middelburg)