"""Production WSGI entrypoint.

Gunicorn should invoke ``wsgi:app``; the development ``run.py`` server is not
used for production traffic.
"""

from app import create_app

app = create_app()
