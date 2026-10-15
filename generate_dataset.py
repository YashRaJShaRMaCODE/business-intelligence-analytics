import pandas as pd
import numpy as np

np.random.seed(42)
n = 600

ages = np.random.randint(55, 95, size=n)
heart_rate = np.random.normal(76, 11, size=n).astype(int)
bp = (np.random.normal(120, 15, size=n) + (ages - 60) * 0.5).astype(int)
chol = (np.random.normal(180, 25, size=n) + (ages - 65) * 0.4).astype(int)
risk = ((ages > 75) | (bp > 140) | (chol > 220) | (heart_rate > 100)).astype(int)

df = pd.DataFrame({
    "patient_id": np.arange(1, n + 1),
    "age": ages,
    "heart_rate": heart_rate,
    "systolic_bp": bp,
    "cholesterol": chol,
    "risk": risk
})

df.to_csv("agewell_data.csv", index=False)
print("✅ 600-row dataset generated and saved as 'agewell_data.csv'")
