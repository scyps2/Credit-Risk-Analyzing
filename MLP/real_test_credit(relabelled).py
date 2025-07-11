import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.preprocessing import OneHotEncoder
from sklearn.neural_network import MLPClassifier
from sklearn.model_selection import train_test_split

df_performance = pd.read_csv('2020Q1_standard_performance.csv').head(500000)
df_origination = pd.read_csv('2020Q1_standard_origination.csv').head(500000)

df_performance = df_performance[[
    "Loan Sequence Number", "Monthly Reporting Period", 
    "Current Loan Delinquency Status"
]]
df_origination = df_origination[[
    "Loan Sequence Number", "Credit Score"
]]
df = pd.merge(df_origination, df_performance, on="Loan Sequence Number", how="inner")
print(df.head(), df.shape)


def reclassify(df):
    df = df.dropna()
    df = df[df["Current Loan Delinquency Status"] != "RA"]

    # frequency summary for Current Loan Delinquency Status
    df['Current Loan Delinquency Status'] = df['Current Loan Delinquency Status'].astype(int)
    status_counts = df["Current Loan Delinquency Status"].value_counts().sort_index()
    total_count = len(df)
    cumulative_ratio = status_counts.cumsum() / total_count

    status_summary = pd.DataFrame({
        "Delinquency Status": status_counts.index,
        "Frequency": status_counts.values,
        "Cumulative Ratio": cumulative_ratio.values
    }).sort_values(by="Delinquency Status", ascending=True)

    print("Delinquency Status | Frequency | Cumulative Ratio")
    print("-" * 50)
    for _, row in status_summary.iterrows():
        print(f"{row['Delinquency Status']:<17} | {row['Frequency']:<9} | {row['Cumulative Ratio']:.4f}")

    # reclassify
    threshold = 0.995
    n = int(status_summary[status_summary["Cumulative Ratio"] <= threshold]["Delinquency Status"].max())
    # df["Processed Loan Delinquency Status"] = df["Current Loan Delinquency Status"].apply(
    #     lambda x: x if x <= n else f"{n}+"
    # )
    # df['Current Loan Delinquency Status'] = df['Processed Loan Delinquency Status'].astype(str)
    df["Current Loan Delinquency Status"] = df["Current Loan Delinquency Status"].apply(
        lambda x: x if x <= n else n+1
    )
    print(df["Current Loan Delinquency Status"].unique())

    # relabel credit score
    df["Credit Score"] = df["Credit Score"].apply(lambda x: 0 if x <= 700 else 1)
    
    return df

df = reclassify(df)

def preprocess(df):
    # creat states of next month
    df = df.sort_values(by=['Loan Sequence Number', "Monthly Reporting Period"])
    df['Next Loan Delinquency Status'] = df.groupby('Loan Sequence Number')['Current Loan Delinquency Status'].shift(-1)
    df = df.dropna()
    df = df[df["Next Loan Delinquency Status"] != "RA"]
    df = df.reset_index(drop=True)

    # standarization
    exclude_cols = ['Loan Sequence Number', 'Monthly Reporting Period', 
                    'Current Loan Delinquency Status', 'Next Loan Delinquency Status', 'Credit Score']
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    cols_to_standardize = [col for col in numeric_cols if col not in exclude_cols]
    for col in cols_to_standardize:
        mean = df[col].mean()
        std = df[col].std()
        df[col] = (df[col] - mean) / std
    
    return df

df = preprocess(df)
print(df.head(), df.shape)

# Encode y and y_next to one hot form
inputs = ["Current Loan Delinquency Status", 'Next Loan Delinquency Status']
def one_hot_encoder(df):
    encoder = OneHotEncoder(sparse_output=False)
    one_hot_encoded = encoder.fit_transform(df[inputs])
    df_one_hot = pd.DataFrame(one_hot_encoded, columns = encoder.get_feature_names_out(inputs))
    df = pd.concat([df, df_one_hot], axis=1)
    return df, encoder

df, encoder = one_hot_encoder(df)
encoded_columns = encoder.get_feature_names_out(inputs)

# split dataset according to loans
unique_loans = df["Loan Sequence Number"].unique()
train_loans, test_loans = train_test_split(unique_loans, test_size=0.3, random_state=42)
train_df = df[df["Loan Sequence Number"].isin(train_loans)]
test_df = df[df["Loan Sequence Number"].isin(test_loans)]

X_train = train_df[[col for col in encoded_columns if col.startswith('Current Loan Delinquency Status')] + 
                   ["Credit Score"]]
y_train = train_df[[col for col in encoded_columns if col.startswith('Next Loan Delinquency Status')]]

X_test = test_df[[col for col in encoded_columns if col.startswith('Current Loan Delinquency Status')] + 
                 ["Credit Score"]]
y_test = test_df[[col for col in encoded_columns if col.startswith('Next Loan Delinquency Status')]]

# separate dataset by credit 
train_low = train_df[train_df["Credit Score"] == 0]
X_train_low = train_low[[col for col in encoded_columns if col.startswith('Current Loan Delinquency Status')] + ["Credit Score"]]
y_train_low = train_low[[col for col in encoded_columns if col.startswith('Next Loan Delinquency Status')]]
                                                                          
test_low = test_df[test_df["Credit Score"] == 0]
X_test_low = test_low[[col for col in encoded_columns if col.startswith('Current Loan Delinquency Status')] + ["Credit Score"]]
y_test_low = test_low[[col for col in encoded_columns if col.startswith('Next Loan Delinquency Status')]]

train_high = train_df[train_df["Credit Score"] == 1]
X_train_high = train_high[[col for col in encoded_columns if col.startswith('Current Loan Delinquency Status')] + ["Credit Score"]]
y_train_high = train_high[[col for col in encoded_columns if col.startswith('Next Loan Delinquency Status')]]

