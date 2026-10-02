from pathlib import Path

import gdown


DRIVE_FOLDER_URL = (
    "https://drive.google.com/drive/folders/"
    "1gI_rJpsDzJ3HsOBO0Hb50B71vaJDkXY5?usp=sharing"
)

TEST_FOLDER = Path("data/drive_test")


def main() -> None:
    """Test access to the shared MANUALS Google Drive folder."""
    TEST_FOLDER.mkdir(parents=True, exist_ok=True)

    print("Testing Google Drive access...")
    print(DRIVE_FOLDER_URL)

    result = gdown.download_folder(
        url=DRIVE_FOLDER_URL,
        output=str(TEST_FOLDER),
        quiet=False,
        use_cookies=False,
        remaining_ok=True,
    )

    if result:
        print("\nGoogle Drive access: SUCCESS")

        files = [
            path for path in TEST_FOLDER.rglob("*")
            if path.is_file()
        ]

        print(f"Files downloaded during test: {len(files)}")

        for file_path in files[:10]:
            print(f"  {file_path}")

    else:
        print("\nGoogle Drive access: FAILED")


if __name__ == "__main__":
    main()
