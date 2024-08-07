import os
from glob import glob
from typing import List, Optional, Dict, Union
from tqdm import tqdm
import numpy as np
import pandas as pd
from scipy.signal import hilbert
from omegaconf import OmegaConf
from transformers import AutoTokenizer
from src.dataset.base import BaseDataset

from src.utils import read_table, parse_table_labels

LIST_LABELS = ["SEPARATION", "LOCATION", "ENTERTAINMENT", "MONEY", "NATURE", "QUANTITY",
               "POLITICS", "RELIGION", "HOUSE", "MOVE", "SPORT",
               "JUSTICE", "INDUSTRY", "LANGUAGE", "FOOD", "MODE",
               "DEVICE", "FAMILY", "MUSIC", "CRIME", "CATASTROPHE",
               "ARMY", "TIME", "SCHOOL", "CLEANNESS", "DEATH",
               "GLORY", "BODY", "PEOPLE", "MEDICAL", "MATERIAL",
               "GOVERN", "SCIENCE", "PHILOSOPHY", "FEELING"]


def _split_sent_data_into_words_data(start_id: int,
                                     sent_id: str,
                                     eeg_sig: np.array,
                                     labels_df: pd.DataFrame,
                                     filter_labels: Optional[List[str]] = None):
    word_data_list = []
    sentence = " ".join(labels_df["word"].values)
    for i, row in labels_df.iterrows():
        sample = {
            "id": start_id + i,  # Unique key to define the sample
            "sent_id": sent_id,
            "word": row["word"],
            "sentence": sentence,
            "raw_eeg_input_ids": eeg_sig[i],
            "pos": row["pos"],
            "prev_pos": row["prev_pos"],
            "next_pos": row["next_pos"],
            "freq": row["freq"],
            "prev_freq": row["prev_freq"],
            "next_freq": row["next_freq"],
            "len": row["len"],
            "prev_len": row["prev_len"],
            "next_len": row["next_len"],
        }
        # Apply Specific label filtering if needed
        if filter_labels is not None and sample["pos"] not in filter_labels:
            continue
        word_data_list.append(sample)

    return word_data_list


def _compute_eeg_power_signal(sent_eeg: np.array):
    """

    :param sent_eeg: "2D array of shape (N_WORDS X TIMESTEPS, Channels)
    :return:
    """
    return np.abs(hilbert(sent_eeg) * np.conjugate(hilbert(sent_eeg)))


def get_dataset_electrodes(rootpath: str, dataname: str) -> Union[pd.DataFrame, List[pd.DataFrame]]:
    """

    :param rootpath: Path to the datasets
    :param dataname: name of the dataset (also the name of the folder)
    :return:
    """
    channels = pd.read_csv(os.path.join(rootpath, dataname, "locs3d.csv"))
    return channels

def project_3d_coordinates_in_plan(coords: np.array,) -> np.array:
    COEF = 0.4
    max_z = np.max(coords[:, 2])
    print(max_z)
    coords[:, 0] /= (1 - COEF * ((max_z - coords[:, 2]) / max_z))
    coords[:, 1] /= (1 - COEF * ((max_z - coords[:, 2]) / max_z))
    return coords



