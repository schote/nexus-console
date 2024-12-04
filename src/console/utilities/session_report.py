# %%
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

def create_report(data_path: str):
    """Create the session report.

    Parameters
    ----------
    data_path
        Path to session or acquisition data
    """
    # Create a PDF
    output_pdf = os.path.join(data_path, "nexus_report.pdf")
    pdf_canvas = canvas.Canvas(output_pdf, pagesize=A4)

    if os.path.exists(os.path.join(data_path, "meta.json")):
        # Check if path belongs to session or acquisition
        acq_ids = [data_path]
    else:
        # Get all the acquisition ids, i.e. folders with acquisition data from the base path
        acq_ids = [d for d in glob(os.path.join(data_path, "*")) if os.path.isdir(d)]

    margin = 40
    font_size = 9
    acq_counter = 0

    for acq_id in tqdm(acq_ids, desc="Creating session report"):
        if not os.path.exists(raw_data_path := os.path.join(acq_id, "raw_data.npy")):
            continue

        meta_file = os.path.join(acq_id, "meta.json")
        with open(meta_file) as fh:
            meta = json.load(fh)

        num_averages, num_coils, num_pe, num_samples = meta["dimensions"][0]
        raw_data = np.load(raw_data_path)

        if num_pe == 1:
            # Only one phase encoding step -> spectrum
            data = np.average(raw_data, axis=0).squeeze()
            data_fft = np.fft.ifftshift(np.fft.fft(np.fft.fftshift(data), axis=-1))
            # Define time/frequency axis
            dwell_time = meta["dwell_time"]
            time_ax = np.linspace(0, num_samples*dwell_time, num_samples)
            freq_ax = np.fft.fftshift(np.fft.fftfreq(num_samples, dwell_time))

            fig, ax = plt.subplots(1, 2, figsize=(10, 4), dpi=300)

            # TIME DOMAIN
            if num_coils > 1:
                for k in range(num_coils):
                    # Only plot magnitude data if multiple coils are available
                    ax[0].plot(time_ax*1e3, np.abs(data[k, ...]), label=f"Coil {k+1}")
            else:
                ax[0].plot(time_ax*1e3, np.abs(data), label="Abs.")
                ax[0].plot(time_ax*1e3, np.real(data), label="Real")
                ax[0].plot(time_ax*1e3, np.imag(data), label="Imag")
            ax[0].legend(loc="upper right")
            ax[0].set_xlabel("Time / ms")
            ax[0].set_ylabel("Amplitude / mV")

            # FREQUENCY DOMAIN
            if num_coils > 1:
                for k in range(num_coils):
                    ax[1].plot(freq_ax/1e3, np.abs(data_fft[k, ...]), label=f"Coil {k+1}")
                ax[1].legend(loc="upper right")
            else:
                ax[1].plot(freq_ax/1e3, np.abs(data_fft))
            ax[1].set_yscale('log')
            ax[1].set_xlabel("Frequency / kHz")
            ax[1].set_ylabel("Abs. spectrum / dB")

        else:
            if not os.path.exists(img_path := os.path.join(acq_id, "image.npy")):
                continue
            img = np.load(img_path)

            if num_averages > 1:
                # Calculate mean over averages, applies to any imaging data
                img = np.mean(img, axis=0)

            if num_coils > 1:
                # Take only main coil data if multicoil data is available
                img = img[0, ...]

            if img.ndim == 2:
                fig, _ = plot_2d(np.abs(img), set_aspect=False)
            elif img.ndim == 3:
                fig, _ = plot_slices(np.abs(img), set_aspect=False)
            else:
                print("Invalid image shape...")
                continue
        plt.close()
        acq_counter += 1

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
        pdf_canvas.setFont("Helvetica-Bold", 10)
        pdf_canvas.drawString(margin, PAGE_HEIGHT - margin - 10, "ACQUISITION: " + meta["folder_name"])

        # Add the image to the page
        fig_size = fig.get_size_inches()
        fig_aspect = fig_size[1]/fig_size[0]
        image_height = (PAGE_HEIGHT - 2 * margin)/3
        image_width = image_height / fig_aspect
        if image_width > (max_width := PAGE_WIDTH - 2*margin):
            # Set max. width to page width if exceeded
            image_width = max_width
            image_height = image_width * fig_aspect

        pdf_canvas.drawImage(img, margin, PAGE_HEIGHT - margin - image_height - 30, width=image_width, height=image_height)
        # canvas.drawInlineImage(img, margin, PAGE_HEIGHT - margin - image_height - 30, width=image_width, height=image_height)

        # Add metadata below the image
        text_start_y = PAGE_HEIGHT - margin - image_height - 50
        pdf_canvas.setFont("Helvetica", font_size)

        # Render the metadata dictionary dynamically
        for section, content in meta_text.items():
            pdf_canvas.drawString(margin, text_start_y, f"{section}:")
            text_start_y -= 12
            if isinstance(content, dict):
                for key, value in content.items():
                    pdf_canvas.drawString(margin + 12, text_start_y, f"{key}: {value}")
                    text_start_y -= 12
                    if text_start_y < margin:
                        pdf_canvas.showPage()
                        text_start_y = PAGE_HEIGHT - margin
                        pdf_canvas.setFont("Helvetica", font_size)
            else:
                pdf_canvas.drawString(margin + 12, text_start_y, f"{content}")
                text_start_y -= 12
                if text_start_y < margin:
                    pdf_canvas.showPage()
                    text_start_y = PAGE_HEIGHT - margin
                    pdf_canvas.setFont("Helvetica", font_size)
            text_start_y -= 6

        # Finalize the page
        pdf_canvas.showPage()

    if not acq_counter > 0:
        print("No acquisition data or invalid acquisition data available...\nReport could not be created.")
        return

    # Save the PDF
    pdf_canvas.save()
    print("Report saved to: ", os.path.abspath(output_pdf))


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

# %%
if __name__ == '__main__':
    main()
