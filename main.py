"""
app-source-space-v2: Compute surface-based source space from FreeSurfer output.

Inputs : FreeSurfer subject directory (from recon-all).
Outputs: source_space-src.fif (candidate source locations on cortical surface).
"""

import os
import sys
import numpy as np

# Set up FreeSurfer environment
if not os.environ.get('FREESURFER_HOME'):
    os.environ['FREESURFER_HOME'] = '/usr/local/freesurfer'
fs_home = os.environ['FREESURFER_HOME']
os.environ['PATH'] = os.path.join(fs_home, 'bin') + ':' + os.environ.get('PATH', '')

# Resolve brainlife_utils — try local copy first, then parent monorepo
app_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(app_dir)
for search_path in [app_dir, parent_dir]:
    if os.path.isdir(os.path.join(search_path, 'brainlife_utils')):
        sys.path.insert(0, search_path)
        break

from brainlife_utils import (
    setup_matplotlib_backend,
    load_config,
    ensure_output_dirs,
    add_info_to_product,
    add_image_to_product,
    create_product_json,
)

setup_matplotlib_backend()
import matplotlib.pyplot as plt

import mne

# == SETUP ==
ensure_output_dirs('out_dir', 'out_figs', 'out_dir_report')
report_items = []

# == LOAD CONFIG ==
config = load_config()

# == RESOLVE FREESURFER DIRECTORY ==
fs_path      = config.get('freesurfer') or config.get('output')
subjects_dir = config.get('subjects_dir')
subject      = config.get('subject')

if fs_path and os.path.isdir(fs_path):
    fs_path = os.path.abspath(fs_path)
    if not subjects_dir:
        subjects_dir = os.path.dirname(fs_path)
    if not subject:
        subject = os.path.basename(fs_path)

if not subjects_dir or not subject:
    add_info_to_product(
        report_items,
        "FATAL: No FreeSurfer directory found. "
        "Set 'freesurfer' in config.json to the subject's FreeSurfer directory.",
        "error"
    )
    create_product_json(report_items)
    sys.exit(1)

if not os.path.isdir(os.path.join(subjects_dir, subject)):
    add_info_to_product(
        report_items,
        f"FATAL: FreeSurfer subject directory not found: "
        f"{os.path.join(subjects_dir, subject)}",
        "error"
    )
    create_product_json(report_items)
    sys.exit(1)

add_info_to_product(report_items, f"Subject: {subject} | subjects_dir: {subjects_dir}", "info")

# == PARAMETERS ==
# spacing: 'oct6' → 4098 sources/hemisphere (recommended for real analyses)
#          'oct5' → 1026 sources/hemisphere (faster)
#          'oct4' → 258 sources/hemisphere (testing only)
spacing = config.get('spacing') or 'oct6'
surface = config.get('surface') or 'white'

# add_dist: False = no distance/patch info (fastest, avoids scikit-learn)
#           'patch' = patch info only (needs SciPy >=1.3, recommended)
#           True = full distance + patch (slowest, needs scikit-learn)
add_dist_raw = config.get('add_dist') or 'false'
if add_dist_raw in (True, 'true', 'True', '1'):
    add_dist = True
elif add_dist_raw in (False, 'false', 'False', '0', 'none', 'None', ''):
    add_dist = False
else:
    add_dist = add_dist_raw  # 'patch' or other string passed directly

add_info_to_product(
    report_items,
    f"Source space parameters: spacing={spacing} | surface={surface} | add_dist={add_dist}",
    "info"
)

# == COMPUTE SOURCE SPACE ==
try:
    src = mne.setup_source_space(
        subject,
        spacing=spacing,
        surface=surface,
        subjects_dir=subjects_dir,
        add_dist=add_dist,
        verbose=True
    )
    n_sources = sum(s['nuse'] for s in src)
    add_info_to_product(
        report_items,
        f"Source space: {n_sources} sources total "
        f"({src[0]['nuse']} left + {src[1]['nuse']} right hemisphere)",
        "info"
    )
except Exception as e:
    add_info_to_product(report_items, f"FATAL: Source space setup failed: {e}", "error")
    create_product_json(report_items)
    sys.exit(1)

# == SAVE SOURCE SPACE ==
src_path = os.path.join('out_dir', 'source_space-src.fif')
try:
    mne.write_source_spaces(src_path, src, overwrite=True)
    add_info_to_product(report_items, f"Saved: {src_path}", "info")
except Exception as e:
    add_info_to_product(report_items, f"FATAL: Could not save source space: {e}", "error")
    create_product_json(report_items)
    sys.exit(1)

# == QC FIGURE — middle slice from all 3 orientations with source points overlaid ==
_brain_surfaces = "white"
if not os.path.isfile(os.path.join(subjects_dir, subject, 'surf', 'lh.white')):
    _brain_surfaces = None

def _crop_middle_slice(fig):
    axes = fig.axes
    mid_ax = axes[len(axes) // 2]
    fig.canvas.draw()
    buf = fig.canvas.buffer_rgba()
    full_img = np.asarray(buf)[..., :3]
    bbox = mid_ax.get_position()
    h, w = full_img.shape[:2]
    x0, x1 = int(bbox.x0 * w), int(bbox.x1 * w)
    y0, y1 = int((1 - bbox.y1) * h), int((1 - bbox.y0) * h)
    return full_img[y0:y1, x0:x1]

slices = {}
for orientation in ('coronal', 'axial', 'sagittal'):
    try:
        fig = mne.viz.plot_bem(
            subject=subject, subjects_dir=subjects_dir,
            brain_surfaces=_brain_surfaces,
            src=src,
            orientation=orientation, show=False
        )
        slices[orientation] = _crop_middle_slice(fig)
        plt.close(fig)
    except Exception as e:
        add_info_to_product(
            report_items, f"Could not plot source space ({orientation}): {e}", "warning"
        )

if slices:
    n = len(slices)
    combined, axes = plt.subplots(1, n, figsize=(4 * n, 4))
    if n == 1:
        axes = [axes]
    for ax, (orientation, img) in zip(axes, slices.items()):
        ax.imshow(img)
        ax.set_title(orientation, fontsize=10)
        ax.axis('off')
    thumb_path = os.path.join('out_figs', 'source_space_thumb.png')
    combined.savefig(thumb_path, dpi=100, bbox_inches='tight')
    plt.close(combined)
    add_image_to_product(report_items, 'Source space — middle slice', filepath=thumb_path)

# == SAVE REPORT — interactive slider ==
report = mne.Report(title='Source Space Report')
try:
    report.add_bem(
        subject=subject, subjects_dir=subjects_dir,
        title='Source space on MRI (interactive)',
        decim=4, width=512
    )
except Exception as e:
    add_info_to_product(report_items, f"Could not add interactive view to report: {e}", "warning")
    if os.path.isfile(os.path.join('out_figs', 'source_space_thumb.png')):
        report.add_image(
            os.path.join('out_figs', 'source_space_thumb.png'),
            title='Source space'
        )
report.save(os.path.join('out_dir_report', 'report.html'), overwrite=True)

add_info_to_product(report_items, "Source space computation completed successfully.", "success")
create_product_json(report_items)
print("Done.")
