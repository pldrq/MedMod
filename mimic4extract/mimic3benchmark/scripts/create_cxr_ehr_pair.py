from __future__ import absolute_import
from __future__ import print_function

import os
import argparse
import pandas as pd

from mimic3benchmark.util import get_test_patients, get_val_patients, get_subject_split


def main():
    parser = argparse.ArgumentParser(
        description="Build medmod_cxr_ehr_pair.csv locally: pairs each ICU stay with the CXR studies taken "
                    "during that hospital admission (+/- a buffer, to catch ED X-rays taken shortly before "
                    "formal ICU admission), and stamps each row with the same fixed, subject-level "
                    "train/validate/test split every other MedMod-produced listfile uses (resources/"
                    "testset_iv.csv, resources/valset_iv.csv) -- so CXR images never land in a different "
                    "split than their paired ICU stay. Equivalent to running the three BigQuery queries in "
                    "mimic3benchmark/sql/ (create_MedMod_CXR_IDs.sql, create_MedMod_CXR_dicom_ids.sql, "
                    "create_MedMod_cxr_ehr_pair.sql) followed by create_mimic_cxr_ehr_split.py, but works "
                    "entirely from local files -- no BigQuery project/billing needed, and no dependency on "
                    "having already generated task listfiles. Only requires mimic-cxr-2.0.0-metadata.csv "
                    "locally, the same file msc_climber's own dataloader already reads from cxr_data_root.")
    parser.add_argument('ehr_data_root', type=str,
                        help="Path containing root/all_stays.csv (produced by extract_subjects_iv.py).")
    parser.add_argument('cxr_data_root', type=str,
                        help="Path containing mimic-cxr-2.0.0-metadata.csv.")
    parser.add_argument('output_csv', type=str,
                        help="Where to write the resulting pair CSV (e.g. data/processed/medmod_cxr_ehr_pair.csv).")
    parser.add_argument('--view_position', type=str, default='AP',
                        help="Restrict to this ViewPosition. Pass an empty string to keep all views.")
    parser.add_argument('--buffer_hours', type=float, default=24.0,
                        help="Hours of buffer added before admittime / after dischtime, to catch ED X-rays "
                             "taken shortly before formal hospital admission.")
    args = parser.parse_args()

    cxr_metadata = pd.read_csv(os.path.join(args.cxr_data_root, 'mimic-cxr-2.0.0-metadata.csv'))
    all_stays = pd.read_csv(os.path.join(args.ehr_data_root, 'root', 'all_stays.csv'))

    if args.view_position:
        cxr_metadata = cxr_metadata[cxr_metadata['ViewPosition'] == args.view_position]

    cxr_metadata = cxr_metadata.copy()
    cxr_metadata['StudyTime'] = cxr_metadata['StudyTime'].apply(lambda x: '{:06}'.format(int(float(x))))
    cxr_metadata['study_datetime'] = pd.to_datetime(
        cxr_metadata['StudyDate'].astype(str) + ' ' + cxr_metadata['StudyTime'].astype(str),
        format='%Y%m%d %H%M%S',
    )

    stay_columns = ['subject_id', 'hadm_id', 'stay_id', 'last_careunit', 'intime', 'outtime',
                    'admittime', 'dischtime']
    all_stays = all_stays[stay_columns].copy()
    all_stays['admittime'] = pd.to_datetime(all_stays['admittime'])
    all_stays['dischtime'] = pd.to_datetime(all_stays['dischtime'])

    merged = cxr_metadata[['subject_id', 'dicom_id', 'study_id', 'study_datetime', 'ViewPosition']].merge(
        all_stays, how='inner', on='subject_id')

    buffer = pd.Timedelta(hours=args.buffer_hours)
    paired = merged[
        (merged['study_datetime'] >= merged['admittime'] - buffer)
        & (merged['study_datetime'] <= merged['dischtime'] + buffer)
    ]

    output_columns = ['subject_id', 'dicom_id', 'study_id', 'study_datetime', 'ViewPosition', 'hadm_id',
                       'stay_id', 'last_careunit', 'intime', 'outtime', 'admittime', 'dischtime']
    paired = paired[output_columns].drop_duplicates()

    test_patients = get_test_patients()
    val_patients = get_val_patients()
    paired['split'] = paired['subject_id'].apply(
        lambda subject_id: get_subject_split(subject_id, test_patients, val_patients))

    output_dir = os.path.dirname(args.output_csv)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    paired.to_csv(args.output_csv, index=False)

    print("Paired {} CXR/stay rows across {} unique stay_ids -> {}".format(
        len(paired), paired['stay_id'].nunique(), args.output_csv))
    print(paired['split'].value_counts().to_string())


if __name__ == '__main__':
    main()
