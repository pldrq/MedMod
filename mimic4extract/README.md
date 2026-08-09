MIMIC-IV Data Extraction
=========================

Here we modified the [codes](https://github.com/YerevaNN/mimic3-benchmarks/) for the publicly available Medical Information Mart for Intensive Care (MIMIC-IV) database ([paper](http://www.nature.com/articles/sdata201635), [website](http://mimic.physionet.org)). 

## Structure

       cd mimic4extract 
The `mimic3benchmark/scripts` directory contains scripts for creating the benchmark datasets.
The reading tools are in `mimic3benchmark/readers.py`.
All evaluation scripts are stored in the `mimic3benchmark/evaluation` directory.
The `mimic3models` directory contains the baselines models along with some helper tools.
Those tools include discretizers, normalizers and functions for computing metrics.


## Requirements

We do not provide the MIMIC-IV data itself. You must acquire the data yourself from https://mimic.physionet.org/. Specifically, download the CSVs. Otherwise, generally we make liberal use of the following packages:


## Building a benchmark data

    
2. The following command takes MIMIC-IV CSVs, generates one directory per `SUBJECT_ID` and writes ICU stay information to `data/{SUBJECT_ID}/stays.csv`, diagnoses to `data/{SUBJECT_ID}/diagnoses.csv`, and events to `data/{SUBJECT_ID}/events.csv`. This step might take around an hour.

       python -m mimic3benchmark.scripts.extract_subjects_iv {PATH TO MIMIC-IV CSVs} data/root/

3. The following command attempts to fix some issues (ICU stay ID is missing) and removes the events that have missing information. About 80% of events remain after removing all suspicious rows (more information can be found in [`mimic3benchmark/scripts/more_on_validating_events.md`](mimic3benchmark/scripts/more_on_validating_events.md)).

       python -m mimic3benchmark.scripts.validate_events data/root/

4. The next command breaks up per-subject data into separate episodes (pertaining to ICU stays). Time series of events are stored in ```{SUBJECT_ID}/episode{#}_timeseries.csv``` (where # counts distinct episodes) while episode-level information (patient age, gender, ethnicity, height, weight) and outcomes (mortality, length of stay, diagnoses) are stores in ```{SUBJECT_ID}/episode{#}.csv```. This script requires two files, one that maps event ITEMIDs to clinical variables and another that defines valid ranges for clinical variables (for detecting outliers, etc.). **Outlier detection is disabled in the current version**.

       python -m mimic3benchmark.scripts.extract_episodes_from_subjects data/root/

5. The next command splits the whole dataset into training and testing sets. Note that the train/test split is the same of all tasks. 

       python -m mimic3benchmark.scripts.split_train_and_test data/root/

6. (Optional, needed for the `paired`/radiology workflow) Pair ICU stays with CXR studies, entirely locally --
   joins your own `all_stays` table (from step 2) against `mimic-cxr-2.0.0-metadata.csv` (the same file
   msc_climber's dataloader already reads from `cxr_data_root`), filtering to AP-view images taken within a
   24h buffer of each stay's hospital admission (to catch ED X-rays taken shortly before ICU admission). Each
   row is also stamped with a `split` column (`train`/`validate`/`test`), resolved from the same fixed,
   subject-level split every other MedMod listfile uses (`resources/testset_iv.csv`, `resources/valset_iv.csv`)
   -- so a CXR can never land in a different split than its paired ICU stay. Write the output directly to
   `cxr_data_root`, since that's where msc_climber's dataloader expects to find it:

       python -m mimic3benchmark.scripts.create_cxr_ehr_pair data/ /path/to/cxr_data_root/ /path/to/cxr_data_root/mimic-cxr-ehr-split.csv

   No BigQuery project/billing needed -- this only requires `mimic-cxr-2.0.0-metadata.csv` locally, which is a
   small (~227k row) file, not the full MIMIC-CXR-JPG image set. It also doesn't depend on any task listfiles
   having been generated yet (unlike the old two-step BigQuery + listfile-lookup approach), so it can run any
   time after step 2.

   `mimic-cxr-ehr-split.csv` is read by msc_climber's `get_base_cxr_icustays()` instead of that function
   re-deriving the same subject/CXR-timestamp join from raw files on every `DataModule.setup()` call.

   Separately, if you're using CXR labels (any task other than a pure EHR-only baseline), attach CheXpert
   labels to every CXR study -- independent of ICU-stay pairing, since a study either has a chexpert.csv row
   or it doesn't:

       python -m mimic3benchmark.scripts.create_cxr_labels /path/to/cxr_data_root/ /path/to/cxr_data_root/mimic-cxr-2.0.0-metadata-with-chexpert.csv

   This is read by msc_climber's `load_cxr_metadata_with_labels()` instead of that function re-parsing
   `mimic-cxr-2.0.0-chexpert.csv` and re-joining on every call.

7. (Optional) If you only need stays that have a paired CXR study (e.g. `data_pairs=paired` in msc_climber), this
   command copies just those subjects/episodes into a new, smaller root, dropping any of a subject's other,
   unpaired ICU stays and (if the subject has no paired stay at all) the subject entirely. Pass `--drop_events` to
   also skip `events.csv` (raw, unbinned chart events), which is unused by any `create_<task>.py` script once
   episodes have already been extracted.

       python -m mimic3benchmark.scripts.filter_paired_stays data/root/ data/root_paired/ /path/to/cxr_data_root/mimic-cxr-ehr-split.csv

   If you run this step, use `data/root_paired/` as the `root_path` in step 8 instead of `data/root/`.

8. The following commands will generate task-specific datasets, which can later be used in models. These commands are independent, if you are going to work only on one benchmark task, you can run only the corresponding command. Each command also carves the training partition into train/validation using the same fixed patient split for every task (`mimic3benchmark/resources/valset_iv.csv`), so there is no separate train/validation split step to run afterwards.

       python -m mimic3benchmark.scripts.create_in_hospital_mortality data/root/ data/in-hospital-mortality/
       python -m mimic3benchmark.scripts.create_decompensation data/root/ data/decompensation/
       python -m mimic3benchmark.scripts.create_length_of_stay data/root/ data/length-of-stay/
       python -m mimic3benchmark.scripts.create_phenotyping data/root/ data/phenotyping/ --radiology_output_path data/radiology/

The `--radiology_output_path` flag on `create_phenotyping` also writes `data/radiology/`: the radiology task shares
its EHR-side stay windowing (full ICU stay) with phenotyping, so both are produced from the same pass over
`data/root/` rather than a separate script. Its listfiles carry a single placeholder label column — real radiology
labels are CheXpert labels resolved downstream (in msc_climber, from the CXR side) via a stay/study join, not from
this listfile. Omit the flag to only produce `data/phenotyping/`.

9. (Optional, needs step 6) If you already have the full MIMIC-CXR-JPG image set locally, you're done after step
   6 -- just point `cxr_data_root` at it.
   `mimic3benchmark/scripts/cxr_downloader.py` exists for the case where you *don't*: it downloads only the CXR
   jpgs listed in the pair CSV (i.e. only images actually paired with an ICU stay) from the public `mimic-cxr-jpg`
   GCS bucket, with optional resize/crop applied on the way down -- avoiding pulling the full ~500GB dataset when
   you only need the paired subset. It's configured via `mimic3benchmark/scripts/cxr_downloader_config.yaml`
   (input CSV, output directory, GCS bucket, worker count, resize/crop) rather than CLI flags:

       python -m mimic3benchmark.scripts.cxr_downloader

After the above commands are done, there will be a directory `data/{task}` for each created benchmark task, containing
`train_listfile.csv`, `val_listfile.csv` and `test_listfile.csv` directly (no intermediate `train`/`test`
sub-directories with a nested `listfile.csv`, except where the task itself needs to store truncated per-stay
timeseries, e.g. `create_readmission`/`create_multitask`, which still populate `train`/`test` sub-directories with
those copies).
Each row of a listfile has the following form: `icu_stay, period_length, label(s)`.
A row specifies a sample for which the input is the collection of ICU event of `icu_stay` that occurred in the first `period_length` hours of the stay and the target is/are `label(s)`.
In in-hospital mortality prediction task `period_length` is always 48 hours, so it is not listed in corresponding listfiles.

