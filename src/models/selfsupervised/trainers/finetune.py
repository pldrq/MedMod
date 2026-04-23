# Import libraries
import argparse
import os

# Import custom functions
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytorch_lightning as pl

# Import Pytorch
import torch
from pytorch_lightning import loggers as pl_loggers

sys.path.append(".")
import warnings

import src.parser as par
from src.data.preprocessing import ehr_funcs
from src.data.utils import get_cxr_datasets, get_datasets, load_cxr_ehr
from src.models.selfsupervised.models.finetune import test, train

warnings.filterwarnings("ignore")

# seeds = 1002, 2918, 5793, 7261, 84305
seed = 84305
print("Seed", seed)
torch.manual_seed(seed)
np.random.seed(seed)


gpu_num = os.environ["CUDA_VISIBLE_DEVICES"]


def initiate_logger(tags):
    logger = pl_loggers.NeptuneLogger(
        project="shaza-workspace/mml-ssl",
        api_key="eyJhcGlfYWRkcmVzcyI6Imh0dHBzOi8vYXBwLm5lcHR1bmUuYWkiLCJhcGlfdXJsIjoiaHR0cHM6Ly9hcHAubmVwdHVuZS5haSIsImFwaV9rZXkiOiI4NDU3ZDlmMi01OGEyLTQzMTAtODJmYS01Mjc5N2U4ZjgyMTAifQ==",
        tags=tags,
        log_model_checkpoints=False,
    )
    return logger


if __name__ == "__main__":

    parser = par.initiate_parsing()
    args = parser.parse_args()

    # Set cuda device
    if args.device == "0":
        device = "cuda:0" if torch.cuda.is_available() else "cpu"
    elif args.device == "1":
        device = "cuda:1" if torch.cuda.is_available() else "cpu"
    elif args.device == "2":
        device = "cuda:2" if torch.cuda.is_available() else "cpu"
    elif args.device == "3":
        device = "cuda:3" if torch.cuda.is_available() else "cpu"
    elif args.device == "4":
        device = "cuda:4" if torch.cuda.is_available() else "cpu"
    elif args.device == "5":
        device = "cuda:5" if torch.cuda.is_available() else "cpu"
    elif args.device == "6":
        device = "cuda:6" if torch.cuda.is_available() else "cpu"
    elif args.device == "7":
        device = "cuda:7" if torch.cuda.is_available() else "cpu"
    elif args.device == "8":
        device = "cuda:8" if torch.cuda.is_available() else "cpu"
    else:
        device = "None"
    print(f"Using {device} device...")

    job_number = args.job_number
    path = Path(args.save_dir)
    path.mkdir(parents=True, exist_ok=True)

    # Load datasets and initiate dataloaders
    print("Loading datasets...")
    discretizer, normalizer = ehr_funcs(args)
    ehr_train_ds, ehr_val_ds, ehr_test_ds = get_datasets(discretizer, normalizer, args)
    cxr_train_ds, cxr_val_ds, cxr_test_ds = get_cxr_datasets(args)
    train_dl, val_dl, test_dl = load_cxr_ehr(
        args,
        ehr_train_ds,
        ehr_val_ds,
        cxr_train_ds,
        cxr_val_ds,
        ehr_test_ds,
        cxr_test_ds,
    )
    print("Length of training dataset: ", len(train_dl.dataset))
    print("Length of validation dataset:", len(val_dl.dataset))
    print("Length of test dataset: ", len(test_dl.dataset))

    # Store arguments after loading datasets
    os.makedirs(os.path.dirname(f"{args.save_dir}/args/args_{job_number}.txt"), exist_ok=True)
    with open(f"{args.save_dir}/args/args_{job_number}.txt", "w") as results_file:
        print("Storing arguments...")
        for arg in vars(args):
            print(f"  {arg:<40}: {getattr(args, arg)}")
            results_file.write(f"  {arg:<40}: {getattr(args, arg)}\n")

    # Initiate logger
    neptune_logger = initiate_logger([args.tag, args.job_number])
    neptune_logger.experiment["args"] = vars(args)

    # Load the model, weights (if any), and freeze layers (if any)
    print("Loading model...")
    model = LinearEval(args, train_dl)

    if args.mode == "train":
        print("==> training")
        train(
            model,
            args,
            train_dl,
            val_dl,
            logger=neptune_logger,
            load_state_prefix=args.load_state_simclr,
        )
        test(model, args, test_dl, logger=neptune_logger)

    elif args.mode == "eval":
        if args.eval_set == "val":
            print("==> evaluating on the val set")
            test_dl = val_dl
        elif args.eval_set == "train":
            print("==> evaluating on the train set")
            test_dl = train_dl
        else:
            print("==> evaluating on the test set")
        test(model, args, test_dl, logger=neptune_logger)

    else:
        raise ValueError("Incorrect value for args.mode")
