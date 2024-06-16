import pandas as pd
import numpy as np
import mne
# import spacy
from kiloword.config import Config


def read_table(table_path: str):
    return pd.read_csv(table_path)


def save_table(df: pd.DataFrame, dest_path: str):
    return df.to_csv(dest_path, index=False)


def load_kiloword_metadata(datapath: str = Config().METADATA) -> pd.DataFrame:
    """

    :param datapath: Path to the dataset's metadata (a txt file)
    :return: table containing all metadata info
    """
    metadata = open(datapath, "r")
    columns = metadata.readline().strip().split()
    metadata_df = pd.DataFrame(columns=columns)
    for line in metadata.readlines():
        data = line.strip().split()
        metadata_df.loc[len(metadata_df)] = data
    return metadata_df


def load_data_from_fif(datapath: str = Config().DATA):
    raw = mne.read_epochs(datapath)
    list_features = []

    data = raw.copy().get_data()

    for i in range(data.shape[0]):
        list_features.append(data[i].reshape(-1))

    return np.array(list_features)


def split_into_chunks(input_list: list, chunk_size: int = 10):
    # Using list comprehension to split the list into chunks
    return [input_list[i:i + chunk_size] for i in range(0, len(input_list), chunk_size)]


def normalize_data(data: np.array, mode: str = "min_max"):
    if mode == "min_max":
        from sklearn.preprocessing import MinMaxScaler
        scaler = MinMaxScaler()
        return scaler.fit_transform(data)
    elif mode == "normal":
        from sklearn.preprocessing import StandardScaler
        scaler = StandardScaler()
        return scaler.fit_transform(data)
    return data


def parse_table_labels(table: pd.DataFrame,
                       list_labels: list,
                       labelcolname: str = "SEMANTIC_FIELD"):
    labels = table[[labelcolname]]
    if labelcolname == "SEMANTIC_FIELD":
        labels = labels.fillna("")
        tab_labels = pd.DataFrame({k: labels[labelcolname].apply(lambda x: k in x) for k in list_labels})
    else:
        tab_labels = pd.DataFrame({labelcolname: labels[labelcolname].apply(lambda x: x == "YES")})
    return tab_labels


def extract_correlations_and_periods(grouped_tab):
    pears_corr_values = []
    spear_corr_values = []
    sub_titles = []

    for i, (state, frame) in enumerate(grouped_tab):
        pears_corr_values.append(frame["pearson"].values)
        spear_corr_values.append(frame["spearman"].values)
        sub_titles.append(f"{int(float(state) * 1000 / 256)} to {int(frame['truncate_end'].values[0] * 1000 / 256)} ms")

    return pears_corr_values, spear_corr_values, sub_titles