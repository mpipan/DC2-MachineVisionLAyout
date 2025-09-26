import matplotlib.pyplot as plt
from matplotlib.ticker import FixedLocator
import cv2
import numpy as np

# Import plotting parameters from config.py
from config import dpi, tick_step_cm

def plot_result(image_px, img, cm_per_pixel, x_offset_cm, y_offset_cm):
    """
    Creates a plot of the image with a centimeter-based coordinate grid.

    This function was in the original `camera_master.py` file and is now
    isolated here for modularity.

    Args:
        image_px (int): The image resolution in pixels (e.g., 2000 for 2000x2000).
        img (np.ndarray): The image to be plotted.
        cm_per_pixel (float): The conversion factor from pixels to centimeters.
        x_offset_cm (float): The offset for the x-axis labels in cm.
        y_offset_cm (float): The offset for the y-axis labels in cm.
    """
    # Use dpi from config.py
    fig, ax = plt.subplots(figsize=(image_px / dpi, image_px / dpi), dpi=dpi)
    ax.imshow(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    ax.set_xlim(0, image_px)
    ax.set_ylim(image_px, 0)  # invert Y

    # --- Create Tick Locations and Labels ---
    # Use tick_step_cm from config.py
    tick_step_px = tick_step_cm / cm_per_pixel

    # X-axis
    x_ticks_px = np.arange(0, image_px, tick_step_px)
    x_labels_cm = [f"{(x * cm_per_pixel - x_offset_cm):.0f}" for x in x_ticks_px]
    ax.xaxis.set_major_locator(FixedLocator(x_ticks_px))
    ax.set_xticklabels(x_labels_cm)

    # Y-axis
    y_ticks_px = np.arange(0, image_px, tick_step_px)
    y_labels_cm = [f"{(y * cm_per_pixel - y_offset_cm):.0f}" for y in y_ticks_px]
    ax.yaxis.set_major_locator(FixedLocator(y_ticks_px))
    ax.set_yticklabels(y_labels_cm)

    # --- Axis Labels ---
    ax.set_xlabel('X [cm]')
    ax.set_ylabel('Y [cm]')
    plt.show()

