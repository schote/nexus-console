# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

# -- Path setup --------------------------------------------------------------

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.

import os
import sys

sys.path.insert(0, os.path.abspath('../../console'))

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'Spectrum-Pypulseq MRI Console'
copyright = '2023, David Schote'
author = 'David Schote <david.schote@ptb.de>'
release = '01.09.2023'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.doctest',
    'sphinx.ext.autodoc',
    'sphinx.ext.autosummary',
    'sphinx.ext.viewcode',
    'sphinx.ext.napoleon'
]

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output
# >> Theme configuration

html_theme = "pydata_sphinx_theme"
html_show_sphinx = False

# Add any paths that contain custom static files (such as style sheets) here,
# relative to this directory. They are copied after the builtin static files,
# so a file named "default.css" will overwrite the builtin "default.css".
html_static_path = ['_static']

html_logo = "_static/scanner_config.png"

html_theme_options = {
    "pygment_light_style": "default",
    "pygment_dark_style": "github-dark",
    "show_toc_level": 3,
    "icon_links": [
        {
            # Label for this link
            "name": "GitHub",
            # URL where the link will redirect
            "url": "https://github.com/schote/spectrum-console",  # required
            # Icon class (if "type": "fontawesome"), or path to local image (if "type": "local")
            "icon": "fa-brands fa-github",
        },
        {
            # Label for this link
            "name": "GitLab",
            # URL where the link will redirect
            "url": "https://gitlab1.ptb.de/mri-lab/spectrum-console",  # required
            # Icon class (if "type": "fontawesome"), or path to local image (if "type": "local")
            "icon": "fab fa-gitlab",
        },
        {
            # Label for this link
            "name": "Open Source Imaging",
            # URL where the link will redirect
            "url": "https://www.opensourceimaging.org/",  # required
            # Icon class (if "type": "fontawesome"), or path to local image (if "type": "local")
            "icon": "http://www.opensourceimaging.org/wp-content/uploads/logos/OSI_logo_3.gif",
            # The type of image to be used (see below for details)
            "type": "url",
        },
        
    ]
}
