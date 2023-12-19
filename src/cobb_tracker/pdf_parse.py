import fitz
import sys
import pytesseract

from PIL import Image
from sqlite_utils import Database
from sqlite_utils import db
import io

from pathlib import Path
import os
from multiprocessing import Process
from multiprocessing import Semaphore

import re

from cobb_tracker.municipalities.file_ops import write_minutes_doc
from cobb_tracker.municipalities.file_ops import minutes_files
from cobb_tracker.cobb_config import cobb_config

def pdf_to_database(config: cobb_config):

    DATABASE_DIR=config.get_config("directories","database_dir")
    DB = Database(os.path.join(DATABASE_DIR,"minutes.db"))
    all_minutes_files = minutes_files(
        minutes_dir=config.get_config("directories","minutes_dir")
    )
    if not DB["pages"].exists():
        DB["pages"].create(
            {"body": str, "date": str, "page": int, "text": str},
            pk=("body", "date", "page"),
        )
        DB["pages"].enable_fts(["text"], create_triggers=True)
    semaphore = Semaphore(len(os.sched_getaffinity(0)))
    db_processes = [Process(target=write_to_database,args=(config, file, DB, semaphore,)) for file in all_minutes_files]
    for process in db_processes:
        process.start()
    for process in db_processes:
        process.join()

def write_to_database(config: cobb_config, minutes_file: str, DB: db.Database, semaphore: Semaphore):
    with semaphore:
        pytesseract.pytesseract.tesseract_cmd = r"/usr/bin/tesseract"
        # Must zoom in in order for tesseract to give accurate transcription
        ZOOM = 2
        MAT = fitz.Matrix(ZOOM, ZOOM)
        file = minutes_file
        doc = fitz.open(file)

        rel_doc_path=file.replace(config.get_config('directories','minutes_dir'),'')
        body = os.path.normpath(rel_doc_path).split(os.path.sep)[2]
        date = (os.path.split(Path(file))[1]).replace('-minutes.pdf','')

        print(f"Writing {rel_doc_path} contents to database")
        for page in doc:
            pix = page.get_pixmap(matrix=MAT)
            image_bytes = io.BytesIO(
                        pix.tobytes(output="jpeg", jpg_quality=98)
                    )
            page_text = pytesseract.image_to_string(Image.open(image_bytes))
            DB["pages"].insert(
                {
                    "body": body,
                    "date": date,
                    "page": page.number,
                    "text": page_text,

                },
                replace=True,
            )
