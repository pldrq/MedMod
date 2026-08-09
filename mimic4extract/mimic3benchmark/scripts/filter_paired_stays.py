from __future__ import absolute_import
from __future__ import print_function

import os
import argparse
import shutil
import pandas as pd
from tqdm import tqdm

SUBJECT_LEVEL_FILES = ('stays.csv', 'diagnoses.csv', 'events.csv')


def load_paired_stay_ids(cxr_ehr_pair_csv):
    df = pd.read_csv(cxr_ehr_pair_csv, usecols=['stay_id'])
    stay_ids = set(df['stay_id'].dropna().astype(int).unique())
    if not stay_ids:
        raise ValueError(
            "No stay_id values found in {} -- refusing to prune to an empty set.".format(cxr_ehr_pair_csv))
    return stay_ids


def prune_partition(args, partition, paired_stay_ids):
    src_partition_dir = os.path.join(args.root_path, partition)
    dst_partition_dir = os.path.join(args.output_path, partition)
    os.makedirs(dst_partition_dir, exist_ok=True)

    subject_level_files = [f for f in SUBJECT_LEVEL_FILES if f != 'events.csv' or not args.drop_events]

    subjects = list(filter(str.isdigit, os.listdir(src_partition_dir)))
    kept_subjects = 0
    kept_episodes = 0
    total_episodes = 0

    for subject in tqdm(subjects, desc='Filtering subjects in {}'.format(partition)):
        src_subject_dir = os.path.join(src_partition_dir, subject)
        ts_files = list(filter(lambda x: x.find("timeseries") != -1, os.listdir(src_subject_dir)))

        kept_pairs = []
        for ts_filename in ts_files:
            lb_filename = ts_filename.replace("_timeseries", "")
            total_episodes += 1

            label_df = pd.read_csv(os.path.join(src_subject_dir, lb_filename))
            if label_df.shape[0] == 0:
                continue

            icustay = label_df['Icustay'].iloc[0]
            if pd.isnull(icustay) or int(icustay) not in paired_stay_ids:
                continue

            kept_pairs.append((lb_filename, ts_filename))

        if not kept_pairs:
            continue

        dst_subject_dir = os.path.join(dst_partition_dir, subject)
        os.makedirs(dst_subject_dir, exist_ok=True)
        kept_subjects += 1

        for shared_filename in subject_level_files:
            src_shared = os.path.join(src_subject_dir, shared_filename)
            if os.path.exists(src_shared):
                shutil.copy2(src_shared, os.path.join(dst_subject_dir, shared_filename))

        for lb_filename, ts_filename in kept_pairs:
            shutil.copy2(os.path.join(src_subject_dir, lb_filename), os.path.join(dst_subject_dir, lb_filename))
            shutil.copy2(os.path.join(src_subject_dir, ts_filename), os.path.join(dst_subject_dir, ts_filename))
            kept_episodes += 1

    print("[{}] kept {}/{} subjects, {}/{} episodes (stays with a paired CXR)".format(
        partition, kept_subjects, len(subjects), kept_episodes, total_episodes))


def main():
    parser = argparse.ArgumentParser(
        description="Copy only ICU stays that have a paired CXR study into a new, smaller root directory. "
                    "Run after split_train_and_test.py and before any create_<task>.py script -- point "
                    "create_<task>.py's root_path at the output of this script instead of the full root.")
    parser.add_argument('root_path', type=str,
                        help="Path to root folder containing train/ and test/ subject sub-directories "
                             "(output of split_train_and_test.py).")
    parser.add_argument('output_path', type=str,
                        help="Directory where the pruned root (train/, test/) should be written.")
    parser.add_argument('cxr_ehr_pair_csv', type=str,
                        help="Path to medmod_cxr_ehr_pair.csv (or equivalent), containing a stay_id column "
                             "listing every ICU stay paired with a CXR study.")
    parser.add_argument('--drop_events', action='store_true',
                        help="Also skip copying events.csv (raw, unbinned chart events). Unused by any "
                             "create_<task>.py script once episodes have already been extracted, so this is "
                             "safe to drop for extra space savings if you don't need it for provenance/debugging.")
    args = parser.parse_args()

    paired_stay_ids = load_paired_stay_ids(args.cxr_ehr_pair_csv)
    print("Loaded {} paired stay_ids from {}".format(len(paired_stay_ids), args.cxr_ehr_pair_csv))

    if not os.path.exists(args.output_path):
        os.makedirs(args.output_path)

    for partition in ("train", "test"):
        prune_partition(args, partition, paired_stay_ids)


if __name__ == '__main__':
    main()
