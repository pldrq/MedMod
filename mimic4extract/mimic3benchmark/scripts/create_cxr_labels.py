from __future__ import absolute_import
from __future__ import print_function

import os
import argparse
import pandas as pd

# Non-label identifier columns in mimic-cxr-2.0.0-chexpert.csv. Everything else in that file is a
# CheXpert finding column -- the class list is discovered from the file itself, not hardcoded here,
# so this script is the single source of truth for msc_climber's R_CLASSES (which reads it back via
# load_r_classes(cxr_data_root) instead of keeping its own copy).
ID_COLUMNS = ['subject_id', 'study_id']


def main():
    parser = argparse.ArgumentParser(
        description="Attach CheXpert labels to every CXR study locally: LEFT-joins "
                    "mimic-cxr-2.0.0-metadata.csv with mimic-cxr-2.0.0-chexpert.csv on study_id, covering "
                    "every study regardless of whether it's paired with an ICU stay (see "
                    "create_cxr_ehr_pair.py for that, separate concern). Studies without a chexpert entry "
                    "are kept with all label columns left null, so the row/dicom_id set is unchanged from "
                    "the raw metadata file. Equivalent to what msc_climber's load_cxr_metadata_with_labels() "
                    "computes at runtime on every DataModule.setup() call, done once here instead. Also "
                    "writes cxr_data_root/r_classes.txt, the CheXpert class list discovered from "
                    "chexpert.csv's own columns -- the single source msc_climber reads instead of "
                    "hardcoding its own copy.")
    parser.add_argument('cxr_data_root', type=str,
                        help="Path containing mimic-cxr-2.0.0-metadata.csv and mimic-cxr-2.0.0-chexpert.csv.")
    parser.add_argument('output_csv', type=str,
                        help="Where to write the result (e.g. "
                             "cxr_data_root/mimic-cxr-2.0.0-metadata-with-chexpert.csv).")
    args = parser.parse_args()

    metadata = pd.read_csv(os.path.join(args.cxr_data_root, 'mimic-cxr-2.0.0-metadata.csv'))
    labels = pd.read_csv(os.path.join(args.cxr_data_root, 'mimic-cxr-2.0.0-chexpert.csv'))

    available_classes = [c for c in labels.columns if c not in ID_COLUMNS]
    labels = labels.copy()
    labels[available_classes] = labels[available_classes].fillna(0).replace(-1.0, 0.0)

    merged = metadata.merge(labels[available_classes + ['study_id']], how='left', on='study_id')

    output_dir = os.path.dirname(args.output_csv)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    merged.to_csv(args.output_csv, index=False)

    r_classes_path = os.path.join(args.cxr_data_root, 'r_classes.txt')
    with open(r_classes_path, 'w') as f:
        f.write('\n'.join(available_classes) + '\n')

    matched = merged[available_classes[0]].notna().sum() if available_classes else 0
    print("Attached CheXpert labels to {}/{} CXR studies -> {}".format(matched, len(merged), args.output_csv))
    print("Wrote {} CheXpert class names -> {}".format(len(available_classes), r_classes_path))


if __name__ == '__main__':
    main()