class UBIRADataset(BaseDataset):

    def __init__(self, cfg, tokenizer=None):
        super().__init__(cfg, tokenizer)
        self.folders = cfg.list_folders
        self.eegs = []
        self.meta_data = []
        self._load_sentence_labels()
        self._load_channels()
        self._load_data(mode=cfg.mode, use_power=cfg.use_power)
        self._word_list = self._get_dataset_words()

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        return self.data[idx]

    def _load_sentence_labels(self):
        self.sentence_labels = pd.read_csv(os.path.join(self.datapath, "sentences_indices.csv"))

    def _load_channels(self):
        self.channels = pd.read_csv(os.path.join(self.datapath, "locs3d.csv"))

    def _get_sentence_wise_data(self, sent_id: str, mode: str = "average", power: bool = True) -> List:

        if mode == "average":
            list_paths = glob(os.path.join(self.datapath, "*", f"{sent_id}", "*.npy"))
            labels_path = list_paths[0].replace("eeg.npy", "labels.csv")

            labels_df = pd.read_csv(labels_path)
            labels_df = labels_df[["word", "pos", "filename", "freq", "len",
                                   "prev_pos", "next_pos", "prev_freq", "next_freq", "prev_len", "next_len"]]

            # Array of shape (n_sessions, n_words, n_channels, n_timesteps)
            eeg_sigs_arr = np.stack([np.load(path) for path in list_paths])
            n_words, channels, timesteps = eeg_sigs_arr[0].shape

            if not power:
                eeg_sig = np.mean(eeg_sigs_arr, axis=0)

            else:
                # we want to compute the power, so we reshape the signal
                eeg_sigs_arr = eeg_sigs_arr.transpose(0, 2, 1, 3)
                # Reshape the array to (n_sessions,  n_channels, n_words * n_timesteps)
                eeg_sigs_arr = eeg_sigs_arr.reshape(-1, channels, n_words * timesteps)
                # Apply the Power computation for each trial
                eeg_pows_arr = _compute_eeg_power_signal(eeg_sigs_arr)
                eeg_pows_arr = eeg_pows_arr.reshape(-1, channels, n_words, timesteps).transpose(0, 2, 1, 3)
                eeg_sig = np.mean(eeg_pows_arr, axis=0)
            return sent_id, eeg_sig, labels_df

        else:
            # We only consider a single session so mode must be in ["session_{i}"]

            path = glob(os.path.join(self.datapath, mode, f"{sent_id}", "*.npy"))
            assert len(path) == 1
            labels_path = path.replace("eeg.npy", "labels.csv")

            labels_df = pd.read_csv(labels_path)
            labels_df = labels_df[["word", "pos", "filename", "freq", "len",
                                   "prev_pos", "next_pos", "prev_freq", "next_freq", "prev_len", "next_len"]]

            # Array of shape (n_words, n_channels, n_timesteps)
            eeg_sigs_arr = np.load(path)
            n_words, channels, timesteps = eeg_sigs_arr.shape

            if not power:
                eeg_sig = eeg_sigs_arr

            else:
                # we want to compute the power, so we reshape the signal
                eeg_sigs_arr = eeg_sigs_arr.transpose(1, 0, 2)
                # Reshape the array to (n_channels, n_words * n_timesteps)
                eeg_sigs_arr = eeg_sigs_arr.reshape(-1, n_words * timesteps)
                # Apply the Power computation for each trial
                eeg_pows_arr = _compute_eeg_power_signal(eeg_sigs_arr)
                eeg_pows_arr = eeg_pows_arr.reshape(-1, n_words, timesteps).transpose(1, 0, 2)
                eeg_sig = eeg_pows_arr
            return sent_id, eeg_sig, labels_df

    def _load_data(self, mode: str = "word", use_power: bool = True):
        """

        :param mode: (str) whether we load the signals on the sentence of word level
        :return: the data from the specified folder (6 in this dataset)
        """
        self.data = []
        self.start_id = 0

        # Iterate on sentence level
        for sent_i, row in tqdm(self.sentence_labels.iterrows(), total=self.config.n_sentences):
            if sent_i > self.config.n_sentences:
                break
            sent_id_name = row["common_id"]

            _, eeg_sig, labels_df = self._get_sentence_wise_data(sent_id_name, mode="average", power=use_power)

            if mode == "word":
                word_data_list = _split_sent_data_into_words_data(self.start_id + sent_i,
                                                                  sent_id_name,
                                                                  eeg_sig,
                                                                  labels_df,
                                                                  filter_labels=self.filter_labels)
                self.data.extend(word_data_list)
                self.start_id += len(word_data_list) - 1

            elif mode == "sentence":
                continue

    def _get_dataset_words(self):
        list_words = []
        for i in range(len(self.data)):
            list_words.append(self.data[i]["word"])
        return list_words


class KilowordDataset(BaseDataset):

    def __init__(self, config, tokenizer=None):
        super().__init__(config, tokenizer)
        self.data = []
        self._load_channels()
        self._load_labels()
        self.words_list = self._get_dataset_words()
        self._load_data()

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        return self.data[idx]

    def _load_labels(self):
        self.labels = pd.read_csv(os.path.join(self.datapath, "words_and_pos.csv"))
        self.labels_df = parse_table_labels(self.labels, LIST_LABELS,  # Here self.filter_labels must be LIST_LABELS
                                            labelcolname="SEMANTIC_FIELD")

        # Filter the labels
        if self.filter_labels is not None:
            if self.filter_labels == "OBJECT":
                all_ids = self.labels[self.labels["MATERIAL"] == "YES"].index
            elif self.filter_labels == "ABSTRACT":
                all_ids = self.labels[self.labels["MATERIAL"] != "YES"].index
            else:
                all_ids = self.labels_df[self.labels_df[self.filter_labels] is True].index
        else:
            self.all_ids = len(self.labels)

    def _get_dataset_words(self):
        return self.labels["WORD"].values[self.all_ids]

    def _load_channels(self):
        self.channels = pd.read_csv(os.path.join(self.datapath, "locs3d.csv"))

    def _load_data(self):
        # THen retrieve all the filtered data
        eeg_data = read_table(os.path.join(self.datapath, "KWORD_ERP_LEXICAL_DECISION_DGMH2015.csv"))

        grouped_data = eeg_data.groupby("WORD")
        for i, word in enumerate(self.words_list):
            da = grouped_data.get_group(word)
            da = da[~da['ELECNAME'].isin(["REJ1", "REJ2", "REJ3"])]
            d = da.drop(columns=['WORD#', 'WORD', 'ELEC#', 'ELECNAME']).to_numpy()
            sample = {
                "raw_eeg_input_ids": d,
                "id": i,
                "pos": None,
                "len": len(word),
                "word": word
            }
            self.data.append(sample)


def get_dataset(config: Union[Dict, OmegaConf],
                tokenizer: AutoTokenizer,
                dataname: str):
    if dataname.lower() == "kiloword":
        return KilowordDataset(config, tokenizer)
    elif dataname.lower() == "ubira":
        return UBIRADataset(config, tokenizer)


if __name__ == '__main__':
    conf = OmegaConf.load("../configs/data/ubira.yaml")
    print(conf)
    config = conf
    dataset = UBIRADataset(config)
    print("Data Length", len(dataset), "\n")
    # print([dataset[i]["id"] for i in range(len(dataset))])
    # print(dataset[86])
