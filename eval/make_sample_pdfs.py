"""Create the two sample notifications used by the evaluation set.

Run inside the app container (PyMuPDF is installed there):
    docker compose exec app python eval/make_sample_pdfs.py
"""

from pathlib import Path

import fitz

OUTPUT_DIR = Path("data/samples")

DOCUMENTS = {
    "notif_12_2023.pdf": """Government of India
Ministry of Finance
Notification No. 12/2023
New Delhi, 1 April 2023
Subject: GST rates on packaged food items

The GST rate on packaged food items is 5 percent.
Returns shall be filed monthly by the 20th day of the following month.
Late filing attracts a penalty of Rs 100 per day.
This notification comes into force on 1 April 2023.""",
    "notif_25_2024.pdf": """Government of India
Ministry of Finance
Notification No. 25/2024
New Delhi, 15 March 2024
Subject: Revised GST rates on packaged food items

In supersession of the Notification No. 12/2023, the Government hereby notifies the following.
The GST rate on packaged food items is 12 percent.
Returns shall be filed monthly by the 20th day of the following month.
Late filing attracts interest at 18 percent per annum.
This notification comes into force on 1 April 2024.""",
    "circular_04_2024.pdf": """Government of India
Ministry of Finance
Central Board of Indirect Taxes and Customs
Circular No. 4/2024
New Delhi, 10 May 2024
Subject: Extension of the due date for monthly returns

This circular amends the Notification No. 25/2024 to give taxpayers more time.
The due date for filing monthly returns is extended to the 25th day of the following month.
Interest on late filing continues at 18 percent per annum.
This circular applies to returns for May 2024 onwards.""",
    "order_07_2024.pdf": """Government of India
Ministry of Finance
Department of Revenue
Order No. 7/2024
New Delhi, 1 July 2024
Subject: Withdrawal of obsolete instructions

Circulars No. 1/2019 and No. 2/2019 are hereby withdrawn.
Order No. 3/2018 is hereby rescinded.
Officers shall follow Circular No. 4/2024 for current filing timelines.""",
}


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, text in DOCUMENTS.items():
        document = fitz.open()
        page = document.new_page()
        page.insert_textbox(fitz.Rect(50, 50, 550, 800), text, fontsize=11)
        document.save(OUTPUT_DIR / name)
        print(f"wrote {OUTPUT_DIR / name}")


if __name__ == "__main__":
    main()
