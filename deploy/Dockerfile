# Laufzeit der NG-Customs-Plattform. Der Code kommt per Volume aus dem Git-Checkout auf dem Server,
# damit `git pull` neue Kunden ohne Neubau des Images live schaltet.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
 && useradd --create-home --uid 1000 agent
USER agent

EXPOSE 8080
HEALTHCHECK --interval=60s --timeout=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/gesundheit', timeout=4)"
CMD ["python", "-m", "runtime", "plattform", "/app/kunden", "--port", "8080"]
