from pathlib import Path

import gdown


DRIVE_FOLDER_URL = (
    "https://drive.google.com/drive/folders/"
    "1gI_rJpsDzJ3HsOBO0Hb50B71vaJDkXY5?usp=sharing"
)

MANUALS_FOLDER = Path("data/manuals")


def create_manual_folder() -> None:
    """Create the local folder for downloaded OEM manuals."""
    MANUALS_FOLDER.mkdir(parents=True, exist_ok=True)


def download_manuals() -> str:
    """Download the Google Drive MANUALS folder."""
    create_manual_folder()

    gdown.download_folder(
        url=DRIVE_FOLDER_URL,
        output=str(MANUALS_FOLDER),
        quiet=False,
        use_cookies=False,
    )

    return str(MANUALS_FOLDER)
