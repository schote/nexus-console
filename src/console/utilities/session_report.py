"""Create PDF report for Nexus session data."""
import argparse
import json
import os
from glob import glob
from io import BytesIO

import matplotlib.pyplot as plt
import numpy as np
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas
from tqdm import tqdm

from console.utilities.plot import plot_2d, plot_slices, plt

PAGE_WIDTH, PAGE_HEIGHT = A4


def get_image_from_matplotlib(fig):
    """Convert matplotlib figure to a ReportLab-compatible image.

    Parameters
    ----------
    fig
        Matplotlib figure

    Returns
    -------
        ReportLab image
    """
    imgdata = BytesIO()
    fig.savefig(imgdata, format='png', bbox_inches='tight')
    imgdata.seek(0)  # Rewind the buffer
    return ImageReader(imgdata)

def create_report(session_path: str):
    """Create the session report.

    Parameters
    ----------
    session_path
        Path to session
    """
    # Create a PDF
    output_pdf = os.path.join(session_path, "nexus_report.pdf")
    pdf_canvas = canvas.Canvas(output_pdf, pagesize=A4)

    # Get all the acquisition ids in base path
    acq_ids = glob(session_path+"*")

    margin = 40
    font_size = 9

    for acq_id in tqdm(acq_ids, desc="Creating session report"):
        if not os.path.exists(raw_data_path := os.path.join(acq_id, "raw_data.npy")):
            continue

        raw_data = np.load(raw_data_path)
        meta_file = os.path.join(acq_id, "meta.json")
        with open(meta_file) as fh:
            meta = json.load(fh)

        if raw_data.shape[-2] == 1:
            # Only one phase encoding dimension
            data = np.average(raw_data, axis=0).squeeze()
            data_fft = np.fft.ifftshift(np.fft.fft(np.fft.fftshift(data)))
            # Define x-axis
            dwell_time = meta["dwell_time"]
            time_ax = np.linspace(0, data.size*dwell_time, data.size)
            freq_ax = np.fft.fftshift(np.fft.fftfreq(data.size, dwell_time))

            fig, ax = plt.subplots(1, 2, figsize=(10, 4), dpi=300)
            ax[0].plot(time_ax*1e3, np.abs(data), label="Abs.")
            ax[0].plot(time_ax*1e3, np.real(data), label="Real")
            ax[0].plot(time_ax*1e3, np.imag(data), label="Imag")
            ax[0].legend(loc="upper right")
            ax[1].plot(freq_ax/1e3, np.abs(data_fft))
            ax[1].set_yscale('log')
            ax[0].set_xlabel("Time / ms")
            ax[0].set_ylabel("Amplitude / mV")
            ax[1].set_xlabel("Frequency / kHz")
            ax[1].set_ylabel("Abs. spectrum / dB")

        else:
            if not os.path.exists(img_path := os.path.join(acq_id, "image.npy")):
                continue
            img = np.load(img_path)
            if raw_data.shape[0] > 1:
                # Calculate mean over averages, applies to any imaging data
                img = np.mean(img, axis=0)

            if img.ndim == 2:
                fig, _ = plot_2d(np.abs(img), set_aspect=True)
            elif img.ndim == 3:
                fig, _ = plot_slices(np.abs(img), set_aspect=True)
            else:
                print("Invalid image shape...")
                continue
        plt.close()

        # Define meta entries to print to PDF
        meta_text={
            "DATETIME": meta["date_time"],
            "ACQUISITION PARAMETER": meta['acquisition_parameter'],
            "INFO": meta["info"],
            "DIMENISONS": meta["dimensions"][0]
        }

        # Convert the figure to a ReportLab image
        img = get_image_from_matplotlib(fig)
        plt.close(fig)

        # Add title to the page
        canvas.setFont("Helvetica-Bold", 10)
        canvas.drawString(margin, PAGE_HEIGHT - margin - 10, "ACQUISITION: " + meta["folder_name"])

        # Add the image to the page
        fig_size = fig.get_size_inches()
        fig_aspect = fig_size[1]/fig_size[0]
        image_height = (PAGE_HEIGHT - 2 * margin)/3
        image_width = image_height / fig_aspect
        if image_width > (max_width := PAGE_WIDTH - 2*margin):
            # Set max. width to page width if exceeded
            image_width = max_width
            image_height = image_width * fig_aspect

        canvas.drawImage(img, margin, PAGE_HEIGHT - margin - image_height - 30, width=image_width, height=image_height)
        # canvas.drawInlineImage(img, margin, PAGE_HEIGHT - margin - image_height - 30, width=image_width, height=image_height)

        # Add metadata below the image
        text_start_y = PAGE_HEIGHT - margin - image_height - 50
        canvas.setFont("Helvetica", font_size)

        # Render the metadata dictionary dynamically
        for section, content in meta_text.items():
            canvas.drawString(margin, text_start_y, f"{section}:")
            text_start_y -= 12
            if isinstance(content, dict):
                for key, value in content.items():
                    canvas.drawString(margin + 12, text_start_y, f"{key}: {value}")
                    text_start_y -= 12
                    if text_start_y < margin:
                        canvas.showPage()
                        text_start_y = PAGE_HEIGHT - margin
                        canvas.setFont("Helvetica", font_size)
            else:
                canvas.drawString(margin + 12, text_start_y, f"{content}")
                text_start_y -= 12
                if text_start_y < margin:
                    canvas.showPage()
                    text_start_y = PAGE_HEIGHT - margin
                    canvas.setFont("Helvetica", font_size)
            text_start_y -= 6

        # Finalize the page
        canvas.showPage()

    # Save the PDF
    pdf_canvas.save()
    print("Report saved to: ", output_pdf)


def main():
    """Parse arguments and start the dashboard server."""
    parser = argparse.ArgumentParser(description="Generate a PDF report for all the data recorded in a Nexus session.")
    parser.add_argument(
        "-p", "--session_path",
        required=True,
        type=str,
        help="Directory of the session. The report is stored in the same location."
    )

    args = parser.parse_args()
    create_report(os.path.join(args.session_path, ""))


if __name__ == '__main__':
    main()
