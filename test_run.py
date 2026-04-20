from src.data.load_data import load_all_data

print("Loading data...")

data = load_all_data()

for name, df in data.items():
    print(name, df.shape)