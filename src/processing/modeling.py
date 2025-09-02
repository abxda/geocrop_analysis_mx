import pandas as pd
import joblib
import os
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report
from tpot import TPOTClassifier
from datetime import datetime

def _log(message):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}")

def _balance_classes(data, config):
    if not config.get('balance_classes', False):
        return data

    max_samples = config.get('max_samples_per_class', 500)
    col_clase = 'label'
    _log(f"Balancing classes to a max of {max_samples} samples per class.")

    conteo_clases = data[col_clase].value_counts()
    clases_grandes = conteo_clases[conteo_clases > max_samples].index
    
    frames = []
    for clase in clases_grandes:
        clase_df = data[data[col_clase] == clase]
        clase_df_reducido = clase_df.sample(n=max_samples, random_state=config.get('random_state', 42))
        frames.append(clase_df_reducido)
    
    otras_clases_df = data[~data[col_clase].isin(clases_grandes)]
    data_balanceado = pd.concat([otras_clases_df] + frames)
    _log(f"Data balanced. New size: {len(data_balanceado)} rows.")
    return data_balanceado

def train_model(config, output_dir):
    _log("--- Executing PHASE: Train Model ---")
    
    # --- Define Paths ---
    features_path = os.path.join(output_dir, config['output_names']['features_csv'])
    label_map_path = os.path.join(output_dir, 'labeling', 'segment_label_map.csv')
    modeling_dir = os.path.join(output_dir, 'modeling')
    os.makedirs(modeling_dir, exist_ok=True)
    
    model_path = os.path.join(modeling_dir, config['modeling_params']['output_model_name'])
    report_path = os.path.join(modeling_dir, 'classification_report.txt')

    if os.path.exists(model_path):
        _log(f"Model already exists at {model_path}. Skipping training.")
        return

    # --- Load Data ---
    _log(f"Loading features from {features_path}")
    features_df = pd.read_csv(features_path)
    
    _log(f"Loading label map from {label_map_path}")
    label_map_df = pd.read_csv(label_map_path)

    # --- Prepare Data for Training ---
    _log("Preparing data for training...")
    # Merge features with labels, handling potential duplicate columns
    training_data = pd.merge(features_df, label_map_df, on='segment_id', suffixes=('_features', '_labels'))

    # If merge created duplicate columns, clean them up, prioritizing the label map
    if 'label_labels' in training_data.columns:
        training_data['label'] = training_data['label_labels']
        training_data['class_id'] = training_data['class_id_labels']
        training_data.drop(columns=['label_labels', 'class_id_labels', 'label_features', 'class_id_features'], inplace=True)

    # Balance classes
    balanced_data = _balance_classes(training_data, config['modeling_params'])
    
    # Define features (X) and target (y)
    # Drop non-feature columns
    drop_cols = ['segment_id', 'label', 'class_id']
    if 'klass' in balanced_data.columns:
        drop_cols.append('klass')
        
    X = balanced_data.drop(columns=drop_cols)
    y = balanced_data['class_id']

    # Split data
    test_size = config['modeling_params'].get('test_size', 0.3)
    random_state = config['modeling_params'].get('random_state', 42)
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=test_size, random_state=random_state, stratify=y)

    _log(f"Training data shape: {X_train.shape}")
    _log(f"Testing data shape: {X_test.shape}")

    # --- Train TPOT Model ---
    tpot_config = {
        'generations': config['modeling_params'].get('tpot_generations', 5),
        'population_size': config['modeling_params'].get('tpot_population_size', 20),
        'verbosity': 2,
        'random_state': random_state,
        'n_jobs': -1,
        'config_dict': 'TPOT light'
    }
    _log(f"Initializing TPOT with config: {tpot_config}")
    tpot = TPOTClassifier(**tpot_config)
    
    _log("Starting TPOT training...")
    tpot.fit(X_train, y_train)
    
    _log("TPOT training complete. Evaluating model...")

    # --- Evaluate and Save Report ---
    predictions = tpot.predict(X_test)
    report = classification_report(y_test, predictions)
    
    _log("Classification Report:")
    print(report)
    
    with open(report_path, 'w') as f:
        f.write(report)
    _log(f"Classification report saved to {report_path}")

    # --- Save Model ---
    _log(f"Saving trained model to {model_path}")
    joblib.dump(tpot.fitted_pipeline_, model_path)
    
    _log("--- Train Model phase complete ---")