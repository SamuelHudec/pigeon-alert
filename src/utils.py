import os
import shutil


def create_and_clean_folder(folder_path):
    if os.path.exists(folder_path):
        shutil.rmtree(folder_path)
        os.makedirs(folder_path, exist_ok=True)
        print(f"Cleaned and recreated folder: {folder_path}")
    else:
        os.makedirs(folder_path, exist_ok=True)
        print(f"Folder '{folder_path}' created.")
