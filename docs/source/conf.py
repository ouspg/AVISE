# -- Project information -----------------------------------------------------
import datetime
import os
import sys

sys.path.insert(0, os.path.abspath('..'))


project = 'AVISE'
copyright = f'{datetime.datetime.now().year}, Oulu University Secure Programming Group (OUSPG)'
author = 'Joni Kemppainen, Mikko Lempinen'
release = '0.2.0'

# -- General configuration ---------------------------------------------------

extensions = ['sphinx_github_style', 
              'sphinx.ext.autodoc', 
              'sphinx.ext.napoleon', 
              'sphinx.ext.autosummary',
              'sphinx.ext.viewcode'] 

todo_include_todos = False #Remove TODOs from docs
templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# -- sphinx_github_style configs
linkcode_link_text = "Source"
linkcode_url = "https://github.com/ouspg/AVISE"
link_github = True

# -- Options for HTML output -------------------------------------------------

html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']
html_show_sourcelink = False
html_theme_options = {
    "navigation_depth": 1,  # The default is 4
    "collapse_navigation": False, # set to False to prevent collapsing
    "includehidden": True, # set to True to include hidden toctree directives
}

