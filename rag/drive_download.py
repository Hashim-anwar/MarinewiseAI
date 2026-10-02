from pathlib import Path

import gdown


DRIVE_FOLDER_URL = (
    "https://drive.google.com/drive/folders/"
    "1gI_rJpsDzJ3HsOBO0Hb50B71vaJDkXY5?usp=sharing"
)

MANUALS_FOLDER = Path("data/manuals")


def create_manual_folder() -> None:
    """Create the local OEM manuals directory."""
    MANUALS_FOLDER.mkdir(
        parents=True,
        exist_ok=True,
    )


def download_manuals() -> str:
    """Download the shared MANUALS folder."""
    create_manual_folder()

    print("=" * 60)
    print("MARINEWISE AI - GOOGLE DRIVE DOWNLOAD")
    print("=" * 60)

    print("\nSource:")
    print(DRIVE_FOLDER_URL)

    print("\nDestination:")
    print(MANUALS_FOLDER)

    gdown.download_folder(
        url=DRIVE_FOLDER_URL,
        output=str(MANUALS_FOLDER),
        quiet=False,
        use_cookies=False,
        remaining_ok=True,
    )

    return str(MANUALS_FOLDER)
