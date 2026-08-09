from __future__ import absolute_import
from __future__ import print_function

import os
import argparse
import pandas as pd
import yaml
import random
random.seed(49297)
from tqdm import tqdm

from mimic3benchmark.util import get_val_patients, split_train_val_lines, write_listfiles


def process_partition(args, definitions, code_to_group, id_to_group, group_to_id,
                      partition, eps=1e-6):
    xty_triples = []
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

                los = 24.0 * label_df.iloc[0]['Length of Stay']  # in hours
                if pd.isnull(los):
                    print("\n\t(length of stay is missing)", patient, ts_filename)
                    continue

                ts_lines = tsfile.readlines()
                header = ts_lines[0]
                ts_lines = ts_lines[1:]
                event_times = [float(line.split(',')[0]) for line in ts_lines]

                ts_lines = [line for (line, t) in zip(ts_lines, event_times)
                            if -eps < t < los + eps]

                # no measurements in ICU
                if len(ts_lines) == 0:
                    print("\n\t(no events in ICU) ", patient, ts_filename)
                    continue

                relative_path = os.path.join(patient, ts_filename)

                cur_labels = [0 for i in range(len(id_to_group))]

                icustay = label_df['Icustay'].iloc[0]
                diagnoses_df = pd.read_csv(os.path.join(patient_folder, "diagnoses.csv"),
                                           dtype={"icd_code": str})
                diagnoses_df = diagnoses_df[diagnoses_df.stay_id == icustay]
                for index, row in diagnoses_df.iterrows():
                    if row['USE_IN_BENCHMARK']:
                        code = row['icd_code']
                        if code in code_to_group:
                            group = code_to_group[code]
                            group_id = group_to_id[group]
                            cur_labels[group_id] = 1
                        else:
                            print(f'{code} code not found')    
                # import pdb; pdb.set_trace()
                cur_labels = [x for (i, x) in enumerate(cur_labels)
                              if definitions[id_to_group[i]]['use_in_benchmark']]

                xty_triples.append((relative_path, 0.0, los, los, icustay, cur_labels))


    print("Number of created samples:", len(xty_triples))
    if partition == "train":
        random.shuffle(xty_triples)
    if partition == "test":
        xty_triples = sorted(xty_triples)

    return xty_triples


def format_phenotyping_lines(xty_triples):
    """ Format stay windows with the real per-stay ICD phenotype label vector. """
    lines = []
    for (x, lower, upper, period_length, stay_id, y) in xty_triples:
        labels = ','.join(map(str, y))
        lines.append('{},{:.6f},{:.6f},{:.6f},{},{}\n'.format(x, lower, upper, period_length, stay_id, labels))
    return lines


def format_radiology_lines(xty_triples):
    """ Format the same stay windows with a placeholder label column.

    The radiology task shares its EHR-side stay windowing (full ICU stay) with phenotyping, but its
    real labels are CheXpert labels resolved downstream (msc_climber) from the CXR side via a
    stay/study join, not from this listfile. A single placeholder column is enough to keep the
    listfile schema valid (readers index into the label columns and don't accept an empty list).
    """
    return ['{},{:.6f},{:.6f},{:.6f},{},0\n'.format(x, lower, upper, period_length, stay_id)
            for (x, lower, upper, period_length, stay_id, y) in xty_triples]


def main():
    parser = argparse.ArgumentParser(description="Create data for phenotype classification task.")
    parser.add_argument('root_path', type=str, help="Path to root folder containing train and test sets.")
    parser.add_argument('output_path', type=str, help="Directory where the created data should be stored.")
    parser.add_argument('--phenotype_definitions', '-p', type=str,
                        default=os.path.join(os.path.dirname(__file__), '../resources/icd_9_10_definitions_2.yaml'),
                        help='YAML file with phenotype definitions.')
    parser.add_argument('--radiology_output_path', type=str, default=None,
                        help="If set, also write the same per-stay EHR windows (full ICU stay, placeholder "
                             "label column) to this directory for the radiology task. Real radiology labels "
                             "are resolved downstream from CheXpert data, not from this listfile.")
    args, _ = parser.parse_known_args()
    print(args.phenotype_definitions)

    with open(args.phenotype_definitions) as definitions_file:
        definitions = yaml.safe_load(definitions_file)

    code_to_group = {}

   
    for group in definitions:
        codes = definitions[group]['codes']
        for code in codes:
            if code not in code_to_group:
                code_to_group[code] = group
            else:
                print(f'code, {code}')
                assert code_to_group[code] == group

    # import pdb;pdb.set_trace()
    # ['Diabetes mellitus with complication', ]
    # 'ICD-10-CM CODE' 'Default CCSR CATEGORY DESCRIPTION IP'
    id_to_group = sorted(definitions.keys())
    group_to_id = dict((x, i) for (i, x) in enumerate(id_to_group))

    if not os.path.exists(args.output_path):
        os.makedirs(args.output_path)

    test_triples = process_partition(args, definitions, code_to_group, id_to_group, group_to_id, "test")
    trainval_triples = process_partition(args, definitions, code_to_group, id_to_group, group_to_id, "train")

    val_patients = get_val_patients()

    codes_in_benchmark = [x for x in id_to_group if definitions[x]['use_in_benchmark']]
    pheno_header = "stay,lower,upper,period_length,stay_id," + ",".join(codes_in_benchmark) + "\n"
    pheno_train_lines, pheno_val_lines = split_train_val_lines(
        format_phenotyping_lines(trainval_triples), val_patients)
    write_listfiles(args.output_path, pheno_header, pheno_train_lines, pheno_val_lines,
                    format_phenotyping_lines(test_triples))

    if args.radiology_output_path:
        if not os.path.exists(args.radiology_output_path):
            os.makedirs(args.radiology_output_path)

        radiology_header = "stay,lower,upper,period_length,stay_id,placeholder\n"
        radiology_train_lines, radiology_val_lines = split_train_val_lines(
            format_radiology_lines(trainval_triples), val_patients)
        write_listfiles(args.radiology_output_path, radiology_header, radiology_train_lines, radiology_val_lines,
                        format_radiology_lines(test_triples))


if __name__ == '__main__':
    main()
