import numpy as np
import argparse
import os

import pandas as pd

from kiloword.vis import plot_2d_topomap
from kiloword.config import Config as cfg
from kiloword.utils import read_table, extract_correlations_and_periods, split_into_chunks
from kiloword.evaluation import CorrelationsTable


def vis_parser():
    parser = argparse.ArgumentParser()
    parser.add_argument("--save_folder", type=str,
                        default="/home/viki/Downloads/kiloword_correlations",
                        help="folder where the experiments are saved")
    parser.add_argument("--dataset_path", type=str,
                        default="/home/viki/mne_data/MNE-kiloword-data",
                        help="Path to where all the info of the dataset is stored")
    parser.add_argument("--tab_attrs", type=list,
                        default=['Channel', 'distance', 'truncate_start', 'truncate_end', 'pearson', 'spearman'],
                        nargs="+",
                        help="keys to figure in the saved documents")
    parser.add_argument("--tab_name", type=str,
                        default="bert_BODY_correlations.csv",
                        help="Name of the document where the experiments are saved")
    parser.add_argument("-d", "--distance", type=str,
                        default="l2",
                        choices=["cosine", "l2", "levenshtein-l2", "levenshtein-cosine"],
                        help="distance between EEG representations")
    return parser.parse_args()


def main(args):
    # Load the electrodes names
    eeg_data = read_table(cfg.DATA)
    list_electrodes = pd.unique(eeg_data["ELECNAME"])[3:]
    # Load the electrodes coordinates
    electrodes_pos = np.load(os.path.join(cfg.MNE_PATH, "locs3d.npy"))[:, :2]

    # Plot correlations topographies
    label_name = os.path.basename(args.tab_name).split("_")[-2]
    args.save_folder = os.path.join(args.save_folder, label_name)

    if not os.path.exists(os.path.join(args.save_folder, label_name)):
        os.mkdir(os.path.join(args.save_folder, label_name))

    corr_save_folder = os.path.join(args.save_folder, "csv")

    # Load Experiment Results table
    corr = CorrelationsTable(name=args.tab_name,
                             table_folder=corr_save_folder,
                             table_columns=args.tab_attrs,
                             eval=True)

    # Re-order the table by time-wise
    results_grouped_table = corr.extract_sub_table(attribute="distance",
                                                   value=args.distance,
                                                   groupby_key="truncate_start")

    # Extract the correlations
    pears_corr_values, spear_corr_values, sub_titles = extract_correlations_and_periods(results_grouped_table)
    # Reshape the plots
    pears_corr_values = split_into_chunks(pears_corr_values, 8)
    spear_corr_values = split_into_chunks(spear_corr_values, 8)
    sub_titles = split_into_chunks(sub_titles, 8)

    # Plot correlations topographies
    label_name = os.path.basename(corr.table_path).split("_")[-2]
    topo_name = os.path.basename(corr.table_path).replace("csv", "png")
    if args.distance != "l2":
        topo_name = topo_name.replace(".png", f"_{args.distance}.png")
    if not os.path.exists(os.path.join(args.save_folder, "image")):
        os.mkdir(os.path.join(args.save_folder,  "image"))
    if not os.path.exists(os.path.join(args.save_folder, "image", "pearson")):
        os.mkdir(os.path.join(args.save_folder,  "image", "pearson"))
    if not os.path.exists(os.path.join(args.save_folder, "image", "spearman")):
        os.mkdir(os.path.join(args.save_folder,  "image", "spearman"))
    pears_dest_file_path = os.path.join(args.save_folder,  "image", "pearson", f"pearson_{topo_name}")
    spear_dest_file_path = os.path.join(args.save_folder,  "image", "spearman", f"spearman_{topo_name}")


    n_rows, n_cols = len(pears_corr_values), len(pears_corr_values[0])

    print(n_rows, n_cols, len(pears_corr_values[0][0]))

    plot_2d_topomap(electrodes_pos, pears_corr_values, grid_res=100,
                    rows=n_rows, size=4, cols=n_cols, edgecolor="navy",
                    subfig_name=sub_titles,
                    coords_name=list_electrodes, dpi=200,
                    savepath=pears_dest_file_path)

    plot_2d_topomap(electrodes_pos, spear_corr_values, grid_res=100,
                    rows=n_rows, size=4, cols=n_cols, edgecolor="navy",
                    subfig_name=sub_titles,
                    coords_name=list_electrodes, dpi=200,
                    savepath=spear_dest_file_path)

    print("Done !!!")


if __name__ == '__main__':
    args = vis_parser()
    main(args)
