import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, confusion_matrix
import seaborn as sns
import matplotlib.pyplot as plt
import joblib

# 1. Load Dataset
df = pd.read_csv('agewell_data.csv')
print("✅ Dataset loaded successfully!\n")
print("Shape:", df.shape)
print("\nSample Data:\n", df.head())

# 2. Basic Stats
print("\nDescriptive Statistics:\n", df.describe())

# 3. Prepare Features and Target
X = df[['age', 'heart_rate', 'systolic_bp', 'cholesterol']]
y = df['risk']

# 4. Split Data
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, random_state=42, stratify=y
)

# 5. Train Model
model = LogisticRegression(max_iter=1000)
model.fit(X_train, y_train)
y_pred = model.predict(X_test)

# 6. Evaluate
acc = accuracy_score(y_test, y_pred)
cm = confusion_matrix(y_test, y_pred)
print(f"\n✅ Model trained successfully with Accuracy: {acc*100:.2f}%")
print("\nConfusion Matrix:\n", cm)

# 7. Save Model
joblib.dump(model, 'agewell_model.joblib')
print("\n💾 Model saved as 'agewell_model.joblib'")

# 8. Visualization for Report
sns.boxplot(x='risk', y='systolic_bp', data=df)
plt.title('Blood Pressure Distribution by Risk Level')
plt.savefig('bp_vs_risk.png')
print("\n📊 Graph saved as 'bp_vs_risk.png'")
