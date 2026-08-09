from __future__ import absolute_import
from __future__ import print_function

import os
import argparse
import pandas as pd
import random
random.seed(49297)
from tqdm import tqdm

from mimic3benchmark.util import get_val_patients, split_train_val_lines, write_listfiles

LISTFILE_HEADER = 'stay,lower,upper,period_length,stay_id,y_true\n'


def process_partition(args, partition, eps=1e-6, n_hours=48):
    xy_pairs = []
    patients = list(filter(str.isdigit, os.listdir(os.path.join(args.root_path, partition))))
    for patient in tqdm(patients, desc='Iterating over patients in {}'.format(partition)):
        patient_folder = os.path.join(args.root_path, partition, patient)
        patient_ts_files = list(filter(lambda x: x.find("timeseries") != -1, os.listdir(patient_folder)))

        for ts_filename in patient_ts_files:
            with open(os.path.join(patient_folder, ts_filename)) as tsfile:
                lb_filename = ts_filename.replace("_timeseries", "")
                label_df = pd.read_csv(os.path.join(patient_folder, lb_filename))

                # empty label file
                if label_df.shape[0] == 0:
                    continue
                icustay = label_df['Icustay'].iloc[0]
                
                mortality = int(label_df.iloc[0]["Mortality"])
                los = 24.0 * label_df.iloc[0]['Length of Stay']  # in hours
                if pd.isnull(los):
                    print("\n\t(length of stay is missing)", patient, ts_filename)
                    continue

                if los < n_hours - eps:
                    continue

                ts_lines = tsfile.readlines()
                header = ts_lines[0]
                ts_lines = ts_lines[1:]
                event_times = [float(line.split(',')[0]) for line in ts_lines]

                ts_lines = [line for (line, t) in zip(ts_lines, event_times)
                            if -eps < t < n_hours + eps]

                # no measurements in ICU
                if len(ts_lines) == 0:
                    print("\n\t(no events in ICU) ", patient, ts_filename)
                    continue

                relative_path = os.path.join(patient, ts_filename)
                xy_pairs.append((relative_path, 0.0, float(n_hours), float(n_hours), icustay, mortality))

    print("Number of created samples:", len(xy_pairs))
    if partition == "train":
        random.shuffle(xy_pairs)
    if partition == "test":
        xy_pairs = sorted(xy_pairs)

    return ['{},{:.6f},{:.6f},{:.6f},{},{:d}\n'.format(x, lower, upper, period_length, icustay, y)
            for (x, lower, upper, period_length, icustay, y) in xy_pairs]


def main():
    parser = argparse.ArgumentParser(description="Create data for in-hospital mortality prediction task.")
    parser.add_argument('root_path', type=str, help="Path to root folder containing train and test sets.")
    parser.add_argument('output_path', type=str, help="Directory where the created data should be stored.")
    args, _ = parser.parse_known_args()

    if not os.path.exists(args.output_path):
        os.makedirs(args.output_path)

    test_lines = process_partition(args, "test")
    trainval_lines = process_partition(args, "train")

    train_lines, val_lines = split_train_val_lines(trainval_lines, get_val_patients())
    write_listfiles(args.output_path, LISTFILE_HEADER, train_lines, val_lines, test_lines)


if __name__ == '__main__':
    main()
