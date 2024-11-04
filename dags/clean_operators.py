import os


def clean(file_path_or_dir):
    """Deletes File on Path or every File within the underlying Directory Structure
       !This is a sharp sword, use it carefully!
    """
    if os.path.isdir(file_path_or_dir):
        entries = [os.path.join(file_path_or_dir, entry) for entry in os.listdir(file_path_or_dir)]
        for entry in entries:
            clean(entry)
    else:
        os.remove(file_path_or_dir)