test_high = test_df[test_df["Credit Score"] == 1]
X_test_high = test_high[[col for col in encoded_columns if col.startswith('Current Loan Delinquency Status')] + ["Credit Score"]]
y_test_high = test_high[[col for col in encoded_columns if col.startswith('Next Loan Delinquency Status')]]


# MLP Classifying
mlp = MLPClassifier(hidden_layer_sizes = (10, 10, 10), activation = 'relu', max_iter = 5000, random_state = 1,
                   learning_rate_init = 0.0001, learning_rate = 'adaptive')

mlp.fit(X_train, y_train)
y_pred_proba = mlp.predict_proba(X_test)

mlp.fit(X_train_low, y_train_low)
y_pred_proba_low = mlp.predict_proba(X_test_low)
np.savetxt("credit_low_predict.csv", y_pred_proba_low, delimiter=',')

mlp.fit(X_train_high, y_train_high)
y_pred_proba_high = mlp.predict_proba(X_test_high)
np.savetxt("credit_high_predict.csv", y_pred_proba_high, delimiter=',')

# generate transition matrix and visualization
def transition_matrix(current_state, y_pred_proba):
    num_classes = y_pred_proba.shape[1]
    transition_matrix = np.zeros((num_classes, num_classes))

    for row in range(len(current_state)): # iterate over rows
        from_state = current_state[row]
        transition_matrix[from_state] += y_pred_proba[row]

    row_sum = transition_matrix.sum(axis=1, keepdims=True)
    row_sum[row_sum == 0] = 1 # state not appear in test set
    transition_matrix = transition_matrix / row_sum
    
    return transition_matrix

def plot_transition_heatmap(transition_matrix):
    plt.figure(figsize=(8, 6))
    ax = sns.heatmap(
        transition_matrix, 
        fmt=".2f", cmap="Blues"
    )
    ax.xaxis.set_ticks_position('top')

    plt.xlabel("To State")
    plt.ylabel("From State")
    plt.title("Transition Matrix Heatmap")
    plt.tight_layout()
    plt.show()

current_state = np.argmax( # decode into integer columns(before one-hot)
    X_test[[col for col in encoded_columns if col.startswith('Current Loan Delinquency Status')]].values,
    axis=1
)
T = transition_matrix(current_state, y_pred_proba)
print("Transition Matrix:\n", T)
plot_transition_heatmap(T)

current_state_low = np.argmax(
    X_test_low[[col for col in encoded_columns if col.startswith('Current Loan Delinquency Status')]].values, 
    axis=1
)
T_low = transition_matrix(current_state_low, y_pred_proba_low)
print("Transition Matrix for credit 0:\n", T_low)
plot_transition_heatmap(T_low)

current_state_high = np.argmax(
    X_test_high[[col for col in encoded_columns if col.startswith('Current Loan Delinquency Status')]].values, 
    axis=1
)
T_high = transition_matrix(current_state_high, y_pred_proba_high)
print("Transition Matrix for credit 1:\n", T_high)
plot_transition_heatmap(T_high)

# Evaluation by mean probability
def mean_prob(y_pred_proba, y_test):
    mean_prob_class = []
    for i in range(y_pred_proba.shape[1]):
        rows_i = y_test[:, i] == 1 # select all rows whose true label is i (boolean)
        if np.sum(rows_i) > 0:
            mean_prob_i = np.mean(y_pred_proba[rows_i, i]) # y_pred_proba[rows_i, i]: only calculate rows of True
        else:
            mean_prob_i = np.nan
        print(f"Probability of truly predicting class {i} is {mean_prob_i}")
        mean_prob_class.append(mean_prob_i)

    mean_prob = np.nanmean(mean_prob_class)
    return mean_prob

print("\nOverall PTP")
average_probability = mean_prob(y_pred_proba, y_test.to_numpy())
print(f'average probability = {average_probability}')

print("\nPTP for credit 0")
average_probability_low = mean_prob(y_pred_proba_low, y_test_low.to_numpy())
print(f'average probability for credit 0 = {average_probability_low}')

print("\nPTP for credit 1")
average_probability_high = mean_prob(y_pred_proba_high, y_test_high.to_numpy())
print(f'average probability for credit 1 = {average_probability_high}')

# Evaluation by brier score
def brier(y_pred_proba, y_test):
    score_matrix = (y_pred_proba - y_test)**2
    brier_score_states = np.mean(score_matrix, axis = 0)
    for i, score in enumerate(brier_score_states):
        print(f"Brier score for state {i} is {score}")
    brier_score = np.sum(brier_score_states)
    return brier_score

def brier_weighted(y_pred_proba, y_test, distance_power = 1):
    score_matrix = (y_pred_proba - y_test)**2

    # decode one hot
    true_labels = np.argmax(y_test, axis=1)
    num_classes = y_pred_proba.shape[1]

    weighted_scores = []

    for i, true_label in enumerate(true_labels):
        # calculate weight list
        distances = np.abs(np.arange(num_classes) - true_label)
        weights = (distances + 1) ** distance_power

        weighted_score = weights * score_matrix[i] / np.sum(weights)
        weighted_scores.append(weighted_score)

    brier_score_states = np.mean(weighted_scores, axis = 0)
    for i, score in enumerate(brier_score_states):
        print(f"Brier score for state {i} is {score}")
    brier_score = np.sum(brier_score_states)

    return brier_score

print("\nOverall brier score")
brier_score = brier(y_pred_proba, y_test.to_numpy())
print('brier score = ', brier_score)
brier_score = brier_weighted(y_pred_proba, y_test.to_numpy())
print('adjusted brier score = ', brier_score)

