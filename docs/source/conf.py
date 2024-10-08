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

from sphinx_pyproject import SphinxConfig

config = SphinxConfig('../../pyproject.toml', globalns=globals())
sys.path.insert(0, os.path.abspath('../../src/'))  # Source code dir relative to this file

# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'Nexus-Console'
author = author
version = version
copyright = '2024, Physikalisch-Technische Bundesanstalt (PTB) Berlin'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    'sphinx.ext.doctest',
    'sphinx.ext.autodoc',
    # 'sphinx.ext.autosummary',
    'sphinx.ext.viewcode',
    'sphinx.ext.napoleon',
    'sphinx.ext.mathjax',
    'sphinx_design',
]

# templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']
source_suffix = {'.rst': 'restructuredtext', '.txt': 'restructuredtext', '.md': 'markdown'}

autodoc_mock_imports = ["console.spcm_control.spcm"]

# autosummary_imported_members = True
# autosummary_generate = True

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output
# >> Theme configuration

html_theme = "pydata_sphinx_theme"
html_show_sphinx = False
html_static_path = ['_static']
html_css_files = [
    "custom.css",
    "https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.1.1/css/all.min.css",
]
html_logo = "_static/logo.png"
html_favicon = "_static/favicon.ico"
html_sidebars = {
    "index": [],
    "quick_start": [],
    "api_reference/index": [],
    "code_examples/index": [],
    "**": ["search-field", "sidebar-nav-bs.html"],
}



numfig = True   # use numbered figures
html_theme_options = {
    "logo": {"text": "Nexus-Console"},
    "pygment_light_style": "default",
    "pygment_dark_style": "github-dark",
    "show_toc_level": 2,
    "show_nav_level": 2,
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
            "name": "Open Source Imaging",
            # URL where the link will redirect
            "url": "https://www.opensourceimaging.org/project/nexus-console/",  # required
            # Icon class (if "type": "fontawesome"), or path to local image (if "type": "local")
            "icon": "http://www.opensourceimaging.org/wp-content/uploads/logos/OSI_logo_3.gif",
            # The type of image to be used (see below for details)
            "type": "url",
        },
    ]
}
