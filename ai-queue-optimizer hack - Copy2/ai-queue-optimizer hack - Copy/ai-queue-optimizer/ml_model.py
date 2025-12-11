import numpy as np
import pickle
import os

MODEL_PATH = "instance/model.pkl"

# Ensure the directory exists
os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)

# Train a simple model if not exists
def train_model():
    from sklearn.ensemble import RandomForestRegressor

    # Fake training data (replace with real later)
    X = np.array([
        [2, 5, 1],   # people_in_queue, avg_service_time, peak_hour_flag
        [5, 7, 1],
        [10, 6, 1],
        [1, 4, 0],
        [3, 5, 0]
    ])
    y = np.array([10, 25, 40, 5, 12])  # predicted wait time (minutes)

    model = RandomForestRegressor()
    model.fit(X, y)

    # Save the trained model
    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model, f)

def load_model():
    if not os.path.exists(MODEL_PATH):
        train_model()

    with open(MODEL_PATH, "rb") as f:
        return pickle.load(f)

# Load the model once when the module is imported
model = load_model()

def predict_wait_time(people, avg_service, is_peak):
    features = np.array([[people, avg_service, is_peak]])
    return model.predict(features)[0]
