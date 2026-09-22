FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY seed_demo.py tests_parcours.py ./

# Les données (base SQLite et fichiers déposés) vivent hors de l'image : c'est ce
# volume que l'hébergeur sauvegarde.
ENV PLATEFORME_DATA=/data
VOLUME ["/data"]

RUN useradd --system --uid 10001 plateforme && mkdir -p /data && chown plateforme /data
USER plateforme

EXPOSE 8000
HEALTHCHECK --interval=60s --timeout=5s --start-period=10s \
  CMD python3 -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/sante', timeout=4).status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
