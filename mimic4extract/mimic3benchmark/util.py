from __future__ import absolute_import
from __future__ import print_function

import os
import pandas as pd
import numpy as np

def dataframe_from_csv(path, header=0, index_col=0):
    return pd.read_csv(path, header=header, index_col=index_col)


def _load_patient_flag_set(resource_filename):
    resource_path = os.path.join(os.path.dirname(__file__), 'resources', resource_filename)
    patients = set()
    with open(resource_path, 'r') as flag_file:
        for line in flag_file:
            x, y = line.strip().split(',')
            if int(y) == 1:
                patients.add(x)
    return patients


def get_test_patients():
    """ Subject IDs held out into the test partition. Resolved against `resources/testset_iv.csv`. """
    return _load_patient_flag_set('testset_iv.csv')


def get_val_patients():
    """ Subject IDs held out from the training partition to form the validation set.

    Same split is shared by all tasks, resolved against `resources/valset_iv.csv`.
    """
    return _load_patient_flag_set('valset_iv.csv')


def get_subject_split(subject_id, test_patients, val_patients):
    """ Resolve a single subject_id to "test", "validate" or "train", using the same fixed,
    subject-level split (test_patients/val_patients) every other MedMod-produced split derives from.
    Precedence matches split_train_and_test.py -> create_<task>.py: test, then validation, then train.
    """
    subject_id = str(subject_id)
    if subject_id in test_patients:
        return 'test'
    if subject_id in val_patients:
        return 'validate'
    return 'train'


def _patient_id_from_listfile_line(line):
    # stay column is either "{patient}/{episode}_timeseries.csv" or "{patient}_{episode}_timeseries.csv"
    stay = line.split(',', 1)[0]
    return stay.split('/')[0].split('_')[0]


def split_train_val_lines(lines, val_patients):
    """ Split formatted listfile row strings into (train_lines, val_lines) by patient id. """
    train_lines = [line for line in lines if _patient_id_from_listfile_line(line) not in val_patients]
    val_lines = [line for line in lines if _patient_id_from_listfile_line(line) in val_patients]
    assert len(train_lines) + len(val_lines) == len(lines)
    return train_lines, val_lines


def write_listfiles(output_path, header, train_lines, val_lines, test_lines):
    """ Write train_listfile.csv, val_listfile.csv and test_listfile.csv directly under output_path. """
    for name, lines in (('train_listfile.csv', train_lines),
                        ('val_listfile.csv', val_lines),
                        ('test_listfile.csv', test_lines)):
        with open(os.path.join(output_path, name), 'w') as listfile:
            listfile.write(header)
            listfile.writelines(lines)


def count_class(values, class_label):
    return np.where(values==class_label)[0].shape[0]

def get_data_stats(data_root, dataset='mimic-iii'):


    train = pd.read_csv(f'{data_root}/train_listfile.csv').y_true.values
    val = pd.read_csv(f'{data_root}/val_listfile.csv').y_true.values
    test = pd.read_csv(f'{data_root}/test_listfile.csv').y_true.values
    total_0 = 0
    total_1 = 0
    total_0 = count_class(train, 0) + count_class(val, 0) + count_class(test, 0)
    total_1 = count_class(train, 1) + count_class(val, 1) + count_class(test, 1)
    print(f'{dataset}')
    print(f'overall 0s {total_0}  1s {total_1}')
    print(f'train  0s {count_class(train, 0)}  1s {count_class(train, 1)}')
    print(f'val  0s {count_class(val, 0)}  1s {count_class(val, 1)}')
    print(f'test  0s {count_class(test, 0)}  1s {count_class(test, 1)}')
